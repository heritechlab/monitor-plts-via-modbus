import csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Device, GatewayStatus, InverterTelemetry
from app.db.session import get_db
from app.services.analytics import as_utc, build_monthly_summary, get_or_build_daily_summary
from app.services.register_analysis import build_register_analysis

router = APIRouter(prefix="/devices", tags=["devices"])
METRIC_FIELDS = [
    "pv_voltage_v",
    "pv_current_a",
    "pv_power_w",
    "battery_voltage_v",
    "ac_output_voltage_v",
    "ac_output_current_a",
    "ac_output_power_w",
    "load_percent",
    "inverter_temperature_c",
]
RESOLUTION_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
MAX_SPANS = {
    "raw": timedelta(hours=6),
    "1m": timedelta(days=2),
    "5m": timedelta(days=14),
    "15m": timedelta(days=62),
    "1h": timedelta(days=732),
}


async def find_device(session: AsyncSession, slug: str) -> Device:
    device = await session.scalar(
        select(Device).where(Device.slug == slug, Device.is_active.is_(True))
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    return device


def iso(value: datetime | str | None) -> str | None:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return as_utc(parsed).isoformat()
    return as_utc(value).isoformat() if value else None


def age_seconds(value: datetime | None, now: datetime) -> float | None:
    return (now - as_utc(value)).total_seconds() if value else None


def status_from_age(age: float | None) -> str:
    if age is None or age > settings.degraded_after_seconds:
        return "offline"
    if age > settings.online_after_seconds:
        return "degraded"
    return "online"


def telemetry_dict(row: InverterTelemetry, include_raw: bool = False) -> dict:
    result = {
        "sample_id": str(row.sample_id),
        "recorded_at": iso(row.recorded_at),
        "received_at": iso(row.received_at),
        "metrics": {field: getattr(row, field) for field in METRIC_FIELDS},
        "quality_flags": row.quality_flags or [],
        "quality_details": row.quality_details or {},
        "gateway_version": row.gateway_version,
        "source": row.source,
        "sequence_number": row.sequence_number,
    }
    if include_raw:
        result["raw_registers"] = row.raw_registers
        result["register_map_version"] = row.register_map_version
    return result


@router.get("/{slug}")
async def device_detail(slug: str, session: AsyncSession = Depends(get_db)) -> dict:
    device = await find_device(session, slug)
    gateway = await session.get(GatewayStatus, device.id)
    return {
        "slug": device.slug,
        "name": device.name,
        "location": device.location,
        "timezone": device.timezone,
        "inverter_model": device.inverter_model,
        "inverter_rated_w": device.inverter_rated_w,
        "pv_rated_wp": device.pv_rated_wp,
        "battery_nominal_v": device.battery_nominal_v,
        "battery_capacity_ah": device.battery_capacity_ah,
        "tariff_idr_per_kwh": device.tariff_idr_per_kwh,
        "gateway": {
            "version": gateway.gateway_version if gateway else None,
            "source": gateway.source if gateway else None,
            "queue_depth": gateway.queue_depth if gateway else None,
            "serial_status": gateway.serial_status if gateway else "unknown",
            "last_contact_at": iso(gateway.last_contact_at) if gateway else None,
            "last_serial_success_at": iso(gateway.last_serial_success_at) if gateway else None,
        },
    }


@router.get("/{slug}/latest")
async def latest(slug: str, session: AsyncSession = Depends(get_db)) -> dict:
    device = await find_device(session, slug)
    latest_row = await session.scalar(
        select(InverterTelemetry)
        .where(InverterTelemetry.device_id == device.id)
        .order_by(InverterTelemetry.recorded_at.desc())
        .limit(1)
    )
    gateway = await session.get(GatewayStatus, device.id)
    now = datetime.now(UTC)
    gateway_age = age_seconds(gateway.last_contact_at, now) if gateway else None
    telemetry_age = age_seconds(device.last_telemetry_recorded_at, now)
    return {
        "device": {"slug": device.slug, "name": device.name, "timezone": device.timezone},
        "status": status_from_age(gateway_age),
        "telemetry_status": status_from_age(telemetry_age),
        "gateway_age_seconds": round(gateway_age, 1) if gateway_age is not None else None,
        "telemetry_age_seconds": round(telemetry_age, 1) if telemetry_age is not None else None,
        "gateway": {
            "serial_status": gateway.serial_status if gateway else "unknown",
            "queue_depth": gateway.queue_depth if gateway else None,
            "last_contact_at": iso(gateway.last_contact_at) if gateway else None,
            "last_serial_success_at": iso(gateway.last_serial_success_at) if gateway else None,
        },
        "telemetry": telemetry_dict(latest_row, include_raw=True) if latest_row else None,
        "server_time": now.isoformat(),
    }


@router.get("/{slug}/register-analysis")
async def register_analysis(
    slug: str,
    hours: Annotated[int, Query(ge=1, le=24)] = 6,
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await find_device(session, slug)
    return await build_register_analysis(session, device, hours)


@router.get("/{slug}/telemetry")
async def telemetry_history(
    slug: str,
    from_at: Annotated[datetime, Query(alias="from")],
    to_at: Annotated[datetime, Query(alias="to")],
    resolution: Literal["raw", "1m", "5m", "15m", "1h"] = "5m",
    fields: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await find_device(session, slug)
    start, end = as_utc(from_at), as_utc(to_at)
    if end <= start:
        raise HTTPException(status_code=422, detail="Parameter to harus setelah from")
    if end - start > MAX_SPANS[resolution]:
        raise HTTPException(
            status_code=422,
            detail=f"Rentang terlalu besar untuk resolution={resolution}",
        )
    selected = METRIC_FIELDS
    if fields:
        requested = [item.strip() for item in fields.split(",") if item.strip()]
        invalid = set(requested) - set(METRIC_FIELDS)
        if invalid:
            raise HTTPException(status_code=422, detail=f"Field tidak valid: {sorted(invalid)}")
        selected = requested

    if resolution == "raw":
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
                    .limit(5000)
                )
            ).all()
        )
        points = [
            {
                "recorded_at": iso(row.recorded_at),
                **{field: getattr(row, field) for field in selected},
                "quality_flags": row.quality_flags,
            }
            for row in rows
        ]
    else:
        seconds = RESOLUTION_SECONDS[resolution]
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            epoch = cast(func.strftime("%s", InverterTelemetry.recorded_at), Integer)
            bucket = func.datetime(func.floor(epoch / seconds) * seconds, "unixepoch").label(
                "bucket"
            )
        else:
            epoch = func.extract("epoch", InverterTelemetry.recorded_at)
            bucket = func.to_timestamp(func.floor(epoch / seconds) * seconds).label("bucket")
        columns = [
            bucket,
            *[func.avg(getattr(InverterTelemetry, field)).label(field) for field in selected],
        ]
        statement = (
            select(*columns)
            .where(
                InverterTelemetry.device_id == device.id,
                InverterTelemetry.recorded_at >= start,
                InverterTelemetry.recorded_at <= end,
            )
            .group_by(bucket)
            .order_by(bucket)
            .limit(3000)
        )
        mappings = (await session.execute(statement)).mappings().all()
        points = [
            {"recorded_at": iso(row["bucket"]), **{field: row[field] for field in selected}}
            for row in mappings
        ]
    return {
        "device_slug": device.slug,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "resolution": resolution,
        "points": points,
    }


