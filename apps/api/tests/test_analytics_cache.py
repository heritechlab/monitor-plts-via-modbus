import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import DailySummary, Device, InverterTelemetry
from app.schemas.telemetry import MetricsPayload, TelemetryPayload
from app.services.analytics import (
    SUMMARY_VERSION_KEY,
    build_monthly_summary,
    get_or_build_daily_summary,
)
from app.services.ingest import store_telemetry

JAKARTA = ZoneInfo("Asia/Jakarta")


def sample(device_id, at: datetime, power: float) -> InverterTelemetry:
    return InverterTelemetry(
        sample_id=uuid.uuid4(),
        device_id=device_id,
        recorded_at=at,
        received_at=at,
        pv_power_w=power,
        ac_output_power_w=power / 2,
        battery_voltage_v=27.0,
        inverter_temperature_c=33.0,
        raw_registers={f"0x{0x3000 + index:04X}": 0 for index in range(32)},
        raw_start_address=0x3000,
        register_map_version="prime-v2",
        quality_flags=[],
        quality_details={},
        source="test",
    )


async def seed(session_factory, device: Device, day: date, count: int = 12) -> None:
    """Isi satu hari lokal dengan sampel berjarak 5 menit."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=JAKARTA).astimezone(UTC)
    async with session_factory() as session:
        session.add(device)
        await session.flush()
        for index in range(count):
            session.add(sample(device.id, start + timedelta(minutes=5 * index), 500))
        await session.commit()


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_past_day_is_cached_and_reused(session_factory) -> None:
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    yesterday = datetime.now(JAKARTA).date() - timedelta(days=1)
    await seed(session_factory, device, yesterday)

    async with session_factory() as session:
        first = await get_or_build_daily_summary(session, device, yesterday)
        cached_rows = await session.scalar(select(func.count()).select_from(DailySummary))
        assert cached_rows == 1

        # Nilai yang dikembalikan tidak boleh membocorkan kunci internal versi.
        assert SUMMARY_VERSION_KEY not in first
        assert first["sample_count"] == 12

        second = await get_or_build_daily_summary(session, device, yesterday)
        assert second == first


@pytest.mark.asyncio
async def test_cached_summary_survives_deleted_raw_rows(session_factory) -> None:
    """Bukti hasil kedua benar-benar dari cache, bukan dihitung ulang."""
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    yesterday = datetime.now(JAKARTA).date() - timedelta(days=1)
    await seed(session_factory, device, yesterday)

    async with session_factory() as session:
        first = await get_or_build_daily_summary(session, device, yesterday)

    async with session_factory() as session:
        await session.execute(InverterTelemetry.__table__.delete())
        await session.commit()

    async with session_factory() as session:
        second = await get_or_build_daily_summary(session, device, yesterday)
    assert second == first
    assert second["sample_count"] == 12


@pytest.mark.asyncio
async def test_today_is_never_cached(session_factory) -> None:
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    today = datetime.now(JAKARTA).date()
    await seed(session_factory, device, today, count=3)

    async with session_factory() as session:
        await get_or_build_daily_summary(session, device, today)
        cached_rows = await session.scalar(select(func.count()).select_from(DailySummary))
    assert cached_rows == 0


@pytest.mark.asyncio
async def test_backfilled_sample_invalidates_cached_day(session_factory) -> None:
    """Flush antrean offline untuk hari lampau harus membatalkan cache hari itu."""
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    yesterday = datetime.now(JAKARTA).date() - timedelta(days=1)
    await seed(session_factory, device, yesterday)

    async with session_factory() as session:
        before = await get_or_build_daily_summary(session, device, yesterday)
        assert before["sample_count"] == 12

    late = datetime.combine(yesterday, datetime.min.time(), tzinfo=JAKARTA) + timedelta(hours=2)
    payload = TelemetryPayload(
        sample_id=uuid.uuid4(),
        device_slug=device.slug,
        recorded_at=late,
        metrics=MetricsPayload(pv_power_w=500, ac_output_power_w=250),
        raw_registers={"0x3000": 1},
    )
    async with session_factory() as session:
        stored_device = await session.get(Device, device.id)
        await store_telemetry(session, stored_device, payload)
        await session.commit()
        remaining = await session.scalar(select(func.count()).select_from(DailySummary))
    assert remaining == 0

    async with session_factory() as session:
        after = await get_or_build_daily_summary(session, device, yesterday)
    assert after["sample_count"] == 13


@pytest.mark.asyncio
async def test_live_sample_for_today_leaves_cache_alone(session_factory) -> None:
    """Jalur normal (data hari ini) tidak boleh menyentuh cache hari lampau."""
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    yesterday = datetime.now(JAKARTA).date() - timedelta(days=1)
    await seed(session_factory, device, yesterday)

    async with session_factory() as session:
        await get_or_build_daily_summary(session, device, yesterday)

    payload = TelemetryPayload(
        sample_id=uuid.uuid4(),
        device_slug=device.slug,
        recorded_at=datetime.now(JAKARTA),
        metrics=MetricsPayload(pv_power_w=500, ac_output_power_w=250),
        raw_registers={"0x3000": 1},
    )
    async with session_factory() as session:
        stored_device = await session.get(Device, device.id)
        await store_telemetry(session, stored_device, payload)
        await session.commit()
        remaining = await session.scalar(select(func.count()).select_from(DailySummary))
    assert remaining == 1


@pytest.mark.asyncio
async def test_monthly_summary_matches_uncached_values(session_factory) -> None:
    device = Device(slug="dev", name="Dev", timezone="Asia/Jakarta")
    yesterday = datetime.now(JAKARTA).date() - timedelta(days=1)
    await seed(session_factory, device, yesterday)

    async with session_factory() as session:
        direct = await get_or_build_daily_summary(session, device, yesterday)
        monthly = await build_monthly_summary(session, device, yesterday.year, yesterday.month)

    day_in_month = next(item for item in monthly["days"] if item["date"] == yesterday.isoformat())
    assert day_in_month == direct
    assert monthly["pv_energy_kwh"] == pytest.approx(direct["pv_energy_kwh"])
