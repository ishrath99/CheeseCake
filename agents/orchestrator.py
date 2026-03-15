"""Team orchestration: build Intelligence Team, run query, parse per-agent findings."""

import asyncio
import json
import logging
import re

from agents.domain_agents import AGENT_DOMAIN_MAP
from agents.team import build_intelligence_team

logger = logging.getLogger(__name__)

# Ordered list of all possible agent names for skipped-agent computation
_ALL_AGENT_NAMES: list[str] = list(AGENT_DOMAIN_MAP.keys())


def _parse_findings(content) -> list[dict]:
    """Extract a JSON array of findings from an agent's response content."""
    if not isinstance(content, str):
        content = json.dumps(content) if content else ""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []


async def _arun_team(query: str, session_id: str) -> list[dict]:
    """Build and run the Intelligence Team; return per-agent result dicts."""
    team = build_intelligence_team()
    team_output = await team.arun(query, session_id=session_id)

    results: list[dict] = []
    for member_resp in team_output.member_responses or []:
        agent_name = getattr(member_resp, "agent_name", None) or "Unknown"
        content = member_resp.content
        if not isinstance(content, str):
            content = str(content) if content else ""
        findings = _parse_findings(content)
        results.append(
            {
                "agent": agent_name,
                "domain": AGENT_DOMAIN_MAP.get(agent_name, agent_name),
                "findings": findings,
                "error": None,
            }
        )
    return results


def run_team(query: str, session_id: str) -> tuple[list[dict], list[str], list[str]]:
    """Run the Intelligence Team for a query.

    Returns (agent_results, used_agent_names, skipped_agent_names).
    agent_results follows the same schema as before: list of dicts with
    keys agent, domain, findings, error.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(_arun_team(query, session_id))
    except Exception as e:
        logger.error("IntelligenceTeam run failed: %s", e)
        results = []
    finally:
        loop.close()

    used_names = [r["agent"] for r in results]
    skipped_names = [n for n in _ALL_AGENT_NAMES if n not in used_names]
    return results, used_names, skipped_names
