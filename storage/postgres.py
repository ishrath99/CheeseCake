"""Factory functions for Agno Postgres database instances."""

import asyncio
import re

from agno.db.base import SessionType
from agno.db.postgres import AsyncPostgresDb

from core.config import POSTGRES_URL

# All agent slugs — must match domain_agents.py AGENT_CONFIGS slugs
_AGENT_SLUGS = ["market", "competitive", "winloss", "pricing", "positioning", "adjacent"]


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
    """Create all required Postgres tables. Safe to call multiple times."""
    asyncio.run(_create_all_tables())


def _extract_query(run) -> str:
    """Pull the original user query out of a session run's input."""
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
        result.append(
            {
                "session_id": s.session_id,
                "query": query,
                "created_at": s.created_at,
            }
        )
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


def delete_session(session_id: str) -> None:
    """Delete a session from all agent and synthesis tables."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_delete_session_async(session_id))
    finally:
        loop.close()
