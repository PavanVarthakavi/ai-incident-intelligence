"""A stand-in for the Claude model, so diagnosis tests never call the API."""

from anthropic.types.beta import BetaUsage

from app.diagnosis.llm import LLMError, ModelReply
from app.diagnosis.schemas import DiagnosisOutput


def output_citing(ids: list[str]) -> DiagnosisOutput:
    """A plausible diagnosis whose every claim cites the given evidence IDs."""
    first, second = ids[0], ids[-1]
    return DiagnosisOutput.model_validate(
        {
            "summary": "Checkout fails because inventory 3.2.0 is slow.",
            "root_cause": {
                "statement": "inventory release 3.2.0 added about 2.5s to POST /reserve",
                "service": "inventory",
                "confidence": "high",
                "evidence_ids": [first, second],
            },
            "contributing_factors": [
                {"statement": "orders times out after 2s", "evidence_ids": [second]}
            ],
            "timeline": [
                {
                    "time": "2026-10-23T05:14:20Z",
                    "event": "inventory deployed",
                    "evidence_ids": [first],
                }
            ],
            "ruled_out": [{"statement": "gateway is healthy", "evidence_ids": [first]}],
            "unknowns": ["database metrics are not collected"],
            "recommended_actions": [
                {
                    "action": "roll back inventory",
                    "rationale": "symptoms began after the deploy",
                    "evidence_ids": [first],
                }
            ],
        }
    )


def reply(
    output: DiagnosisOutput | None = None,
    *,
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    input_tokens: int = 5_000,
    output_tokens: int = 3_000,
    refusal_category: str | None = None,
    parse_error: str | None = None,
    fallback_used: bool = False,
) -> ModelReply:
    return ModelReply(
        output=output,
        parse_error=parse_error,
        model=model,
        stop_reason=stop_reason,
        refusal_category=refusal_category,
        fallback_used=fallback_used,
        usage=BetaUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        request_id="req_fake",
    )


class FakeModel:
    model = "claude-opus-5-5"
    effort = "medium"
    max_tokens = 16_000

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.next: ModelReply | LLMError | None = None

    async def diagnose(self, system: str, user: str) -> ModelReply:
        self.calls.append((system, user))
        if isinstance(self.next, LLMError):
            raise self.next
        assert self.next is not None, "set FakeModel.next before calling"
        return self.next
