"""Seed the playground SQLite database with demo EA Diary data.

Idempotent by default: it records a seed version in `seed_meta` and will no-op
on subsequent runs.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


SEED_VERSION = "v2"
DEFAULT_USERS = ["ea_demo", "ea_demo_2"]


@dataclass(frozen=True)
class ContactSeed:
    user_id: str
    name: str
    email: Optional[str]
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class EntityRefSeed:
    user_id: str
    entity_type: str  # thread|event|message
    display_name: str
    ref: str
    notes: Optional[str] = None


@dataclass(frozen=True)
class ContextEntrySeed:
    user_id: str
    type: str  # decision|commitment|preferences|insight|relationships
    content: str
    entity_type: str  # contact|thread|message|event|global
    entity_id: Optional[str]
    created_by: str  # Teeks|You
    importance_level: str  # low|normal|high


@dataclass(frozen=True)
class InboxThreadSeed:
    user_id: str
    thread_id: str
    subject: str
    snippet: str
    last_sender: str
    unread_count: int
    status: str


@dataclass(frozen=True)
class InboxMessageSeed:
    user_id: str
    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: str
    body_preview: str
    direction: str
    needs_reply: int


@dataclass(frozen=True)
class CalendarEventSeed:
    user_id: str
    event_id: str
    subject: str
    description: str
    location: str
    attendees: str
    status: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seed_meta (
          version TEXT PRIMARY KEY,
          seeded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS context_entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          type TEXT NOT NULL CHECK (type IN ('decision','commitment','preferences','insight','relationships')),
          content TEXT NOT NULL,
          entity_type TEXT NOT NULL CHECK (entity_type IN ('contact','thread','message','event','global')),
          entity_id TEXT,
          created_by TEXT NOT NULL CHECK (created_by IN ('Teeks','You')),
          created_at TEXT NOT NULL,
          importance_level TEXT NOT NULL DEFAULT 'normal' CHECK (importance_level IN ('low','normal','high'))
        );

        CREATE TABLE IF NOT EXISTS contacts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          name TEXT NOT NULL COLLATE NOCASE,
          email TEXT COLLATE NOCASE,
          role TEXT,
          organization TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CONSTRAINT uq_contacts_user_email UNIQUE (user_id, email)
        );

        CREATE TABLE IF NOT EXISTS entity_references (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          entity_type TEXT NOT NULL CHECK (entity_type IN ('thread','message','event')),
          display_name TEXT NOT NULL COLLATE NOCASE,
          ref TEXT NOT NULL,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CONSTRAINT uq_entity_refs_user_type_name UNIQUE (user_id, entity_type, display_name),
          CONSTRAINT uq_entity_refs_user_type_ref UNIQUE (user_id, entity_type, ref)
        );

        CREATE TABLE IF NOT EXISTS inbox_threads (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          subject TEXT NOT NULL,
          snippet TEXT,
          last_sender TEXT,
          last_received_at TEXT NOT NULL,
          unread_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','waiting','closed')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CONSTRAINT uq_inbox_threads_user_thread UNIQUE (user_id, thread_id)
        );

        CREATE TABLE IF NOT EXISTS inbox_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          message_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          subject TEXT NOT NULL,
          sender TEXT NOT NULL,
          recipients TEXT,
          body_preview TEXT,
          sent_at TEXT NOT NULL,
          direction TEXT NOT NULL DEFAULT 'inbound' CHECK (direction IN ('inbound','outbound','draft')),
          needs_reply INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CONSTRAINT uq_inbox_messages_user_message UNIQUE (user_id, message_id)
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          subject TEXT NOT NULL,
          description TEXT,
          location TEXT,
          attendees TEXT,
          start_at TEXT NOT NULL,
          end_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','tentative','cancelled')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CONSTRAINT uq_calendar_events_user_event UNIQUE (user_id, event_id)
        );
        """
    )


def already_seeded(conn: sqlite3.Connection, version: str) -> bool:
    row = conn.execute("SELECT version FROM seed_meta WHERE version = ?", (version,)).fetchone()
    return row is not None


