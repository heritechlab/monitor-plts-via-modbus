from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, InverterTelemetry
from app.services.analytics import as_utc

KNOWN_REGISTERS: dict[str, dict[str, Any]] = {
    "0x3001": {
        "name": "Tegangan output AC",
        "unit": "V",
        "scale": "raw / 10",
        "metric": "ac_output_voltage_v",
    },
    "0x3002": {
        "name": "Tegangan baterai",
        "unit": "V",
        "scale": "raw / 10",
        "metric": "battery_voltage_v",
    },
    "0x3003": {
        "name": "Arus output AC",
        "unit": "A",
        "scale": "raw / 10",
        "metric": "ac_output_current_a",
    },
    "0x3004": {
        "name": "Beban inverter",
        "unit": "%",
        "scale": "raw",
        "metric": "load_percent",
    },
    "0x3005": {
        "name": "Beban AC estimasi",
        "unit": "VA",
        "scale": "raw (estimasi)",
        "metric": "ac_output_power_w",
    },
    "0x3009": {
        "name": "Suhu inverter",
        "unit": "°C",
        "scale": "raw",
        "metric": "inverter_temperature_c",
    },
    "0x3010": {
        "name": "Arus PV",
        "unit": "A",
        "scale": "raw / 10",
        "metric": "pv_current_a",
    },
    "0x3012": {
        "name": "Tegangan PV",
        "unit": "V",
        "scale": "raw / 10",
        "metric": "pv_voltage_v",
    },
}

REFERENCE_METRICS = {
    "pv_voltage_v": "tegangan PV",
    "pv_current_a": "arus PV",
    "battery_voltage_v": "tegangan baterai",
    "ac_output_voltage_v": "tegangan AC",
    "ac_output_current_a": "arus AC",
    "load_percent": "beban inverter",
    "inverter_temperature_c": "suhu inverter",
}


def pearson_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    if denominator == 0:
        return None
    return numerator / denominator


def analyze_register_rows(rows: list[InverterTelemetry]) -> list[dict[str, Any]]:
    if not rows:
        return []

    addresses = sorted(
        {
            address
            for row in rows
            for address in (row.raw_registers or {}).keys()
        },
        key=lambda value: int(value, 16),
    )
    latest = rows[-1]
    result = []

    for address in addresses:
        values = [
            float(row.raw_registers[address])
            for row in rows
            if address in (row.raw_registers or {})
        ]
        changes = sum(left != right for left, right in zip(values, values[1:], strict=False))
        correlations = []
        for metric, label in REFERENCE_METRICS.items():
            raw_values = []
            metric_values = []
            for row in rows:
                raw = (row.raw_registers or {}).get(address)
                metric_value = getattr(row, metric)
                if raw is not None and metric_value is not None:
                    raw_values.append(float(raw))
                    metric_values.append(float(metric_value))
            coefficient = pearson_correlation(raw_values, metric_values)
            if coefficient is not None:
                correlations.append(
                    {
                        "metric": metric,
                        "label": label,
                        "coefficient": round(coefficient, 3),
                    }
                )

        strongest = max(
            correlations,
            key=lambda item: abs(item["coefficient"]),
            default=None,
        )
        definition = KNOWN_REGISTERS.get(address)
        is_candidate = (
            definition is None
            and changes > 0
            and len(values) >= 10
            and strongest is not None
            and abs(strongest["coefficient"]) >= 0.8
        )
        latest_raw = (latest.raw_registers or {}).get(address)
        decoded_value = (
            getattr(latest, definition["metric"])
            if definition and latest_raw is not None
            else None
        )
        result.append(
            {
                "address": address,
                "status": "known" if definition else "candidate" if is_candidate else "unknown",
                "name": definition["name"] if definition else None,
                "unit": definition["unit"] if definition else None,
                "scale": definition["scale"] if definition else None,
                "latest_raw": latest_raw,
                "decoded_value": decoded_value,
                "min_raw": int(min(values)),
                "max_raw": int(max(values)),
                "distinct_values": len(set(values)),
                "changes": changes,
                "activity": (
                    "zero"
                    if max(values) == 0 and min(values) == 0
                    else "dynamic"
                    if changes > 0
                    else "stable"
                ),
                "strongest_correlation": strongest,
            }
        )
    return result


async def build_register_analysis(
    session: AsyncSession,
    device: Device,
    hours: int,
) -> dict[str, Any]:
    latest = await session.scalar(
        select(InverterTelemetry)
        .where(InverterTelemetry.device_id == device.id)
        .order_by(InverterTelemetry.recorded_at.desc())
        .limit(1)
    )
    if latest is None:
        return {
            "device_slug": device.slug,
            "hours": hours,
            "from": None,
            "to": None,
            "sample_count": 0,
            "analyzed_sample_count": 0,
            "latest_recorded_at": None,
            "register_map_version": None,
            "decoder_version": None,
            "read_mode": "database-only",
            "serial_requests_added": 0,
            "summary": {"known": 0, "candidate": 0, "unknown": 0},
            "registers": [],
        }

    end = as_utc(latest.recorded_at)
    start = end - timedelta(hours=hours)
    rows = list(
        (
            await session.scalars(
                select(InverterTelemetry)
                .where(
                    InverterTelemetry.device_id == device.id,
                    InverterTelemetry.recorded_at >= start,
                    InverterTelemetry.recorded_at <= end,
                )
                .order_by(InverterTelemetry.recorded_at)
                .limit(20000)
            )
        ).all()
    )
    total_samples = len(rows)
    if len(rows) > 5000:
        stride = math.ceil(len(rows) / 5000)
        analyzed = rows[::stride]
        if analyzed[-1] is not rows[-1]:
            analyzed.append(rows[-1])
    else:
        analyzed = rows

    registers = analyze_register_rows(analyzed)
    summary = {
        status: sum(item["status"] == status for item in registers)
        for status in ("known", "candidate", "unknown")
    }
    return {
        "device_slug": device.slug,
        "hours": hours,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "sample_count": total_samples,
        "analyzed_sample_count": len(analyzed),
        "latest_recorded_at": end.isoformat(),
        "register_map_version": latest.register_map_version,
        "decoder_version": latest.decoder_version,
        "read_mode": "database-only",
        "serial_requests_added": 0,
        "summary": summary,
        "registers": registers,
    }
