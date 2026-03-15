"""Agent layer: domain agents, team orchestrator, and synthesis."""

from agents.domain_agents import AGENT_DOMAIN_MAP, ALL_AGENTS
from agents.orchestrator import run_team
from agents.synthesis import synthesize

__all__ = ["ALL_AGENTS", "AGENT_DOMAIN_MAP", "run_team", "synthesize"]
