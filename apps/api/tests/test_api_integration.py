import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import api_key_prefix, hash_api_key
from app.db.base import Base
from app.db.models import Device, DeviceApiKey
from app.db.session import get_db
from app.main import app


def payload(sample_id: uuid.UUID | None = None) -> dict:
    return {
        "schema_version": 1,
        "sample_id": str(sample_id or uuid.uuid4()),
        "device_slug": "prime-rumah-01",
        "recorded_at": datetime.now(UTC).isoformat(),
        "sequence_number": 1,
        "gateway_version": "test",
        "source": "simulator",
        "metrics": {
            "pv_voltage_v": 80,
            "pv_current_a": 10,
            "pv_power_w": 800,
            "battery_voltage_v": 26.8,
            "ac_output_voltage_v": 220,
            "ac_output_current_a": 1,
            "ac_output_power_w": 220,
            "load_percent": 22,
            "inverter_temperature_c": 37,
        },
        "raw_registers": {f"0x{0x3000 + index:04X}": 0 for index in range(32)},
    }


@pytest.mark.asyncio
async def test_ingest_duplicate_latest_and_partial_batch() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    key = "plts_integration_test_key"
    async with session_factory() as session:
        device = Device(slug="prime-rumah-01", name="Test", timezone="Asia/Jakarta")
        session.add(device)
        await session.flush()
        session.add(
            DeviceApiKey(
                device_id=device.id,
                key_prefix=api_key_prefix(key),
                key_hash=hash_api_key(key),
            )
        )
        await session.commit()

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    headers = {"Authorization": f"Bearer {key}"}
    sample = payload()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post("/api/v1/ingest/telemetry", json=sample, headers=headers)
            assert first.status_code == 201
            duplicate = await client.post("/api/v1/ingest/telemetry", json=sample, headers=headers)
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True

            invalid = payload()
            invalid["raw_registers"] = {}
            batch = await client.post(
                "/api/v1/ingest/telemetry/batch",
                json={"samples": [payload(), invalid]},
                headers=headers,
            )
            assert batch.status_code == 200
            assert batch.json()["accepted"] == 1
            assert batch.json()["rejected"] == 1
            assert batch.json()["results"][1]["retryable"] is False

            latest = await client.get("/api/v1/devices/prime-rumah-01/latest")
            assert latest.status_code == 200
            assert latest.json()["telemetry"] is not None

            registers = await client.get(
                "/api/v1/devices/prime-rumah-01/register-analysis",
                params={"hours": 6},
            )
            assert registers.status_code == 200
            assert registers.json()["serial_requests_added"] == 0
            # Bertambah dari 8 setelah 0x3000/0x3008/0x300A/0x3016 teridentifikasi.
            assert registers.json()["summary"]["known"] == 12

            # Endpoint membucket per hari LOKAL device (Asia/Jakarta), jadi tanggal
            # acuan harus lokal juga. Memakai tanggal UTC membuat test merah setiap
            # kali dijalankan pada 00:00-06:59 WIB, saat tanggal UTC masih kemarin.
            today = datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()
            daily = await client.get(f"/api/v1/devices/prime-rumah-01/analytics/daily?date={today}")
            assert daily.status_code == 200
            assert daily.json()["sample_count"] == 2
            assert daily.json()["ac_load_estimate_kvah"] >= 0
            assert daily.json()["ac_output_energy_kwh"] is None
            assert daily.json()["estimated_surplus_kwh"] is None

            start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            history = await client.get(
                "/api/v1/devices/prime-rumah-01/telemetry",
                params={
                    "from": start.isoformat(),
                    "to": datetime.now(UTC).isoformat(),
                    "resolution": "5m",
                },
            )
            assert history.status_code == 200
            assert history.json()["points"]

            quality = await client.get(f"/api/v1/devices/prime-rumah-01/data-quality?date={today}")
            assert quality.status_code == 200
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
