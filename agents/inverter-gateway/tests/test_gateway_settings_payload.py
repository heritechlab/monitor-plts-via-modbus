import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import GatewayConfig
from gateway import build_settings_payload


def _config() -> GatewayConfig:
    return GatewayConfig(
        device_slug="prime-rumah-01",
        device_api_key="test-key",
        api_base_url="http://127.0.0.1:8000",
        serial_port="COM3",
        serial_baud=9600,
        slave_id=1,
        poll_interval_seconds=5.0,
        settings_poll_interval_seconds=300.0,
        serial_timeout_seconds=2.0,
        http_timeout_seconds=10.0,
        upload_batch_size=100,
        heartbeat_interval_seconds=30.0,
        queue_db_path=Path("./data/offline_queue.sqlite3"),
        csv_backup_dir=Path("./data/csv"),
        log_file=Path("./data/gateway.log"),
        gateway_version="test",
        timezone="Asia/Jakarta",
        verify_tls=True,
    )


def test_build_settings_payload_shape() -> None:
    registers = list(range(32))
    recorded_at = datetime.now(ZoneInfo("Asia/Jakarta"))
    payload = build_settings_payload(_config(), registers, recorded_at)

    assert payload["device_slug"] == "prime-rumah-01"
    assert payload["register_map_version"] == "prime-settings-v1"
    assert payload["raw_registers"]["0x4000"] == 0
    assert payload["raw_registers"]["0x4008"] == 8
    assert len(payload["raw_registers"]) == 32
    # Must be a fresh, valid UUID every call -- dedup on the API side keys off it.
    assert uuid.UUID(payload["sample_id"])


def test_build_settings_payload_generates_distinct_sample_ids() -> None:
    registers = list(range(32))
    recorded_at = datetime.now(ZoneInfo("Asia/Jakarta"))
    config = _config()
    first = build_settings_payload(config, registers, recorded_at)
    second = build_settings_payload(config, registers, recorded_at)
    assert first["sample_id"] != second["sample_id"]
