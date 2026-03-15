"""Pydantic data models for intelligence findings and reports."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Confidence(str, Enum):
    """Signal confidence level."""

    high = "high"
    medium = "medium"
    low = "low"


class Finding(BaseModel):
    """A single intelligence finding from a domain agent."""

    domain: str
    fact: str
    interpretation: str
    confidence: Confidence
    source_url: Optional[str] = None
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
