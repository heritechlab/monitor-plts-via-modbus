import csv
import json
import threading
from pathlib import Path
from zoneinfo import ZoneInfo

METRIC_FIELDS = [
    "pv_voltage_v",
    "pv_current_a",
    "pv_power_w",
    "battery_voltage_v",
    "ac_output_voltage_v",
    "ac_output_current_a",
    "ac_output_power_w",
    "load_percent",
    "inverter_temperature_c",
]
RAW_FIELDS = [f"0x{0x3000 + index:04X}" for index in range(32)]


class CsvBackup:
    def __init__(self, directory: Path, device_slug: str, timezone: str) -> None:
        self.directory = directory
        self.device_slug = device_slug
        self.timezone = ZoneInfo(timezone)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, payload: dict) -> Path:
        recorded = payload["recorded_at"]
        from datetime import datetime

        local_date = datetime.fromisoformat(recorded).astimezone(self.timezone).date()
        path = self.directory / f"{self.device_slug}_{local_date.isoformat()}.csv"
        metrics = payload["metrics"]
        raw = payload["raw_registers"]
        row = {
            "sample_id": payload["sample_id"],
            "recorded_at": recorded,
            "sequence_number": payload.get("sequence_number"),
            "gateway_boot_id": payload.get("gateway_boot_id"),
            "initial_status": "queued",
            **{field: metrics.get(field) for field in METRIC_FIELDS},
            **{field: raw.get(field) for field in RAW_FIELDS},
            "raw_registers_json": json.dumps(raw, separators=(",", ":")),
        }
        with self._lock:
            is_new = not path.exists() or path.stat().st_size == 0
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
        return path
