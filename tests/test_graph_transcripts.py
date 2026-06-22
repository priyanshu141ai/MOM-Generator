import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from meeting_assistant.automation import process_meeting, run_automation
from meeting_assistant.database import (
    create_meeting,
    get_meeting,
    init_db,
    set_meeting_status,
)
from meeting_assistant.graph_transcripts import (
    GraphConfig,
    GraphPermanentError,
    MicrosoftGraphTranscriptProvider,
    TranscriptNotReadyError,
)


class MicrosoftGraphTranscriptProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = GraphConfig("tenant", "client", "secret")
        self.meeting = {
            "graph_organizer_user_id": "organizer-id",
            "graph_online_meeting_id": "meeting/id",
        }

    def test_collects_latest_teams_transcript_content(self) -> None:
        requested_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_paths.append(request.url.path)
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            if request.url.path.endswith("/transcripts"):
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {"id": "older", "createdDateTime": "2026-01-01T10:00:00Z"},
                            {"id": "latest", "createdDateTime": "2026-01-01T11:00:00Z"},
                        ]
                    },
                )
            return httpx.Response(200, text="WEBVTT\n\n00:00.000 --> 00:02.000\nHello")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = MicrosoftGraphTranscriptProvider(
            self.config, client=client, token_getter=lambda: "test-token"
        )

        transcript = provider.collect(self.meeting, [])

        self.assertIn("Hello", transcript)
        self.assertTrue(requested_paths[-1].endswith("/transcripts/latest/content"))

    def test_empty_transcript_list_is_a_retryable_waiting_state(self) -> None:
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"value": []})
            )
        )
        provider = MicrosoftGraphTranscriptProvider(
            self.config, client=client, token_getter=lambda: "test-token"
        )

        with self.assertRaises(TranscriptNotReadyError):
            provider.collect(self.meeting, [])

    def test_graph_throttling_honors_retry_after(self) -> None:
        request_count = 0
        delays: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                return httpx.Response(429, headers={"Retry-After": "2"})
            if request.url.path.endswith("/transcripts"):
                return httpx.Response(200, json={"value": [{"id": "one"}]})
            return httpx.Response(200, text="WEBVTT\nTranscript")

        provider = MicrosoftGraphTranscriptProvider(
            self.config,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            token_getter=lambda: "test-token",
            sleep=delays.append,
        )

        provider.collect(self.meeting, [])

        self.assertEqual(delays, [2.0])
        self.assertEqual(request_count, 3)

    def test_permission_error_is_not_retried(self) -> None:
        requests = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal requests
            requests += 1
            return httpx.Response(403)

        provider = MicrosoftGraphTranscriptProvider(
            self.config,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            token_getter=lambda: "test-token",
        )

        with self.assertRaises(GraphPermanentError):
            provider.collect(self.meeting, [])

        self.assertEqual(requests, 1)


class AutomationRetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_db(self.db_path, seed=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_transcript_not_ready_is_persisted_and_not_polled_immediately(self) -> None:
        start = datetime.now() - timedelta(hours=1)
        meeting_id = create_meeting(
            "Graph Meeting",
            start,
            start + timedelta(minutes=30),
            "Organizer",
            "organizer@example.com",
            True,
            [("Owner", "owner@example.com")],
            graph_online_meeting_id="meeting-id",
            graph_organizer_user_id="organizer-id",
            db_path=self.db_path,
        )
        set_meeting_status(meeting_id, "Meeting ended", self.db_path)

        class WaitingProvider:
            name = "Waiting provider"
            calls = 0

            def collect(self, meeting: dict, attendees: list[dict]) -> str:
                del meeting, attendees
                self.calls += 1
                raise TranscriptNotReadyError("Not ready")

        provider = WaitingProvider()
        first = run_automation(provider=provider, db_path=self.db_path)
        second = run_automation(provider=provider, db_path=self.db_path)

        meeting = get_meeting(meeting_id, self.db_path)
        assert meeting is not None
        self.assertEqual(first.waiting_for_transcript, 1)
        self.assertEqual(second.waiting_for_transcript, 0)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(meeting["status"], "Waiting for transcript")
        self.assertEqual(meeting["automation_attempts"], 1)
        self.assertIsNotNone(meeting["next_automation_attempt"])

    def test_missing_graph_link_requires_attention_without_retry(self) -> None:
        start = datetime.now() - timedelta(hours=1)
        meeting_id = create_meeting(
            "Unlinked Graph Meeting",
            start,
            start + timedelta(minutes=30),
            "Organizer",
            "organizer@example.com",
            True,
            [("Owner", "owner@example.com")],
            db_path=self.db_path,
        )
        set_meeting_status(meeting_id, "Meeting ended", self.db_path)
        provider = MicrosoftGraphTranscriptProvider(
            GraphConfig("tenant", "client", "secret"),
            client=httpx.Client(
                transport=httpx.MockTransport(lambda request: httpx.Response(500))
            ),
            token_getter=lambda: "test-token",
        )

        outcome = process_meeting(meeting_id, provider, self.db_path)

        meeting = get_meeting(meeting_id, self.db_path)
        assert meeting is not None
        self.assertEqual(outcome, "failed")
        self.assertEqual(meeting["status"], "Needs attention")
        self.assertIsNone(meeting["next_automation_attempt"])
        self.assertIn("not linked", meeting["last_automation_error"])


if __name__ == "__main__":
    unittest.main()
