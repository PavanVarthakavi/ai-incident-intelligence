"""A stand-in diagnosis model for end-to-end tests and demos without an API key.

It does not analyse anything: it returns a fixed, clearly labelled diagnosis that cites
the snapshot's evidence IDs (found in the rendered prompt), so the full flow, including
citation validation, runs without network calls or cost. Enabled with
APP_LLM_PROVIDER=offline and refused in production (see config).
"""

import json

from anthropic.types.beta import BetaUsage

from app.diagnosis.llm import ModelReply
from app.diagnosis.schemas import DiagnosisOutput

MODEL_NAME = "offline-stand-in"
NOTE = "Offline stand-in, not an analysis"


class OfflineDiagnosisModel:
    model = MODEL_NAME
    effort = "none"
    max_tokens = 1024

    async def diagnose(self, system: str, user: str) -> ModelReply:
        records = evidence_records(user)
        return ModelReply(
            output=stand_in_output(
                [r["id"] for r in records], {r["id"]: r.get("service") for r in records}
            ),
            parse_error=None,
            model=MODEL_NAME,
            stop_reason="end_turn",
            refusal_category=None,
            fallback_used=False,
            usage=BetaUsage(input_tokens=0, output_tokens=0),
            request_id=None,
        )


def evidence_records(user: str) -> list[dict]:
    """The evidence records of a prompt rendered by app.diagnosis.prompt."""
    block = user.partition("<evidence")[2].partition("</evidence>")[0]
    return [json.loads(line) for line in block.splitlines() if line.startswith("{")]


def stand_in_output(ids: list[str], services: dict[str, str | None]) -> DiagnosisOutput:
    if not ids:
        return DiagnosisOutput(
            summary=f"{NOTE}: the snapshot has no evidence, so no root cause is named.",
            root_cause=None,
            contributing_factors=[],
            timeline=[],
            ruled_out=[],
            unknowns=["The snapshot contains no evidence."],
            recommended_actions=[],
        )
    first = ids[0]
    return DiagnosisOutput.model_validate(
        {
            "summary": f"{NOTE}: cites the first evidence items of the snapshot.",
            "root_cause": {
                "statement": f"{NOTE}: the first evidence item is reported as the cause.",
                "service": services.get(first),
                "confidence": "low",
                "evidence_ids": ids[:2],
            },
            "contributing_factors": [
                {"statement": f"{NOTE}: listed for display only.", "evidence_ids": ids[-1:]}
            ],
            "timeline": [],
            "ruled_out": [],
            "unknowns": ["Everything: no model analysed this snapshot."],
            "recommended_actions": [
                {
                    "action": "Run the diagnosis with a real model.",
                    "rationale": NOTE,
                    "evidence_ids": [first],
                }
            ],
        }
    )
