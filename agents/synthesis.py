"""Synthesis agent: deduplicates findings and produces structured reports."""

import asyncio
import json
import logging
import re

from agno.agent import Agent
from agno.memory import MemoryManager
from agno.models.google import Gemini

from core.models import SynthesisOutput
from storage.postgres import get_synthesis_db

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Strategic analyst. Deduplicate and rank the top 5 findings from the agent results. "
    "Write a 3-sentence executive summary and 3 actionable recommendations. "
    "Each finding needs: domain, fact, interpretation, confidence (high/medium/low), source_url."
)

_db = get_synthesis_db("sessions_synthesis", "memories_synthesis")

synthesis_agent = Agent(
    name="SynthesisAgent",
    model=Gemini(id="gemini-3-flash-preview"),
    db=_db,
    memory_manager=MemoryManager(model=Gemini(id="gemini-3-flash-preview"), db=_db),
    enable_agentic_memory=True,
    add_history_to_context=True,
    num_history_runs=10,
    output_schema=SynthesisOutput,
    instructions=[_SYSTEM_PROMPT],
    debug_mode=True,
)


def _build_prompt(query: str, raw_results: list[dict]) -> str:
    """Assemble the synthesis prompt from the original query and agent findings."""
    tagged: list[dict] = []
    for result in raw_results:
        domain = result.get("domain", "Unknown")
        for finding in result.get("findings", []):
            tagged.append({**finding, "domain": domain})
    return f"Query: {query}\n\nFindings:\n{json.dumps(tagged, indent=2)}"


def _parse_response(response) -> dict:
    """Extract a SynthesisOutput-compatible dict from an Agno RunOutput."""
    content = response.content

    # Agno may return the parsed Pydantic model directly
    if isinstance(content, SynthesisOutput):
        return content.model_dump()
    if isinstance(content, dict):
        return content

    # Fall back to parsing text content
    text = response.get_content_as_string()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return SynthesisOutput.model_validate(data).model_dump()

    raise ValueError(f"Could not parse synthesis response: {text[:200]}")


def synthesize(query: str, raw_results: list[dict], session_id: str) -> dict:
    """Run the synthesis agent and return a SynthesisOutput-compatible dict."""
    prompt = _build_prompt(query, raw_results)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                synthesis_agent.arun(prompt, session_id=session_id)
            )
        finally:
            loop.close()
        return _parse_response(response)
    except Exception as e:
        logger.error("Synthesis failed: %s", e)

    return {
        "summary": "Synthesis unavailable — check logs for details.",
        "top_findings": [],
        "recommended_actions": [],
    }
