"""Parallel agent dispatch via ThreadPoolExecutor."""

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.domain_agents import ALL_AGENTS, make_domain_agent
from core.config import make_firecrawl_mcp, make_meta_ads_mcp

logger = logging.getLogger(__name__)


def _extract_content(response) -> str:
    """Pull the text content string out of an Agno RunResponse."""
    if hasattr(response, "content") and isinstance(response.content, str):
        return response.content
    return str(response)


def _parse_findings(content: str) -> list[dict]:
    """Extract and parse the JSON array from the agent's response text."""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []


async def _run_agent_async(config: dict, query: str, session_id: str) -> dict:
    """Async core: opens MCP tool contexts, builds agent, runs query."""
    if config.get("use_meta_ads"):
        async with make_firecrawl_mcp() as firecrawl, make_meta_ads_mcp() as meta_ads:
            tools: list = [firecrawl, meta_ads]
            # Phase 2: inject search_reddit here when use_reddit=True
            agent = make_domain_agent(config, tools)
            response = await agent.arun(query, session_id=session_id)
    else:
        async with make_firecrawl_mcp() as firecrawl:
            tools = [firecrawl]
            # Phase 2: inject search_reddit here when use_reddit=True
            agent = make_domain_agent(config, tools)
            response = await agent.arun(query, session_id=session_id)

    content = _extract_content(response)
    findings = _parse_findings(content)
    return {
        "agent": config["name"],
        "domain": config["domain"],
        "findings": findings,
        "error": None,
    }


def run_agent(config: dict, query: str, session_id: str) -> dict:
    """Run a single domain agent in its own event loop (safe for threads).

    All exceptions are caught and surfaced in the returned error field.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_agent_async(config, query, session_id))
        finally:
            loop.close()
    except Exception as e:
        logger.error("Agent %s failed: %s", config["name"], e)
        return {
            "agent": config["name"],
            "domain": config["domain"],
            "findings": [],
            "error": str(e),
        }


def run_all_agents(query: str, session_id: str) -> list[dict]:
    """Dispatch all 6 domain agents in parallel and collect results."""
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(run_agent, config, query, session_id): config
            for config in ALL_AGENTS
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results
