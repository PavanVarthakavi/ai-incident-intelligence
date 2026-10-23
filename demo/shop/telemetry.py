"""OpenTelemetry setup for demo services.

Traces, metrics, and logs are exported over OTLP/HTTP to the collector. The
endpoint and export intervals come from the standard ``OTEL_*`` environment
variables, so nothing here is environment-specific. Set ``OTEL_SDK_DISABLED=true``
to run without exporting (as the tests do).
"""

import logging
import os
import sys

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAMESPACE = "demo-shop"
# Health and admin traffic is operational noise, not user traffic.
EXCLUDED_URLS = "health,admin"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs every request at INFO, which would flood the log backend.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def configure_telemetry(service_name: str, service_version: str) -> None:
    configure_logging()
    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": SERVICE_NAMESPACE,
            "service.version": service_version,
            "deployment.environment.name": os.getenv("DEPLOYMENT_ENVIRONMENT", "local-demo"),
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
        )
    )

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))

    HTTPXClientInstrumentor().instrument()


def instrument_app(app: FastAPI) -> None:
    # Skip per-message ASGI "receive"/"send" spans: they add noise, not evidence.
    FastAPIInstrumentor.instrument_app(
        app, excluded_urls=EXCLUDED_URLS, exclude_spans=["receive", "send"]
    )


def shutdown_telemetry() -> None:
    """Flush buffered telemetry so the last spans/logs before exit are not lost."""
    providers = (trace.get_tracer_provider(), metrics.get_meter_provider(), get_logger_provider())
    for provider in providers:
        # The default no-op providers have no shutdown method.
        shutdown = getattr(provider, "shutdown", None)
        if shutdown:
            shutdown()
