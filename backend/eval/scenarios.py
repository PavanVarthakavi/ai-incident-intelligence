"""Fault scenarios for the diagnosis evaluation.

Each scenario is injected into the demo stack (see capture.py) and frozen as a
case file with the answer known by construction. Incident text is what an
on-call engineer or user would plausibly report: symptoms, not the cause.

Timeouts that shape the cascades: gateway waits 3 s for orders, orders waits
2 s for inventory. Faults on a service apply to all its business endpoints.
"""

from dataclasses import dataclass
from typing import Literal

Service = Literal["gateway", "orders", "inventory"]
BASELINE_RELEASES: dict[str, str] = {"gateway": "1.4.2", "orders": "2.7.0", "inventory": "3.1.5"}


@dataclass(frozen=True)
class Step:
    """A change to the stack. ``deploy`` records a deployment event; ``fault`` does not."""

    kind: Literal["deploy", "fault"]
    service: Service
    version: str | None = None
    latency_ms: int = 0
    error_rate: float = 0.0
    message: str | None = None
    description: str | None = None
    wait_after_s: int = 0  # pause before the next step


@dataclass(frozen=True)
class Scenario:
    id: str
    group: str  # first tag: the reporting group
    tags: tuple[str, ...]
    title: str
    severity: str
    description: str | None
    expected_service: Service | None  # None means no root cause should be named
    expected_release: str | None  # set when a deploy caused the fault
    onset: tuple[Step, ...] = ()  # applied after the healthy baseline, inside the window
    before_window: tuple[Step, ...] = ()  # applied, then settled, before the window opens
    services: tuple[str, ...] | None = None  # incident scope; None means all
    notes: str = ""


def _deploy(service: Service, version: str, **faults) -> Step:
    return Step("deploy", service, version, description=f"Deploy {service} {version}", **faults)


def _fault(service: Service, **faults) -> Step:
    return Step("fault", service, **faults)


