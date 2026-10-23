"""Health and admin endpoints shared by every demo service.

The admin API is unauthenticated and intended only for the local demo stack,
where ports are bound to 127.0.0.1. It is excluded from tracing.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from shop.context import State
from shop.faults import FaultConfig

logger = logging.getLogger("shop.admin")
router = APIRouter()


class ServiceStatus(BaseModel):
    service: str
    release: str
    faults: FaultConfig


class ReleaseChange(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    # Faults that ship with this release; omitted means a healthy release.
    faults: FaultConfig = Field(default_factory=FaultConfig)


def _status(state: State) -> ServiceStatus:
    return ServiceStatus(
        service=state.name, release=state.faults.release, faults=state.faults.config
    )


@router.get("/health", tags=["health"])
def health(state: State) -> dict[str, str]:
    return {"status": "ok", "service": state.name}


@router.get("/admin/status", tags=["admin"])
def get_status(state: State) -> ServiceStatus:
    return _status(state)


@router.put("/admin/faults", tags=["admin"])
def set_faults(config: FaultConfig, state: State) -> ServiceStatus:
    state.faults.set(config)
    return _status(state)


@router.delete("/admin/faults", tags=["admin"])
def clear_faults(state: State) -> ServiceStatus:
    state.faults.clear()
    return _status(state)


@router.put("/admin/release", tags=["admin"])
def change_release(change: ReleaseChange, state: State) -> ServiceStatus:
    """Simulate a deployment: switch the running release and its behaviour atomically."""
    previous = state.faults.release
    state.faults.release = change.version
    state.faults.set(change.faults)
    # A real deploy would log this; it is a legitimate, observable signal.
    logger.info(
        "release changed from %s to %s",
        previous,
        change.version,
        extra={"release": change.version, "previous_release": previous},
    )
    return _status(state)
