"""Run the diagnosis evaluation.

    python -m eval.run --check oracle          # free: grader against known answers
    python -m eval.run --check null            # free: constant answers must score low
    python -m eval.run --variant baseline      # paid: one diagnosis per case
    python -m eval.run --variant v1 --effort high --reps 1

Paid runs refuse to start until the current harness (runner, grader, prompt,
client, and case files) has been approved with --approve-harness, so a run
always corresponds to code and cases a person looked at.

Results go to eval/results/<variant>/: results.jsonl (one row per case and
rep, written as each finishes; rerunning resumes), errors.jsonl (attempts that
produced nothing gradable), traces/, and run.json.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db.models import EvidenceItem, EvidenceSnapshot, Incident
from app.diagnosis import pricing
from app.diagnosis.llm import OUTPUT_SCHEMA_CHARS, DiagnosisModel, LLMError
from app.diagnosis.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_user_message
from app.main import build_diagnosis_model
from eval.grade import constant_output, grade, oracle_output

EVAL_DIR = Path(__file__).parent
CASES_DIR = EVAL_DIR / "cases"
RESULTS_DIR = EVAL_DIR / "results"
APPROVAL_FILE = RESULTS_DIR / "approved_harness.json"
HARNESS_FILES = (
    EVAL_DIR / "run.py",
    EVAL_DIR / "grade.py",
    EVAL_DIR.parent / "app" / "diagnosis" / "prompt.py",
    EVAL_DIR.parent / "app" / "diagnosis" / "llm.py",
    EVAL_DIR.parent / "app" / "diagnosis" / "validation.py",
)


def load_cases(ids: list[str] | None = None) -> list[dict[str, Any]]:
    cases = [json.loads(p.read_text()) for p in sorted(CASES_DIR.glob("*.json"))]
    return [c for c in cases if not ids or c["id"] in ids]


def harness_sha() -> str:
    digest = hashlib.sha256()
    for path in [*HARNESS_FILES, *sorted(CASES_DIR.glob("*.json"))]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def to_orm(case: dict[str, Any]) -> tuple[Incident, EvidenceSnapshot]:
    """The incident and snapshot the app would load from the database for this case."""
    incident = Incident(**{k: case["incident"][k] for k in ("title", "severity", "description")})
    snap = case["snapshot"]
    snapshot = EvidenceSnapshot(
        window_start=datetime.fromisoformat(snap["window"]["start"]),
        window_end=datetime.fromisoformat(snap["window"]["end"]),
        services=case["incident"]["services"],
        source_errors=snap["source_errors"],
        items=[
            EvidenceItem(
                evidence_id=e["id"],
                source=e["source"],
                kind=e["kind"],
                service=e["service"],
                observed_at=datetime.fromisoformat(e["observed_at"]) if e["observed_at"] else None,
                summary=e["summary"],
                query=e["query"],
                reference=e["reference"],
                data=e["data"],
            )
            for e in snap["evidence"]
        ],
    )
    return incident, snapshot


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def done_keys(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    return {(r["prompt_id"], r["rep"]) for r in map(json.loads, path.read_text().splitlines())}


class SpendCap:
    """Keeps spend plus the worst case of in-flight calls under the cap.

    A case that does not fit waits for in-flight calls to settle (they usually cost far
    less than their worst case) and is skipped only when it cannot fit with nothing in
    flight.
    """

    def __init__(self, cap_usd: float) -> None:
        self.cap = Decimal(str(cap_usd))
        self.spent = Decimal(0)
        self.reserved = Decimal(0)
        self._settled = asyncio.Event()

    async def reserve(self, amount: Decimal) -> bool:
        while self.spent + self.reserved + amount > self.cap:
            if self.reserved == 0:
                return False
            self._settled.clear()
            await self._settled.wait()
        self.reserved += amount
        return True

    def settle(self, reserved: Decimal, actual: Decimal) -> None:
        self.reserved -= reserved
        self.spent += actual
        self._settled.set()


async def run_case(
    case: dict[str, Any],
    rep: int,
    model: DiagnosisModel,
    out: Path,
    cap: SpendCap,
    timeout_s: float,
) -> str:
    incident, snapshot = to_orm(case)
    user = render_user_message(incident, snapshot)
    worst = pricing.worst_case_cost_usd(
        model.model, len(SYSTEM_PROMPT) + len(user) + OUTPUT_SCHEMA_CHARS, model.max_tokens
    )
    if not await cap.reserve(worst):
        return "skipped"
    started = time.monotonic()
    base = {
        "prompt_id": case["id"],
        "rep": rep,
        "tags": case["tags"],
        "requested_model": model.model,
    }
    try:
        reply = await asyncio.wait_for(model.diagnose(SYSTEM_PROMPT, user), timeout=timeout_s)
    except (LLMError, TimeoutError) as exc:
        failure = "timeout" if isinstance(exc, TimeoutError) else "api_error"
        # Unknown cost: count the worst case so the cap stays conservative.
        billed = failure == "timeout" or exc.may_have_billed
        cap.settle(worst, worst if billed else Decimal(0))
        append_jsonl(out / "errors.jsonl", base | {"failure": failure, "message": str(exc)})
        return failure
    except BaseException:
        cap.settle(worst, worst)
        raise

    latency = round(time.monotonic() - started, 2)
    cost = pricing.cost_usd(reply.model, reply.usage)
    cap.settle(worst, cost)
    usage = {
        "input_tokens": reply.usage.input_tokens,
        "output_tokens": reply.usage.output_tokens,
        "cache_read_input_tokens": reply.usage.cache_read_input_tokens or 0,
        "cache_creation_input_tokens": reply.usage.cache_creation_input_tokens or 0,
    }
    if reply.model != model.model or reply.fallback_used:
        append_jsonl(
            out / "errors.jsonl",
            base | {"failure": "served_model_mismatch", "model": reply.model, "usage": usage},
        )
        return "served_model_mismatch"

    trace = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {
            "role": "assistant",
            "content": reply.output.model_dump_json(indent=1)
            if reply.output
            else (reply.parse_error or ""),
        },
    ]
    (out / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=1))

    if reply.stop_reason == "refusal":
        status, scores = "refused", None
    elif reply.output is None:
        status, scores = ("truncated" if reply.stop_reason == "max_tokens" else "unparsed"), None
    else:
        status, scores = "ok", grade(case, reply.output)
    root = reply.output.root_cause if reply.output else None
    append_jsonl(
        out / "results.jsonl",
        base
        | {
            "prompt": user,
            "status": status,
            "stop_reason": reply.stop_reason,
            "grade": scores,
            "model": reply.model,
            "usage": usage,
            "cost_usd": str(cost),
            "latency_s": latency,
            "meta": {
                "expected": case["expected"],
                "root_cause": root.model_dump() if root else None,
                "refusal_category": reply.refusal_category,
                "request_id": reply.request_id,
            },
        },
    )
    return status


async def run_variant(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    sha = harness_sha()
    approved = json.loads(APPROVAL_FILE.read_text())["sha"] if APPROVAL_FILE.exists() else None
    if args.approve_harness:
        APPROVAL_FILE.write_text(
            json.dumps({"sha": sha, "approved_at": datetime.now(UTC).isoformat()})
        )
    elif sha != approved:
        print(
            "The harness or cases changed since the last approved run. Review them, then rerun "
            "with --approve-harness.",
            file=sys.stderr,
        )
        return 2

    overrides = {k: v for k, v in (("llm_model", args.model), ("llm_effort", args.effort)) if v}
    settings = Settings(**overrides)
    model = build_diagnosis_model(settings)
    if model is None:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    out = RESULTS_DIR / args.variant
    (out / "traces").mkdir(parents=True, exist_ok=True)
    run_info = {
        "model": model.model,
        "effort": model.effort,
        "max_tokens": model.max_tokens,
        "prompt_version": PROMPT_VERSION,
        "harness_sha": sha,
        "cases": len(cases),
        "reps": args.reps,
    }
    info_path = out / "run.json"
    if info_path.exists():
        previous = json.loads(info_path.read_text())
        changed = {
            k
            for k in ("model", "effort", "prompt_version", "harness_sha")
            if previous.get(k) != run_info[k]
        }
        if changed:
            print(
                f"{args.variant} was run with different {sorted(changed)}; use a new variant name.",
                file=sys.stderr,
            )
            return 2
    info_path.write_text(json.dumps(run_info, indent=1))

    done = done_keys(out / "results.jsonl")
    todo = [(c, r) for c in cases for r in range(args.reps) if (c["id"], r) not in done]
    cap = SpendCap(args.max_usd)
    gate = asyncio.Semaphore(args.concurrency)
    print(
        f"{args.variant}: {len(todo)} to run ({len(done)} already done) on {model.model} "
        f"effort={model.effort}, cap ${args.max_usd}"
    )

    async def bounded(case: dict[str, Any], rep: int) -> str:
        async with gate:
            status = await run_case(case, rep, model, out, cap, args.timeout_s)
            print(f"  {case['id']} rep{rep}: {status}", flush=True)
            return status

    started = time.monotonic()
    statuses = await asyncio.gather(*(bounded(c, r) for c, r in todo))
    print(
        f"done in {time.monotonic() - started:.0f}s; spent ${cap.spent}; "
        f"skipped by cap: {statuses.count('skipped')}"
    )
    return 0


def run_check(kind: str) -> int:
    """Push known answers (oracle) or constant answers (null) through the grader."""
    cases = load_cases()
    totals: dict[str, list[float]] = {}
    for case in cases:
        output = oracle_output(case) if kind == "oracle" else constant_output(None)
        for metric, value in grade(case, output).items():
            if value is not None:
                totals.setdefault(metric, []).append(value)
    summary = {m: f"{sum(v) / len(v):.2f} (n={len(v)})" for m, v in totals.items()}
    print(f"{kind} check over {len(cases)} cases: {summary}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", choices=["oracle", "null"])
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--max-usd", type=float, default=2.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=300)
    parser.add_argument("--approve-harness", action="store_true")
    args = parser.parse_args()
    if args.variant != "baseline" and not (
        args.variant.startswith("v") and args.variant[1:].isdigit()
    ):
        parser.error("--variant must be 'baseline' or v<N>")
    sys.exit(run_check(args.check) if args.check else asyncio.run(run_variant(args)))


if __name__ == "__main__":
    main()