@router.get("/{slug}/analytics/daily")
async def daily_analytics(
    slug: str,
    date_value: Annotated[date, Query(alias="date")],
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await find_device(session, slug)
    return await get_or_build_daily_summary(session, device, date_value)


@router.get("/{slug}/analytics/monthly")
async def monthly_analytics(
    slug: str,
    month: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await find_device(session, slug)
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Format month harus YYYY-MM") from exc
    return await build_monthly_summary(session, device, parsed.year, parsed.month)


@router.get("/{slug}/data-quality")
async def data_quality(
    slug: str,
    date_value: Annotated[date, Query(alias="date")],
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await find_device(session, slug)
    summary = await get_or_build_daily_summary(session, device, date_value)
    start = (
        datetime.fromisoformat(summary["first_sample_at"]) if summary["first_sample_at"] else None
    )
    end = datetime.fromisoformat(summary["last_sample_at"]) if summary["last_sample_at"] else None
    anomalies = []
    if start and end:
        rows = (
            await session.scalars(
                select(InverterTelemetry)
                .where(
                    InverterTelemetry.device_id == device.id,
                    InverterTelemetry.recorded_at >= start,
                    InverterTelemetry.recorded_at <= end,
                    InverterTelemetry.quality_flags != [],  # noqa: E711
                )
                .order_by(InverterTelemetry.recorded_at.desc())
                .limit(100)
            )
        ).all()
        anomalies = [telemetry_dict(item, include_raw=True) for item in rows]
    return {"summary": summary, "anomalies": anomalies}


@router.get("/{slug}/export.csv")
async def export_csv(
    slug: str,
    from_at: Annotated[datetime, Query(alias="from")],
    to_at: Annotated[datetime, Query(alias="to")],
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    device = await find_device(session, slug)
    start, end = as_utc(from_at), as_utc(to_at)
    if end - start > timedelta(days=31):
        raise HTTPException(status_code=422, detail="Export raw maksimal 31 hari")
    rows = (
        await session.scalars(
            select(InverterTelemetry)
            .where(
                InverterTelemetry.device_id == device.id,
                InverterTelemetry.recorded_at >= start,
                InverterTelemetry.recorded_at <= end,
            )
            .order_by(InverterTelemetry.recorded_at)
        )
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sample_id", "recorded_at", *METRIC_FIELDS, "quality_flags", "raw_registers"])
    for row in rows:
        writer.writerow(
            [
                row.sample_id,
                iso(row.recorded_at),
                *[getattr(row, field) for field in METRIC_FIELDS],
                "|".join(row.quality_flags or []),
                row.raw_registers,
            ]
        )
    filename = f"{device.slug}_{start.date()}_{end.date()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
