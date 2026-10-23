"""Construction of backend clients and evidence collectors from settings."""

from dataclasses import dataclass
from typing import Annotated, Self

import httpx
from fastapi import Depends, Request

from app.config import Settings
from app.evidence.deployments import DeploymentsCollector
from app.evidence.logs import LogsCollector
from app.evidence.metrics import MetricsCollector
from app.evidence.service import EvidenceService
from app.evidence.traces import TracesCollector
from app.integrations.jaeger import JaegerClient
from app.integrations.opensearch import OpenSearchClient
from app.integrations.prometheus import PrometheusClient


@dataclass(frozen=True)
class Backends:
    prometheus: PrometheusClient
    jaeger: JaegerClient
    opensearch: OpenSearchClient
    evidence: EvidenceService

    @classmethod
    def create(cls, settings: Settings, http: httpx.AsyncClient) -> Self:
        prometheus = PrometheusClient(settings.prometheus_url, http)
        jaeger = JaegerClient(settings.jaeger_url, http)
        opensearch = OpenSearchClient(settings.opensearch_url, http)
        evidence = EvidenceService(
            [
                MetricsCollector(prometheus),
                TracesCollector(jaeger),
                LogsCollector(opensearch, settings.logs_index),
                DeploymentsCollector(opensearch, settings.deploy_events_index),
            ]
        )
        return cls(prometheus, jaeger, opensearch, evidence)


def get_backends(request: Request) -> Backends:
    return request.app.state.backends


BackendsDep = Annotated[Backends, Depends(get_backends)]
