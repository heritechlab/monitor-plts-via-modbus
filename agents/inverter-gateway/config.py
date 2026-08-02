from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class GatewayConfig:
    device_slug: str
    device_api_key: str
    api_base_url: str
    serial_port: str
    serial_baud: int
    slave_id: int
    poll_interval_seconds: float
    serial_timeout_seconds: float
    http_timeout_seconds: float
    upload_batch_size: int
    heartbeat_interval_seconds: float
    queue_db_path: Path
    csv_backup_dir: Path
    gateway_version: str
    timezone: str
    verify_tls: bool

    @classmethod
    def load(cls) -> "GatewayConfig":
        load_dotenv()
        api_key = getenv("DEVICE_API_KEY", "")
        if not api_key or api_key.startswith("ganti-"):
            raise ValueError("DEVICE_API_KEY belum dikonfigurasi di .env gateway")
        return cls(
            device_slug=getenv("DEVICE_SLUG", "prime-rumah-01"),
            device_api_key=api_key,
            api_base_url=getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            serial_port=getenv("SERIAL_PORT", "COM3"),
            serial_baud=int(getenv("SERIAL_BAUD", "9600")),
            slave_id=int(getenv("SLAVE_ID", "1")),
            poll_interval_seconds=float(getenv("POLL_INTERVAL_SECONDS", "5")),
            serial_timeout_seconds=float(getenv("SERIAL_TIMEOUT_SECONDS", "2")),
            http_timeout_seconds=float(getenv("HTTP_TIMEOUT_SECONDS", "10")),
            upload_batch_size=min(int(getenv("UPLOAD_BATCH_SIZE", "100")), 100),
            heartbeat_interval_seconds=float(
                getenv("HEARTBEAT_INTERVAL_SECONDS", "30")
            ),
            queue_db_path=Path(getenv("QUEUE_DB_PATH", "./data/offline_queue.sqlite3")),
            csv_backup_dir=Path(getenv("CSV_BACKUP_DIR", "./data/csv")),
            gateway_version=getenv("GATEWAY_VERSION", "0.1.0"),
            timezone=getenv("TIMEZONE", "Asia/Jakarta"),
            verify_tls=getenv("VERIFY_TLS", "true").lower()
            in {"1", "true", "yes", "on"},
        )
