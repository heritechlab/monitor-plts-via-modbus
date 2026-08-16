from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.devices import age_seconds, find_device, iso, status_from_age
from app.db.models import BmsTelemetry, Device, GatewayStatus
from app.db.session import get_db
from app.services.analytics import as_utc

router = APIRouter(prefix="/bms-devices", tags=["bms"])


@router.get("")
async def list_bms_devices(session: AsyncSession = Depends(get_db)) -> dict:
    rows = (
        await session.scalars(
            select(Device)
            .where(Device.device_type == "bms", Device.is_active.is_(True))
            .order_by(Device.name)
        )
    ).all()
    return {"devices": [{"slug": row.slug, "name": row.name} for row in rows]}

METRIC_FIELDS = [
    "pack_voltage_v",
    "pack_power_w",
    "pack_current_a",
    "temperature_1_c",
    "temperature_2_c",
    "soc_percent",
    "remaining_capacity_ah",
    "full_capacity_ah",
    "cycle_count",
    "balance_current_a",
]
RESOLUTION_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
MAX_SPANS = {
    "raw": timedelta(hours=6),
    "1m": timedelta(days=2),
    "5m": timedelta(days=14),
    "15m": timedelta(days=62),
    "1h": timedelta(days=732),
}


def telemetry_dict(row: BmsTelemetry, include_raw: bool = False) -> dict:
    result = {
        "sample_id": str(row.sample_id),
        "recorded_at": iso(row.recorded_at),
        "received_at": iso(row.received_at),
        "cell_count": row.cell_count,
        "metrics": {
            "cell_voltages_mv": row.cell_voltages_mv,
            **{field: getattr(row, field) for field in METRIC_FIELDS},
        },
        "quality_flags": row.quality_flags or [],
        "gateway_version": row.gateway_version,
        "source": row.source,
        "sequence_number": row.sequence_number,
    }
    if include_raw:
        result["raw_registers"] = row.raw_registers
        result["register_map_version"] = row.register_map_version
    return result


@router.get("/{slug}/latest")
async def latest(slug: str, session: AsyncSession = Depends(get_db)) -> dict:
    device = await find_device(session, slug)
    latest_row = await session.scalar(
        select(BmsTelemetry)
        .where(BmsTelemetry.device_id == device.id)
        .order_by(BmsTelemetry.recorded_at.desc())
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


@router.get("/{slug}/telemetry")
async def telemetry_history(
    slug: str,
    from_at: Annotated[datetime, Query(alias="from")],
    to_at: Annotated[datetime, Query(alias="to")],
    resolution: Literal["raw", "1m", "5m", "15m", "1h"] = "5m",
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

    if resolution == "raw":
        rows = list(
            (
                await session.scalars(
                    select(BmsTelemetry)
                    .where(
                        BmsTelemetry.device_id == device.id,
                        BmsTelemetry.recorded_at >= start,
                        BmsTelemetry.recorded_at <= end,
                    )
                    .order_by(BmsTelemetry.recorded_at)
                    .limit(5000)
                )
            ).all()
        )
        points = [
            {
                "recorded_at": iso(row.recorded_at),
                "cell_voltages_mv": row.cell_voltages_mv,
                **{field: getattr(row, field) for field in METRIC_FIELDS},
            }
            for row in rows
        ]
    else:
        seconds = RESOLUTION_SECONDS[resolution]
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            epoch = cast(func.strftime("%s", BmsTelemetry.recorded_at), Integer)
            bucket = func.datetime(func.floor(epoch / seconds) * seconds, "unixepoch").label(
                "bucket"
            )
        else:
            epoch = func.extract("epoch", BmsTelemetry.recorded_at)
            bucket = func.to_timestamp(func.floor(epoch / seconds) * seconds).label("bucket")
        columns = [
            bucket,
            *[func.avg(getattr(BmsTelemetry, field)).label(field) for field in METRIC_FIELDS],
        ]
        statement = (
            select(*columns)
            .where(
                BmsTelemetry.device_id == device.id,
                BmsTelemetry.recorded_at >= start,
                BmsTelemetry.recorded_at <= end,
            )
            .group_by(bucket)
            .order_by(bucket)
            .limit(3000)
        )
        mappings = (await session.execute(statement)).mappings().all()
        points = [
            {"recorded_at": iso(row["bucket"]), **{field: row[field] for field in METRIC_FIELDS}}
            for row in mappings
        ]
    return {
        "device_slug": device.slug,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "resolution": resolution,
        "points": points,
    }
