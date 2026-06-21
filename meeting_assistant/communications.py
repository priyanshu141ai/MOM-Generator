from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .database import DB_PATH, db_session, fetch_all, get_intelligence, get_meeting, now_iso


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_CHANNELS = {"Email", "Teams", "Email + Teams"}


def queue_meeting_results(
    meeting_id: int,
    recipients: list[str],
    include_summary: bool = True,
    include_mom: bool = True,
    include_actions: bool = True,
    channel: str = "Email + Teams",
    db_path: Path | str = DB_PATH,
) -> int:
    meeting = get_meeting(meeting_id, db_path)
    intelligence = get_intelligence(meeting_id, db_path)
    if not meeting or not intelligence:
        raise ValueError("Generate meeting intelligence before distributing results.")
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("Choose a valid delivery channel.")
    clean_recipients = sorted(
        {email.strip().lower() for email in recipients if EMAIL_PATTERN.fullmatch(email.strip())}
    )
    if not clean_recipients:
        raise ValueError("Choose at least one valid recipient.")
    if not any((include_summary, include_mom, include_actions)):
        raise ValueError("Choose at least one item to share.")

    sections: list[str] = []
    if include_summary:
        sections.append(f"Summary\n{intelligence['summary']}")
    if include_mom:
        sections.append(f"Minutes of Meeting\n{intelligence['mom']}")
    if include_actions:
        sections.append("Action items are available in the assistant action tracker.")
    message = "\n\n".join(sections)

    created = 0
    with db_session(db_path) as connection:
        for recipient in clean_recipients:
            dedupe_source = (
                f"{meeting_id}|{intelligence['generated_at']}|{recipient}|{channel}|"
                f"{include_summary}|{include_mom}|{include_actions}"
            )
            dedupe_key = hashlib.sha256(dedupe_source.encode("utf-8")).hexdigest()
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notifications
                    (reminder_id, recipient_email, subject, message, channel, status,
                     created_at, dedupe_key)
                VALUES (NULL, ?, ?, ?, ?, 'Queued', ?, ?)
                """,
                (
                    recipient,
                    f"Meeting follow-up: {meeting['title']}",
                    message,
                    channel,
                    now_iso(),
                    dedupe_key,
                ),
            )
            created += cursor.rowcount
        connection.execute(
            "UPDATE intelligence SET approved = 1 WHERE meeting_id = ?",
            (meeting_id,),
        )
        connection.commit()
    return created


def get_notifications(db_path: Path | str = DB_PATH) -> list[dict]:
    return fetch_all(
        "SELECT * FROM notifications ORDER BY created_at DESC", db_path=db_path
    )


def mark_notification_sent(notification_id: int, db_path: Path | str = DB_PATH) -> None:
    with db_session(db_path) as connection:
        connection.execute(
            """
            UPDATE notifications
            SET status = 'Sent (demo)', sent_at = ?
            WHERE id = ?
            """,
            (now_iso(), notification_id),
        )
        connection.commit()


def send_all_queued(db_path: Path | str = DB_PATH) -> int:
    with db_session(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET status = 'Sent (demo)', sent_at = ?
            WHERE status = 'Queued'
            """,
            (now_iso(),),
        )
        connection.commit()
        return cursor.rowcount
