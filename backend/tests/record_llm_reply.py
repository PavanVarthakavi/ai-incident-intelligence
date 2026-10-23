"""Diagnose a stored snapshot with the real Claude API and record the raw reply.

    python -m tests.record_llm_reply                       # count tokens only (free)
    python -m tests.record_llm_reply --yes --name healthy  # run one paid diagnosis
    python -m tests.record_llm_reply --yes --snapshot <id> --name bad_deploy

Uses the latest snapshot in APP_DATABASE_URL unless --snapshot is given. The
diagnosis goes through the same service as the API (budget reservation,
validation, storage). The raw API reply is written to
tests/fixtures/anthropic_reply_<name>.json so unit tests can replay it.
"""

import argparse
import asyncio
import json
import uuid

import anthropic
import httpx2
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import EvidenceSnapshot, Incident
from app.db.session import Database
from app.diagnosis import pricing
from app.diagnosis.llm import OUTPUT_SCHEMA, AnthropicDiagnosisModel
from app.diagnosis.prompt import SYSTEM_PROMPT, render_user_message
from app.diagnosis.service import run_diagnosis
from tests.fakes import FIXTURES


async def main(snapshot_id: uuid.UUID | None, spend: bool, name: str) -> None:
    settings = Settings()
    if settings.anthropic_api_key is None or settings.database_url is None:
        raise SystemExit("ANTHROPIC_API_KEY and APP_DATABASE_URL must be set (see .env.example)")

    captured: dict = {}

    async def capture(response: httpx2.Response) -> None:
        if response.request.url.path == "/v1/messages":
            await response.aread()
            captured["reply"] = {"status": response.status_code, "body": response.json()}

    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        http_client=httpx2.AsyncClient(event_hooks={"response": [capture]}),
    )
    model = AnthropicDiagnosisModel(
        client,
        model=settings.llm_model,
        effort=settings.llm_effort,
        max_tokens=settings.llm_max_tokens,
        fallbacks=settings.llm_fallbacks,
    )
    database = Database.connect(settings.database_url.get_secret_value())
    try:
        async with database.sessions() as session:
            query = select(EvidenceSnapshot).options(selectinload(EvidenceSnapshot.items))
            query = (
                query.where(EvidenceSnapshot.id == snapshot_id)
                if snapshot_id
                else query.order_by(EvidenceSnapshot.collected_at.desc()).limit(1)
            )
            snapshot = await session.scalar(query)
            if snapshot is None:
                raise SystemExit("no snapshot found")
            incident = await session.get(Incident, snapshot.incident_id)
            user = render_user_message(incident, snapshot)

            count = await client.beta.messages.count_tokens(
                model=settings.llm_model,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            )
            input_price, output_price = pricing.prices_for(settings.llm_model)
            print(f"snapshot {snapshot.id} ({len(snapshot.items)} evidence items)")
            print(
                f"input tokens: {count.input_tokens} "
                f"(${count.input_tokens * input_price / pricing.PER_MILLION:.4f} at "
                f"{settings.llm_model} input rates)"
            )
            if not spend:
                print("dry run: pass --yes to run one paid diagnosis")
                return

            await session.commit()
            diagnosis = await run_diagnosis(
                session, incident, snapshot, model, settings.llm_daily_budget_usd
            )
    finally:
        await database.engine.dispose()

    if "reply" in captured:
        fixture = FIXTURES / f"anthropic_reply_{name}.json"
        fixture.write_text(json.dumps(captured["reply"], indent=1, sort_keys=True) + "\n")
        print(f"recorded raw reply to {fixture.relative_to(FIXTURES.parent.parent)}")
    print(f"diagnosis {diagnosis.id}: status={diagnosis.status} model={diagnosis.model_used}")
    print(
        f"tokens in/out: {diagnosis.input_tokens}/{diagnosis.output_tokens} "
        f"cost: ${diagnosis.cost_usd} fallback: {diagnosis.fallback_used}"
    )
    if diagnosis.validation_errors:
        print("validation errors:", *diagnosis.validation_errors, sep="\n  ")
    if diagnosis.error_message:
        print("error:", diagnosis.error_message)
    if diagnosis.output:
        print(json.dumps(diagnosis.output, indent=1))


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=uuid.UUID)
    parser.add_argument("--yes", action="store_true", help="spend money on one diagnosis")
    parser.add_argument("--name", default="latest", help="fixture name suffix")
    args = parser.parse_args()
    asyncio.run(main(args.snapshot, args.yes, args.name))


if __name__ == "__main__":
    cli()
