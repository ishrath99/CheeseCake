"""Synthesis agent: full intelligence runs and conversational follow-ups."""

import asyncio
import json
import logging
import re

from agno.agent import Agent
from agno.memory import MemoryManager
from agno.models.google import Gemini

from core.config import GEMINI_MODEL_ID
from core.models import SynthesisOutput
from storage.postgres import get_synthesis_db

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a strategic analyst. "
    "For full intelligence requests (those that include a Findings JSON block): "
    "deduplicate and rank the top 5 findings, write a 3-sentence executive summary, "
    "and produce 3 specific actionable recommendations. "
    "Each finding must preserve the exact domain, fact, interpretation, and source_url "
    "copied verbatim — never invent or modify URLs. "
    "Respond ONLY with valid JSON, no prose, no markdown fences:\n"
    '{"summary": "...", '
    '"top_findings": [{"domain": "...", "fact": "...", "interpretation": "...", "source_url": "..."}], '
    '"recommended_actions": ["...", "...", "..."]}\n'
    "For follow-up questions (no Findings block), answer concisely in plain text."
)

# Shared agent id so both agents below read/write the same Agno session record.
_AGENT_ID = "cheesecake-synthesis"
_db = get_synthesis_db("sessions_synthesis", "memories_synthesis")

# Used for full intelligence runs — enforces SynthesisOutput schema.
synthesis_agent = Agent(
    id=_AGENT_ID,
    name="SynthesisAgent",
    model=Gemini(id=GEMINI_MODEL_ID),
    db=_db,
    memory_manager=MemoryManager(model=Gemini(id=GEMINI_MODEL_ID), db=_db),
    enable_agentic_memory=True,
    add_history_to_context=True,
    num_history_runs=10,
    output_schema=SynthesisOutput,
    instructions=[_SYSTEM_PROMPT],
    debug_mode=True,
)

# Used for conversational follow-ups — same session history, no structured schema.
_chat_agent = Agent(
    id=_AGENT_ID,
    name="SynthesisAgent",
    model=Gemini(id=GEMINI_MODEL_ID),
    db=_db,
    add_history_to_context=True,
    num_history_runs=10,
    instructions=[_SYSTEM_PROMPT],
    debug_mode=True,
)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_prompt(query: str, raw_results: list[dict]) -> str:
    tagged = []
    for result in raw_results:
        domain = result.get("domain", "Unknown")
        for finding in result.get("findings", []):
            tagged.append({**finding, "domain": domain})
    return f"Query: {query}\n\nFindings:\n{json.dumps(tagged, indent=2)}"


def _parse_response(response) -> dict:
    content = response.content

    # Already the right type
    if isinstance(content, SynthesisOutput):
        return content.model_dump()

    # Get a raw value to work with — prefer content, fall back to string
    raw = content if content is not None else response.get_content_as_string()
    logger.debug("Synthesis raw content type=%s value=%s", type(raw).__name__, str(raw)[:300])

    # If it's a string, strip fences and extract JSON object
    if isinstance(raw, str):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip(), flags=re.IGNORECASE)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in synthesis response: {raw[:200]}")
        raw = json.loads(match.group())

    # raw is now a dict — validate against the schema
    if isinstance(raw, dict):
        try:
            return SynthesisOutput.model_validate(raw).model_dump()
        except Exception as ve:
            logger.warning("SynthesisOutput validation failed (%s) — using raw dict", ve)
            # Return what we have if it has the minimum required keys
            if "summary" in raw:
                return raw

    raise ValueError(f"Could not parse synthesis response: {str(raw)[:200]}")


def synthesize(query: str, raw_results: list[dict], session_id: str) -> dict:
    """Full intelligence run — returns a SynthesisOutput-compatible dict."""
    prompt = _build_prompt(query, raw_results)
    try:
        response = _run_async(synthesis_agent.arun(prompt, session_id=session_id))
        return _parse_response(response)
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
    return {"summary": "Synthesis unavailable.", "top_findings": [], "recommended_actions": []}


def chat(message: str, session_id: str) -> str:
    """Conversational follow-up — returns plain text using the session's existing context."""
    try:
        response = _run_async(_chat_agent.arun(message, session_id=session_id))
        return response.get_content_as_string()
    except Exception as e:
        logger.error("Chat failed: %s", e)
        return "Sorry, something went wrong. Please try again."
