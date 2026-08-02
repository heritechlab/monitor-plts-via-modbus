import logging
import os
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

from api_client import ApiClient, ApiClientError
from config import GatewayConfig
from csv_backup import CsvBackup
from decoder import DECODER_VERSION, decode_registers
from modbus_reader import ModbusError, PrimeModbusReader
from offline_queue import OfflineQueue

LOGGER = logging.getLogger("plts-gateway")


@dataclass
class RuntimeState:
    boot_id: uuid.UUID
    last_serial_success_at: str | None = None
    serial_status: str = "unknown"
    last_serial_error: str | None = None
    active_serial_port: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def serial_success(self, recorded_at: str, serial_port: str) -> None:
        with self.lock:
            self.last_serial_success_at = recorded_at
            self.serial_status = "ok"
            self.last_serial_error = None
            self.active_serial_port = serial_port

    def serial_error(self, error: str) -> None:
        with self.lock:
            self.serial_status = "error"
            self.last_serial_error = error

    def heartbeat(self, config: GatewayConfig, queue: OfflineQueue) -> dict:
        with self.lock:
            return {
                "schema_version": 1,
                "device_slug": config.device_slug,
                "gateway_boot_id": str(self.boot_id),
                "gateway_version": config.gateway_version,
                "source": "usb-rs485-laptop",
                "last_serial_success_at": self.last_serial_success_at,
                "queue_depth": queue.depth(),
                "serial_status": self.serial_status,
                "detail": {
                    "serial_port": self.active_serial_port or config.serial_port,
                    "configured_serial_port": config.serial_port,
                    "dead_letter_depth": queue.dead_letter_depth(),
                    "last_serial_error": self.last_serial_error,
                },
            }


class SingleInstance:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                if self.path.stat().st_size == 0:
                    self.handle.write("0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            raise RuntimeError("Gateway sudah berjalan pada instance lain") from exc
        return self

    def __exit__(self, *_args):
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


def configure_logging(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_file,
                maxBytes=5_000_000,
                backupCount=5,
                encoding="utf-8",
            )
        )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def build_payload(
    config: GatewayConfig,
    queue: OfflineQueue,
    state: RuntimeState,
    registers: list[int],
    recorded_at: datetime,
) -> dict:
    metrics, raw = decode_registers(registers)
    return {
        "schema_version": 1,
        "sample_id": str(uuid.uuid4()),
        "device_slug": config.device_slug,
        "recorded_at": recorded_at.isoformat(timespec="milliseconds"),
        "sequence_number": queue.next_sequence(),
        "gateway_version": config.gateway_version,
        "gateway_boot_id": str(state.boot_id),
        "source": "usb-rs485-laptop",
        "register_map_version": "prime-v1",
        "decoder_version": DECODER_VERSION,
        "metrics": metrics,
        "raw_registers": raw,
    }


def upload_worker(
    config: GatewayConfig,
    queue: OfflineQueue,
    state: RuntimeState,
    stop_event: threading.Event,
) -> None:
    client = ApiClient(
        config.api_base_url,
        config.device_api_key,
        config.http_timeout_seconds,
        config.verify_tls,
    )
    backoff = 1.0
    last_heartbeat = 0.0
    try:
        while not stop_event.is_set():
            items = queue.oldest(config.upload_batch_size)
            if items:
                try:
                    response = client.send_batch([item.payload for item in items])
                    queue.acknowledge(response.get("results", []))
                    LOGGER.info(
                        "API OK | accepted=%s duplicate=%s rejected=%s | QUEUE %s",
                        response.get("accepted", 0),
                        response.get("duplicates", 0),
                        response.get("rejected", 0),
                        queue.depth(),
                    )
                    backoff = 1.0
                except ApiClientError as exc:
                    queue.mark_attempt([item.sample_id for item in items], str(exc))
                    LOGGER.warning(
                        "API ERROR | %s | retry %.0fs | QUEUE %s",
                        exc,
                        backoff,
                        queue.depth(),
                    )
                    if not exc.retryable:
                        backoff = max(backoff, 60)
                    stop_event.wait(backoff)
                    backoff = min(backoff * 2, 300)
                    continue

            now = time.monotonic()
            if now - last_heartbeat >= config.heartbeat_interval_seconds:
                try:
                    client.heartbeat(state.heartbeat(config, queue))
                    last_heartbeat = now
                except ApiClientError as exc:  # heartbeat must never stop queueing
                    LOGGER.warning("Heartbeat gagal: %s", exc)
            stop_event.wait(0.5 if items else 1.0)
    finally:
        client.close()


