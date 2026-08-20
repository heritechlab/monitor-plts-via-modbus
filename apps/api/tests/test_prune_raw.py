import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.cli import prune_raw_registers
from app.db.base import Base
from app.db.models import Device, InverterTelemetry


def sample(device_id, age_days: float) -> InverterTelemetry:
    at = datetime.now(UTC) - timedelta(days=age_days)
    return InverterTelemetry(
        sample_id=uuid.uuid4(),
        device_id=device_id,
        recorded_at=at,
        received_at=at,
        pv_power_w=800.0,
        ac_output_power_w=220.0,
        battery_voltage_v=27.0,
        inverter_temperature_c=33.0,
        raw_registers={f"0x{0x3000 + index:04X}": index for index in range(32)},
        raw_start_address=0x3000,
        register_map_version="prime-v2",
        quality_flags=[],
        quality_details={},
        source="test",
    )


@pytest.fixture
async def wired(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr("app.cli.SessionLocal", factory)

    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    async with factory() as session:
        session.add(device)
        await session.flush()
        session.add(sample(device.id, age_days=30))  # lama -> harus dikosongkan
        session.add(sample(device.id, age_days=10))  # lama -> harus dikosongkan
        session.add(sample(device.id, age_days=1))  # baru -> harus dipertahankan
        await session.commit()
    yield factory
    await engine.dispose()


async def raw_sizes(factory) -> list[int]:
    async with factory() as session:
        rows = (
            await session.execute(
                select(func.length(cast(InverterTelemetry.raw_registers, String))).order_by(
                    InverterTelemetry.recorded_at
                )
            )
        ).scalars().all()
    return list(rows)


@pytest.mark.asyncio
async def test_only_old_rows_are_emptied(wired) -> None:
    await prune_raw_registers(days=7, run_vacuum=False)
    sizes = await raw_sizes(wired)
    # dua tertua kosong ("{}" = 2 karakter), yang terbaru tetap utuh
    assert sizes[0] == 2
    assert sizes[1] == 2
    assert sizes[2] > 2


@pytest.mark.asyncio
async def test_decoded_metrics_survive_pruning(wired) -> None:
    await prune_raw_registers(days=7, run_vacuum=False)
    async with wired() as session:
        rows = (
            await session.scalars(
                select(InverterTelemetry).order_by(InverterTelemetry.recorded_at)
            )
        ).all()
    for row in rows:
        assert row.pv_power_w == 800.0
        assert row.ac_output_power_w == 220.0
        assert row.battery_voltage_v == 27.0
        assert row.inverter_temperature_c == 33.0


@pytest.mark.asyncio
async def test_second_run_rewrites_nothing(wired, capsys) -> None:
    await prune_raw_registers(days=7, run_vacuum=False)
    capsys.readouterr()
    await prune_raw_registers(days=7, run_vacuum=False)
    assert "Total 0 baris" in capsys.readouterr().out
