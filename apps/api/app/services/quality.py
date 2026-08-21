from datetime import UTC, datetime, timedelta
from math import isclose

from app.core.config import settings
from app.schemas.telemetry import TelemetryPayload

RANGES: dict[str, tuple[float, float]] = {
    "pv_voltage_v": (0, 120),
    "pv_current_a": (0, 20),
    "pv_power_w": (0, 1500),
    "battery_voltage_v": (20, 30),
    "ac_output_voltage_v": (180, 260),
    "ac_output_current_a": (0, 10),
    "ac_output_power_w": (0, 1200),
    "load_percent": (0, 150),
    "inverter_temperature_c": (-20, 100),
    "grid_active": (0, 1),
    "grid_voltage_v": (0, 300),
    "grid_frequency_hz": (0, 70),
    "inverter_soc_percent": (0, 100),
}


def evaluate_quality(
    payload: TelemetryPayload, now: datetime | None = None
) -> tuple[list[str], dict]:
    now = now or datetime.now(UTC)
    recorded = payload.recorded_at.astimezone(UTC)
    flags: list[str] = []
    invalid_metrics: dict[str, dict[str, float]] = {}

    metrics = payload.metrics.model_dump()
    for field, value in metrics.items():
        if value is None:
            continue
        minimum, maximum = RANGES[field]
        if not minimum <= value <= maximum:
            invalid_metrics[field] = {"value": value, "min": minimum, "max": maximum}

    if invalid_metrics:
        flags.append("out_of_range")
    if recorded > now + timedelta(seconds=settings.future_tolerance_seconds):
        flags.append("timestamp_in_future")
    if recorded < now - timedelta(hours=settings.old_sample_after_hours):
        flags.append("timestamp_too_old")

    expected_pv = None
    if payload.metrics.pv_voltage_v is not None and payload.metrics.pv_current_a is not None:
        expected_pv = payload.metrics.pv_voltage_v * payload.metrics.pv_current_a
        if payload.metrics.pv_power_w is not None and not isclose(
            payload.metrics.pv_power_w, expected_pv, rel_tol=0.01, abs_tol=1.0
        ):
            flags.append("decoded_value_mismatch")

    details: dict = {"invalid_metrics": invalid_metrics}
    if expected_pv is not None:
        details["expected_pv_power_w"] = round(expected_pv, 3)
    return flags, details
