from __future__ import annotations

import html
import json
import logging
import os
import sqlite3
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from meeting_assistant.ai_engine import analyze_transcript, azure_is_configured
from meeting_assistant.communications import (
    get_notifications,
    mark_notification_sent,
    queue_meeting_results,
    send_all_queued,
)
from meeting_assistant.database import (
    create_meeting,
    dashboard_stats,
    get_actions,
    get_attendees,
    get_intelligence,
    get_meeting,
    get_meetings,
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


load_dotenv()
LOGGER = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 1_000_000
st.set_page_config(
    page_title="Meetwise | Meeting Intelligence",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="auto",
)
try:
    init_db()
except sqlite3.DatabaseError:
    LOGGER.exception("Database initialization failed")
    st.error("The local database could not be opened. Ask an administrator to check the data file.")
    st.stop()


st.markdown(
    """
    <style>
    :root {
        --ink: #242424;
        --muted: #5f5f67;
        --line: #d8d8dc;
        --surface: #ffffff;
        --canvas: #f4f4f6;
        --teams: #5b5fc7;
        --teams-dark: #3f4068;
        --green: #107c10;
        --coral: #c50f1f;
    }
    html, body, [class*="css"] { font-family:"Segoe UI Variable", "Segoe UI", sans-serif; }
    .stApp { background: var(--canvas); color: var(--ink); }
    .teams-topbar { position:fixed; inset:0 0 auto 0; height:52px; z-index:999999;
        display:flex; align-items:center; justify-content:space-between; padding:0 18px 0 56px;
        background:var(--teams-dark); color:#fff; box-shadow:0 1px 3px rgba(0,0,0,.22);
        pointer-events:none; }
    .stApp:has(button[data-testid="stExpandSidebarButton"]) .teams-topbar::before {
        content:""; position:absolute; left:18px; top:18px; width:18px; height:2px;
        border-radius:1px; background:#fff; box-shadow:0 6px 0 #fff, 0 12px 0 #fff;
    }
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stExpandSidebarButton"] {
        position:fixed !important; top:7px !important; left:8px !important;
        z-index:1000001 !important; width:38px !important; height:38px !important;
        opacity:1 !important;
    }
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="stExpandSidebarButton"],
    [data-testid="stExpandSidebarButton"] button {
        color:#fff !important; background:transparent !important; border-color:transparent !important;
    }
    [data-testid="stSidebarCollapsedControl"] button:hover,
    [data-testid="stExpandSidebarButton"] button:hover {
        background:rgba(255,255,255,.12);
    }
    .teams-product { display:flex; align-items:center; gap:10px; font-size:.9rem; font-weight:600; }
    .teams-app-grid { width:18px; height:18px; display:grid; grid-template-columns:repeat(3,4px);
        grid-auto-rows:4px; gap:2px; align-content:center; }
    .teams-app-grid i { display:block; width:4px; height:4px; background:#fff; opacity:.9; }
    .teams-context { opacity:.78; font-weight:400; padding-left:10px; border-left:1px solid rgba(255,255,255,.35); }
    .teams-avatar { width:28px; height:28px; display:grid; place-items:center; border-radius:50%;
        background:#dff6dd; color:#0b6a0b; font-size:.7rem; font-weight:700; }
    [data-testid="stSidebar"] { background:#f1f1f3; border-right:1px solid var(--line);
        padding-top:52px; box-shadow:2px 0 8px rgba(36,36,36,.04); }
    [data-testid="stSidebar"] * { color: var(--ink); }
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        min-height:40px; padding: 0.5rem 0.65rem; border-radius: 4px; margin-bottom: 0.1rem;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover { background: #e5e5e5; }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:has(input:checked) {
        background:#e8e8f8; color:#3d3e78; font-weight:650; box-shadow:inset 3px 0 0 var(--teams); }
    [data-testid="stSidebar"] hr { border-color: var(--line); }
    .block-container { padding-top:4.65rem; padding-bottom:4rem; max-width:1420px; }
    h1, h2, h3 { letter-spacing: 0 !important; color: var(--ink); }
    h1 { font-size: 1.55rem !important; font-weight: 650 !important; }
    h2 { font-size: 1.15rem !important; font-weight:650 !important; }
    h3 { font-size: .95rem !important; font-weight:650 !important; }
    .eyebrow { color: var(--teams); font-weight: 650; font-size: 0.72rem;
        text-transform: uppercase; letter-spacing: .06em; margin-bottom: .2rem; }
    .page-copy { color:var(--muted); margin:-.35rem 0 1.55rem; max-width:760px; line-height:1.55; }
    .brand { display:flex; align-items:center; gap:.65rem; padding:.1rem 0 .9rem; }
    .brand-mark { width:32px; height:32px; display:grid; place-items:center;
        background:var(--teams); color:white; border-radius:5px; font-weight:750; }
    .brand-name { font-weight:650; font-size:1rem; color:var(--ink); }
    .brand-sub { color:var(--muted); font-size:.68rem; }
    .surface { background:var(--surface); border:1px solid var(--line); border-radius:6px;
        padding:1.1rem 1.2rem; min-height:100%; box-shadow:0 2px 8px rgba(36,36,36,.045); }
    .meeting-row { background:white; border:1px solid var(--line); border-left:3px solid var(--teams);
        border-radius:5px; padding:.82rem .95rem; margin-bottom:.55rem;
        box-shadow:0 1px 4px rgba(36,36,36,.035); transition:border-color .15s, box-shadow .15s; }
    .meeting-row:hover { border-color:#b8b8c0; border-left-color:var(--teams);
        box-shadow:0 4px 12px rgba(36,36,36,.075); }
    .meeting-row.no-ai { border-left-color:#9aa5af; }
    .meeting-title { font-weight:650; color:var(--ink); margin-bottom:.2rem; }
    .meta { color:var(--muted); font-size:.82rem; }
    .pill { display:inline-block; padding:.16rem .45rem; border-radius:4px; font-size:.69rem;
        font-weight:650; margin-right:.3rem; background:#e8e8f8; color:#3d3e78; }
    .pill.green { background:#dff6dd; color:#0b6a0b; }
    .pill.gray { background:#ebebeb; color:#505050; }
    .pill.red { background:#fde7e9; color:#a80000; }
    .privacy-note { border-left:3px solid var(--teams); background:#f0f0ff; padding:.75rem .9rem;
        color:#3d3e78; border-radius:0 4px 4px 0; font-size:.84rem; margin:.5rem 0 1rem; }
    [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:6px;
        padding:.95rem 1.05rem; min-height:98px; box-shadow:0 2px 8px rgba(36,36,36,.045); }
    [data-testid="stMetricLabel"] { color:var(--muted); }
    [data-testid="stMetricValue"] { color:var(--ink); font-size:1.7rem; }
    .integration { display:flex; justify-content:space-between; align-items:center; gap:1rem;
        padding:.8rem 0; border-bottom:1px solid var(--line); }
    .integration:last-child { border-bottom:0; }
    .integration strong { display:block; }
    .integration span { color:var(--muted); font-size:.8rem; }
    div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:6px;
        padding:1.1rem; box-shadow:0 2px 8px rgba(36,36,36,.04); }
    div[data-testid="stExpander"] { border-color:var(--line); background:#fff; border-radius:6px; }
    .stButton > button { border-radius:4px; font-weight:600; min-height:34px; }
    .stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible {
        outline:2px solid var(--teams); outline-offset:2px; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background:var(--teams); border-color:var(--teams); }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
        background:#4f52b2; border-color:#4f52b2; }
    div[data-baseweb="input"] { border-radius:4px; }
    div[data-baseweb="input"], div[data-baseweb="textarea"],
    div[data-baseweb="select"] > div {
        background:#fff !important; color:var(--ink) !important; border-color:#b9b9bf !important;
    }
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea,
    div[data-baseweb="select"] span {
        color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important;
    }
    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="textarea"] textarea::placeholder {
        color:#85858d !important; -webkit-text-fill-color:#85858d !important;
    }
    [data-testid="stWidgetLabel"] p, [data-testid="stRadio"] label p,
    [data-testid="stCheckbox"] label p, [data-testid="stToggle"] label p {
        color:var(--ink) !important;
    }
    .stButton > button[kind="secondary"] {
        background:#fff !important; color:var(--ink) !important; border:1px solid #b9b9bf !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background:#f0f0f3 !important; border-color:#8f8f98 !important;
    }
    [data-testid="stSegmentedControl"] { background:#e9e9ee !important;
        border:1px solid #d1d1d7 !important; border-radius:5px !important; padding:2px !important; }
    [data-testid="stSegmentedControl"] button {
        background:transparent !important; color:#4b4b52 !important; border:0 !important;
    }
    [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
        background:#fff !important; color:var(--teams) !important;
        box-shadow:0 1px 4px rgba(36,36,36,.12) !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap:1rem; }
    .stTabs [data-baseweb="tab"] { padding-left:0; padding-right:0; color:var(--muted) !important; }
    .stTabs [aria-selected="true"] { color:var(--teams) !important; }
    @media (max-width: 700px) {
        .teams-context { display:none; }
        .block-container { padding:4.4rem .8rem 3rem; }
        h1 { font-size:1.35rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="teams-topbar">
        <div class="teams-product">
            <span class="teams-app-grid" aria-hidden="true">
                <i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>
            </span>
            <span>Microsoft Teams</span><span class="teams-context">Meetwise</span>
        </div>
        <div class="teams-avatar" title="Aarav Mehta">AM</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def page_header(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1>{html.escape(title)}</h1>'
        f'<div class="page-copy">{html.escape(description)}</div>',
        unsafe_allow_html=True,
    )


def fmt_datetime(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d %b %Y, %I:%M %p")


def meeting_selector(label: str, assistant_only: bool = False) -> int | None:
    meetings = get_meetings()
    if assistant_only:
        meetings = [meeting for meeting in meetings if meeting["assistant_enabled"]]
    if not meetings:
        st.info("No eligible meetings yet.")
        return None
    options = {meeting["id"]: meeting for meeting in meetings}
    return st.selectbox(
        label,
        options=list(options),
        format_func=lambda meeting_id: (
            f"{options[meeting_id]['title']}  ·  {fmt_datetime(options[meeting_id]['start_time'])}"
        ),
    )


def parse_attendees(raw: str) -> tuple[list[tuple[str, str]], list[str]]:
    attendees: list[tuple[str, str]] = []
    invalid: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "<" in line and line.endswith(">"):
            name, email = line[:-1].split("<", 1)
        elif "," in line:
            name, email = line.split(",", 1)
        else:
            invalid.append(line)
            continue
        if "@" not in email:
            invalid.append(line)
            continue
        attendees.append((name.strip(), email.strip()))
    return attendees, invalid


with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">M</div>
            <div><div class="brand-name">Meetwise</div>
            <div class="brand-sub">MEETING INTELLIGENCE</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Workspace",
        [
            "Overview",
            "Meetings",
            "Intelligence",
            "Action tracker",
            "Notifications",
            "Integrations",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    mode = "Azure connected" if azure_is_configured() else "Demo mode"
    st.caption(f"● {mode}")
    st.caption("Privacy-first: the assistant joins only when explicitly enabled.")


if page == "Overview":
    page_header(
        "Operations workspace",
        "Meeting follow-up, without the follow-up chase",
        "Monitor upcoming meetings, approved intelligence, action ownership, and reminders from one place.",
    )
    stats = dashboard_stats()
    metric_cols = st.columns(4)
    metric_cols[0].metric("Upcoming meetings", stats["upcoming"])
    metric_cols[1].metric("Assistant enabled", stats["assistant"])
    metric_cols[2].metric("Open actions", stats["open_actions"])
    metric_cols[3].metric("Overdue", stats["overdue"])

    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.subheader("Upcoming meetings")
        upcoming = [
            meeting
            for meeting in reversed(get_meetings())
            if datetime.fromisoformat(meeting["start_time"]) >= datetime.now()
        ][:5]
        if not upcoming:
            st.info("No upcoming meetings. Schedule one from the Meetings page.")
        for meeting in upcoming:
            ai_class = "" if meeting["assistant_enabled"] else " no-ai"
            badge = (
                '<span class="pill">Assistant enabled</span>'
                if meeting["assistant_enabled"]
                else '<span class="pill gray">Reminders only</span>'
            )
            st.markdown(
                f'<div class="meeting-row{ai_class}"><div class="meeting-title">'
                f'{html.escape(meeting["title"])}</div>{badge}'
                f'<span class="pill green">{meeting["attendee_count"]} attendees</span>'
                f'<div class="meta">{fmt_datetime(meeting["start_time"])} · '
                f'{html.escape(meeting["organizer_name"])}</div></div>',
                unsafe_allow_html=True,
            )
    with right:
        st.subheader("Attention needed")
        open_actions = [a for a in get_actions() if a["status"] != "Completed"][:5]
        if not open_actions:
            st.success("All action items are complete.")
        for action in open_actions:
            is_overdue = action["status"] == "Overdue" or action["due_date"] < date.today().isoformat()
            badge_class = "red" if is_overdue else "green"
            label = "Overdue" if is_overdue else f"Due {action['due_date']}"
            st.markdown(
                f'<div class="meeting-row"><div class="meeting-title">'
                f'{html.escape(action["task"])}</div><span class="pill {badge_class}">'
                f'{label}</span><div class="meta">{html.escape(action["owner_name"])} · '
                f'{html.escape(action["meeting_title"])}</div></div>',
                unsafe_allow_html=True,
            )


elif page == "Meetings":
    page_header(
        "Calendar and consent",
        "Meetings",
        "Schedule meetings, choose whether the assistant may join, and configure reminders independently.",
    )
    schedule_tab, manage_tab = st.tabs(["Schedule meeting", "Manage meetings"])
    with schedule_tab:
        st.markdown(
            '<div class="privacy-note"><strong>Consent boundary:</strong> Turning the assistant off prevents transcript access and AI processing. Calendar reminders remain available.</div>',
            unsafe_allow_html=True,
        )
        with st.form("schedule_meeting", clear_on_submit=True):
            st.markdown("#### Meeting details")
            col1, col2 = st.columns(2)
            title = col1.text_input("Meeting title", placeholder="Weekly Project Review")
            organizer_name = col2.text_input("Organizer name", placeholder="Aarav Mehta")
            organizer_email = col1.text_input(
                "Organizer email", placeholder="aarav.mehta@company.com"
            )
            teams_channel = col2.text_input(
                "Teams channel (optional)", placeholder="Project Phoenix"
            )
            dcol, scol, ecol = st.columns([1.2, 1, 1])
            meeting_date = dcol.date_input("Date", value=date.today() + timedelta(days=1))
            start_at = scol.time_input("Starts", value=time(11, 0))
            end_at = ecol.time_input("Ends", value=time(12, 0))
            attendee_text = st.text_area(
                "Attendees",
                placeholder="Rahul Sharma <rahul@company.com>\nPriya Nair <priya@company.com>",
                help="Enter one attendee per line as Name <email> or Name, email.",
            )
            st.markdown("#### AI assistant access")
            assistant_choice = st.radio(
                "Allow the AI assistant to join and process this meeting?",
                ["No - reminders only", "Yes - add AI assistant"],
                horizontal=True,
                help="Allows transcript capture and meeting intelligence for this meeting only.",
            )
            assistant_enabled = assistant_choice == "Yes - add AI assistant"
            st.markdown("#### Reminder delivery")
            reminder_scope = st.selectbox(
                "Meeting reminder recipients",
                ["All attendees", "Organizer only"],
            )
            submitted = st.form_submit_button(
                "Schedule meeting", type="primary", icon=":material/event_available:"
            )
        if submitted:
            attendees, invalid = parse_attendees(attendee_text)
            start_datetime = datetime.combine(meeting_date, start_at)
            end_datetime = datetime.combine(meeting_date, end_at)
            if not title.strip() or not organizer_name.strip() or "@" not in organizer_email:
                st.error("Add a title and valid organizer details.")
            elif end_datetime <= start_datetime:
                st.error("The meeting end time must be after its start time.")
            elif invalid:
                st.error("Check these attendee entries: " + "; ".join(invalid))
            else:
                try:
                    meeting_id = create_meeting(
                        title,
                        start_datetime,
                        end_datetime,
                        organizer_name,
                        organizer_email,
                        assistant_enabled,
                        attendees,
                        teams_channel,
                    )
                    created = schedule_meeting_reminders(meeting_id, reminder_scope)
                    st.success(f"Meeting scheduled. {created} reminder events created.")
                except (ValueError, sqlite3.DatabaseError) as exc:
                    LOGGER.exception("Meeting creation failed")
                    st.error(str(exc) if isinstance(exc, ValueError) else "The meeting could not be saved.")

    with manage_tab:
        meeting_id = meeting_selector("Select meeting")
        if meeting_id:
            meeting = get_meeting(meeting_id)
            if meeting is None:
                st.error("This meeting could not be found.")
                st.stop()
            attendees = get_attendees(meeting_id)
            left, right = st.columns([1.2, 1])
            with left:
                st.subheader(meeting["title"])
                st.write(f"**When:** {fmt_datetime(meeting['start_time'])}")
                st.write(
                    f"**Organizer:** {meeting['organizer_name']} ({meeting['organizer_email']})"
                )
                st.write(f"**Teams channel:** {meeting['teams_channel'] or 'Not selected'}")
                badge = "Assistant enabled" if meeting["assistant_enabled"] else "Reminders only"
                st.info(badge)
            with right:
                st.subheader("Participants")
                for attendee in attendees:
                    st.write(f"**{attendee['name']}** ({attendee['email']})")
            st.divider()
            st.subheader("AI assistant access")
            assistant_choice = st.radio(
                "Allow the AI assistant to join and process this meeting?",
                ["No - reminders only", "Yes - add AI assistant"],
                index=1 if meeting["assistant_enabled"] else 0,
                horizontal=True,
                key=f"assistant_access_{meeting_id}",
            )
            desired_assistant_state = assistant_choice == "Yes - add AI assistant"
            if desired_assistant_state != bool(meeting["assistant_enabled"]):
                st.caption(
                    "Turning access off blocks new transcript processing. Existing reviewed records follow your data retention policy."
                )
                if st.button(
                    "Save assistant access",
                    type="primary",
                    icon=":material/admin_panel_settings:",
                ):
                    try:
                        set_meeting_assistant(meeting_id, desired_assistant_state)
                        st.success("AI assistant access updated.")
                        st.rerun()
                    except (ValueError, sqlite3.DatabaseError) as exc:
                        LOGGER.exception("Assistant access update failed")
                        st.error(
                            str(exc)
                            if isinstance(exc, ValueError)
                            else "Assistant access could not be updated."
                        )
            st.subheader("Meeting reminders")
            scope = st.selectbox(
                "Reminder recipients",
                ["All attendees", "Organizer only", "Custom attendees"],
                key="manage_scope",
            )
            custom: list[str] = []
            if scope == "Custom attendees":
                attendee_names = {
                    str(attendee["email"]): str(attendee["name"])
                    for attendee in attendees
                }
                custom = st.multiselect(
                    "Choose attendees",
                    options=list(attendee_names),
                    format_func=lambda email: attendee_names.get(str(email), str(email)),
                )
            if st.button(
                "Schedule reminder set", icon=":material/notifications_active:"
            ):
                created = schedule_meeting_reminders(meeting_id, scope, custom)
                st.success(f"{created} new reminder events scheduled.")


elif page == "Intelligence":
    page_header(
        "Organizer review",
        "Meeting intelligence",
        "Generate a structured record from an authorized transcript, edit it, then approve recipients and distribution.",
    )
    meeting_id = meeting_selector("Meeting with assistant enabled", assistant_only=True)
    if meeting_id:
        meeting = get_meeting(meeting_id)
        if meeting is None:
            st.error("This meeting could not be found.")
            st.stop()
        attendees = get_attendees(meeting_id)
        existing = get_intelligence(meeting_id)
        if not meeting["assistant_enabled"]:
            st.error("The assistant was not enabled for this meeting. Transcript processing is blocked.")
            st.stop()

        provider = "Azure OpenAI" if azure_is_configured() else "Demo intelligence"
        st.caption(f"Processing provider: {provider}")
        transcript_upload = st.file_uploader("Upload transcript", type=["txt", "md"])
        uploaded_text = ""
        if transcript_upload:
            upload_bytes = transcript_upload.getvalue()
            if len(upload_bytes) > MAX_UPLOAD_BYTES:
                st.error("The transcript file is too large. Use a UTF-8 text file under 1 MB.")
                st.stop()
            try:
                uploaded_text = upload_bytes.decode("utf-8")
            except UnicodeDecodeError:
                st.error("The transcript must be a UTF-8 text file.")
                st.stop()
        transcript = st.text_area(
            "Transcript",
            value=uploaded_text or (existing["transcript"] if existing else ""),
            height=190,
            placeholder="Aarav: We agreed to...\nRahul: I will submit... by 2026-06-25.",
        )
        if st.button(
            "Generate intelligence",
            type="primary",
            icon=":material/auto_awesome:",
        ):
            try:
                with st.spinner("Extracting decisions, actions, and risks..."):
                    result = analyze_transcript(transcript, meeting["title"], attendees)
                    save_intelligence(
                        meeting_id,
                        transcript,
                        result.summary,
                        result.mom,
                        result.decisions,
                        result.risks,
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
                    )
                    schedule_action_reminders(meeting_id)
                st.success(f"Draft generated with {result.provider}. Review it below.")
                st.rerun()
            except (ValueError, json.JSONDecodeError):
                LOGGER.exception("Transcript validation or model output failed")
                st.error("The transcript could not be processed. Check its format and try again.")
            except Exception:
                LOGGER.exception("Meeting intelligence generation failed")
                st.error("The AI service is not available right now. Try again later.")

        existing = get_intelligence(meeting_id)
        if existing:
            st.divider()
            st.subheader("Review draft")
            with st.form("review_intelligence"):
                summary = st.text_area("Executive summary", existing["summary"], height=110) or ""
                mom = st.text_area("Minutes of Meeting", existing["mom"], height=230) or ""
                col1, col2 = st.columns(2)
                decisions = col1.text_area("Decision log", existing["decisions"], height=150) or ""
                risks = col2.text_area("Risks and follow-ups", existing["risks"], height=150) or ""
                action_rows = get_actions(meeting_id)
                action_records = [
                    {
                        "owner_name": action["owner_name"],
                        "owner_email": action["owner_email"],
                        "task": action["task"],
                        "due_date": date.fromisoformat(action["due_date"]),
                    }
                    for action in action_rows
                ]
                action_df = (
                    pd.DataFrame(action_records)
                    if action_records
                    else pd.DataFrame(
                        {
                            "owner_name": [],
                            "owner_email": [],
                            "task": [],
                            "due_date": [],
                        }
                    )
                )
                edited_actions = st.data_editor(
                    action_df,
                    num_rows="dynamic",
                    width="stretch",
                    column_config={
                        "owner_name": st.column_config.TextColumn("Owner", required=True),
                        "owner_email": st.column_config.TextColumn("Owner email", required=True),
                        "task": st.column_config.TextColumn("Action item", required=True, width="large"),
                        "due_date": st.column_config.DateColumn("Due date", required=True),
                    },
                    hide_index=True,
                )
                save_review = st.form_submit_button(
                    "Save reviewed draft", icon=":material/save:"
                )
            if save_review:
                actions_payload = []
                for row in edited_actions.to_dict("records"):
                    if row.get("task") and row.get("owner_name") and row.get("due_date"):
                        due_value = row["due_date"]
                        actions_payload.append(
                            {
                                "owner_name": str(row["owner_name"]),
                                "owner_email": str(row.get("owner_email", "")),
                                "task": str(row["task"]),
                                "due_date": due_value.isoformat()
                                if hasattr(due_value, "isoformat")
                                else str(due_value),
                            }
                        )
                try:
                    save_intelligence(
                        meeting_id, transcript, summary, mom, decisions, risks, approved=False
                    )
                    replace_actions(meeting_id, actions_payload)
                    schedule_action_reminders(meeting_id)
                    st.success("Organizer edits saved.")
                except (ValueError, sqlite3.DatabaseError) as exc:
                    LOGGER.exception("Organizer review save failed")
                    st.error(str(exc) if isinstance(exc, ValueError) else "The review could not be saved.")

            st.subheader("Approve and distribute")
            recipient_map = {
                f"{meeting['organizer_name']} (Organizer)": meeting["organizer_email"],
                **{a["name"]: a["email"] for a in attendees},
            }
            selected_names = st.multiselect(
                "Recipients",
                options=list(recipient_map),
                default=list(recipient_map),
            )
            output_cols = st.columns(3)
            include_summary = output_cols[0].checkbox("Summary", value=True)
            include_mom = output_cols[1].checkbox("MOM", value=True)
            include_actions = output_cols[2].checkbox("Action items", value=True)
            channel = st.segmented_control(
                "Delivery channel",
                ["Email", "Teams", "Email + Teams"],
                default="Email + Teams",
            )
            if st.button(
                "Approve and queue results",
                type="primary",
                icon=":material/send:",
                disabled=not selected_names,
            ):
                try:
                    count = queue_meeting_results(
                        meeting_id,
                        [recipient_map[name] for name in selected_names],
                        include_summary,
                        include_mom,
                        include_actions,
                        channel or "Email + Teams",
                    )
                    message = (
                        f"Approved. {count} personalized messages added to the outbox."
                        if count
                        else "These results are already in the outbox."
                    )
                    st.success(message)
                except (ValueError, sqlite3.DatabaseError) as exc:
                    LOGGER.exception("Meeting result distribution failed")
                    st.error(str(exc) if isinstance(exc, ValueError) else "The messages could not be queued.")


elif page == "Action tracker":
    page_header(
        "Accountability",
        "Action tracker",
        "Track owners, due dates, completion, and automatic reminders extracted from meetings.",
    )
    actions = get_actions()
    if not actions:
        st.info("No action items yet. Generate meeting intelligence to create them.")
    else:
        action_counts = {
            status: sum(action["status"] == status for action in actions)
            for status in ("Open", "Overdue", "Completed")
        }
        action_metrics = st.columns(3)
        action_metrics[0].metric("Open actions", action_counts["Open"])
        action_metrics[1].metric("Overdue actions", action_counts["Overdue"])
        action_metrics[2].metric("Completed actions", action_counts["Completed"])
        status_filter = st.segmented_control(
            "Status",
            ["All", "Open", "Overdue", "Completed"],
            default="All",
        )
        filtered = actions if status_filter == "All" else [
            action for action in actions if action["status"] == status_filter
        ]
        for action in filtered:
            with st.expander(
                f"{action['task']}  ·  {action['owner_name']}  ·  due {action['due_date']}"
            ):
                col1, col2, col3 = st.columns([1.4, 1, 1])
                col1.write(f"**Meeting:** {action['meeting_title']}")
                col1.write(f"**Owner:** {action['owner_email']}")
                new_status = col2.selectbox(
                    "Status",
                    ["Open", "Overdue", "Completed"],
                    index=["Open", "Overdue", "Completed"].index(action["status"]),
                    key=f"status_{action['id']}",
                )
                if col3.button(
                    "Update", key=f"update_{action['id']}", icon=":material/check:"
                ):
                    set_action_status(action["id"], new_status)
                    st.success("Action status updated.")
                    st.rerun()
        if st.button(
            "Refresh task reminder schedules", icon=":material/schedule:"
        ):
            count = schedule_action_reminders()
            st.success(f"{count} new reminder events scheduled.")


elif page == "Notifications":
    page_header(
        "Communication engine",
        "Notifications",
        "Review scheduled reminder events and the email/Teams outbox before live integrations are connected.",
    )
    notification_rows = get_notifications()
    reminder_rows = get_reminders()
    notification_metrics = st.columns(3)
    notification_metrics[0].metric(
        "Queued messages",
        sum(item["status"] == "Queued" for item in notification_rows),
    )
    notification_metrics[1].metric(
        "Sent messages",
        sum(str(item["status"]).startswith("Sent") for item in notification_rows),
    )
    notification_metrics[2].metric(
        "Pending reminders",
        sum(item["status"] == "Pending" for item in reminder_rows),
    )
    outbox_tab, schedule_tab = st.tabs(["Outbox", "Reminder schedule"])
    with outbox_tab:
        col1, col2, spacer = st.columns([1, 1, 3])
        if col1.button(
            "Run reminder engine", type="primary", icon=":material/play_arrow:"
        ):
            created = run_reminder_engine()
            st.success(f"Reminder engine queued {created} notification(s).")
            st.rerun()
        if col2.button("Send queued (demo)", icon=":material/send:"):
            sent = send_all_queued()
            st.success(f"{sent} notification(s) marked as sent in demo mode.")
            st.rerun()
        notifications = notification_rows
        if not notifications:
            st.info("The outbox is empty.")
        for notification in notifications:
            status_class = "green" if notification["status"].startswith("Sent") else "gray"
            with st.expander(
                f"{notification['subject']}  ·  {notification['recipient_email']}"
            ):
                st.markdown(
                    f'<span class="pill {status_class}">{html.escape(str(notification["status"]))}</span>'
                    f'<span class="pill gray">{html.escape(str(notification["channel"]))}</span>',
                    unsafe_allow_html=True,
                )
                st.text(notification["message"])
                if notification["status"] == "Queued" and st.button(
                    "Mark sent", key=f"send_{notification['id']}", icon=":material/done:"
                ):
                    mark_notification_sent(notification["id"])
                    st.rerun()
    with schedule_tab:
        reminders = reminder_rows
        if not reminders:
            st.info("No reminders scheduled yet.")
        else:
            reminder_df = pd.DataFrame(reminders)
            reminder_df["scheduled_for"] = pd.to_datetime(
                reminder_df["scheduled_for"]
            ).dt.strftime("%d %b %Y, %I:%M %p")
            reminder_df["context"] = reminder_df["task"].fillna(
                reminder_df["meeting_title"]
            )
            st.dataframe(
                reminder_df[
                    [
                        "kind",
                        "context",
                        "recipient_email",
                        "label",
                        "scheduled_for",
                        "status",
                    ]
                ],
                width="stretch",
                hide_index=True,
                column_config={
                    "kind": "Type",
                    "context": "Meeting / action",
                    "recipient_email": "Recipient",
                    "label": "Trigger",
                    "scheduled_for": "Scheduled for",
                    "status": "Status",
                },
            )


elif page == "Integrations":
    page_header(
        "Deployment readiness",
        "Integrations",
        "The prototype runs locally today and switches to organizational services as access is granted.",
    )
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.subheader("Connection status")
        azure_status = "Connected" if azure_is_configured() else "Demo fallback"
        graph_configured = bool(os.getenv("MS_GRAPH_CLIENT_ID"))
        graph_status = "Configured" if graph_configured else "Awaiting access"
        st.markdown(
            f"""
            <div class="surface">
                <div class="integration"><div><strong>Azure OpenAI</strong><span>Summary, MOM, decisions, actions, and risks</span></div><span class="pill {'green' if azure_is_configured() else 'gray'}">{azure_status}</span></div>
                <div class="integration"><div><strong>Microsoft Graph</strong><span>Calendar, participants, and meeting metadata</span></div><span class="pill {'green' if graph_configured else 'gray'}">{graph_status}</span></div>
                <div class="integration"><div><strong>Microsoft Teams</strong><span>Meeting join, messages, and channel distribution</span></div><span class="pill gray">Awaiting access</span></div>
                <div class="integration"><div><strong>Email delivery</strong><span>Reminder and follow-up delivery</span></div><span class="pill gray">Outbox simulation</span></div>
                <div class="integration"><div><strong>Local database</strong><span>Meetings, intelligence, actions, and audit state</span></div><span class="pill green">Active</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.subheader("Privacy controls")
        st.markdown(
            """
            <div class="surface">
                <strong>Assistant not added</strong><br><span class="meta">Calendar reminders only. No join, transcript, or AI processing.</span><br><br>
                <strong>Assistant added</strong><br><span class="meta">Transcript intelligence is enabled for that meeting. Organizer approval is required before distribution.</span><br><br>
                <strong>Data handling</strong><br><span class="meta">This prototype stores data locally. Production retention and deletion policies should follow organizational policy.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.subheader("Access needed for production")
        st.write("Microsoft Entra app registration and approved Graph permissions")
        st.write("Teams application and meeting bot approval")
        st.write("Azure OpenAI endpoint, deployment, and key")
        st.write("Approved email or Graph notification sender")
