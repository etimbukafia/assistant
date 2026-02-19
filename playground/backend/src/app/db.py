"""Playground database session utilities."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.data.models import Base

DB_PATH = Path(__file__).resolve().parents[3] / "playground.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_contacts_schema()


def _migrate_contacts_schema() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    conn = engine.raw_connection()
    try:
        conn.row_factory = None
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(contacts)")
        cols = cur.fetchall()
        if not cols:
            return

        email_nullable = True
        for col in cols:
            if col[1] == "email":
                email_nullable = col[3] == 0

        cur.execute("PRAGMA index_list(contacts)")
        indexes = cur.fetchall()
        name_unique = False
        for idx in indexes:
            if idx[2] != 1:
                continue
            idx_name = idx[1]
            cur.execute(f"PRAGMA index_info({idx_name})")
            parts = [row[2] for row in cur.fetchall()]
            if parts == ["user_id", "name"]:
                name_unique = True

        if email_nullable and not name_unique:
            return

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              name TEXT NOT NULL COLLATE NOCASE,
              email TEXT COLLATE NOCASE,
              role TEXT,
              organization TEXT,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            INSERT INTO contacts_new (id, user_id, name, email, role, organization, notes, created_at, updated_at)
            SELECT id, user_id, name, email, role, organization, notes, created_at, updated_at FROM contacts
            """
        )
        cur.execute("DROP TABLE contacts")
        cur.execute("ALTER TABLE contacts_new RENAME TO contacts")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_user_email ON contacts(user_id, email) WHERE email IS NOT NULL"
        )
        conn.commit()
    finally:
        conn.close()


def migrate_context_entries_entity_type() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    conn = engine.raw_connection()
    try:
        conn.row_factory = None
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='context_entries'")
        if not cur.fetchone():
            return

        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='context_entries'")
        row = cur.fetchone()
        table_sql = (row[0] or "") if row else ""

        cur.execute("PRAGMA table_info(context_entries)")
        cols = [r[1] for r in cur.fetchall() if r and r[1]]

        cur.execute("SELECT DISTINCT entity_type FROM context_entries")
        types = {r[0] for r in cur.fetchall() if r and r[0]}

        needs_migration = (
            ("executive" not in table_sql)
            or ("assistant" not in table_sql)
            or ("global" in types)
            or ("status" not in cols)
            or ("expires_at" not in cols)
        )
        if not needs_migration:
            return

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS context_entries_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              type TEXT NOT NULL,
              content TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              importance_level TEXT NOT NULL,
              status TEXT NOT NULL,
              expires_at TEXT,
              CONSTRAINT ck_context_entries_type CHECK (type IN ('decision','commitment','preferences','insight','relationships')),
              CONSTRAINT ck_context_entries_entity_type CHECK (entity_type IN ('assistant','contact','thread','message','event','executive')),
              CONSTRAINT ck_context_entries_created_by CHECK (created_by IN ('Teeks','You')),
              CONSTRAINT ck_context_entries_importance_level CHECK (importance_level IN ('low','normal','high')),
              CONSTRAINT ck_context_entries_status CHECK (status IN ('active','resolved','stale','archived'))
            )
            """
        )
        status_col = "status" if "status" in cols else "'active'"
        expires_col = "expires_at" if "expires_at" in cols else "NULL"
        cur.execute(
            f"""
            INSERT INTO context_entries_new (
              id, user_id, type, content, entity_type, entity_id, created_by, created_at, importance_level, status, expires_at
            )
            SELECT
              id,
              user_id,
              type,
              content,
              CASE WHEN entity_type = 'global' THEN 'executive' ELSE entity_type END,
              entity_id,
              created_by,
              created_at,
              importance_level,
              {status_col},
              {expires_col}
            FROM context_entries
            """
        )
        cur.execute("DROP TABLE context_entries")
        cur.execute("ALTER TABLE context_entries_new RENAME TO context_entries")
        conn.commit()
    finally:
        conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    migrate_context_entries_entity_type()
