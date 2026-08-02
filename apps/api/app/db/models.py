import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
BIGINT_PK = BigInteger().with_variant(Integer(), "sqlite")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jakarta", nullable=False)
    inverter_model: Mapped[str | None] = mapped_column(String(100))
    inverter_rated_w: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    pv_rated_wp: Mapped[int] = mapped_column(Integer, default=1170, nullable=False)
    battery_nominal_v: Mapped[float | None] = mapped_column(Float)
    battery_capacity_ah: Mapped[float | None] = mapped_column(Float)
    tariff_idr_per_kwh: Mapped[float] = mapped_column(Float, default=1550, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_gateway_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_telemetry_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DeviceApiKey(Base):
    __tablename__ = "device_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InverterTelemetry(Base):
    __tablename__ = "inverter_telemetry"
    __table_args__ = (
        Index("ix_telemetry_device_recorded", "device_id", "recorded_at"),
        Index("ix_telemetry_device_received", "device_id", "received_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pv_voltage_v: Mapped[float | None] = mapped_column(Float)
    pv_current_a: Mapped[float | None] = mapped_column(Float)
    pv_power_w: Mapped[float | None] = mapped_column(Float)
    battery_voltage_v: Mapped[float | None] = mapped_column(Float)
    ac_output_voltage_v: Mapped[float | None] = mapped_column(Float)
    ac_output_current_a: Mapped[float | None] = mapped_column(Float)
    ac_output_power_w: Mapped[float | None] = mapped_column(Float)
    load_percent: Mapped[float | None] = mapped_column(Float)
    inverter_temperature_c: Mapped[float | None] = mapped_column(Float)

    raw_registers: Mapped[dict[str, int]] = mapped_column(JSON_TYPE, nullable=False)
    raw_start_address: Mapped[int] = mapped_column(Integer, default=0x3000, nullable=False)
    register_map_version: Mapped[str] = mapped_column(
        String(32), default="prime-v1", nullable=False
    )
    decoder_version: Mapped[str | None] = mapped_column(String(32))
    quality_flags: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    quality_details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    gateway_version: Mapped[str | None] = mapped_column(String(32))
    gateway_boot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(String(64), default="usb-rs485-laptop", nullable=False)
    sequence_number: Mapped[int | None] = mapped_column(BigInteger)


class GatewayStatus(Base):
    __tablename__ = "gateway_status"

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    gateway_boot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    gateway_version: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(64))
    last_contact_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_serial_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    serial_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    api_status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class IngestEvent(Base):
    __tablename__ = "ingest_events"

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class HourlySummary(Base):
    __tablename__ = "hourly_summaries"

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    pv_energy_wh: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    ac_output_energy_wh: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    estimated_surplus_wh: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_pv_power_w: Mapped[float | None] = mapped_column(Float)
    max_pv_power_w: Mapped[float | None] = mapped_column(Float)
    avg_ac_output_power_w: Mapped[float | None] = mapped_column(Float)
    max_ac_output_power_w: Mapped[float | None] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_interval_seconds: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    coverage_percent: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    __table_args__ = (UniqueConstraint("device_id", "local_date"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
