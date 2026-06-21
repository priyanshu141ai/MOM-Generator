import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from meeting_assistant.ai_engine import analyze_transcript
from meeting_assistant.communications import get_notifications, queue_meeting_results
from meeting_assistant.database import (
    create_meeting,
    get_actions,
    init_db,
    replace_actions,
    save_intelligence,
    set_meeting_assistant,
    set_action_status,
)
from meeting_assistant.reminders import (
    get_reminders,
    run_reminder_engine,
    schedule_action_reminders,
    schedule_meeting_reminders,
)


class MeetingAssistantServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_db(self.db_path, seed=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_test_meeting(self, assistant_enabled: bool = True) -> tuple[int, datetime]:
        start = datetime.now().replace(microsecond=0) + timedelta(days=2)
        meeting_id = create_meeting(
            "Delivery Review",
            start,
            start + timedelta(hours=1),
            "Aarav Mehta",
            "aarav@contoso.com",
            assistant_enabled,
            [("Rahul Sharma", "rahul@contoso.com")],
            db_path=self.db_path,
        )
        return meeting_id, start

    def test_meeting_reminders_work_without_ai_and_are_idempotent(self) -> None:
        meeting_id, _ = self.create_test_meeting(assistant_enabled=False)

        first_count = schedule_meeting_reminders(meeting_id, db_path=self.db_path)
        second_count = schedule_meeting_reminders(meeting_id, db_path=self.db_path)

        self.assertEqual(first_count, 6)
        self.assertEqual(second_count, 0)
        self.assertEqual(len(get_reminders(self.db_path)), 6)

    def test_assistant_access_can_be_changed_for_a_meeting(self) -> None:
        meeting_id, _ = self.create_test_meeting(assistant_enabled=False)

        set_meeting_assistant(meeting_id, True, self.db_path)

        from meeting_assistant.database import get_meeting

        meeting = get_meeting(meeting_id, self.db_path)
        self.assertIsNotNone(meeting)
        assert meeting is not None
        self.assertEqual(meeting["assistant_enabled"], 1)

    def test_local_analysis_extracts_actions_decisions_and_risks(self) -> None:
        transcript = (
            "Aarav: We agreed to keep the launch scope.\n"
            "Rahul: I will submit the proposal by 2026-07-01.\n"
            "Aarav: Vendor delay is a delivery risk."
        )
        attendees = [{"name": "Rahul Sharma", "email": "rahul@contoso.com"}]
        cleared = {
            "AZURE_OPENAI_ENDPOINT": "",
            "AZURE_OPENAI_API_KEY": "",
            "AZURE_OPENAI_DEPLOYMENT": "",
        }
        with patch.dict(os.environ, cleared):
            result = analyze_transcript(transcript, "Delivery Review", attendees)

        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].owner_email, "rahul@contoso.com")
        self.assertIn("agreed", result.decisions.lower())
        self.assertIn("risk", result.risks.lower())

    def test_action_reminders_trigger_notification_outbox(self) -> None:
        meeting_id, _ = self.create_test_meeting()
        due = (datetime.now() + timedelta(days=3)).date().isoformat()
        replace_actions(
            meeting_id,
            [{
                "owner_name": "Rahul Sharma",
                "owner_email": "rahul@contoso.com",
                "task": "Submit proposal",
                "due_date": due,
            }],
            self.db_path,
        )

        self.assertEqual(schedule_action_reminders(meeting_id, self.db_path), 4)
        run_at = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        self.assertEqual(run_reminder_engine(run_at, self.db_path), 1)
        self.assertEqual(len(get_notifications(self.db_path)), 1)

    def test_approved_results_are_queued_for_selected_recipients(self) -> None:
        meeting_id, _ = self.create_test_meeting()
        save_intelligence(
            meeting_id,
            "Transcript",
            "Summary",
            "MOM",
            "- Decision",
            "None identified.",
            db_path=self.db_path,
        )

        count = queue_meeting_results(
            meeting_id,
            ["aarav@contoso.com", "rahul@contoso.com"],
            db_path=self.db_path,
        )

        self.assertEqual(count, 2)
        self.assertEqual(len(get_notifications(self.db_path)), 2)

        duplicate_count = queue_meeting_results(
            meeting_id,
            ["aarav@contoso.com", "rahul@contoso.com"],
            db_path=self.db_path,
        )
        self.assertEqual(duplicate_count, 0)
        self.assertEqual(len(get_notifications(self.db_path)), 2)

    def test_completed_action_cancels_pending_reminders(self) -> None:
        meeting_id, _ = self.create_test_meeting()
        due = (datetime.now() + timedelta(days=3)).date().isoformat()
        replace_actions(
            meeting_id,
            [{
                "owner_name": "Rahul Sharma",
                "owner_email": "rahul@contoso.com",
                "task": "Submit proposal",
                "due_date": due,
            }],
            self.db_path,
        )
        schedule_action_reminders(meeting_id, self.db_path)
        action = get_actions(meeting_id, self.db_path)[0]

        set_action_status(action["id"], "Completed", self.db_path)
        run_at = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        self.assertEqual(run_reminder_engine(run_at, self.db_path), 0)
        self.assertTrue(
            all(reminder["status"] == "Cancelled" for reminder in get_reminders(self.db_path))
        )

    def test_large_transcript_is_rejected_before_ai_call(self) -> None:
        with self.assertRaisesRegex(ValueError, "too large"):
            analyze_transcript("x" * 200_001, "Delivery Review", [])


if __name__ == "__main__":
    unittest.main()
