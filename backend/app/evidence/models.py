import hashlib
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

MAX_WINDOW = timedelta(hours=24)


class EvidenceSource(StrEnum):
    METRICS = "metrics"
    TRACES = "traces"
    LOGS = "logs"
    DEPLOYMENTS = "deployments"


class TimeWindow(BaseModel):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.end - self.start > MAX_WINDOW:
            raise ValueError(f"window must not exceed {MAX_WINDOW}")
        return self

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


class Evidence(BaseModel):
    """One citable observation, traceable back to the exact query that produced it."""

    id: str = Field(description="Stable ID: same source, kind, key, and window give the same ID.")
    source: EvidenceSource
    kind: str = Field(description="What the observation is, e.g. 'log_pattern'.")
    service: str | None = None
    observed_at: datetime | None = Field(
        default=None, description="When the observed behaviour started, if known."
    )
    summary: str = Field(description="Factual one-line description, derived only from `data`.")
    query: str = Field(description="The backend query that produced this evidence.")
    reference: str | None = Field(default=None, description="URL to inspect the raw data.")
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def build(
        cls, *, source: EvidenceSource, kind: str, key: str, window: TimeWindow, **fields: Any
    ) -> Self:
        digest = hashlib.sha256(
            f"{source}|{kind}|{key}|{window.start.isoformat()}|{window.end.isoformat()}".encode()
        ).hexdigest()
        return cls(id=f"ev-{digest[:12]}", source=source, kind=kind, **fields)


class SourceError(BaseModel):
    source: EvidenceSource
    message: str


class EvidenceBundle(BaseModel):
    window: TimeWindow
    services: list[str] | None = Field(description="Services requested; null means all.")
    collected_at: datetime
    evidence: list[Evidence]
    errors: list[SourceError] = Field(
        description="Sources that could not be queried. Their evidence is missing, not empty."
    )
