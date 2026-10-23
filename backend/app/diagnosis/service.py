"""Runs a diagnosis: reserve budget, call the model, validate, store.

The budget check and the reservation happen in one transaction under a
PostgreSQL advisory lock, so concurrent requests cannot both pass the check
and overspend. A row stuck in ``running`` (e.g. after a crash) keeps its
reservation until the end of the UTC day, which errs on the side of spending
less.
"""

from datetime import UTC, datetime, time
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Diagnosis, EvidenceSnapshot, Incident
from app.diagnosis import pricing
from app.diagnosis.llm import OUTPUT_SCHEMA_CHARS, DiagnosisModel, LLMError, ModelReply
from app.diagnosis.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_user_message
from app.diagnosis.schemas import DiagnosisStatus
from app.diagnosis.validation import citable_ids, citation_errors

BUDGET_LOCK_ID = 7_310_001  # arbitrary constant naming the budget advisory lock


class BudgetExceededError(Exception):
    def __init__(self, spent: Decimal, needed: Decimal, budget: Decimal) -> None:
        super().__init__(
            f"daily LLM budget of ${budget} would be exceeded: ${spent} spent or reserved "
            f"today, this request may cost up to ${needed}"
        )


async def spent_today(session: AsyncSession) -> Decimal:
    midnight = datetime.combine(datetime.now(UTC).date(), time(), UTC)
    total = await session.scalar(
        select(
            func.coalesce(
                func.sum(func.coalesce(Diagnosis.cost_usd, Diagnosis.reserved_cost_usd)), 0
            )
        ).where(Diagnosis.created_at >= midnight)
    )
    return Decimal(total)


async def typical_cost(session: AsyncSession, last: int = 20) -> Decimal | None:
    """Median cost of the most recent completed diagnoses, or None before any."""
    recent = (
        select(Diagnosis.cost_usd)
        .where(Diagnosis.cost_usd.is_not(None))
        .order_by(Diagnosis.created_at.desc())
        .limit(last)
        .subquery()
    )
    median = await session.scalar(select(func.percentile_cont(0.5).within_group(recent.c.cost_usd)))
    return None if median is None else Decimal(str(median)).quantize(Decimal("0.0001"))


async def reserve(
    session: AsyncSession,
    snapshot: EvidenceSnapshot,
    model: DiagnosisModel,
    request_chars: int,
    daily_budget_usd: float,
) -> Diagnosis:
    needed = pricing.worst_case_cost_usd(model.model, request_chars, model.max_tokens)
    budget = Decimal(str(daily_budget_usd))
    async with session.begin():
        await session.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": BUDGET_LOCK_ID})
        spent = await spent_today(session)
        if spent + needed > budget:
            raise BudgetExceededError(spent, needed, budget)
        diagnosis = Diagnosis(
            snapshot_id=snapshot.id,
            status=DiagnosisStatus.RUNNING.value,
            model_requested=model.model,
            effort=model.effort,
            prompt_version=PROMPT_VERSION,
            validation_errors=[],
            fallback_used=False,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            reserved_cost_usd=needed,
        )
        session.add(diagnosis)
    return diagnosis


def apply_reply(diagnosis: Diagnosis, reply: ModelReply, known_ids: set[str]) -> None:
    usage = reply.usage
    diagnosis.model_used = reply.model
    diagnosis.stop_reason = reply.stop_reason
    diagnosis.fallback_used = reply.fallback_used
    diagnosis.request_id = reply.request_id
    diagnosis.input_tokens = usage.input_tokens
    diagnosis.output_tokens = usage.output_tokens
    diagnosis.cache_read_tokens = usage.cache_read_input_tokens or 0
    diagnosis.cache_creation_tokens = usage.cache_creation_input_tokens or 0
    diagnosis.cost_usd = pricing.cost_usd(reply.model, usage)

    if reply.stop_reason == "refusal":
        diagnosis.status = DiagnosisStatus.REFUSED.value
        category = reply.refusal_category or "unspecified"
        diagnosis.error_message = f"request declined (category: {category})"
    elif reply.output is None:
        diagnosis.status = DiagnosisStatus.ERROR.value
        diagnosis.error_message = reply.parse_error
    else:
        diagnosis.output = reply.output.model_dump(mode="json")
        errors = citation_errors(reply.output, known_ids)
        diagnosis.validation_errors = errors
        diagnosis.status = (DiagnosisStatus.INVALID if errors else DiagnosisStatus.VALID).value


async def run_diagnosis(
    session: AsyncSession,
    incident: Incident,
    snapshot: EvidenceSnapshot,
    model: DiagnosisModel,
    daily_budget_usd: float,
) -> Diagnosis:
    """Diagnose a snapshot (items loaded). Raises BudgetExceededError before any spend."""
    user = render_user_message(incident, snapshot)
    request_chars = len(SYSTEM_PROMPT) + len(user) + OUTPUT_SCHEMA_CHARS
    diagnosis = await reserve(session, snapshot, model, request_chars, daily_budget_usd)
    known_ids = citable_ids(
        ((item.evidence_id, item.source) for item in snapshot.items), snapshot.source_errors
    )

    # No transaction is held open during the model call, which can take minutes.
    try:
        reply, failure = await model.diagnose(SYSTEM_PROMPT, user), None
    except LLMError as exc:
        reply, failure = None, exc
    async with session.begin():
        session.add(diagnosis)
        if failure is not None:
            diagnosis.status = DiagnosisStatus.ERROR.value
            diagnosis.error_message = str(failure)
            # Unknown cost stays NULL, so the reservation keeps counting against the budget.
            diagnosis.cost_usd = None if failure.may_have_billed else Decimal(0)
        else:
            apply_reply(diagnosis, reply, known_ids)
        diagnosis.completed_at = datetime.now(UTC)
    return diagnosis
