from typing import Protocol

from app.evidence.models import Evidence, EvidenceSource, TimeWindow


class Collector(Protocol):
    source: EvidenceSource

    async def collect(self, window: TimeWindow, services: list[str] | None) -> list[Evidence]:
        """Return evidence for the window. Raise ``BackendError`` if the backend fails."""
        ...
