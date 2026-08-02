import argparse
import math
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from api_client import ApiClient


def sample(device_slug: str, index: int, timezone: str) -> dict:
    phase = index / 12
    pv_voltage = 79.5 + math.sin(phase) * 1.8
    pv_current = max(0.0, 8 + math.sin(phase / 2) * 3)
    pv_power = pv_voltage * pv_current
    output_power = 220 + math.sin(phase * 1.4) * 90
    raw_values = [0] * 32
    raw_values[0x01] = 2200
    raw_values[0x02] = 268
    raw_values[0x03] = round(output_power / 220 * 10)
    raw_values[0x04] = round(output_power / 10)
    raw_values[0x05] = round(output_power)
    raw_values[0x09] = 37
    raw_values[0x10] = round(pv_current * 10)
    raw_values[0x12] = round(pv_voltage * 10)
    return {
        "schema_version": 1,
        "sample_id": str(uuid.uuid4()),
        "device_slug": device_slug,
        "recorded_at": datetime.now(ZoneInfo(timezone)).isoformat(
            timespec="milliseconds"
        ),
        "sequence_number": index,
        "gateway_version": "simulator-0.1.0",
        "gateway_boot_id": str(uuid.uuid4()),
        "source": "simulator",
        "register_map_version": "prime-v1",
        "decoder_version": "prime-v1",
        "metrics": {
            "pv_voltage_v": round(pv_voltage, 1),
            "pv_current_a": round(pv_current, 1),
            "pv_power_w": round(pv_power, 1),
            "battery_voltage_v": 26.8,
            "ac_output_voltage_v": 220,
            "ac_output_current_a": round(output_power / 220, 1),
            "ac_output_power_w": round(output_power, 1),
            "load_percent": round(output_power / 10, 1),
            "inverter_temperature_c": 37,
        },
        "raw_registers": {
            f"0x{0x3000 + register_index:04X}": value
            for register_index, value in enumerate(raw_values)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kirim telemetry simulasi ke API lokal"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--device", default="prime-rumah-01")
    parser.add_argument("--timezone", default="Asia/Jakarta")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--interval", type=float, default=1)
    args = parser.parse_args()
    client = ApiClient(args.url, args.api_key, timeout=10, verify_tls=True)
    try:
        boot_id = uuid.uuid4()
        for index in range(1, args.count + 1):
            payload = sample(args.device, index, args.timezone)
            payload["gateway_boot_id"] = str(boot_id)
            result = client.send_batch([payload])
            print(
                f"{payload['recorded_at']} | PV {payload['metrics']['pv_power_w']:.1f} W | "
                f"OUT {payload['metrics']['ac_output_power_w']:.1f} W | {result}"
            )
            time.sleep(args.interval)
    finally:
        client.close()


if __name__ == "__main__":
    main()
