"""The diagnosis the model must return, and the API models around it.

``DiagnosisOutput`` is sent to the API as a JSON schema (structured outputs),
so the response always parses into it. Citations are checked separately in
``validation.py``, because a schema cannot know which evidence IDs exist.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["high", "medium", "low"]


class CitedClaim(BaseModel):
    statement: str = Field(description="One factual claim, stated plainly.")
    evidence_ids: list[str] = Field(description="IDs of the evidence supporting the claim.")


class RootCause(BaseModel):
    statement: str = Field(description="The most likely root cause.")
    service: str | None = Field(description="Service where the cause lies, if one.")
    confidence: Confidence
    evidence_ids: list[str]


class TimelineEntry(BaseModel):
    time: str = Field(description="ISO 8601 timestamp taken from the evidence.")
    event: str
    evidence_ids: list[str]


class RecommendedAction(BaseModel):
    action: str
    rationale: str
    evidence_ids: list[str]


class DiagnosisOutput(BaseModel):
    summary: str = Field(description="Two or three sentences for an on-call engineer.")
    root_cause: RootCause | None = Field(
        description="Null when the evidence does not support any root cause."
    )
    contributing_factors: list[CitedClaim]
    timeline: list[TimelineEntry] = Field(description="Ordered by time.")
    ruled_out: list[CitedClaim] = Field(description="Plausible causes the evidence argues against.")
    unknowns: list[str] = Field(
        description="Open questions and evidence that is missing or would change the conclusion."
    )
    recommended_actions: list[RecommendedAction]


class DiagnosisStatus(StrEnum):
    RUNNING = "running"
    VALID = "valid"  # parsed and every claim cites evidence from the snapshot
    INVALID = "invalid"  # parsed, but citations failed validation
    REFUSED = "refused"  # the model (and any fallback) declined
    ERROR = "error"  # API error, timeout, or output that could not be parsed


class DiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    snapshot_id: uuid.UUID
    status: DiagnosisStatus
    created_at: datetime
    completed_at: datetime | None
    model_requested: str
    model_used: str | None
    effort: str
    prompt_version: str
    output: DiagnosisOutput | None
    validation_errors: list[str]
    error_message: str | None
    stop_reason: str | None
    fallback_used: bool
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    request_id: str | None
