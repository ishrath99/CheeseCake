"""Domain agent configurations and factory function."""

import os

from agno.agent import Agent
from agno.models.google import Gemini

from storage.postgres import get_agent_db

# Prefer search (returns snippets) over scrape (returns full pages).
# Hard cap: 3 tool calls per agent run to limit token consumption.
_J = 'JSON array of 2-3 objects: [{"fact":"...","interpretation":"...","source_url":"<exact URL>"}]. source_url is required — never omit it.'
_SEARCH_HINT = "Use search tools only, not scrape. Maximum 3 searches."

AGENT_CONFIGS: list[dict] = [
    {
        "name": "MarketTrendsAgent",
        "domain": "Market & Trends",
        "slug": "market",
        "use_meta_ads": False,
        "use_reddit": False,
        "system_prompt": f"Market intelligence: find market size, funding, job trends. {_SEARCH_HINT} Return {_J}",
    },
    {
        "name": "CompetitiveAgent",
        "domain": "Competitive Intel",
        "slug": "competitive",
        "use_meta_ads": True,
        "use_reddit": False,
        "system_prompt": f"Competitive intel: find competitor features, ads, messaging. {_SEARCH_HINT} Return {_J}",
    },
    {
        "name": "WinLossAgent",
        "domain": "Win / Loss",
        "slug": "winloss",
        "use_meta_ads": False,
        "use_reddit": False,  # Phase 2: set True to enable Reddit
        "system_prompt": f"Win/loss: search G2, Capterra, Trustpilot for buyer complaints and switching reasons. {_SEARCH_HINT} Return {_J}",
    },
    {
        "name": "PricingAgent",
        "domain": "Pricing Intel",
        "slug": "pricing",
        "use_meta_ads": False,
        "use_reddit": False,
        "system_prompt": f"Pricing intel: search competitor pricing for packaging changes and WTP signals. {_SEARCH_HINT} Return {_J}",
    },
    {
        "name": "PositioningAgent",
        "domain": "Positioning",
        "slug": "positioning",
        "use_meta_ads": True,
        "use_reddit": False,
        "system_prompt": f"Positioning: search taglines, ad copy, landing pages for messaging gaps. {_SEARCH_HINT} Return {_J}",
    },
    {
        "name": "AdjacentMarketsAgent",
        "domain": "Adjacent Markets",
        "slug": "adjacent",
        "use_meta_ads": False,
        "use_reddit": False,
        "system_prompt": f"Adjacent markets: search for platform expansions and category collision signals. {_SEARCH_HINT} Return {_J}",
    },
]


def _is_enabled(slug: str) -> bool:
    """Check AGENT_<SLUG>=false to disable; enabled by default."""
    return os.getenv(f"AGENT_{slug.upper()}", "true").strip().lower() != "false"


AGENT_DOMAIN_MAP: dict[str, str] = {c["name"]: c["domain"] for c in AGENT_CONFIGS}

# Only includes agents not explicitly disabled via env vars.
ALL_AGENTS: list[dict] = [c for c in AGENT_CONFIGS if _is_enabled(c["slug"])]


def make_domain_agent(config: dict, tools: list) -> Agent:
    """Instantiate a domain Agent with the given tools and session storage."""
    return Agent(
        name=config["name"],
        model=Gemini(id="gemini-3-flash-preview"),
        tools=tools,
        tool_call_limit=3,
        compress_tool_results=True,
        db=get_agent_db(f"sessions_{config['slug']}"),
        add_history_to_context=True,
        num_history_runs=3,
        instructions=[config["system_prompt"]],
        debug_mode=True,
    )
