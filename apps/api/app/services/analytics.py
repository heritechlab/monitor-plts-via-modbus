from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Device, InverterTelemetry


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def metric_is_valid(sample: InverterTelemetry, field: str) -> bool:
    value = getattr(sample, field)
    if value is None:
        return False
    details = sample.quality_details or {}
    invalid = details.get("invalid_metrics", {})
    return field not in invalid and "timestamp_in_future" not in (sample.quality_flags or [])


def integrate_metric(
    samples: list[InverterTelemetry],
    field: str,
    window_start: datetime,
    window_end: datetime,
    max_gap_seconds: int,
) -> tuple[float, float]:
    """Integrate a metric while clipping linear intervals to the requested window."""
    energy_wh = 0.0
    valid_seconds = 0.0
    ordered = sorted(samples, key=lambda item: as_utc(item.recorded_at))
    start = as_utc(window_start)
    end = as_utc(window_end)

    for left, right in zip(ordered, ordered[1:], strict=False):
        left_at = as_utc(left.recorded_at)
        right_at = as_utc(right.recorded_at)
        delta = (right_at - left_at).total_seconds()
        if delta <= 0 or delta > max_gap_seconds:
            continue
        if not metric_is_valid(left, field) or not metric_is_valid(right, field):
            continue

        clipped_start = max(left_at, start)
        clipped_end = min(right_at, end)
        clipped_seconds = (clipped_end - clipped_start).total_seconds()
        if clipped_seconds <= 0:
            continue

        left_value = float(getattr(left, field))
        right_value = float(getattr(right, field))
        start_ratio = (clipped_start - left_at).total_seconds() / delta
        end_ratio = (clipped_end - left_at).total_seconds() / delta
        start_value = left_value + (right_value - left_value) * start_ratio
        end_value = left_value + (right_value - left_value) * end_ratio
        energy_wh += ((start_value + end_value) / 2) * clipped_seconds / 3600
        valid_seconds += clipped_seconds
    return energy_wh, valid_seconds


