from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from .ai_engine import analyze_transcript
from .database import (
    DB_PATH,
    claim_meeting_for_processing,
    get_automation_candidates,
    get_attendees,
    get_meeting,
    mark_automation_attention,
    mark_automation_complete,
    mark_due_meetings_ended,
    replace_actions,
    save_intelligence,
    save_transcript,
    schedule_automation_retry,
    set_meeting_status,
)
from .graph_transcripts import (
    GraphConfigurationError,
    GraphMeetingNotLinkedError,
    GraphPermanentError,
    MicrosoftGraphTranscriptProvider,
    TranscriptNotReadyError,
)
from .reminders import schedule_action_reminders


LOGGER = logging.getLogger(__name__)


class TranscriptProvider(Protocol):
    name: str

    def collect(
        self, meeting: dict, attendees: list[dict]
    ) -> str: ...


class DemoTranscriptProvider:
    name = "Automatic demo transcript"

    def collect(self, meeting: dict, attendees: list[dict]) -> str:
        organizer = str(meeting["organizer_name"]).split()[0]
        participants = attendees or [
            {
                "name": meeting["organizer_name"],
                "email": meeting["organizer_email"],
            }
        ]
        first = str(participants[0]["name"]).split()[0]
        second_person = participants[1] if len(participants) > 1 else participants[0]
        second = str(second_person["name"]).split()[0]
        first_due = (date.today() + timedelta(days=3)).isoformat()
        second_due = (date.today() + timedelta(days=5)).isoformat()
        title = str(meeting["title"])
        return (
            f"{organizer}: We reviewed the main updates for {title}.\n"
            f"{organizer}: Decision: keep the agreed scope and review progress next week.\n"
            f"{first}: I will prepare the follow-up update by {first_due}.\n"
            f"{second}: I will review the meeting decisions by {second_due}.\n"
            f"{organizer}: A delayed approval is a risk to the planned timeline."
        )


@dataclass
class AutomationRun:
    detected: int = 0
    processed: int = 0
    completed_without_ai: int = 0
    waiting_for_transcript: int = 0
    failed: list[int] = field(default_factory=list)


def configured_transcript_provider() -> TranscriptProvider:
    provider_name = os.getenv("TRANSCRIPT_PROVIDER", "demo").strip().lower()
    if provider_name == "demo":
        return DemoTranscriptProvider()
    if provider_name == "microsoft_graph":
        return MicrosoftGraphTranscriptProvider()
    raise GraphConfigurationError(
        "TRANSCRIPT_PROVIDER must be 'demo' or 'microsoft_graph'."
    )


def transcript_provider_label() -> str:
    provider_name = os.getenv("TRANSCRIPT_PROVIDER", "demo").strip().lower()
    return (
        "Microsoft Teams via Graph"
        if provider_name == "microsoft_graph"
        else "Automatic demo transcript"
    )


def process_meeting(
    meeting_id: int,
    provider: TranscriptProvider | None = None,
    db_path: Path | str = DB_PATH,
) -> str:
    meeting = get_meeting(meeting_id, db_path)
    if not meeting:
        return "skipped"
    if not meeting["assistant_enabled"]:
        mark_automation_complete(meeting_id, "Completed", db_path)
        return "completed_without_ai"
    if not claim_meeting_for_processing(meeting_id, db_path):
        return "skipped"

    transcript_provider: TranscriptProvider
    try:
        transcript_provider = provider or configured_transcript_provider()
        attendees = get_attendees(meeting_id, db_path)
        transcript = transcript_provider.collect(meeting, attendees)
        save_transcript(meeting_id, transcript, transcript_provider.name, db_path)
        result = analyze_transcript(transcript, str(meeting["title"]), attendees)
        save_intelligence(
            meeting_id,
            transcript,
            result.summary,
            result.mom,
            result.decisions,
            result.risks,
            approved=False,
            db_path=db_path,
        )
        replace_actions(
            meeting_id,
            [
                {
                    "owner_name": action.owner_name,
                    "owner_email": action.owner_email,
                    "task": action.task,
                    "due_date": action.due_date,
                }
                for action in result.actions
            ],
            db_path,
        )
        schedule_action_reminders(meeting_id, db_path)
        mark_automation_complete(meeting_id, "Review ready", db_path)
        return "processed"
    except TranscriptNotReadyError as exc:
        schedule_automation_retry(
            meeting_id,
            "Waiting for transcript",
            delay_seconds=60,
            error_message=str(exc),
            db_path=db_path,
        )
        return "waiting"
    except (GraphConfigurationError, GraphMeetingNotLinkedError, GraphPermanentError) as exc:
        LOGGER.warning("Graph transcript configuration blocked meeting %s", meeting_id)
        mark_automation_attention(
            meeting_id,
            error_message=str(exc),
            db_path=db_path,
        )
        return "failed"
    except Exception as exc:
        LOGGER.exception("Automatic meeting processing failed for meeting %s", meeting_id)
        attempts = int(meeting.get("automation_attempts") or 0)
        if attempts >= 5:
            mark_automation_attention(
                meeting_id,
                error_message=f"Retry limit reached: {type(exc).__name__}",
                db_path=db_path,
            )
            return "failed"
        retry_delay = min(60 * (2 ** min(attempts, 5)), 3600)
        schedule_automation_retry(
            meeting_id,
            "Automation failed",
            delay_seconds=retry_delay,
            error_message=type(exc).__name__,
            db_path=db_path,
        )
        return "failed"


def run_automation(
    at: datetime | None = None,
    provider: TranscriptProvider | None = None,
    db_path: Path | str = DB_PATH,
) -> AutomationRun:
    run = AutomationRun()
    run.detected = mark_due_meetings_ended(at, db_path)
    for meeting in get_automation_candidates(at, db_path):
        meeting_id = int(meeting["id"])
        if not meeting["assistant_enabled"]:
            mark_automation_complete(meeting_id, "Completed", db_path)
            run.completed_without_ai += 1
            continue
        outcome = process_meeting(meeting_id, provider, db_path)
        if outcome == "processed":
            run.processed += 1
        elif outcome == "waiting":
            run.waiting_for_transcript += 1
        elif outcome == "failed":
            run.failed.append(meeting_id)
    return run


def simulate_meeting_ended(
    meeting_id: int, db_path: Path | str = DB_PATH
) -> AutomationRun:
    meeting = get_meeting(meeting_id, db_path)
    if not meeting:
        raise ValueError("This meeting could not be found.")
    if meeting["status"] in {"Processing", "Review ready", "Approved", "Completed"}:
        raise ValueError("This meeting has already been processed.")
    set_meeting_status(meeting_id, "Meeting ended", db_path)
    return run_automation(provider=DemoTranscriptProvider(), db_path=db_path)
