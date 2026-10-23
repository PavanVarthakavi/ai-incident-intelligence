#!/usr/bin/env python3
"""Control faults and deployments in the local demo stack.

Examples:
    python demo/tools/incidentctl.py status
    python demo/tools/incidentctl.py fault inventory --latency-ms 2500
    python demo/tools/incidentctl.py fault orders --error-rate 0.3 --message "pool exhausted"
    python demo/tools/incidentctl.py deploy inventory 3.2.0 --latency-ms 2500
    python demo/tools/incidentctl.py clear

`deploy` changes the running release (optionally shipping faults with it) and
records a deployment event in OpenSearch, the way a CD pipeline would. `fault`
changes behaviour silently: no deployment event, like an infrastructure problem.
"""

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime

from _http import HttpError, request

SERVICES = {
    "gateway": os.getenv("GATEWAY_URL", "http://localhost:8080"),
    "orders": os.getenv("ORDERS_URL", "http://localhost:8081"),
    "inventory": os.getenv("INVENTORY_URL", "http://localhost:8082"),
}
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
DEPLOY_INDEX = "deploy-events"
ENVIRONMENT = "local-demo"


def _faults(args: argparse.Namespace) -> dict:
    faults = {"latency_ms": args.latency_ms, "error_rate": args.error_rate}
    if args.message:
        faults["error_message"] = args.message
    return faults


def _print_status(status: dict) -> None:
    f = status["faults"]
    detail = "healthy"
    if f["latency_ms"] or f["error_rate"]:
        detail = (
            f"latency={f['latency_ms']}ms error_rate={f['error_rate']} msg={f['error_message']!r}"
        )
    print(f"{status['service']:<10} release={status['release']:<8} {detail}")


def cmd_status(args: argparse.Namespace) -> None:
    for name, url in SERVICES.items():
        try:
            _print_status(request("GET", f"{url}/admin/status"))
        except HttpError as exc:
            print(f"{name:<10} UNREACHABLE ({exc})")


def cmd_fault(args: argparse.Namespace) -> None:
    _print_status(request("PUT", f"{SERVICES[args.service]}/admin/faults", _faults(args)))


def cmd_clear(args: argparse.Namespace) -> None:
    unknown = set(args.services) - set(SERVICES)
    if unknown:
        sys.exit(f"error: unknown service(s): {', '.join(sorted(unknown))}")
    for name in args.services or SERVICES:
        _print_status(request("DELETE", f"{SERVICES[name]}/admin/faults"))


def cmd_deploy(args: argparse.Namespace) -> None:
    url = SERVICES[args.service]
    previous = request("GET", f"{url}/admin/status")["release"]
    status = request(
        "PUT", f"{url}/admin/release", {"version": args.version, "faults": _faults(args)}
    )
    event = {
        "@timestamp": datetime.now(UTC).isoformat(),
        "event_id": str(uuid.uuid4()),
        "service": args.service,
        "version": args.version,
        "previous_version": previous,
        "environment": ENVIRONMENT,
        "change_type": "deploy",
        "author": args.author,
        "description": args.description or f"Deploy {args.service} {args.version}",
    }
    request("POST", f"{OPENSEARCH_URL}/{DEPLOY_INDEX}/_doc?refresh=true", event)
    _print_status(status)
    print(f"recorded deploy event {event['event_id']} ({previous} -> {args.version})")


def _add_fault_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--latency-ms", type=int, default=0, help="Mean added latency.")
    parser.add_argument("--error-rate", type=float, default=0.0, help="Failure probability 0-1.")
    parser.add_argument("--message", help="Error log message emitted when a failure fires.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="Show release and faults per service.").set_defaults(
        func=cmd_status
    )

    fault = commands.add_parser("fault", help="Inject a fault without a deployment.")
    fault.add_argument("service", choices=SERVICES)
    _add_fault_args(fault)
    fault.set_defaults(func=cmd_fault)

    clear = commands.add_parser("clear", help="Remove faults (all services by default).")
    clear.add_argument("services", nargs="*", metavar="service", help=", ".join(SERVICES))
    clear.set_defaults(func=cmd_clear)

    deploy = commands.add_parser("deploy", help="Simulate a deployment and record the event.")
    deploy.add_argument("service", choices=SERVICES)
    deploy.add_argument("version")
    deploy.add_argument("--description")
    deploy.add_argument("--author", default="ci-pipeline")
    _add_fault_args(deploy)
    deploy.set_defaults(func=cmd_deploy)

    args = parser.parse_args()
    try:
        args.func(args)
    except HttpError as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