def mark_seeded(conn: sqlite3.Connection, version: str) -> None:
    conn.execute(
        "INSERT INTO seed_meta(version, seeded_at) VALUES (?, ?)",
        (version, utc_now_iso()),
    )


def upsert_contacts(conn: sqlite3.Connection, contacts: Sequence[ContactSeed]) -> None:
    now = utc_now_iso()
    rows = [
        (
            c.user_id,
            c.name.strip(),
            c.email.strip().lower() if c.email else None,
            (c.role or "").strip() or None,
            (c.organization or "").strip() or None,
            (c.notes or "").strip() or None,
            now,
            now,
        )
        for c in contacts
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO contacts(
          user_id, name, email, role, organization, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def upsert_entity_refs(conn: sqlite3.Connection, refs: Sequence[EntityRefSeed]) -> None:
    now = utc_now_iso()
    rows = [
        (
            e.user_id,
            e.entity_type.strip(),
            e.display_name.strip(),
            e.ref.strip(),
            (e.notes or "").strip() or None,
            now,
            now,
        )
        for e in refs
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO entity_references(
          user_id, entity_type, display_name, ref, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def insert_context_entries(conn: sqlite3.Connection, entries: Sequence[ContextEntrySeed]) -> None:
    now = utc_now_iso()
    for e in entries:
        entity_id = e.entity_id.strip() if isinstance(e.entity_id, str) else None
        exists = conn.execute(
            """
            SELECT 1 FROM context_entries
            WHERE user_id = ? AND type = ? AND content = ? AND entity_type = ? AND COALESCE(entity_id, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (
                e.user_id,
                e.type.strip(),
                e.content.strip(),
                e.entity_type.strip(),
                entity_id,
            ),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO context_entries(
              user_id, type, content, entity_type, entity_id, created_by, created_at, importance_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e.user_id,
                e.type.strip(),
                e.content.strip(),
                e.entity_type.strip(),
                entity_id,
                e.created_by.strip(),
                now,
                e.importance_level.strip(),
            ),
        )


def upsert_inbox_threads(conn: sqlite3.Connection, threads: Sequence[InboxThreadSeed]) -> None:
    now = utc_now_iso()
    rows = [
        (
            t.user_id,
            t.thread_id.strip(),
            t.subject.strip(),
            t.snippet.strip(),
            t.last_sender.strip(),
            now,
            t.unread_count,
            t.status.strip(),
            now,
            now,
        )
        for t in threads
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO inbox_threads(
          user_id, thread_id, subject, snippet, last_sender, last_received_at, unread_count, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def upsert_inbox_messages(conn: sqlite3.Connection, messages: Sequence[InboxMessageSeed]) -> None:
    now = utc_now_iso()
    rows = [
        (
            m.user_id,
            m.message_id.strip(),
            m.thread_id.strip(),
            m.subject.strip(),
            m.sender.strip(),
            m.recipients.strip(),
            m.body_preview.strip(),
            now,
            m.direction.strip(),
            m.needs_reply,
            now,
            now,
        )
        for m in messages
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO inbox_messages(
          user_id, message_id, thread_id, subject, sender, recipients, body_preview, sent_at, direction, needs_reply, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def upsert_calendar_events(conn: sqlite3.Connection, events: Sequence[CalendarEventSeed]) -> None:
    now = utc_now_iso()
    rows = [
        (
            e.user_id,
            e.event_id.strip(),
            e.subject.strip(),
            e.description.strip(),
            e.location.strip(),
            e.attendees.strip(),
            now,
            now,
            e.status.strip(),
            now,
            now,
        )
        for e in events
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO calendar_events(
          user_id, event_id, subject, description, location, attendees, start_at, end_at, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def build_seed_data(
    users: Sequence[str],
) -> Tuple[
    List[ContactSeed],
    List[EntityRefSeed],
    List[ContextEntrySeed],
    List[InboxThreadSeed],
    List[InboxMessageSeed],
    List[CalendarEventSeed],
]:
    u1 = users[0] if users else "ea_demo"
    u2 = users[1] if len(users) > 1 else "ea_demo_2"

    contacts = [
        ContactSeed(u1, "Alex Chen", "alex@northbridge.io", role="Founder", organization="Northbridge", notes="Seed contact"),
        ContactSeed(u1, "Sarah Kim", "sarah@finco.com", role="Finance lead", organization="FinCo", notes="Budget owner"),
        ContactSeed(u1, "John Patel", "john@counsel.com", role="Legal counsel", organization="Counsel LLP", notes="Contract reviews"),
        ContactSeed(u1, "Maya Lopez", "maya@acme.com", role="Chief of Staff", organization="Acme", notes="Exec partner"),
        ContactSeed(u2, "Priya Shah", "priya@investors.com", role="Partner", organization="Investors & Co", notes="Investor contact"),
    ]

    refs = [
        EntityRefSeed(u1, "thread", "Q3 Budget - Sarah", "thr_q3_budget_sarah", notes="Seed thread"),
        EntityRefSeed(u1, "thread", "Alex follow-up", "thr_alex_followup", notes="Seed thread"),
        EntityRefSeed(u1, "event", "Board Sync", "evt_board_sync_2026_02_28", notes="Seed event"),
        EntityRefSeed(u1, "event", "Budget Review", "evt_budget_review_2026_03_04", notes="Seed event"),
        EntityRefSeed(u1, "message", "John contract follow-up", "msg_contract_followup_2026_02_10", notes="Seed message"),
        EntityRefSeed(u2, "event", "Investor Update", "evt_investor_update_2026_03_06", notes="Seed event"),
    ]

    entries = [
        # Global preferences/profile
        ContextEntrySeed(u1, "preferences", "[seed] Keep outputs short; lead with next action.", "global", None, "Teeks", "high"),
        ContextEntrySeed(u1, "preferences", "[seed] No meetings before 9:30am unless urgent.", "global", None, "Teeks", "high"),
        ContextEntrySeed(u1, "preferences", "[seed] Drafting tone: calm, direct, no fluff.", "global", None, "Teeks", "normal"),
        # Contact-scoped
        ContextEntrySeed(u1, "relationships", "[seed] Alex prefers async updates; hates long email threads.", "contact", "alex@northbridge.io", "Teeks", "normal"),
        ContextEntrySeed(u1, "preferences", "[seed] Sarah likes tables + clear numbers.", "contact", "sarah@finco.com", "Teeks", "normal"),
        ContextEntrySeed(u1, "insight", "[seed] John is slow to respond on Fridays; ping Tue/Wed.", "contact", "john@counsel.com", "Teeks", "low"),
        # Thread-scoped
        ContextEntrySeed(u1, "decision", "[seed] We will cap Q3 discretionary spend at $120k.", "thread", "thr_q3_budget_sarah", "Teeks", "high"),
        ContextEntrySeed(u1, "commitment", "[seed] Sarah to send revised forecast by Thursday EOD.", "thread", "thr_q3_budget_sarah", "Teeks", "high"),
        ContextEntrySeed(u1, "insight", "[seed] Risk: hiring plan assumes pipeline conversion >30%.", "thread", "thr_q3_budget_sarah", "Teeks", "normal"),
        # Event-scoped
        ContextEntrySeed(u1, "decision", "[seed] Board Sync agenda: runway, hiring, key risks.", "event", "evt_board_sync_2026_02_28", "Teeks", "normal"),
        ContextEntrySeed(u1, "commitment", "[seed] Send board deck 24h before meeting.", "event", "evt_board_sync_2026_02_28", "Teeks", "high"),
        # Message-scoped
        ContextEntrySeed(u1, "commitment", "[seed] John to redline section 7 (indemnity) today.", "message", "msg_contract_followup_2026_02_10", "Teeks", "normal"),
        # Second user
        ContextEntrySeed(u2, "preferences", "[seed] Scheduling: batch calls Tue/Thu afternoons.", "global", None, "Teeks", "normal"),
        ContextEntrySeed(u2, "relationships", "[seed] Priya prefers 2-sentence updates + numbers.", "contact", "priya@investors.com", "Teeks", "normal"),
        ContextEntrySeed(u2, "decision", "[seed] Investor Update: focus on progress + specific asks.", "event", "evt_investor_update_2026_03_06", "Teeks", "normal"),
    ]

    threads = [
        InboxThreadSeed(u1, "thr_q3_budget_sarah", "Q3 Budget - Sarah", "Need final headcount assumptions before close.", "sarah@finco.com", 2, "open"),
        InboxThreadSeed(u1, "thr_alex_followup", "Alex follow-up", "Can we move sync to afternoon?", "alex@northbridge.io", 1, "waiting"),
        InboxThreadSeed(u1, "thr_contract_john", "Vendor contract redlines", "Updated indemnity language attached.", "john@counsel.com", 0, "open"),
        InboxThreadSeed(u2, "thr_investor_update", "Investor update prep", "Need latest KPI snapshot.", "priya@investors.com", 1, "open"),
    ]

    messages = [
        InboxMessageSeed(u1, "msg_q3_sarah_01", "thr_q3_budget_sarah", "Q3 Budget - Sarah", "sarah@finco.com", "ea_demo@teeks.ai", "Can you confirm discretionary cap for Q3?", "inbound", 1),
        InboxMessageSeed(u1, "msg_q3_you_02", "thr_q3_budget_sarah", "Q3 Budget - Sarah", "ea_demo@teeks.ai", "sarah@finco.com", "Confirmed: keep spend at 120k pending board signoff.", "outbound", 0),
        InboxMessageSeed(u1, "msg_alex_01", "thr_alex_followup", "Alex follow-up", "alex@northbridge.io", "ea_demo@teeks.ai", "I prefer async unless urgent; can we skip tomorrow's call?", "inbound", 1),
        InboxMessageSeed(u1, "msg_contract_followup_2026_02_10", "thr_contract_john", "Vendor contract redlines", "john@counsel.com", "ea_demo@teeks.ai", "Section 7 redline complete. Please review before EOD.", "inbound", 1),
        InboxMessageSeed(u2, "msg_investor_01", "thr_investor_update", "Investor update prep", "priya@investors.com", "ea_demo_2@teeks.ai", "Send two bullets and metrics only.", "inbound", 1),
    ]

    events = [
        CalendarEventSeed(u1, "evt_board_sync_2026_02_28", "Board Sync", "Monthly board update and risk review.", "Zoom", "alex@northbridge.io,sarah@finco.com,maya@acme.com", "confirmed"),
        CalendarEventSeed(u1, "evt_budget_review_2026_03_04", "Budget Review", "Finalize Q3 plan and hiring constraints.", "Conference Room A", "sarah@finco.com,maya@acme.com", "confirmed"),
        CalendarEventSeed(u1, "evt_vendor_legal_2026_03_02", "Vendor Legal Review", "Contract redlines with counsel.", "Zoom", "john@counsel.com", "tentative"),
        CalendarEventSeed(u2, "evt_investor_update_2026_03_06", "Investor Update", "Progress update and asks.", "Zoom", "priya@investors.com", "confirmed"),
    ]

    return contacts, refs, entries, threads, messages, events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[1] / "playground.db"),
        help="Path to playground.db",
    )
    parser.add_argument(
        "--users",
        nargs="*",
        default=DEFAULT_USERS,
        help="User IDs to seed (default: ea_demo ea_demo_2)",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    try:
        ensure_schema(conn)
        if already_seeded(conn, SEED_VERSION):
            print(f"Seed already applied ({SEED_VERSION}). No changes.")
            return 0

        contacts, refs, entries, threads, messages, events = build_seed_data(args.users)
        with conn:
            upsert_contacts(conn, contacts)
            upsert_entity_refs(conn, refs)
            insert_context_entries(conn, entries)
            upsert_inbox_threads(conn, threads)
            upsert_inbox_messages(conn, messages)
            upsert_calendar_events(conn, events)
            mark_seeded(conn, SEED_VERSION)

        print(
            f"Seeded {db_path} with {len(contacts)} contacts, {len(refs)} refs, {len(entries)} entries, "
            f"{len(threads)} threads, {len(messages)} messages, {len(events)} events."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
