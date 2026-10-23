"""Read-only evidence collection API."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.backends import BackendsDep
from app.evidence.models import EvidenceBundle, TimeWindow

router = APIRouter(prefix="/v1", tags=["evidence"])

DEFAULT_LOOKBACK = timedelta(minutes=15)


@router.get("/evidence", response_model=EvidenceBundle)
async def collect_evidence(
    backends: BackendsDep,
    start: Annotated[
        datetime | None, Query(description="Window start (ISO 8601 with timezone).")
    ] = None,
    end: Annotated[datetime | None, Query(description="Window end; defaults to now.")] = None,
    service: Annotated[
        list[str] | None, Query(description="Limit to these services; repeatable.")
    ] = None,
) -> EvidenceBundle:
    """Collect metrics, traces, logs, and deployments for a time window.

    Defaults to the last 15 minutes. Sources that fail are listed in `errors`.
    """
    end = end or datetime.now(UTC)
    start = start or end - DEFAULT_LOOKBACK
    try:
        window = TimeWindow(start=start, end=end)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=[e["msg"] for e in exc.errors(include_url=False)]
        ) from None
    return await backends.evidence.collect(window, service or None)
