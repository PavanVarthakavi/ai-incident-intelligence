"""The real SDK client against a fake HTTP transport: request shape and reply handling."""

import asyncio
import json

import anthropic
import httpx2
import pytest

from app.diagnosis.llm import FALLBACK_BETA, AnthropicDiagnosisModel, LLMError
from tests.diagnosis_fakes import output_citing
from tests.fakes import FIXTURES

OUTPUT = output_citing(["ev-a", "ev-b"]).model_dump(mode="json")


def api_reply(content: list[dict], *, stop_reason: str = "end_turn", **extra) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "stop_details": None,
        "usage": {"input_tokens": 4_000, "output_tokens": 2_500},
        **extra,
    }


def text_reply(text: str, **kwargs) -> dict:
    return api_reply(
        [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
        **kwargs,
    )


def run(body: dict | None = None, status: int = 200, *, fallbacks: bool = True):
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(status, json=body or {}, headers={"request-id": "req_123"})

    client = anthropic.AsyncAnthropic(
        api_key="sk-test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    model = AnthropicDiagnosisModel(
        client, model="claude-opus-5-5", effort="medium", max_tokens=16_000, fallbacks=fallbacks
    )
    return asyncio.run(model.diagnose("system prompt", "user message")), requests


def test_request_shape() -> None:
    _, [request] = run(text_reply(json.dumps(OUTPUT)))
    body = json.loads(request.content)

    assert request.url.path == "/v1/messages"
    assert request.headers["anthropic-beta"] == FALLBACK_BETA
    assert body["model"] == "claude-opus-5-5"
    assert body["max_tokens"] == 16_000
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "root_cause" in body["output_config"]["format"]["schema"]["properties"]
    assert body["system"] == "system prompt"
    assert body["messages"] == [{"role": "user", "content": "user message"}]
    assert "thinking" not in body  # thinking is always on for this model; effort controls it


def test_fallbacks_can_be_disabled() -> None:
    _, [request] = run(text_reply(json.dumps(OUTPUT)), fallbacks=False)

    assert "anthropic-beta" not in request.headers
    assert "fallbacks" not in json.loads(request.content)


def test_parses_reply_and_usage() -> None:
    reply, _ = run(text_reply(json.dumps(OUTPUT)))

    assert reply.output is not None and reply.output.root_cause.service == "inventory"
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (4_000, 2_500)
    assert (reply.model, reply.stop_reason, reply.request_id) == (
        "claude-opus-5-5",
        "end_turn",
        "req_123",
    )
    assert reply.fallback_used is False


def test_truncated_reply_keeps_usage() -> None:
    reply, _ = run(text_reply('{"summary": "cut', stop_reason="max_tokens"))

    assert reply.output is None
    assert reply.parse_error == "reply was cut off at max_tokens"
    assert reply.usage.output_tokens == 2_500


def test_refusal() -> None:
    reply, _ = run(
        api_reply(
            [],
            stop_reason="refusal",
            stop_details={"type": "refusal", "category": "cyber", "explanation": None},
        )
    )

    assert (reply.output, reply.stop_reason, reply.refusal_category) == (None, "refusal", "cyber")


def test_fallback_is_detected_from_usage_iterations() -> None:
    body = text_reply(json.dumps(OUTPUT))
    body["model"] = "claude-opus-5"
    body["usage"]["iterations"] = [
        {"type": "message", "input_tokens": 4_000, "output_tokens": 10},
        {"type": "fallback_message", "input_tokens": 4_000, "output_tokens": 2_490},
    ]

    reply, _ = run(body)

    assert reply.fallback_used is True
    assert reply.model == "claude-opus-5"


@pytest.mark.parametrize(("status", "billed"), [(400, False), (529, False)])
def test_http_errors_raise_without_billing(status: int, billed: bool) -> None:
    with pytest.raises(LLMError, match=f"HTTP {status}") as exc_info:
        run({"type": "error", "error": {"type": "x", "message": "nope"}}, status=status)

    assert exc_info.value.may_have_billed is billed


def test_connection_failure_may_have_billed() -> None:
    def broken(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    client = anthropic.AsyncAnthropic(
        api_key="sk-test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(broken)),
    )
    model = AnthropicDiagnosisModel(
        client, model="claude-opus-5-5", effort="medium", max_tokens=16_000, fallbacks=True
    )

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(model.diagnose("s", "u"))

    assert exc_info.value.may_have_billed is True


def recorded(name: str) -> dict:
    """A raw reply recorded from the live API by tests/record_llm_reply.py."""
    return json.loads((FIXTURES / f"anthropic_reply_{name}.json").read_text())["body"]


def test_recorded_bad_deploy_reply_parses() -> None:
    body = recorded("bad_deploy")

    reply, _ = run(body)

    assert reply.output is not None and reply.parse_error is None
    assert reply.output.root_cause is not None
    assert reply.output.root_cause.service == "inventory"
    assert reply.usage.input_tokens == body["usage"]["input_tokens"]
    assert reply.usage.output_tokens == body["usage"]["output_tokens"]
    assert reply.stop_reason == "end_turn"
    assert reply.fallback_used is False


def test_recorded_healthy_window_reply_has_no_root_cause() -> None:
    reply, _ = run(recorded("healthy"))

    assert reply.output is not None
    assert reply.output.root_cause is None
    assert reply.output.unknowns