async def load_window(
    session: AsyncSession, device_id, start: datetime, end: datetime
) -> list[InverterTelemetry]:
    margin = timedelta(seconds=settings.max_integration_gap_seconds)
    return list(
        (
            await session.scalars(
                select(InverterTelemetry)
                .where(
                    InverterTelemetry.device_id == device_id,
                    InverterTelemetry.recorded_at >= as_utc(start) - margin,
                    InverterTelemetry.recorded_at <= as_utc(end) + margin,
                )
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()
    )


def local_day_bounds(local_date: date, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(local_date, time.min, tzinfo=zone)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def minute_peak(samples: list[InverterTelemetry], field: str) -> float | None:
    groups: dict[datetime, list[float]] = defaultdict(list)
    for sample in samples:
        if metric_is_valid(sample, field):
            bucket = as_utc(sample.recorded_at).replace(second=0, microsecond=0)
            groups[bucket].append(float(getattr(sample, field)))
    return max((mean(values) for values in groups.values()), default=None)


def threshold_minutes(
    samples: list[InverterTelemetry], field: str, threshold: float, start: datetime, end: datetime
) -> float:
    seconds = 0.0
    ordered = sorted(samples, key=lambda item: as_utc(item.recorded_at))
    for left, right in zip(ordered, ordered[1:], strict=False):
        if not metric_is_valid(left, field) or not metric_is_valid(right, field):
            continue
        left_at, right_at = as_utc(left.recorded_at), as_utc(right.recorded_at)
        delta = (right_at - left_at).total_seconds()
        if delta <= 0 or delta > settings.max_integration_gap_seconds:
            continue
        if (
            float(left.__getattribute__(field)) >= threshold
            and float(right.__getattribute__(field)) >= threshold
        ):
            seconds += max(0.0, (min(right_at, end) - max(left_at, start)).total_seconds())
    return seconds / 60


async def build_daily_summary(session: AsyncSession, device: Device, local_date: date) -> dict:
    start, full_end = local_day_bounds(local_date, device.timezone)
    now = datetime.now(UTC)
    end = (
        min(full_end, now)
        if local_date == now.astimezone(ZoneInfo(device.timezone)).date()
        else full_end
    )
    if end <= start:
        end = full_end
    samples = await load_window(session, device.id, start, end)
    visible = [item for item in samples if start <= as_utc(item.recorded_at) < end]

    pv_wh, pv_seconds = integrate_metric(
        samples, "pv_power_w", start, end, settings.max_integration_gap_seconds
    )
    # Kolom lama tetap dipakai agar database existing tidak memerlukan migrasi.
    # Pengujian lapangan menunjukkan 0x3005 adalah estimasi beban semu, bukan watt aktif.
    ac_load_vah, ac_load_seconds = integrate_metric(
        samples, "ac_output_power_w", start, end, settings.max_integration_gap_seconds
    )
    expected_seconds = max((end - start).total_seconds(), 1)
    pv_values = [float(item.pv_power_w) for item in visible if metric_is_valid(item, "pv_power_w")]
    ac_values = [
        float(item.ac_output_power_w)
        for item in visible
        if metric_is_valid(item, "ac_output_power_w")
    ]
    battery_values = [
        float(item.battery_voltage_v)
        for item in visible
        if metric_is_valid(item, "battery_voltage_v")
    ]
    temperature_values = [
        float(item.inverter_temperature_c)
        for item in visible
        if metric_is_valid(item, "inverter_temperature_c")
    ]

    gaps = []
    for left, right in zip(visible, visible[1:], strict=False):
        seconds = (as_utc(right.recorded_at) - as_utc(left.recorded_at)).total_seconds()
        if seconds > settings.max_integration_gap_seconds:
            gaps.append(
                {
                    "from": as_utc(left.recorded_at).isoformat(),
                    "to": as_utc(right.recorded_at).isoformat(),
                    "seconds": seconds,
                }
            )

    return {
        "date": local_date.isoformat(),
        "timezone": device.timezone,
        "pv_energy_kwh": round(pv_wh / 1000, 4),
        "ac_load_estimate_kvah": round(ac_load_vah / 1000, 4),
        "ac_output_energy_kwh": None,
        "estimated_surplus_kwh": None,
        "equivalent_saving_idr": round(pv_wh / 1000 * device.tariff_idr_per_kwh),
        "peak_pv_raw_w": max(pv_values, default=None),
        "peak_pv_1m_avg_w": minute_peak(visible, "pv_power_w"),
        "peak_ac_load_estimate_raw_va": max(ac_values, default=None),
        "peak_ac_load_estimate_1m_avg_va": minute_peak(visible, "ac_output_power_w"),
        "peak_output_raw_w": None,
        "peak_output_1m_avg_w": None,
        "max_temperature_c": max(temperature_values, default=None),
        "min_battery_voltage_v": min(battery_values, default=None),
        "max_battery_voltage_v": max(battery_values, default=None),
        "pv_above_500_minutes": round(threshold_minutes(samples, "pv_power_w", 500, start, end), 1),
        "pv_above_800_minutes": round(threshold_minutes(samples, "pv_power_w", 800, start, end), 1),
        "pv_above_1000_minutes": round(
            threshold_minutes(samples, "pv_power_w", 1000, start, end), 1
        ),
        "sample_count": len(visible),
        "invalid_sample_count": sum(bool(item.quality_flags) for item in visible),
        "pv_coverage_percent": round(min(pv_seconds / expected_seconds * 100, 100), 2),
        "ac_load_coverage_percent": round(
            min(ac_load_seconds / expected_seconds * 100, 100), 2
        ),
        "ac_coverage_percent": round(min(ac_load_seconds / expected_seconds * 100, 100), 2),
        "surplus_coverage_percent": None,
        "first_sample_at": as_utc(visible[0].recorded_at).isoformat() if visible else None,
        "last_sample_at": as_utc(visible[-1].recorded_at).isoformat() if visible else None,
        "gaps": gaps,
    }


async def build_monthly_summary(
    session: AsyncSession, device: Device, year: int, month: int
) -> dict:
    days = monthrange(year, month)[1]
    today = datetime.now(ZoneInfo(device.timezone)).date()
    daily = []
    for day in range(1, days + 1):
        current = date(year, month, day)
        if current > today:
            break
        daily.append(await build_daily_summary(session, device, current))

    available = [item for item in daily if item["sample_count"] > 0]
    best = max(available, key=lambda item: item["pv_energy_kwh"], default=None)
    lowest = min(available, key=lambda item: item["pv_energy_kwh"], default=None)
    total_pv = sum(item["pv_energy_kwh"] for item in available)
    total_ac_load = sum(item["ac_load_estimate_kvah"] for item in available)
    return {
        "month": f"{year:04d}-{month:02d}",
        "timezone": device.timezone,
        "pv_energy_kwh": round(total_pv, 3),
        "ac_load_estimate_kvah": round(total_ac_load, 3),
        "ac_output_energy_kwh": None,
        "estimated_surplus_kwh": None,
        "average_daily_pv_kwh": round(total_pv / len(available), 3) if available else 0,
        "equivalent_saving_idr": round(total_pv * device.tariff_idr_per_kwh),
        "best_day": best,
        "lowest_day": lowest,
        "days_with_data": len(available),
        "days": daily,
    }
