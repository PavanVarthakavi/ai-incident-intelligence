"""Pure evidence logic: windows, IDs, thresholds, and span self time."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.evidence.metrics import first_crossing, onset_text, step_for
from app.evidence.models import Evidence, EvidenceSource, TimeWindow
from app.evidence.traces import self_time
from app.integrations.jaeger import Span

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def span(span_id: str, start_s: float, duration_s: float, parent: str | None = None) -> Span:
    return Span(
        span_id=span_id,
        parent_id=parent,
        service="svc",
        operation="op",
        start=at(start_s),
        duration_us=int(duration_s * 1_000_000),
        error=False,
        status_code=None,
        attributes={},
    )


class TestTimeWindow:
    def test_valid(self) -> None:
        assert TimeWindow(start=at(0), end=at(60)).duration == timedelta(minutes=1)

    @pytest.mark.parametrize(
        ("start", "end"),
        [(at(60), at(0)), (at(0), at(0)), (at(0), at(0) + timedelta(hours=25))],
    )
    def test_invalid_bounds(self, start: datetime, end: datetime) -> None:
        with pytest.raises(ValidationError):
            TimeWindow(start=start, end=end)

    def test_requires_timezone(self) -> None:
        with pytest.raises(ValidationError):
            TimeWindow(start=datetime(2026, 1, 1), end=datetime(2026, 1, 2))


def test_evidence_ids_are_stable_and_distinct() -> None:
    window = TimeWindow(start=at(0), end=at(60))

    def build(key: str) -> Evidence:
        return Evidence.build(
            source=EvidenceSource.LOGS, kind="k", key=key, window=window, summary="s", query="q"
        )

    assert build("a").id == build("a").id
    assert build("a").id != build("b").id
    assert build("a").id.startswith("ev-")


def test_step_targets_about_sixty_points_with_floor() -> None:
    assert step_for(TimeWindow(start=at(0), end=at(3600))) == 60
    assert step_for(TimeWindow(start=at(0), end=at(60))) == 15


class TestFirstCrossing:
    def test_rising_edge(self) -> None:
        points = [(at(0), 0.0), (at(15), 0.01), (at(30), 0.4), (at(45), 0.9)]
        assert first_crossing(points, 0.05) == at(30)

    def test_already_above_at_start(self) -> None:
        points = [(at(0), 0.5), (at(15), 0.6)]
        onset = first_crossing(points, 0.05)
        assert onset == at(0)
        assert onset_text(onset, points, "5%") == "already at or above 5% at window start"

    def test_never_crosses(self) -> None:
        assert first_crossing([(at(0), 0.0), (at(15), 0.01)], 0.05) is None


class TestSelfTime:
    def test_no_children(self) -> None:
        assert self_time(span("a", 0, 2), []) == timedelta(seconds=2)

    def test_overlapping_children_counted_once(self) -> None:
        parent = span("a", 0, 10)
        children = [span("b", 1, 4, "a"), span("c", 3, 4, "a")]  # union covers 1s..7s
        assert self_time(parent, children) == timedelta(seconds=4)

    def test_child_outliving_parent_is_clipped(self) -> None:
        # A caller that times out at 2s while the callee keeps running for 2.5s.
        parent = span("a", 0, 2)
        child = span("b", 0.5, 2.5, "a")
        assert self_time(parent, [child]) == timedelta(seconds=0.5)
