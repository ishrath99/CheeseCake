"""Factory functions for Agno Postgres database instances."""

import asyncio
import json
import re

import psycopg
from agno.db.base import SessionType
from agno.db.postgres import AsyncPostgresDb

from core.config import POSTGRES_URL

_AGENT_SLUGS = ["market", "competitive", "winloss", "pricing", "positioning", "adjacent"]

# psycopg needs postgresql:// not postgresql+psycopg://
_SYNC_URL = POSTGRES_URL.replace("postgresql+psycopg://", "postgresql://")


def get_agent_db(session_table: str) -> AsyncPostgresDb:
    """Return an AsyncPostgresDb for agent session persistence."""
    return AsyncPostgresDb(db_url=POSTGRES_URL, session_table=session_table)


def get_synthesis_db(session_table: str, memory_table: str) -> AsyncPostgresDb:
    """Return an AsyncPostgresDb instance with both session and memory tables."""
    return AsyncPostgresDb(
        db_url=POSTGRES_URL,
        session_table=session_table,
        memory_table=memory_table,
    )


# ── Agno tables ──────────────────────────────────────────────────────────────

async def _create_all_tables() -> None:
    for slug in _AGENT_SLUGS:
        db = AsyncPostgresDb(db_url=POSTGRES_URL, session_table=f"sessions_{slug}")
        await db._create_all_tables()
    synthesis_db = AsyncPostgresDb(
        db_url=POSTGRES_URL,
        session_table="sessions_synthesis",
        memory_table="memories_synthesis",
    )
    await synthesis_db._create_all_tables()


def ensure_tables() -> None:
    """Create all required tables (Agno + artifacts). Safe to call multiple times."""
    asyncio.run(_create_all_tables())
    with psycopg.connect(_SYNC_URL) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cheesecake_artifacts (
                session_id TEXT PRIMARY KEY,
                report     JSONB,
                messages   JSONB NOT NULL DEFAULT '[]',
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()


# ── Artifact persistence ──────────────────────────────────────────────────────

def save_artifact(session_id: str, report: dict | None, messages: list) -> None:
    """Upsert the report and message history for a session."""
    with psycopg.connect(_SYNC_URL) as conn:
        conn.execute(
            """
            INSERT INTO cheesecake_artifacts (session_id, report, messages, updated_at)
            VALUES (%s, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (session_id) DO UPDATE SET
                report     = EXCLUDED.report,
                messages   = EXCLUDED.messages,
                updated_at = NOW()
            """,
            (session_id, json.dumps(report), json.dumps(messages)),
        )
        conn.commit()


def load_artifact(session_id: str) -> dict | None:
    """Return {report, messages} for a session, or None if not found."""
    with psycopg.connect(_SYNC_URL) as conn:
        row = conn.execute(
            "SELECT report, messages FROM cheesecake_artifacts WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if row:
        return {"report": row[0], "messages": row[1]}
    return None


# ── Session listing / deletion ────────────────────────────────────────────────

def _extract_query(run) -> str:
    try:
        content = (
            run.input.input_content
            if hasattr(run.input, "input_content")
            else str(run.input)
        )
        m = re.match(r"Query:\s*(.+?)(?:\n|$)", content)
        return m.group(1).strip() if m else content[:80]
    except Exception:
        return "Unknown query"


async def _list_sessions_async(limit: int) -> list[dict]:
    db = AsyncPostgresDb(db_url=POSTGRES_URL, session_table="sessions_synthesis")
    sessions = await db.get_sessions(
        session_type=SessionType.AGENT,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
    )
    result = []
    for s in sessions:
        query = _extract_query(s.runs[0]) if s.runs else "Empty session"
        result.append({"session_id": s.session_id, "query": query, "created_at": s.created_at})
    return result


def list_sessions(limit: int = 50) -> list[dict]:
    """Return sessions from the synthesis table, newest first."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_list_sessions_async(limit))
    except Exception:
        return []
    finally:
        loop.close()


async def _delete_session_async(session_id: str) -> None:
    for slug in _AGENT_SLUGS + ["synthesis"]:
        db = AsyncPostgresDb(db_url=POSTGRES_URL, session_table=f"sessions_{slug}")
        await db.delete_session(session_id)
    with psycopg.connect(_SYNC_URL) as conn:
        conn.execute("DELETE FROM cheesecake_artifacts WHERE session_id = %s", (session_id,))
        conn.commit()


def delete_session(session_id: str) -> None:
    """Delete a session from all agent tables and the artifacts store."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_delete_session_async(session_id))
    finally:
        loop.close()
