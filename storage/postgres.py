"""Factory functions for Agno Postgres database instances."""

import asyncio

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
    """Async: create tables for every agent and for synthesis."""
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
