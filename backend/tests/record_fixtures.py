"""Record backend responses from the running demo stack into tests/fixtures/.

    python -m tests.record_fixtures --minutes 10

Run while an incident scenario is active so fixtures contain interesting data
(see docs/demo-environment.md). The data is synthetic. Large Jaeger responses
are trimmed to keep fixtures small.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx

from app.backends import Backends
from app.config import Settings
from app.evidence.models import TimeWindow
from app.integrations.base import BackendError
from tests.fakes import FIXTURES, route_key

MAX_TRACES_PER_RESPONSE = 4
# Span tags the collectors read; everything else is dropped to keep fixtures small.
KEPT_SPAN_TAGS = {"error", "otel.status_code", "http.response.status_code", "span.kind"}
KEPT_SPAN_TAG_PREFIXES = ("app.", "http.route")


def trim(key: str, body: dict) -> dict:
    if key.startswith("jaeger_traces_") and body.get("data"):
        body["data"] = body["data"][:MAX_TRACES_PER_RESPONSE]
        for trace in body["data"]:
            for process in trace["processes"].values():
                process["tags"] = []
            for span in trace["spans"]:
                span["tags"] = [
                    t
                    for t in span["tags"]
                    if t["key"] in KEPT_SPAN_TAGS or t["key"].startswith(KEPT_SPAN_TAG_PREFIXES)
                ]
    return body


async def record(minutes: int) -> None:
    end = datetime.now(UTC).replace(microsecond=0)
    window = TimeWindow(start=end - timedelta(minutes=minutes), end=end)
    captured: dict[str, dict] = {}

    async def capture(response: httpx.Response) -> None:
        await response.aread()
        key = route_key(response.request)
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}
        captured[key] = {"status": response.status_code, "body": trim(key, body)}

    async with httpx.AsyncClient(event_hooks={"response": [capture]}, timeout=30) as http:
        backends = Backends.create(Settings(), http)
        for client in (backends.prometheus, backends.jaeger, backends.opensearch):
            try:
                await client.ping()
            except BackendError as exc:
                raise SystemExit(f"backend not reachable: {exc}") from None
        await backends.evidence.collect(window, None)

    FIXTURES.mkdir(exist_ok=True)
    for key, value in sorted(captured.items()):
        (FIXTURES / f"{key}.json").write_text(json.dumps(value, sort_keys=True) + "\n")
    meta = {"window": {"start": window.start.isoformat(), "end": window.end.isoformat()}}
    (FIXTURES / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"recorded {len(captured)} responses for {window.start} .. {window.end}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=10)
    asyncio.run(record(parser.parse_args().minutes))


if __name__ == "__main__":
    main()
