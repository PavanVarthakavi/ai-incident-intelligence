"""Command-line entry point.

python -m shop serve gateway --port 8000
python -m shop loadgen --target http://localhost:8080 --rps 2
"""

import argparse
import asyncio
from typing import get_args

import uvicorn

from shop import loadgen
from shop.app import ServiceName, create_app
from shop.settings import Settings
from shop.telemetry import (
    configure_logging,
    configure_telemetry,
    instrument_app,
    shutdown_telemetry,
)


def _serve(service: ServiceName, host: str, port: int) -> None:
    settings = Settings()
    configure_telemetry(service_name=service, service_version=settings.service_version)
    app = create_app(service, settings)
    instrument_app(app)
    try:
        # log_config=None keeps our logging setup, so uvicorn logs also reach OpenTelemetry.
        uvicorn.run(app, host=host, port=port, access_log=False, log_config=None)
    finally:
        shutdown_telemetry()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m shop")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="Run one demo service.")
    serve.add_argument("service", choices=get_args(ServiceName))
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    load = commands.add_parser("loadgen", help="Send synthetic traffic to the gateway.")
    load.add_argument("--target", default="http://localhost:8080")
    load.add_argument("--rps", type=float, default=2.0, help="Average requests per second.")
    load.add_argument("--timeout", type=float, default=10.0)

    args = parser.parse_args()
    if args.command == "serve":
        _serve(args.service, args.host, args.port)
    else:
        configure_logging()
        asyncio.run(loadgen.run(args.target.rstrip("/"), args.rps, args.timeout))


if __name__ == "__main__":
    main()
