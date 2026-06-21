from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from .database import DB_PATH, db_session, fetch_all, get_actions, get_attendees, get_meeting, now_iso


MEETING_OFFSETS = (
    (timedelta(days=1), "1 day before"),
    (timedelta(minutes=30), "30 minutes before"),
    (timedelta(minutes=10), "10 minutes before"),
)

ACTION_OFFSETS = (
    (timedelta(days=3), "3 days before due date"),
    (timedelta(days=1), "1 day before due date"),
    (timedelta(), "Due date morning"),
    (-timedelta(days=1), "Overdue notification"),
)


def schedule_meeting_reminders(
    meeting_id: int,
    recipient_scope: str = "All attendees",
    custom_emails: list[str] | None = None,
    db_path: Path | str = DB_PATH,
) -> int:
    meeting = get_meeting(meeting_id, db_path)
    if not meeting:
        return 0
    recipients = {meeting["organizer_email"]}
    if recipient_scope == "All attendees":
        recipients.update(a["email"] for a in get_attendees(meeting_id, db_path))
    elif recipient_scope == "Custom attendees":
        recipients.update(custom_emails or [])

    start = datetime.fromisoformat(meeting["start_time"])
    created = 0
    with db_session(db_path) as connection:
        for offset, label in MEETING_OFFSETS:
            scheduled_for = start - offset
            for email in recipients:
                cursor = connection.execute(
                    """
                    INSERT INTO reminders
                        (kind, meeting_id, action_id, recipient_email, scheduled_for,
                         label, channel, status)
                    SELECT 'Meeting', ?, NULL, ?, ?, ?, 'Email + Teams', 'Pending'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM reminders
                        WHERE kind = 'Meeting'
                          AND meeting_id = ?
                          AND action_id IS NULL
                          AND recipient_email = ?
                          AND scheduled_for = ?
                          AND label = ?
                    )
                    """,
                    (
                        meeting_id,
                        email,
                        scheduled_for.isoformat(),
                        label,
                        meeting_id,
                        email,
                        scheduled_for.isoformat(),
                        label,
                    ),
                )
                created += cursor.rowcount
        connection.commit()
    return created


def schedule_action_reminders(
    meeting_id: int | None = None, db_path: Path | str = DB_PATH
) -> int:
    actions = get_actions(meeting_id, db_path)
    created = 0
    with db_session(db_path) as connection:
        for action in actions:
            if action["status"] == "Completed":
                continue
            due = date.fromisoformat(action["due_date"])
            for offset, label in ACTION_OFFSETS:
                reminder_day = due - offset
                scheduled_for = datetime.combine(reminder_day, time(hour=9))
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO reminders
                        (kind, meeting_id, action_id, recipient_email, scheduled_for,
                         label, channel, status)
                    VALUES ('Action', ?, ?, ?, ?, ?, 'Email + Teams', 'Pending')
                    """,
                    (
                        action["meeting_id"],
                        action["id"],
                        action["owner_email"],
                        scheduled_for.isoformat(),
                        label,
                    ),
                )
                created += cursor.rowcount
        connection.commit()
    return created


def run_reminder_engine(
    at: datetime | None = None, db_path: Path | str = DB_PATH
) -> int:
    current = (at or datetime.now()).replace(microsecond=0)
    with db_session(db_path) as connection:
        connection.execute(
            """
            UPDATE actions
            SET status = 'Overdue'
            WHERE status = 'Open' AND due_date < ?
            """,
            (current.date().isoformat(),),
        )
        due_reminders = connection.execute(
            """
            SELECT r.*, m.title AS meeting_title, ac.task
            FROM reminders r
            LEFT JOIN meetings m ON m.id = r.meeting_id
            LEFT JOIN actions ac ON ac.id = r.action_id
            WHERE r.status = 'Pending'
              AND r.scheduled_for <= ?
              AND (r.kind != 'Action' OR ac.status != 'Completed')
            ORDER BY r.scheduled_for
            """,
            (current.isoformat(),),
        ).fetchall()
        created = 0
        for reminder in due_reminders:
            if reminder["kind"] == "Meeting":
                subject = f"Meeting reminder: {reminder['meeting_title']}"
                message = f"{reminder['meeting_title']} is coming up ({reminder['label']})."
            else:
                subject = f"Action reminder: {reminder['task']}"
                message = f"{reminder['task']} - {reminder['label']}."
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notifications
                    (reminder_id, recipient_email, subject, message, channel, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'Queued', ?)
                """,
                (
                    reminder["id"],
                    reminder["recipient_email"],
                    subject,
                    message,
                    reminder["channel"],
                    now_iso(),
                ),
            )
            created += cursor.rowcount
            connection.execute(
                "UPDATE reminders SET status = 'Triggered' WHERE id = ?",
                (reminder["id"],),
            )
        connection.commit()
    return created


def get_reminders(db_path: Path | str = DB_PATH) -> list[dict]:
    return fetch_all(
        """
        SELECT r.*, m.title AS meeting_title, ac.task
        FROM reminders r
        LEFT JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN actions ac ON ac.id = r.action_id
        ORDER BY r.scheduled_for
        """,
        db_path=db_path,
    )
