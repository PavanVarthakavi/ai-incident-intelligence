"""Diagnosis API: run the investigation agent over a stored snapshot."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.db.models import EvidenceSnapshot, Incident
from app.db.session import SessionDep
from app.diagnosis.llm import DiagnosisModel
from app.diagnosis.schemas import DiagnosisRead
from app.diagnosis.service import BudgetExceededError, run_diagnosis
from app.incidents import repository

router = APIRouter(
    prefix="/v1/incidents/{incident_id}/snapshots/{snapshot_id}/diagnoses", tags=["diagnoses"]
)


def get_diagnosis_model(request: Request) -> DiagnosisModel:
    model: DiagnosisModel | None = request.app.state.diagnosis_model
    if model is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not set")
    return model


ModelDep = Annotated[DiagnosisModel, Depends(get_diagnosis_model)]


async def _require_snapshot(
    session: SessionDep, incident_id: uuid.UUID, snapshot_id: uuid.UUID
) -> tuple[Incident, EvidenceSnapshot]:
    incident = await repository.get_incident(session, incident_id)
    snapshot = await repository.get_snapshot(session, incident_id, snapshot_id)
    if incident is None or snapshot is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return incident, snapshot


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DiagnosisRead,
    responses={429: {"description": "The daily LLM budget would be exceeded."}},
)
async def create_diagnosis(
    incident_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: SessionDep,
    model: ModelDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosisRead:
    """Diagnose the snapshot with the configured model. This calls a paid API.

    The result is stored whatever the outcome; check `status`. Only `valid`
    diagnoses passed citation checks.
    """
    incident, snapshot = await _require_snapshot(session, incident_id, snapshot_id)
    await session.commit()  # end the read transaction; run_diagnosis manages its own
    try:
        diagnosis = await run_diagnosis(
            session, incident, snapshot, model, settings.llm_daily_budget_usd
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None
    return DiagnosisRead.model_validate(diagnosis)


@router.get("", response_model=list[DiagnosisRead])
async def list_diagnoses(
    incident_id: uuid.UUID, snapshot_id: uuid.UUID, session: SessionDep
) -> list[DiagnosisRead]:
    """Diagnoses of this snapshot, newest first."""
    await _require_snapshot(session, incident_id, snapshot_id)
    return [
        DiagnosisRead.model_validate(d)
        for d in await repository.list_diagnoses(session, snapshot_id)
    ]


@router.get("/{diagnosis_id}", response_model=DiagnosisRead)
async def get_diagnosis(
    incident_id: uuid.UUID, snapshot_id: uuid.UUID, diagnosis_id: uuid.UUID, session: SessionDep
) -> DiagnosisRead:
    await _require_snapshot(session, incident_id, snapshot_id)
    diagnosis = await repository.get_diagnosis(session, snapshot_id, diagnosis_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="diagnosis not found")
    return DiagnosisRead.model_validate(diagnosis)
