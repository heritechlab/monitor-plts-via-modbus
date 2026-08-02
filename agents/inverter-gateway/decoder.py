from typing import Any

START_ADDRESS = 0x3000
EXPECTED_REGISTER_COUNT = 32
DECODER_VERSION = "prime-v1"


def decode_registers(registers: list[int]) -> tuple[dict[str, float], dict[str, int]]:
    if len(registers) != EXPECTED_REGISTER_COUNT:
        raise ValueError(f"Diperlukan 32 register, diterima {len(registers)}")
    if any(not 0 <= value <= 0xFFFF for value in registers):
        raise ValueError("Register harus berupa uint16")

    raw = {
        f"0x{START_ADDRESS + index:04X}": value for index, value in enumerate(registers)
    }
    metrics: dict[str, Any] = {
        "ac_output_voltage_v": registers[0x01] / 10,
        "battery_voltage_v": registers[0x02] / 10,
        "ac_output_current_a": registers[0x03] / 10,
        "load_percent": float(registers[0x04]),
        "ac_output_power_w": float(registers[0x05]),
        "inverter_temperature_c": float(registers[0x09]),
        "pv_current_a": registers[0x10] / 10,
        "pv_voltage_v": registers[0x12] / 10,
    }
    metrics["pv_power_w"] = round(metrics["pv_voltage_v"] * metrics["pv_current_a"], 2)
    return metrics, raw
