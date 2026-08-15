import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import api_key_prefix, hash_api_key
from app.db.base import Base
from app.db.models import Device, DeviceApiKey
from app.db.session import get_db
from app.main import app

CELL_ADDRESSES = [f"0x{0x1200 + 2 * index:04X}" for index in range(8)]
STAT_ADDRESSES = [f"0x{0x1290 + 2 * index:04X}" for index in range(10)]


def payload(sample_id: uuid.UUID | None = None) -> dict:
    cell_voltages = [3472, 3472, 3472, 3470, 3472, 3472, 3472, 3472]
    return {
        "schema_version": 1,
        "sample_id": str(sample_id or uuid.uuid4()),
        "device_slug": "prime-rumah-01-bms",
        "recorded_at": datetime.now(UTC).isoformat(),
        "sequence_number": 1,
        "gateway_version": "test",
        "source": "simulator",
        "register_map_version": "jk-bd6a24s8p-v1",
        "decoder_version": "jk-bms-v1",
        "metrics": {
            "cell_voltages_mv": cell_voltages,
            "pack_voltage_v": 27.775,
            "pack_power_w": 0,
            "pack_current_a": 0,
            "temperature_1_c": 30.1,
            "temperature_2_c": 30.0,
            "soc_percent": 99.8,
            "remaining_capacity_ah": 99.844,
            "full_capacity_ah": 100.0,
            "cycle_count": 3,
            "balance_current_a": 0.1,
            "alarm_flags": 0,
        },
        "raw_registers": {
            **{addr: value for addr, value in zip(CELL_ADDRESSES, cell_voltages)},
            **{addr: 0 for addr in STAT_ADDRESSES},
        },
    }


@pytest.mark.asyncio
async def test_bms_ingest_duplicate_latest_and_history() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    key = "plts_bms_integration_test_key"
    async with session_factory() as session:
        device = Device(slug="prime-rumah-01-bms", name="Baterai kedua", timezone="Asia/Jakarta")
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
            first = await client.post(
                "/api/v1/ingest/bms-telemetry", json=sample, headers=headers
            )
            assert first.status_code == 201
            duplicate = await client.post(
                "/api/v1/ingest/bms-telemetry", json=sample, headers=headers
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True

            invalid = payload()
            invalid["metrics"]["cell_voltages_mv"] = []
            batch = await client.post(
                "/api/v1/ingest/bms-telemetry/batch",
                json={"samples": [payload(), invalid]},
                headers=headers,
            )
            assert batch.status_code == 200
            assert batch.json()["accepted"] == 1
            assert batch.json()["rejected"] == 1

            latest = await client.get("/api/v1/bms-devices/prime-rumah-01-bms/latest")
            assert latest.status_code == 200
            body = latest.json()
            assert body["telemetry"] is not None
            assert body["telemetry"]["cell_count"] == 8
            assert body["telemetry"]["metrics"]["cell_voltages_mv"] == sample["metrics"][
                "cell_voltages_mv"
            ]
            assert body["telemetry"]["metrics"]["soc_percent"] == 99.8

            start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            history = await client.get(
                "/api/v1/bms-devices/prime-rumah-01-bms/telemetry",
                params={
                    "from": start.isoformat(),
                    "to": datetime.now(UTC).isoformat(),
                    "resolution": "5m",
                },
            )
            assert history.status_code == 200
            assert history.json()["points"]
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
