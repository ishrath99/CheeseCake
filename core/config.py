"""Environment configuration, constants, and MCP tool factories."""

import logging
import os

from agno.tools.mcp import MCPTools
from mcp.client.stdio import StdioServerParameters

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = [
    "GOOGLE_API_KEY",
    "FIRECRAWL_API_KEY",
    "APIFY_API_TOKEN",
    "POSTGRES_URL",
]

# Phase 2 keys — not required in Phase 1
_PHASE2_KEYS = [
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USERNAME",
    "REDDIT_PASSWORD",
]

POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql+psycopg://ai:ai@localhost:5532/ai")
GEMINI_MODEL_ID: str = os.getenv("GEMINI_MODEL_ID", "gemini-3-flash-preview")


def validate_env() -> None:
    """Raise ValueError for any missing required environment variable."""
    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def make_firecrawl_mcp() -> MCPTools:
    """Return a fresh MCPTools instance for the Firecrawl MCP server."""
    return MCPTools(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "firecrawl-mcp"],
            env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "")},
        ),
    )


def make_meta_ads_mcp() -> MCPTools:
    """Return a fresh MCPTools instance for the Apify Facebook Ad Library scraper."""
    token = os.getenv("APIFY_API_TOKEN", "")
    return MCPTools(
        server_params=StdioServerParameters(
            command="npx",
            args=[
                "mcp-remote",
                "https://mcp.apify.com/?tools=igolaizola/facebook-ad-library-scraper",
                "--header",
                f"Authorization: Bearer {token}",
            ],
        ),
    )