def run() -> int:
    configure_logging()
    try:
        config = GatewayConfig.load()
    except (OSError, ValueError) as exc:
        LOGGER.error("Konfigurasi gagal: %s", exc)
        return 2
    configure_logging(config.log_file)

    queue = OfflineQueue(config.queue_db_path)
    backup = CsvBackup(config.csv_backup_dir, config.device_slug, config.timezone)
    state = RuntimeState(boot_id=uuid.uuid4())
    stop_event = threading.Event()
    reader = PrimeModbusReader(
        config.serial_port,
        config.serial_baud,
        config.slave_id,
        config.serial_timeout_seconds,
    )

    def request_stop(*_args) -> None:
        LOGGER.info("Shutdown diminta")
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    uploader = threading.Thread(
        target=upload_worker,
        name="plts-uploader",
        args=(config, queue, state, stop_event),
        daemon=True,
    )
    uploader.start()
    zone = ZoneInfo(config.timezone)
    next_poll = time.monotonic()
    LOGGER.info(
        "Gateway mulai | %s %s 8N1 | slave=%s | FC04 0x3000..0x301F",
        config.serial_port,
        config.serial_baud,
        config.slave_id,
    )
    try:
        while not stop_event.is_set():
            wait = next_poll - time.monotonic()
            if wait > 0 and stop_event.wait(wait):
                break
            next_poll += config.poll_interval_seconds
            try:
                registers = reader.read_prime_registers()
                recorded_at = datetime.now(zone)
                payload = build_payload(config, queue, state, registers, recorded_at)
                queue.enqueue(payload)
                backup.append(payload)
                previous_port = state.active_serial_port
                state.serial_success(payload["recorded_at"], reader.port)
                if previous_port != reader.port:
                    LOGGER.info(
                        "Serial aktif | configured=%s | active=%s",
                        config.serial_port,
                        reader.port,
                    )
                metrics = payload["metrics"]
                LOGGER.info(
                    "PV %.1f V %.1f A %.1f W | BAT %.1f V | OUT %.1f V %.1f A %.0f W %.0f%% "
                    "| TEMP %.0f C | QUEUE %s",
                    metrics["pv_voltage_v"],
                    metrics["pv_current_a"],
                    metrics["pv_power_w"],
                    metrics["battery_voltage_v"],
                    metrics["ac_output_voltage_v"],
                    metrics["ac_output_current_a"],
                    metrics["ac_output_power_w"],
                    metrics["load_percent"],
                    metrics["inverter_temperature_c"],
                    queue.depth(),
                )
            except (ModbusError, OSError) as exc:
                reader.close()
                state.serial_error(str(exc))
                LOGGER.error("SERIAL ERROR | %s", exc)
            except Exception as exc:
                state.serial_error(str(exc))
                LOGGER.exception("Kesalahan gateway tak terduga")
    finally:
        stop_event.set()
        reader.close()
        uploader.join(timeout=config.http_timeout_seconds + 2)
        LOGGER.info("Gateway berhenti | QUEUE %s", queue.depth())
    return 0


if __name__ == "__main__":
    lock_path = Path("./data/gateway.lock")
    try:
        with SingleInstance(lock_path):
            sys.exit(run())
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(3)
