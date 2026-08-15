import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetricsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pv_voltage_v: float | None = None
    pv_current_a: float | None = None
    pv_power_w: float | None = None
    battery_voltage_v: float | None = None
    ac_output_voltage_v: float | None = None
    ac_output_current_a: float | None = None
    ac_output_power_w: float | None = None
    load_percent: float | None = None
    inverter_temperature_c: float | None = None


class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    sample_id: uuid.UUID
    device_slug: str = Field(min_length=1, max_length=100)
    recorded_at: datetime
    sequence_number: int | None = Field(default=None, ge=0)
    gateway_version: str | None = Field(default=None, max_length=32)
    gateway_boot_id: uuid.UUID | None = None
    source: str = Field(default="usb-rs485-laptop", max_length=64)
    register_map_version: str = Field(default="prime-v1", max_length=32)
    decoder_version: str | None = Field(default=None, max_length=32)
    metrics: MetricsPayload
    raw_registers: dict[str, int]

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at wajib memiliki timezone")
        return value

    @field_validator("raw_registers")
    @classmethod
    def validate_registers(cls, value: dict[str, int]) -> dict[str, int]:
        if not 1 <= len(value) <= 64:
            raise ValueError("raw_registers harus berisi 1 sampai 64 register")
        for key, raw in value.items():
            if not key.startswith("0x"):
                raise ValueError(f"alamat register tidak valid: {key}")
            if not 0 <= raw <= 65535:
                raise ValueError(f"nilai register di luar uint16: {key}")
        return value


class BmsMetricsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_voltages_mv: list[int] = Field(min_length=1, max_length=32)
    pack_voltage_v: float | None = None
    pack_power_w: float | None = None
    pack_current_a: float | None = None
    temperature_1_c: float | None = None
    temperature_2_c: float | None = None
    soc_percent: float | None = None
    remaining_capacity_ah: float | None = None
    full_capacity_ah: float | None = None
    cycle_count: int | None = None
    balance_current_a: float | None = None
    alarm_flags: int | None = None


class BmsTelemetryPayload(TelemetryPayload):
    register_map_version: str = Field(default="jk-bd6a24s8p-v1", max_length=32)
    metrics: BmsMetricsPayload


class BatchTelemetryPayload(BaseModel):
    # Validasi item dilakukan satu per satu agar satu payload rusak tidak
    # menggagalkan seluruh flush antrean.
    samples: list[dict] = Field(min_length=1, max_length=100)


class HeartbeatPayload(BaseModel):
    schema_version: Literal[1] = 1
    device_slug: str
    gateway_boot_id: uuid.UUID | None = None
    gateway_version: str | None = None
    source: str = "usb-rs485-laptop"
    last_serial_success_at: datetime | None = None
    queue_depth: int = Field(default=0, ge=0)
    serial_status: Literal["ok", "degraded", "error", "unknown"] = "unknown"
    detail: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    status: Literal["accepted", "duplicate"]
    sample_id: uuid.UUID
    duplicate: bool
    received_at: datetime
    quality_flags: list[str] = Field(default_factory=list)


class BatchItemResult(BaseModel):
    sample_id: str
    status: Literal["accepted", "duplicate", "rejected"]
    retryable: bool = False
    code: str | None = None
    message: str | None = None


class BatchIngestResponse(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    results: list[BatchItemResult]
