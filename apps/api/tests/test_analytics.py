from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import InverterTelemetry
from app.services.analytics import integrate_metric


def point(at: datetime, power: float) -> InverterTelemetry:
    return InverterTelemetry(
        recorded_at=at,
        pv_power_w=power,
        quality_flags=[],
        quality_details={},
    )


def test_trapezoidal_integration() -> None:
    start = datetime(2026, 8, 2, tzinfo=UTC)
    samples = [point(start, 0), point(start + timedelta(seconds=10), 100)]
    energy, seconds = integrate_metric(
        samples, "pv_power_w", start, start + timedelta(minutes=1), 60
    )
    assert energy == pytest.approx(0.138888, rel=1e-4)
    assert seconds == 10


def test_large_gap_is_not_integrated() -> None:
    start = datetime(2026, 8, 2, tzinfo=UTC)
    samples = [point(start, 500), point(start + timedelta(seconds=61), 500)]
    energy, seconds = integrate_metric(
        samples, "pv_power_w", start, start + timedelta(minutes=2), 60
    )
    assert energy == 0
    assert seconds == 0


def test_interval_is_clipped_at_bucket_boundary() -> None:
    start = datetime(2026, 8, 2, tzinfo=UTC)
    samples = [point(start - timedelta(seconds=5), 100), point(start + timedelta(seconds=5), 100)]
    energy, seconds = integrate_metric(samples, "pv_power_w", start, start + timedelta(hours=1), 60)
    assert energy == pytest.approx(100 * 5 / 3600)
    assert seconds == 5
