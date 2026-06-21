from __future__ import annotations

import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


DB_PATH = Path(__file__).resolve().parent.parent / "meeting_assistant.db"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def db_session(db_path: Path | str = DB_PATH):
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path | str = DB_PATH, seed: bool = True) -> None:
    with db_session(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                organizer_name TEXT NOT NULL,
                organizer_email TEXT NOT NULL,
                assistant_enabled INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Scheduled',
                teams_channel TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                receive_reminders INTEGER NOT NULL DEFAULT 1,
                UNIQUE(meeting_id, email)
            );

            CREATE TABLE IF NOT EXISTS intelligence (
                meeting_id INTEGER PRIMARY KEY REFERENCES meetings(id) ON DELETE CASCADE,
                transcript TEXT NOT NULL,
                summary TEXT NOT NULL,
                mom TEXT NOT NULL,
                decisions TEXT NOT NULL,
                risks TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,
                generated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                owner_name TEXT NOT NULL,
                owner_email TEXT NOT NULL,
                task TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
                action_id INTEGER REFERENCES actions(id) ON DELETE CASCADE,
                recipient_email TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                label TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'Email + Teams',
                status TEXT NOT NULL DEFAULT 'Pending',
                UNIQUE(kind, meeting_id, action_id, recipient_email, scheduled_for, label)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER REFERENCES reminders(id) ON DELETE SET NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Queued',
                created_at TEXT NOT NULL,
                sent_at TEXT,
                dedupe_key TEXT,
                UNIQUE(reminder_id)
            );
            """
        )
        notification_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(notifications)").fetchall()
        }
        if "dedupe_key" not in notification_columns:
            connection.execute("ALTER TABLE notifications ADD COLUMN dedupe_key TEXT")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe
            ON notifications(dedupe_key)
            WHERE dedupe_key IS NOT NULL
            """
        )
    if seed:
        seed_demo_data(db_path)


def fetch_all(
    query: str, params: Iterable[Any] = (), db_path: Path | str = DB_PATH
) -> list[dict[str, Any]]:
    with db_session(db_path) as connection:
        return [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]


def fetch_one(
    query: str, params: Iterable[Any] = (), db_path: Path | str = DB_PATH
) -> dict[str, Any] | None:
    with db_session(db_path) as connection:
        row = connection.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None


def execute(
    query: str, params: Iterable[Any] = (), db_path: Path | str = DB_PATH
) -> int:
    with db_session(db_path) as connection:
        cursor = connection.execute(query, tuple(params))
        connection.commit()
        if cursor.lastrowid is None:
            return 0
        return int(cursor.lastrowid)


def create_meeting(
    title: str,
    start_time: datetime,
    end_time: datetime,
    organizer_name: str,
    organizer_email: str,
    assistant_enabled: bool,
    attendees: list[tuple[str, str]],
    teams_channel: str = "",
    db_path: Path | str = DB_PATH,
) -> int:
    if not title.strip():
        raise ValueError("Meeting title is required.")
    if not organizer_name.strip():
        raise ValueError("Organizer name is required.")
    if not EMAIL_PATTERN.fullmatch(organizer_email.strip()):
        raise ValueError("Organizer email is not valid.")
    if end_time <= start_time:
        raise ValueError("Meeting end time must be after its start time.")
    invalid_attendees = [email for _, email in attendees if not EMAIL_PATTERN.fullmatch(email.strip())]
    if invalid_attendees:
        raise ValueError("One or more attendee email addresses are not valid.")

    with db_session(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO meetings
                (title, start_time, end_time, organizer_name, organizer_email,
                 assistant_enabled, status, teams_channel, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?)
            """,
            (
                title.strip(),
                start_time.replace(microsecond=0).isoformat(),
                end_time.replace(microsecond=0).isoformat(),
                organizer_name.strip(),
                organizer_email.strip().lower(),
                int(assistant_enabled),
                teams_channel.strip(),
                now_iso(),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("The meeting could not be saved.")
        meeting_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO attendees (meeting_id, name, email, receive_reminders)
            VALUES (?, ?, ?, 1)
            """,
            [
                (meeting_id, name.strip(), email.strip().lower())
                for name, email in attendees
                if name.strip() and email.strip()
            ],
        )
        connection.commit()
    return meeting_id


