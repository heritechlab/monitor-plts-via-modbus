"""Import CSV logger lama melalui API ingest yang sama dengan gateway."""

import argparse
import csv
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ALIASES = {
    "pv_voltage_v": ["pv_voltage_v", "pv_voltage", "pv_v"],
    "pv_current_a": ["pv_current_a", "pv_current", "pv_a"],
    "pv_power_w": ["pv_power_w", "pv_power", "pv_w"],
    "battery_voltage_v": ["battery_voltage_v", "battery_voltage", "bat_v"],
    "ac_output_voltage_v": ["ac_output_voltage_v", "output_voltage", "ac_voltage"],
    "ac_output_current_a": ["ac_output_current_a", "output_current", "ac_current"],
    "ac_output_power_w": ["ac_output_power_w", "output_power", "ac_power"],
    "load_percent": ["load_percent", "load_pct", "load"],
    "inverter_temperature_c": ["inverter_temperature_c", "temperature", "temp_c"],
}
TIMESTAMP_COLUMNS = ["recorded_at", "timestamp", "datetime", "time"]


def first_value(row: dict[str, str], aliases: list[str]) -> str | None:
    lowered = {key.lower().strip(): value for key, value in row.items()}
    for alias in aliases:
        value = lowered.get(alias)
        if value not in {None, ""}:
            return value
    return None


def parse_timestamp(row: dict[str, str], zone: ZoneInfo) -> datetime:
    raw = first_value(row, TIMESTAMP_COLUMNS)
    if raw is None:
        raise ValueError("Kolom timestamp tidak ditemukan")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed


def parse_float(row: dict[str, str], aliases: list[str]) -> float | None:
    value = first_value(row, aliases)
    return float(value.replace(",", ".")) if value is not None else None


def parse_raw_registers(row: dict[str, str]) -> dict[str, int]:
    result = {}
    for key, value in row.items():
        normalized = key.strip().upper().removeprefix("RAW_").removeprefix("REG_")
        if normalized.startswith("0X") and value not in {None, ""}:
            result[f"0x{int(normalized, 16):04X}"] = int(float(value))
    if result:
        return result
    return {f"0x{0x3000 + index:04X}": 0 for index in range(32)}


def convert_row(
    row: dict[str, str], device: str, zone: ZoneInfo, row_number: int
) -> dict:
    recorded_at = parse_timestamp(row, zone)
    metrics = {field: parse_float(row, aliases) for field, aliases in ALIASES.items()}
    if (
        metrics["pv_power_w"] is None
        and metrics["pv_voltage_v"] is not None
        and metrics["pv_current_a"] is not None
    ):
        metrics["pv_power_w"] = metrics["pv_voltage_v"] * metrics["pv_current_a"]
    raw = parse_raw_registers(row)
    fingerprint = hashlib.sha256(
        json.dumps(
            [device, recorded_at.isoformat(), row_number, raw], sort_keys=True
        ).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "sample_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"plts-csv:{fingerprint}")),
        "device_slug": device,
        "recorded_at": recorded_at.isoformat(),
        "sequence_number": row_number,
        "gateway_version": "csv-import-0.1.0",
        "source": "csv-import",
        "register_map_version": "prime-v1",
        "decoder_version": "csv-import-v1",
        "metrics": metrics,
        "raw_registers": raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--device", default="prime-rumah-01")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--timezone", default="Asia/Jakarta")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    zone = ZoneInfo(args.timezone)
    converted, invalid = [], []
    with args.file.open("r", newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            try:
                converted.append(convert_row(row, args.device, zone, index))
            except (KeyError, TypeError, ValueError) as exc:
                invalid.append((index, str(exc)))
    print(
        f"Terbaca={len(converted) + len(invalid)} valid={len(converted)} invalid={len(invalid)}"
    )
    if invalid:
        print("Contoh error:", invalid[:10])
    if args.dry_run:
        print(json.dumps(converted[:2], indent=2))
        return

    totals = {"accepted": 0, "duplicates": 0, "rejected": 0}
    with httpx.Client(
        base_url=args.api_url,
        headers={"Authorization": f"Bearer {args.api_key}"},
        timeout=30,
    ) as client:
        for start in range(0, len(converted), min(args.batch_size, 100)):
            response = client.post(
                "/api/v1/ingest/telemetry/batch",
                json={"samples": converted[start : start + min(args.batch_size, 100)]},
            )
            response.raise_for_status()
            result = response.json()
            for key in totals:
                totals[key] += result[key]
            print(
                f"Progress {min(start + args.batch_size, len(converted))}/{len(converted)}"
            )
    print("Selesai:", totals)


if __name__ == "__main__":
    main()
