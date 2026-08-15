import csv
import json
import threading
from pathlib import Path
from zoneinfo import ZoneInfo

from decoder import ALL_ADDRESSES, CELL_COUNT, STAT_LAYOUT

METRIC_FIELDS = list(STAT_LAYOUT) + ["soc_percent"]
CELL_FIELDS = [f"cell_{index + 1}_mv" for index in range(CELL_COUNT)]
RAW_FIELDS = [f"0x{address:04X}" for address in ALL_ADDRESSES]


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
        cell_voltages = metrics.get("cell_voltages_mv") or []
        row = {
            "sample_id": payload["sample_id"],
            "recorded_at": recorded,
            "sequence_number": payload.get("sequence_number"),
            "gateway_boot_id": payload.get("gateway_boot_id"),
            "initial_status": "queued",
            **{field: metrics.get(field) for field in METRIC_FIELDS},
            **{
                CELL_FIELDS[index]: cell_voltages[index] if index < len(cell_voltages) else None
                for index in range(CELL_COUNT)
            },
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
