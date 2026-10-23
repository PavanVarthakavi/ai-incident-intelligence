import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from app.evidence.base import Collector
from app.evidence.models import EvidenceBundle, SourceError, TimeWindow
from app.integrations.base import BackendError


class EvidenceService:
    """Runs every collector concurrently and combines their results.

    A failing backend does not fail the whole request: its error is reported in
    the bundle, so callers know that evidence is missing rather than absent.
    Unexpected exceptions (bugs) still propagate.
    """

    def __init__(self, collectors: Sequence[Collector]) -> None:
        self._collectors = collectors

    async def collect(self, window: TimeWindow, services: list[str] | None) -> EvidenceBundle:
        results = await asyncio.gather(
            *(c.collect(window, services) for c in self._collectors), return_exceptions=True
        )
        evidence, errors = [], []
        for collector, result in zip(self._collectors, results, strict=True):
            if isinstance(result, BackendError):
                errors.append(SourceError(source=collector.source, message=str(result)))
            elif isinstance(result, BaseException):
                raise result
            else:
                evidence.extend(result)
        return EvidenceBundle(
            window=window,
            services=services,
            collected_at=datetime.now(UTC),
            evidence=evidence,
            errors=errors,
        )
