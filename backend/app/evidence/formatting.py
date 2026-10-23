"""Consistent number and time formatting for evidence summaries."""

from datetime import UTC, datetime


def ts(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def secs(value: float) -> str:
    return f"{value * 1000:.0f}ms" if value < 1 else f"{value:.2f}s"
