"""Inject each scenario into the running demo stack and freeze it as a case file.

    caffeinate -i python -m eval.capture   # all scenarios (about 2 hours, keep the host awake)
    python -m eval.capture F01 H03         # selected scenarios
    python -m eval.capture --derived-only  # rebuild derived cases from captured ones

Free: no model calls. Requires `docker compose up` and the backend settings in
.env. Evidence is collected with the backend's own collectors, exactly as an
incident would be. Deploy events created by other scenarios are filtered out so
cases do not leak into each other.
"""

import argparse
import asyncio
import json
import subprocess
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.backends import Backends
from app.config import Settings
from app.evidence.models import TimeWindow
from eval.scenarios import BASELINE_RELEASES, DERIVED, SCENARIOS, Scenario, Step

CASES_DIR = Path(__file__).parent / "cases"
SERVICE_URLS = {
    "gateway": "http://localhost:8080",
    "orders": "http://localhost:8081",
    "inventory": "http://localhost:8082",
}
SETTLE_S = 90  # after reset, so the previous scenario ages out of rate windows
BASELINE_S = 90  # healthy traffic inside the window before the fault
OBSERVE_S = 150  # symptoms inside the window after the fault
WINDOW_SLACK_S = 30  # a longer window means the host slept and the telemetry is distorted


def log(message: str) -> None:
    print(f"{datetime.now(UTC).strftime('%H:%M:%S')} {message}", flush=True)


class Stack:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    async def reset(self) -> None:
        """Baseline releases, no faults, without recording deploy events."""
        for service, url in SERVICE_URLS.items():
            response = await self.http.put(
                f"{url}/admin/release", json={"version": BASELINE_RELEASES[service]}
            )
            response.raise_for_status()

    async def apply(self, step: Step) -> str | None:
        """Apply a step; return the deploy event ID it recorded, if any."""
        url = SERVICE_URLS[step.service]
        faults = {"latency_ms": step.latency_ms, "error_rate": step.error_rate}
        if step.message:
            faults["error_message"] = step.message
        if step.kind == "fault":
            (await self.http.put(f"{url}/admin/faults", json=faults)).raise_for_status()
            return None
        previous = (await self.http.get(f"{url}/admin/status")).json()["release"]
        release = {"version": step.version, "faults": faults}
        (await self.http.put(f"{url}/admin/release", json=release)).raise_for_status()
        event_id = str(uuid.uuid4())
        event = {
            "@timestamp": datetime.now(UTC).isoformat(),
            "event_id": event_id,
            "service": step.service,
            "version": step.version,
            "previous_version": previous,
            "environment": "local-demo",
            "change_type": "deploy",
            "author": "ci-pipeline",
            "description": step.description,
        }
        index = f"{self.settings.opensearch_url}/{self.settings.deploy_events_index}"
        (await self.http.post(f"{index}/_doc?refresh=true", json=event)).raise_for_status()
        return event_id


async def run_steps(stack: Stack, steps: tuple[Step, ...], events: set[str]) -> None:
    for step in steps:
        event_id = await stack.apply(step)
        if event_id:
            events.add(event_id)
        log(f"  applied {step.kind} {step.service} {step.version or ''}".rstrip())
        await asyncio.sleep(step.wait_after_s)


async def capture(scenario: Scenario, stack: Stack, backends: Backends, commit: str) -> dict:
    log(f"{scenario.id}: reset, settle {SETTLE_S}s")
    await stack.reset()
    await asyncio.sleep(SETTLE_S)
    events: set[str] = set()
    if scenario.before_window:
        await run_steps(stack, scenario.before_window, events)
        await asyncio.sleep(SETTLE_S)

    start = datetime.now(UTC)
    await asyncio.sleep(BASELINE_S)
    await run_steps(stack, scenario.onset, events)
    await asyncio.sleep(OBSERVE_S)
    end = datetime.now(UTC)
    planned = BASELINE_S + OBSERVE_S + sum(step.wait_after_s for step in scenario.onset)
    if (end - start).total_seconds() > planned + WINDOW_SLACK_S:
        raise RuntimeError(
            f"{scenario.id}: window took {(end - start).total_seconds():.0f}s, planned "
            f"{planned}s; the host probably slept. Rerun with `caffeinate -i`."
        )

    services = list(scenario.services) if scenario.services else None
    bundle = await backends.evidence.collect(TimeWindow(start=start, end=end), services)
    if bundle.errors:
        raise RuntimeError(f"{scenario.id}: collection errors {bundle.errors}")
    evidence = [
        e for e in bundle.evidence if e.kind != "deployment" or e.data.get("event_id") in events
    ]
    await stack.reset()
    log(f"{scenario.id}: captured {len(evidence)} evidence items")
    return {
        "id": scenario.id,
        "tags": [scenario.group, *scenario.tags],
        "incident": {
            "title": scenario.title,
            "severity": scenario.severity,
            "description": scenario.description,
            "services": services,
        },
        "snapshot": {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "collected_at": bundle.collected_at.isoformat(),
            "source_errors": [],
            "evidence": [e.model_dump(mode="json") for e in evidence],
        },
        "expected": {
            "root_cause_service": scenario.expected_service,
            "release": scenario.expected_release,
        },
        "scenario": {
            "before_window": [asdict(s) for s in scenario.before_window],
            "onset": [asdict(s) for s in scenario.onset],
            "notes": scenario.notes,
        },
        "provenance": {"captured_at": end.isoformat(), "git_commit": commit},
    }


def write_case(case: dict) -> None:
    (CASES_DIR / f"{case['id']}.json").write_text(json.dumps(case, indent=1) + "\n")


def build_derived() -> None:
    for case_id, base_id, source, tags in DERIVED:
        base_path = CASES_DIR / f"{base_id}.json"
        if not base_path.exists():
            log(f"{case_id}: skipped, {base_id} not captured yet")
            continue
        base = json.loads(base_path.read_text())
        snapshot = base["snapshot"]
        derived = base | {
            "id": case_id,
            "tags": ["missing-source", *tags],
            "snapshot": snapshot
            | {
                "evidence": [e for e in snapshot["evidence"] if e["source"] != source],
                "source_errors": [
                    {"source": source, "message": f"{source}: timed out calling the backend"}
                ],
            },
            "provenance": base["provenance"] | {"derived_from": base_id, "removed": source},
        }
        write_case(derived)
        log(f"{case_id}: derived from {base_id} without {source}")


async def main(ids: list[str], derived_only: bool) -> None:
    CASES_DIR.mkdir(exist_ok=True)
    if not derived_only:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        settings = Settings()
        selected = [s for s in SCENARIOS if not ids or s.id in ids]
        async with httpx.AsyncClient(timeout=30) as http:
            stack = Stack(http, settings)
            backends = Backends.create(settings, http)
            for scenario in selected:
                write_case(await capture(scenario, stack, backends, commit))
    build_derived()


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--derived-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.ids, args.derived_only))


if __name__ == "__main__":
    cli()
