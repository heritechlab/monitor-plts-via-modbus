"""JK-BD6A24S8P register decoder.

Register map empirically confirmed against the live device (manual address sweep,
cross-checked against https://github.com/tlamoureux24/JK-BMS-by-Modbus-RS485). Values are
individual single-register FC03 reads (see modbus_reader.JkBmsModbusReader) keyed by
absolute address; addresses within this device only exist at even numbers, and a 32-bit
field spans two of those (high word, then low word 2 addresses later).
"""

from typing import Any

DECODER_VERSION = "jk-bms-v1"

CELL_COUNT = 8
CELL_ADDRESSES = [0x1200 + 2 * i for i in range(CELL_COUNT)]

# name -> (addresses, kind, scale). kind: u32/i32 (2 registers, high then low) or
# u16/i16 (1 register). scale is applied after combining/sign-extending the raw int.
STAT_LAYOUT: dict[str, tuple[tuple[int, ...], str, float]] = {
    "pack_voltage_v": ((0x1290, 0x1292), "u32", 0.001),
    "pack_power_w": ((0x1294, 0x1296), "u32", 0.001),
    "pack_current_a": ((0x1298, 0x129A), "i32", 0.001),
    "temperature_1_c": ((0x129C,), "i16", 0.1),
    "temperature_2_c": ((0x129E,), "i16", 0.1),
    "alarm_flags": ((0x12A0, 0x12A2), "u32", 1),
    "balance_current_a": ((0x12A4,), "i16", 0.001),
    "remaining_capacity_ah": ((0x12A8, 0x12AA), "i32", 0.001),
    "full_capacity_ah": ((0x12AC, 0x12AE), "u32", 0.001),
    "cycle_count": ((0x12B0, 0x12B2), "u32", 1),
}
SOC_ADDRESS = 0x12A6

STAT_ADDRESSES = sorted(
    {address for addresses, _kind, _scale in STAT_LAYOUT.values() for address in addresses}
    | {SOC_ADDRESS}
)
ALL_ADDRESSES = CELL_ADDRESSES + STAT_ADDRESSES


def _combine(registers: dict[int, int], addresses: tuple[int, ...], kind: str) -> int:
    if len(addresses) == 1:
        raw = registers[addresses[0]]
        if kind == "i16" and raw >= 0x8000:
            raw -= 0x10000
        return raw
    high, low = (registers[address] for address in addresses)
    raw = (high << 16) | low
    if kind == "i32" and raw >= 0x8000_0000:
        raw -= 0x1_0000_0000
    return raw


def decode_registers(registers: dict[int, int]) -> tuple[dict[str, Any], dict[str, int]]:
    missing = [f"0x{address:04X}" for address in ALL_ADDRESSES if address not in registers]
    if missing:
        raise ValueError(f"Register hilang dari hasil baca: {missing}")

    cell_voltages_mv = [registers[address] for address in CELL_ADDRESSES]
    metrics: dict[str, Any] = {"cell_voltages_mv": cell_voltages_mv}
    for name, (addresses, kind, scale) in STAT_LAYOUT.items():
        raw = _combine(registers, addresses, kind)
        metrics[name] = round(raw * scale, 3) if scale != 1 else raw

    soc_raw = registers[SOC_ADDRESS]
    metrics["soc_percent"] = float(soc_raw & 0xFF)

    raw_out = {f"0x{address:04X}": value for address, value in registers.items()}
    return metrics, raw_out
