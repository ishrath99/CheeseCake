"""Intelligence Team: Agno Team with 6 domain agents orchestrated by a coordinator."""

from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team, TeamMode  # type: ignore[attr-defined]

from agents.domain_agents import ALL_AGENTS
from core.config import GEMINI_MODEL_ID, make_firecrawl_mcp, make_meta_ads_mcp
from storage.postgres import get_agent_db
from tools.playwright_scraper import scrape_with_playwright

_COORDINATOR_INSTRUCTIONS = [
    "You are the coordinator of a growth intelligence research team.",
    "Analyze the user query and delegate tasks ONLY to the most relevant domain agents.",
    "Do NOT invoke all agents for every query — select 2-5 based on query relevance.",
    "Each invoked agent will return a JSON array of research findings.",
    "Competitive/landscape queries → invoke CompetitiveAgent and PositioningAgent.",
    "Pricing focus → invoke PricingAgent and CompetitiveAgent.",
    "User reviews or feedback → invoke WinLossAgent.",
    "Market size or trends → invoke MarketTrendsAgent and AdjacentMarketsAgent.",
    "Broad 'full analysis' or 'everything' requests → invoke all relevant agents.",
]


def _make_member_agents() -> list:  # list[Agent | Team] at runtime
    """Instantiate one Agent per domain config, each with its own MCPTools instance."""
    members = []
    for config in ALL_AGENTS:
        tools = [make_firecrawl_mcp(), scrape_with_playwright]
        if config.get("use_meta_ads"):
            tools.append(make_meta_ads_mcp())
        agent = Agent(
            name=config["name"],
            role=f"{config['domain']} analyst — {config['system_prompt'][:80]}",
            model=Gemini(id=GEMINI_MODEL_ID),
            tools=tools,
            tool_call_limit=3,
            compress_tool_results=True,
            db=get_agent_db(f"sessions_{config['slug']}"),
            add_history_to_context=True,
            num_history_runs=3,
            instructions=[config["system_prompt"]],
            debug_mode=True,
        )
        members.append(agent)
    return members


def build_intelligence_team() -> Team:
    """Build a fresh Intelligence Team for a single query run.

    Creates a new team (with fresh MCPTools instances) each call so MCP
    subprocess connections are never shared across concurrent queries.
    """
    return Team(
        name="IntelligenceTeam",
        mode=TeamMode.coordinate,
        model=Gemini(id=GEMINI_MODEL_ID),
        members=_make_member_agents(),
        instructions=_COORDINATOR_INSTRUCTIONS,
        show_members_responses=True,
        debug_mode=True,
    )