SCENARIOS: tuple[Scenario, ...] = (
    # Deploy-caused faults: the root cause must name the service and the release.
    Scenario(
        "F01",
        "deploy-caused",
        ("latency", "cascade"),
        "Checkout requests are failing",
        "high",
        None,
        "inventory",
        "3.2.1",
        onset=(_deploy("inventory", "3.2.1", latency_ms=2500),),
        notes="Exceeds orders' 2 s timeout: orders 504, gateway 502.",
    ),
    Scenario(
        "F02",
        "deploy-caused",
        ("errors",),
        "Checkout is failing intermittently",
        "high",
        None,
        "inventory",
        "3.2.2",
        onset=(_deploy("inventory", "3.2.2", error_rate=0.5, message="connection pool exhausted"),),
    ),
    Scenario(
        "F03",
        "deploy-caused",
        ("errors",),
        "Customers see errors placing orders",
        "high",
        None,
        "orders",
        "2.8.1",
        onset=(_deploy("orders", "2.8.1", error_rate=0.4, message="failed to serialize order"),),
    ),
    Scenario(
        "F04",
        "deploy-caused",
        ("latency", "no-errors"),
        "Checkout is slow",
        "medium",
        None,
        "orders",
        "2.8.2",
        onset=(_deploy("orders", "2.8.2", latency_ms=1200),),
        notes="Below gateway's 3 s timeout: slow but successful.",
    ),
    Scenario(
        "F05",
        "deploy-caused",
        ("errors", "entry-point"),
        "Some page loads fail",
        "high",
        None,
        "gateway",
        "1.5.1",
        onset=(_deploy("gateway", "1.5.1", error_rate=0.3, message="route table not loaded"),),
    ),
    Scenario(
        "F06",
        "deploy-caused",
        ("latency", "entry-point"),
        "The site feels sluggish",
        "medium",
        None,
        "gateway",
        "1.5.2",
        onset=(_deploy("gateway", "1.5.2", latency_ms=800),),
    ),
    Scenario(
        "F07",
        "deploy-caused",
        ("errors", "subtle"),
        "Occasional checkout errors",
        "low",
        None,
        "inventory",
        "3.2.3",
        onset=(_deploy("inventory", "3.2.3", error_rate=0.08, message="deadlock detected"),),
    ),
    Scenario(
        "F08",
        "deploy-caused",
        ("latency", "subtle"),
        "Checkout is a bit slower than usual",
        "low",
        None,
        "inventory",
        "3.2.4",
        onset=(_deploy("inventory", "3.2.4", latency_ms=600),),
        notes="Below the 1 s latency threshold used in evidence summaries.",
    ),
    Scenario(
        "F09",
        "deploy-caused",
        ("latency", "cascade"),
        "Checkout is timing out",
        "high",
        None,
        "orders",
        "2.8.3",
        onset=(_deploy("orders", "2.8.3", latency_ms=2500),),
        notes="Near gateway's 3 s timeout with jitter: some gateway 504s.",
    ),
    # Silent faults: no deploy, so no release should be blamed.
    Scenario(
        "F10",
        "silent",
        ("errors",),
        "Checkout is failing",
        "high",
        None,
        "inventory",
        None,
        onset=(_fault("inventory", error_rate=0.5, message="connection reset by peer"),),
    ),
    Scenario(
        "F11",
        "silent",
        ("latency", "cascade"),
        "Checkout requests are failing",
        "high",
        None,
        "inventory",
        None,
        onset=(_fault("inventory", latency_ms=2500),),
    ),
    Scenario(
        "F12",
        "silent",
        ("errors",),
        "Order errors reported by customers",
        "high",
        None,
        "orders",
        None,
        onset=(_fault("orders", error_rate=0.3, message="database connection refused"),),
    ),
    Scenario(
        "F13",
        "silent",
        ("latency", "entry-point"),
        "Everything is slow",
        "medium",
        None,
        "gateway",
        None,
        onset=(_fault("gateway", latency_ms=1000),),
    ),
    # Decoy deploys: a harmless deploy next to an unrelated fault.
    Scenario(
        "F14",
        "decoy-deploy",
        ("errors", "misleading-report"),
        "Checkout failing since the gateway release",
        "high",
        "Errors started right after gateway was deployed.",
        "inventory",
        None,
        onset=(
            _deploy("gateway", "1.5.3", wait_after_s=30),
            _fault("inventory", error_rate=0.5, message="connection pool exhausted"),
        ),
        notes="The report blames the gateway deploy; the fault is in inventory.",
    ),
    Scenario(
        "F15",
        "decoy-deploy",
        ("latency", "cascade"),
        "Checkout is timing out",
        "high",
        None,
        "inventory",
        None,
        onset=(_deploy("orders", "2.8.4", wait_after_s=30), _fault("inventory", latency_ms=2500)),
    ),
    Scenario(
        "F16",
        "decoy-deploy",
        ("latency", "cascade", "two-deploys"),
        "Checkout requests are failing",
        "high",
        None,
        "inventory",
        "3.2.5",
        onset=(
            _deploy("orders", "2.8.5", wait_after_s=60),
            _deploy("inventory", "3.2.5", latency_ms=2500),
        ),
        notes="Two deploys a minute apart; only the second is bad.",
    ),
    # Healthy windows: no root cause should be named.
    Scenario(
        "H01",
        "healthy",
        ("plain",),
        "Routine check: any problems right now?",
        "low",
        None,
        None,
        None,
    ),
    Scenario(
        "H02",
        "healthy",
        ("recent-deploy",),
        "Verify the inventory deploy went fine",
        "low",
        None,
        None,
        None,
        onset=(_deploy("inventory", "3.2.6"),),
    ),
    Scenario(
        "H03",
        "healthy",
        ("after-rollback",),
        "Is checkout still affected?",
        "medium",
        "Checkout was failing earlier today.",
        None,
        None,
        before_window=(
            _deploy("inventory", "3.2.7", latency_ms=2500, wait_after_s=90),
            _deploy("inventory", "3.1.5"),
        ),
        notes="A bad deploy and its rollback finish before the window opens.",
    ),
    Scenario(
        "H04",
        "healthy",
        ("vague-report",),
        "A user says checkout felt slow",
        "low",
        "One report, no alerts.",
        None,
        None,
    ),
    Scenario(
        "H05",
        "healthy",
        ("misleading-report",),
        "Checkout is completely down",
        "critical",
        "Customers cannot check out at all.",
        None,
        None,
        notes="The report is wrong; the stack is healthy.",
    ),
    Scenario(
        "H06",
        "healthy",
        ("scoped",),
        "Check orders service health",
        "low",
        None,
        None,
        None,
        services=("orders",),
    ),
)

# Cases derived from captured ones by removing a source, as if its backend were down.
DERIVED: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("F17", "F01", "logs", ("latency", "cascade")),
    ("F18", "F10", "traces", ("errors",)),
)
