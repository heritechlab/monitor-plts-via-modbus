from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, GatewayStatus, InverterTelemetry
from app.schemas.telemetry import HeartbeatPayload, TelemetryPayload
from app.services.quality import evaluate_quality


@dataclass
class StoredSample:
    telemetry: InverterTelemetry
    duplicate: bool


async def store_telemetry(
    session: AsyncSession, device: Device, payload: TelemetryPayload
) -> StoredSample:
    existing = await session.scalar(
        select(InverterTelemetry).where(InverterTelemetry.sample_id == payload.sample_id)
    )
    if existing is not None:
        return StoredSample(existing, duplicate=True)

    now = datetime.now(UTC)
    flags, details = evaluate_quality(payload, now)
    metrics = payload.metrics.model_dump()
    if metrics["pv_power_w"] is None:
        voltage = metrics["pv_voltage_v"]
        current = metrics["pv_current_a"]
        if voltage is not None and current is not None:
            metrics["pv_power_w"] = round(voltage * current, 3)

    telemetry = InverterTelemetry(
        sample_id=payload.sample_id,
        device_id=device.id,
        recorded_at=payload.recorded_at.astimezone(UTC),
        received_at=now,
        raw_registers=payload.raw_registers,
        raw_start_address=min(int(key, 16) for key in payload.raw_registers),
        register_map_version=payload.register_map_version,
        decoder_version=payload.decoder_version,
        quality_flags=flags,
        quality_details=details,
        gateway_version=payload.gateway_version,
        gateway_boot_id=payload.gateway_boot_id,
        source=payload.source,
        sequence_number=payload.sequence_number,
        **metrics,
    )
    session.add(telemetry)
    device.last_gateway_contact_at = now
    if device.last_telemetry_recorded_at is None or _as_utc(
        device.last_telemetry_recorded_at
    ) < payload.recorded_at.astimezone(UTC):
        device.last_telemetry_recorded_at = payload.recorded_at.astimezone(UTC)

    await _touch_gateway_status(
        session,
        device,
        now=now,
        gateway_boot_id=payload.gateway_boot_id,
        gateway_version=payload.gateway_version,
        source=payload.source,
        serial_status="ok",
        last_serial_success_at=payload.recorded_at.astimezone(UTC),
    )
    await session.flush()
    return StoredSample(telemetry, duplicate=False)


async def store_heartbeat(
    session: AsyncSession, device: Device, payload: HeartbeatPayload
) -> GatewayStatus:
    now = datetime.now(UTC)
    device.last_gateway_contact_at = now
    return await _touch_gateway_status(
        session,
        device,
        now=now,
        gateway_boot_id=payload.gateway_boot_id,
        gateway_version=payload.gateway_version,
        source=payload.source,
        queue_depth=payload.queue_depth,
        serial_status=payload.serial_status,
        last_serial_success_at=(
            payload.last_serial_success_at.astimezone(UTC)
            if payload.last_serial_success_at is not None
            else None
        ),
        detail=payload.detail,
    )


async def _touch_gateway_status(
    session: AsyncSession,
    device: Device,
    *,
    now: datetime,
    gateway_boot_id=None,
    gateway_version=None,
    source=None,
    queue_depth: int | None = None,
    serial_status: str | None = None,
    last_serial_success_at: datetime | None = None,
    detail: dict | None = None,
) -> GatewayStatus:
    gateway = await session.get(GatewayStatus, device.id)
    if gateway is None:
        gateway = GatewayStatus(device_id=device.id, last_contact_at=now)
        session.add(gateway)
    gateway.last_contact_at = now
    gateway.api_status = "online"
    if gateway_boot_id is not None:
        gateway.gateway_boot_id = gateway_boot_id
    if gateway_version is not None:
        gateway.gateway_version = gateway_version
    if source is not None:
        gateway.source = source
    if queue_depth is not None:
        gateway.queue_depth = queue_depth
    if serial_status is not None:
        gateway.serial_status = serial_status
    if last_serial_success_at is not None:
        gateway.last_serial_success_at = last_serial_success_at
    if detail is not None:
        gateway.detail = detail
    return gateway


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
