"""Evaluation grader and runner, with a fake model (no API calls)."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.diagnosis.llm import LLMError
from app.diagnosis.schemas import DiagnosisOutput
from eval import run as runner
from eval.grade import constant_output, grade, oracle_output
from eval.report import wilson
from tests.diagnosis_fakes import FakeModel, output_citing, reply

EVIDENCE = [
    {
        "id": f"ev-{n}",
        "source": "metrics",
        "kind": "service_http_metrics",
        "service": "gateway",
        "observed_at": None,
        "summary": f"summary {n}",
        "query": "q",
        "reference": None,
        "data": {},
    }
    for n in range(3)
]


def case(service: str | None, release: str | None = None, case_id: str = "T01") -> dict:
    return {
        "id": case_id,
        "tags": ["deploy-caused" if release else ("healthy" if service is None else "silent")],
        "incident": {"title": "t", "severity": "high", "description": None, "services": None},
        "snapshot": {
            "window": {"start": "2026-10-23T07:00:00+00:00", "end": "2026-10-23T07:05:00+00:00"},
            "collected_at": "2026-10-23T07:05:00+00:00",
            "source_errors": [],
            "evidence": EVIDENCE,
        },
        "expected": {"root_cause_service": service, "release": release},
    }


def diagnosis(
    service: str | None, statement: str = "x", ids: list[str] | None = None
) -> DiagnosisOutput:
    out = output_citing(ids or ["ev-0", "ev-1"])
    if service is None:
        out.root_cause = None
    else:
        out.root_cause.service = service
        out.root_cause.statement = statement
    return out


class TestGrade:
    def test_correct_service_and_release(self) -> None:
        g = grade(case("inventory", "3.2.1"), diagnosis("inventory", "release 3.2.1 is slow."))
        assert g == {
            "correct": 1.0,
            "recall": 1.0,
            "specificity": None,
            "release": 1.0,
            "citations": 1.0,
            "complete": None,
        }

    def test_wrong_service(self) -> None:
        g = grade(case("inventory"), diagnosis("orders"))
        assert (g["correct"], g["recall"], g["release"]) == (0.0, 0.0, None)

    def test_service_name_is_normalised(self) -> None:
        assert grade(case("inventory"), diagnosis(" Inventory "))["correct"] == 1.0

    def test_release_missing_from_statement(self) -> None:
        g = grade(case("inventory", "3.2.1"), diagnosis("inventory", "release 3.2.10 is slow"))
        assert (g["correct"], g["release"]) == (1.0, 0.0)

    def test_healthy_case_rewards_no_root_cause(self) -> None:
        assert grade(case(None), diagnosis(None))["specificity"] == 1.0
        assert grade(case(None), diagnosis("gateway"))["specificity"] == 0.0

    def test_invalid_citation_fails_citations_only(self) -> None:
        g = grade(case("inventory"), diagnosis("inventory", ids=["ev-0", "ev-missing"]))
        assert (g["correct"], g["citations"]) == (1.0, 0.0)

    def test_oracle_passes_and_constant_baselines_fail(self) -> None:
        cases = [case("inventory", "3.2.1"), case("orders"), case(None)]
        assert all(grade(c, oracle_output(c))["correct"] == 1.0 for c in cases)
        assert all(grade(c, oracle_output(c))["citations"] == 1.0 for c in cases)
        none = [grade(c, constant_output(None))["correct"] for c in cases]
        assert none == [0.0, 0.0, 1.0]  # "always healthy" only passes healthy cases
        always = [grade(c, constant_output("inventory")) for c in cases]
        assert [g["citations"] for g in always[:2]] == [0.0, 0.0]  # cites nothing


def test_wilson_interval() -> None:
    # 12/24: p = 0.5, 95% Wilson interval is about 0.314 to 0.686.
    low, high = wilson(12, 24)
    assert round(low, 3) == 0.314 and round(high, 3) == 0.686
    assert wilson(0, 0) == (0.0, 0.0)


def run_one(model: FakeModel, out: Path, c: dict, cap_usd: float = 10.0) -> str:
    (out / "traces").mkdir(parents=True, exist_ok=True)
    return asyncio.run(runner.run_case(c, 0, model, out, runner.SpendCap(cap_usd), timeout_s=5))


def rows(out: Path, name: str = "results.jsonl") -> list[dict]:
    path = out / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class TestRunCase:
    def test_ok_row_has_grade_usage_and_trace(self, tmp_path: Path) -> None:
        model = FakeModel()
        model.next = reply(diagnosis("inventory", "inventory 3.2.1"))

        assert run_one(model, tmp_path, case("inventory", "3.2.1")) == "ok"

        [row] = rows(tmp_path)
        assert row["grade"]["correct"] == 1.0 and row["grade"]["release"] == 1.0
        assert row["usage"]["input_tokens"] == 5_000 and Decimal(row["cost_usd"]) == Decimal("0.08")
        assert row["model"] == "claude-opus-5-5" and row["latency_s"] >= 0
        trace = json.loads((tmp_path / "traces" / "T01_rep0.json").read_text())
        assert [t["role"] for t in trace] == ["system", "user", "assistant"]
        assert '"id":"ev-0"' in trace[1]["content"]

    def test_refusal_and_truncation_are_rows_without_grades(self, tmp_path: Path) -> None:
        model = FakeModel()
        model.next = reply(stop_reason="refusal", refusal_category="cyber")
        run_one(model, tmp_path, case("inventory", case_id="A"))
        model.next = reply(stop_reason="max_tokens", parse_error="cut off")
        run_one(model, tmp_path, case("inventory", case_id="B"))

        assert [(r["status"], r["grade"]) for r in rows(tmp_path)] == [
            ("refused", None),
            ("truncated", None),
        ]

    @pytest.mark.parametrize(
        ("failure", "expected"),
        [
            (LLMError("HTTP 529", may_have_billed=False), "api_error"),
            (TimeoutError(), "timeout"),
        ],
    )
    def test_failures_go_to_errors_not_results(self, tmp_path: Path, failure, expected) -> None:
        model = FakeModel()

        async def fail(system: str, user: str):
            raise failure

        model.diagnose = fail

        assert run_one(model, tmp_path, case("inventory")) == expected
        assert rows(tmp_path) == []
        assert rows(tmp_path, "errors.jsonl")[0]["failure"] == expected

    def test_served_model_mismatch_is_an_error(self, tmp_path: Path) -> None:
        model = FakeModel()
        model.next = reply(diagnosis("inventory"), model="claude-opus-5", fallback_used=True)

        assert run_one(model, tmp_path, case("inventory")) == "served_model_mismatch"
        assert rows(tmp_path) == []

    def test_spend_cap_skips_without_calling(self, tmp_path: Path) -> None:
        model = FakeModel()
        model.next = reply(diagnosis("inventory"))

        assert run_one(model, tmp_path, case("inventory"), cap_usd=0.01) == "skipped"
        assert model.calls == []


def test_spend_cap_accounting() -> None:
    async def scenario() -> None:
        cap = runner.SpendCap(1.0)
        assert await cap.reserve(Decimal("0.6"))
        waiting = asyncio.create_task(cap.reserve(Decimal("0.6")))
        await asyncio.sleep(0)
        assert not waiting.done()  # waits instead of skipping while a call is in flight
        cap.settle(Decimal("0.6"), Decimal("0.1"))
        assert await waiting
        assert cap.spent == Decimal("0.1")
        cap.settle(Decimal("0.6"), Decimal("0.6"))
        assert not await cap.reserve(Decimal("0.6"))  # cannot fit even with nothing in flight

    asyncio.run(scenario())


def test_done_keys_enable_resume(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps({"prompt_id": "F01", "rep": 0}) + "\n")
    assert runner.done_keys(path) == {("F01", 0)}


def test_a_second_real_fault_is_accepted_when_listed() -> None:
    two_faults = {
        "snapshot": {"evidence": [{"id": "ev-1", "source": "metrics"}], "source_errors": []},
        "expected": {
            "root_cause_service": "orders",
            "also_accepted": ["inventory"],
            "release": None,
        },
    }
    assert grade(two_faults, constant_output("inventory"))["correct"] == 1.0
    assert grade(two_faults, constant_output("gateway"))["correct"] == 0.0


TWO_FAULTS = {
    "id": "X1",
    "snapshot": {"evidence": [{"id": "ev-1", "source": "metrics"}], "source_errors": []},
    "expected": {"root_cause_service": "orders", "also_accepted": ["inventory"], "release": None},
}


def test_complete_requires_every_fault_named_outside_ruled_out() -> None:
    output = oracle_output(TWO_FAULTS)  # names inventory as a contributing factor
    assert grade(TWO_FAULTS, output)["complete"] == 1.0

    data = output.model_dump()
    data["contributing_factors"] = []
    data["ruled_out"] = [{"statement": "inventory is healthy", "evidence_ids": ["ev-1"]}]
    output = DiagnosisOutput.model_validate(data)
    assert grade(TWO_FAULTS, output)["complete"] == 0.0

    single = {**TWO_FAULTS, "expected": {**TWO_FAULTS["expected"], "also_accepted": []}}
    assert grade(single, output)["complete"] is None


def test_regrade_recomputes_stored_grades_from_traces(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "v9"
    (out / "traces").mkdir(parents=True)
    output = oracle_output(TWO_FAULTS)
    trace = [{"role": "assistant", "content": output.model_dump_json()}]
    (out / "traces" / "X1_rep0.json").write_text(json.dumps(trace))
    row = {"prompt_id": "X1", "rep": 0, "status": "ok", "grade": {"correct": 0.0}}
    (out / "results.jsonl").write_text(json.dumps(row) + "\n")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner, "load_cases", lambda ids=None: [TWO_FAULTS])

    assert runner.regrade("v9") == 0

    [stored] = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
    assert stored["grade"]["correct"] == 1.0
    assert stored["grade"]["complete"] == 1.0
