"""The offline stand-in model and its configuration guard."""

import asyncio

import pytest
from pydantic import ValidationError

from app.diagnosis.offline import OfflineDiagnosisModel
from app.main import build_diagnosis_model
from tests.conftest import hermetic_settings


def prompt(*records: str) -> str:
    header = ["<collection_errors>", "none", "</collection_errors>", "", "<evidence>"]
    return "\n".join([*header, *records, "</evidence>"])


def test_cites_snapshot_evidence_and_names_its_service() -> None:
    user = prompt(
        '{"id":"ev-aaaaaaaaaaaa","service":"inventory","summary":"see ev-bbbbbbbbbbbb"}',
        '{"id":"ev-cccccccccccc","service":"orders"}',
    )
    reply = asyncio.run(OfflineDiagnosisModel().diagnose("system", user))

    assert reply.output is not None and reply.output.root_cause is not None
    assert reply.output.root_cause.evidence_ids == ["ev-aaaaaaaaaaaa", "ev-cccccccccccc"]
    assert reply.output.root_cause.service == "inventory"
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (0, 0)


def test_empty_snapshot_has_no_root_cause() -> None:
    reply = asyncio.run(OfflineDiagnosisModel().diagnose("system", prompt()))
    assert reply.output is not None
    assert reply.output.root_cause is None


def test_offline_provider_needs_no_key_and_is_refused_in_production() -> None:
    assert isinstance(
        build_diagnosis_model(hermetic_settings(llm_provider="offline")), OfflineDiagnosisModel
    )
    with pytest.raises(ValidationError, match="not production"):
        hermetic_settings(llm_provider="offline", environment="production")
