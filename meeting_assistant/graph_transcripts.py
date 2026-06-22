from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

import httpx


MAX_GRAPH_TRANSCRIPT_CHARS = 200_000
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class GraphTranscriptError(RuntimeError):
    pass


class GraphConfigurationError(GraphTranscriptError):
    pass


class GraphMeetingNotLinkedError(GraphTranscriptError):
    pass


class GraphPermanentError(GraphTranscriptError):
    pass


class TranscriptNotReadyError(GraphTranscriptError):
    pass


@dataclass(frozen=True)
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    graph_base_url: str = "https://graph.microsoft.com/v1.0"

    @classmethod
    def from_environment(cls) -> "GraphConfig":
        values = {
            "tenant_id": os.getenv("MS_GRAPH_TENANT_ID", "").strip(),
            "client_id": os.getenv("MS_GRAPH_CLIENT_ID", "").strip(),
            "client_secret": os.getenv("MS_GRAPH_CLIENT_SECRET", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise GraphConfigurationError(
                "Microsoft Graph configuration is incomplete: " + ", ".join(missing)
            )
        return cls(**values)


class MicrosoftGraphTranscriptProvider:
    name = "Microsoft Teams transcript via Graph"

    def __init__(
        self,
        config: GraphConfig | None = None,
        client: httpx.Client | None = None,
        token_getter: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or GraphConfig.from_environment()
        self.client = client or httpx.Client(timeout=30)
        self.token_getter = token_getter or self._acquire_token
        self.sleep = sleep

    def _acquire_token(self) -> str:
        import msal

        application = msal.ConfidentialClientApplication(
            self.config.client_id,
            authority=f"https://login.microsoftonline.com/{self.config.tenant_id}",
            client_credential=self.config.client_secret,
        )
        result = application.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if not isinstance(result, dict):
            raise GraphTranscriptError("Microsoft Graph authentication returned no result.")
        token = result.get("access_token")
        if not isinstance(token, str) or not token:
            error = str(result.get("error", "authentication_failed"))
            raise GraphTranscriptError(f"Microsoft Graph authentication failed: {error}")
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str = "application/json",
        not_found_is_pending: bool = False,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.token_getter()}",
            "Accept": accept,
        }
        url = f"{self.config.graph_base_url.rstrip('/')}/{path.lstrip('/')}"
        for attempt in range(4):
            response = self.client.request(method, url, headers=headers)
            if 200 <= response.status_code < 300:
                return response
            if response.status_code == 404 and not_found_is_pending:
                raise TranscriptNotReadyError("The Teams transcript is not available yet.")
            if response.status_code in {400, 401, 403}:
                raise GraphPermanentError(
                    f"Microsoft Graph rejected the request with status {response.status_code}. "
                    "Check the meeting IDs, application permissions, admin consent, and application access policy."
                )
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt == 3:
                raise GraphTranscriptError(
                    f"Microsoft Graph request failed with status {response.status_code}."
                )
            retry_after = response.headers.get("Retry-After", "1")
            try:
                delay = min(max(float(retry_after), 0.1), 30.0)
            except ValueError:
                delay = min(2**attempt, 30)
            self.sleep(delay)
        raise GraphTranscriptError("Microsoft Graph retry limit was reached.")

    def collect(self, meeting: dict, attendees: list[dict]) -> str:
        del attendees
        organizer_id = str(meeting.get("graph_organizer_user_id") or "").strip()
        meeting_id = str(meeting.get("graph_online_meeting_id") or "").strip()
        if not organizer_id or not meeting_id:
            raise GraphMeetingNotLinkedError(
                "The meeting is not linked to a Microsoft Graph online meeting."
            )

        user_segment = quote(organizer_id, safe="")
        meeting_segment = quote(meeting_id, safe="")
        transcript_list = self._request(
            "GET",
            f"users/{user_segment}/onlineMeetings/{meeting_segment}/transcripts",
            not_found_is_pending=True,
        ).json()
        transcripts = transcript_list.get("value", [])
        if not isinstance(transcripts, list) or not transcripts:
            raise TranscriptNotReadyError("The Teams transcript is not available yet.")
        valid_transcripts = [
            item for item in transcripts if isinstance(item, dict) and item.get("id")
        ]
        if not valid_transcripts:
            raise TranscriptNotReadyError("The Teams transcript is not available yet.")
        latest = max(
            valid_transcripts,
            key=lambda item: str(item.get("createdDateTime", "")),
        )
        transcript_id = quote(str(latest["id"]), safe="")
        content = self._request(
            "GET",
            (
                f"users/{user_segment}/onlineMeetings/{meeting_segment}/"
                f"transcripts/{transcript_id}/content"
            ),
            accept="text/vtt",
            not_found_is_pending=True,
        ).text.strip()
        if not content:
            raise TranscriptNotReadyError("The Teams transcript content is empty.")
        if len(content) > MAX_GRAPH_TRANSCRIPT_CHARS:
            raise GraphPermanentError(
                "The Teams transcript is too large for the current AI processing limit."
            )
        return content


def graph_is_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in (
            "MS_GRAPH_TENANT_ID",
            "MS_GRAPH_CLIENT_ID",
            "MS_GRAPH_CLIENT_SECRET",
        )
    )
