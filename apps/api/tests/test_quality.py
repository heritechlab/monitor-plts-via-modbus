from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.telemetry import MetricsPayload, TelemetryPayload
from app.services.quality import evaluate_quality


def make_payload(**metrics) -> TelemetryPayload:
    return TelemetryPayload(
        sample_id=uuid4(),
        device_slug="prime-rumah-01",
        recorded_at=datetime.now(UTC),
        metrics=MetricsPayload(**metrics),
        raw_registers={f"0x{0x3000 + index:04X}": 0 for index in range(32)},
    )


def test_out_of_range_is_field_specific() -> None:
    flags, details = evaluate_quality(
        make_payload(pv_voltage_v=80, pv_current_a=10, pv_power_w=800, battery_voltage_v=30.8)
    )
    assert "out_of_range" in flags
    assert set(details["invalid_metrics"]) == {"battery_voltage_v"}


def test_pv_mismatch_is_flagged() -> None:
    flags, _ = evaluate_quality(make_payload(pv_voltage_v=80, pv_current_a=10, pv_power_w=400))
    assert "decoded_value_mismatch" in flags