def get_meetings(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT m.*,
               COUNT(DISTINCT a.id) AS attendee_count,
               COUNT(DISTINCT ac.id) AS action_count,
               i.approved AS intelligence_approved
        FROM meetings m
        LEFT JOIN attendees a ON a.meeting_id = m.id
        LEFT JOIN actions ac ON ac.meeting_id = m.id
        LEFT JOIN intelligence i ON i.meeting_id = m.id
        GROUP BY m.id
        ORDER BY m.start_time DESC
        """,
        db_path=db_path,
    )


def get_meeting(meeting_id: int, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM meetings WHERE id = ?", (meeting_id,), db_path)


def set_meeting_assistant(
    meeting_id: int, enabled: bool, db_path: Path | str = DB_PATH
) -> None:
    with db_session(db_path) as connection:
        cursor = connection.execute(
            "UPDATE meetings SET assistant_enabled = ? WHERE id = ?",
            (int(enabled), meeting_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("This meeting could not be found.")


def get_attendees(meeting_id: int, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT * FROM attendees WHERE meeting_id = ? ORDER BY name",
        (meeting_id,),
        db_path,
    )


def save_intelligence(
    meeting_id: int,
    transcript: str,
    summary: str,
    mom: str,
    decisions: str,
    risks: str,
    approved: bool = False,
    db_path: Path | str = DB_PATH,
) -> None:
    execute(
        """
        INSERT INTO intelligence
            (meeting_id, transcript, summary, mom, decisions, risks, approved, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(meeting_id) DO UPDATE SET
            transcript = excluded.transcript,
            summary = excluded.summary,
            mom = excluded.mom,
            decisions = excluded.decisions,
            risks = excluded.risks,
            approved = excluded.approved,
            generated_at = excluded.generated_at
        """,
        (
            meeting_id,
            transcript,
            summary,
            mom,
            decisions,
            risks,
            int(approved),
            now_iso(),
        ),
        db_path,
    )


def get_intelligence(meeting_id: int, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    return fetch_one(
        "SELECT * FROM intelligence WHERE meeting_id = ?", (meeting_id,), db_path
    )


def replace_actions(
    meeting_id: int,
    actions: list[dict[str, str]],
    db_path: Path | str = DB_PATH,
) -> None:
    for action in actions:
        if not action.get("owner_name", "").strip() or not action.get("task", "").strip():
            raise ValueError("Each action needs an owner and a task.")
        if not EMAIL_PATTERN.fullmatch(action.get("owner_email", "").strip()):
            raise ValueError("Each action needs a valid owner email.")
        try:
            datetime.strptime(action.get("due_date", ""), "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Each action needs a valid due date.") from exc

    with db_session(db_path) as connection:
        connection.execute("DELETE FROM actions WHERE meeting_id = ?", (meeting_id,))
        connection.executemany(
            """
            INSERT INTO actions
                (meeting_id, owner_name, owner_email, task, due_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'Open', ?)
            """,
            [
                (
                    meeting_id,
                    action["owner_name"],
                    action["owner_email"].lower(),
                    action["task"],
                    action["due_date"],
                    now_iso(),
                )
                for action in actions
            ],
        )
        connection.commit()


def get_actions(
    meeting_id: int | None = None, db_path: Path | str = DB_PATH
) -> list[dict[str, Any]]:
    where = "WHERE ac.meeting_id = ?" if meeting_id is not None else ""
    params: tuple[Any, ...] = (meeting_id,) if meeting_id is not None else ()
    return fetch_all(
        f"""
        SELECT ac.*, m.title AS meeting_title
        FROM actions ac
        JOIN meetings m ON m.id = ac.meeting_id
        {where}
        ORDER BY CASE ac.status WHEN 'Overdue' THEN 0 WHEN 'Open' THEN 1 ELSE 2 END,
                 ac.due_date
        """,
        params,
        db_path,
    )


def set_action_status(
    action_id: int, status: str, db_path: Path | str = DB_PATH
) -> None:
    completed_at = now_iso() if status == "Completed" else None
    if status not in {"Open", "Overdue", "Completed"}:
        raise ValueError("Action status is not valid.")
    with db_session(db_path) as connection:
        connection.execute(
            "UPDATE actions SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, action_id),
        )
        if status == "Completed":
            connection.execute(
                """
                UPDATE reminders
                SET status = 'Cancelled'
                WHERE action_id = ? AND status = 'Pending'
                """,
                (action_id,),
            )


def dashboard_stats(db_path: Path | str = DB_PATH) -> dict[str, int]:
    def count(query: str, params: Iterable[Any] = ()) -> int:
        row = fetch_one(query, params, db_path)
        return int(row["count"]) if row else 0

    return {
        "upcoming": count(
            "SELECT COUNT(*) AS count FROM meetings WHERE start_time >= ?",
            (now_iso(),),
        ),
        "assistant": count(
            "SELECT COUNT(*) AS count FROM meetings WHERE assistant_enabled = 1"
        ),
        "open_actions": count(
            "SELECT COUNT(*) AS count FROM actions WHERE status != 'Completed'"
        ),
        "overdue": count(
            "SELECT COUNT(*) AS count FROM actions WHERE status = 'Overdue'"
        ),
    }


def seed_demo_data(db_path: Path | str = DB_PATH) -> None:
    existing = fetch_one("SELECT COUNT(*) AS count FROM meetings", db_path=db_path)
    if existing and existing["count"]:
        return

    now = datetime.now().replace(second=0, microsecond=0)
    first_start = now + timedelta(days=1, hours=2)
    first_due = (now + timedelta(days=4)).date().isoformat()
    second_due = (now + timedelta(days=5)).date().isoformat()
    first_id = create_meeting(
        "Weekly Project Review",
        first_start,
        first_start + timedelta(hours=1),
        "Aarav Mehta",
        "aarav.mehta@contoso.com",
        True,
        [
            ("Rahul Sharma", "rahul.sharma@contoso.com"),
            ("Priya Nair", "priya.nair@contoso.com"),
            ("Neha Singh", "neha.singh@contoso.com"),
        ],
        "Project Phoenix",
        db_path,
    )

    transcript = (
        "Aarav: We agreed to submit the revised commercial proposal this week.\n"
        f"Rahul: I will submit the budget proposal by {first_due}.\n"
        f"Priya: I will review the tender document by {second_due}.\n"
        "Neha: The vendor approval delay is a risk to the planned launch.\n"
        "Aarav: Decision: retain the current launch scope and review progress Friday."
    )
    save_intelligence(
        first_id,
        transcript,
        "The team aligned on the commercial proposal, tender review, and current launch scope. Vendor approval remains the main delivery risk.",
        "### Minutes of Meeting\n\nThe team reviewed commercial readiness and launch dependencies. The revised proposal and tender review will be completed this week. The current launch scope remains unchanged, with progress to be reviewed on Friday.",
        "- Retain the current launch scope.\n- Review delivery progress on Friday.",
        "- Vendor approval delay may affect the planned launch.",
        True,
        db_path,
    )
    replace_actions(
        first_id,
        [
            {
                "owner_name": "Rahul Sharma",
                "owner_email": "rahul.sharma@contoso.com",
                "task": "Submit the budget proposal",
                "due_date": first_due,
            },
            {
                "owner_name": "Priya Nair",
                "owner_email": "priya.nair@contoso.com",
                "task": "Review the tender document",
                "due_date": second_due,
            },
        ],
        db_path,
    )

    second_start = now + timedelta(days=3, hours=1)
    create_meeting(
        "HR Policy Briefing",
        second_start,
        second_start + timedelta(minutes=45),
        "Kavya Rao",
        "kavya.rao@contoso.com",
        False,
        [
            ("Aarav Mehta", "aarav.mehta@contoso.com"),
            ("Priya Nair", "priya.nair@contoso.com"),
        ],
        "People Operations",
        db_path,
    )
