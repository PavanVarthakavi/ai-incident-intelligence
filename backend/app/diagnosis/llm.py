"""Claude client for diagnoses.

Uses structured outputs (``output_config.format``) so the reply is JSON that
matches ``DiagnosisOutput``. The reply is parsed here rather than with the
SDK's ``parse()`` helper so that token usage is always available, including
for truncated or unparseable replies, which are still billed.
"""

import json
from dataclasses import dataclass
from typing import Protocol

import anthropic
from anthropic.types.beta import BetaUsage
from pydantic import ValidationError

from app.diagnosis.schemas import DiagnosisOutput

FALLBACK_BETA = "server-side-fallback-2026-07-01"
OUTPUT_SCHEMA = anthropic.transform_schema(DiagnosisOutput)
OUTPUT_SCHEMA_CHARS = len(json.dumps(OUTPUT_SCHEMA))


class LLMError(Exception):
    """The API could not be called or returned an error. Safe to show to users.

    ``may_have_billed`` is true when the request might have been processed
    (timeouts, dropped connections), so its cost cannot be assumed to be zero.
    """

    def __init__(self, message: str, *, may_have_billed: bool) -> None:
        super().__init__(message)
        self.may_have_billed = may_have_billed


@dataclass(frozen=True)
class ModelReply:
    output: DiagnosisOutput | None
    parse_error: str | None
    model: str
    stop_reason: str | None
    refusal_category: str | None
    fallback_used: bool
    usage: BetaUsage
    request_id: str | None


class DiagnosisModel(Protocol):
    model: str
    effort: str
    max_tokens: int

    async def diagnose(self, system: str, user: str) -> ModelReply: ...


class AnthropicDiagnosisModel:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        *,
        model: str,
        effort: str,
        max_tokens: int,
        fallbacks: bool,
    ) -> None:
        self._client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._fallbacks = fallbacks

    async def diagnose(self, system: str, user: str) -> ModelReply:
        extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if self._fallbacks else {}
        try:
            response = await self._client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
                },
                **extra,
            )
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"Claude API returned HTTP {exc.status_code}: {exc.message}", may_have_billed=False
            ) from None
        except anthropic.APIConnectionError as exc:  # includes APITimeoutError
            raise LLMError(
                f"Claude API request failed: {type(exc).__name__}", may_have_billed=True
            ) from None

        output, parse_error = None, None
        if response.stop_reason != "refusal":
            text = "".join(b.text for b in response.content if b.type == "text")
            try:
                output = DiagnosisOutput.model_validate_json(text)
            except ValidationError as exc:
                parse_error = f"reply did not match the schema ({exc.error_count()} errors)"
                if response.stop_reason == "max_tokens":
                    parse_error = "reply was cut off at max_tokens"

        stop_details = response.stop_details
        return ModelReply(
            output=output,
            parse_error=parse_error,
            model=response.model,
            stop_reason=response.stop_reason,
            refusal_category=getattr(stop_details, "category", None) if stop_details else None,
            fallback_used=any(
                entry.type == "fallback_message" for entry in (response.usage.iterations or [])
            ),
            usage=response.usage,
            request_id=response._request_id,
        )
