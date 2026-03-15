"""Pydantic data models for intelligence findings and reports."""

from typing import List, Optional

from pydantic import BaseModel


class Finding(BaseModel):
    """A single intelligence finding from a domain agent."""

    domain: str
    fact: str
    interpretation: str
    source_url: str
    source_label: Optional[str] = None


class IntelReport(BaseModel):
    """Structured intelligence report produced by the synthesis agent."""

    query: str
    product: str
    findings: List[Finding]
    summary: str
    recommended_actions: List[str]


class SynthesisOutput(BaseModel):
    """Structured output schema for the synthesis agent."""

    summary: str
    top_findings: List[Finding]
    recommended_actions: List[str]
