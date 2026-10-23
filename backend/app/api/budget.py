"""Today's diagnosis budget, so clients can show cost before running a diagnosis."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.db.session import SessionDep
from app.diagnosis.schemas import BudgetRead
from app.diagnosis.service import spent_today, typical_cost

router = APIRouter(prefix="/v1", tags=["diagnoses"])


@router.get("/budget", response_model=BudgetRead)
async def get_budget(
    request: Request, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> BudgetRead:
    limit = Decimal(str(settings.llm_daily_budget_usd))
    spent = await spent_today(session)
    model = request.app.state.diagnosis_model
    return BudgetRead(
        day=datetime.now(UTC).date().isoformat(),
        limit_usd=limit,
        spent_usd=spent,
        remaining_usd=max(limit - spent, Decimal(0)),
        typical_cost_usd=await typical_cost(session),
        enabled=model is not None,
        model=model.model if model is not None else None,
    )
