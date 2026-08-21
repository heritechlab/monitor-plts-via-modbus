from typing import Any

START_ADDRESS = 0x3000
EXPECTED_REGISTER_COUNT = 32
DECODER_VERSION = "prime-v3-grid-source"


def decode_registers(registers: list[int]) -> tuple[dict[str, float], dict[str, int]]:
    if len(registers) != EXPECTED_REGISTER_COUNT:
        raise ValueError(f"Diperlukan 32 register, diterima {len(registers)}")
    if any(not 0 <= value <= 0xFFFF for value in registers):
        raise ValueError("Register harus berupa uint16")

    raw = {
        f"0x{START_ADDRESS + index:04X}": value for index, value in enumerate(registers)
    }
    # Sumber daya aktif. Dibuktikan lewat uji colok-lepas input PLN: kode 1 selalu
    # muncul bersamaan dengan tegangan (0x3000) dan frekuensi (0x3008) PLN hadir
    # serta stage inverter (0x300D) berhenti, sedangkan kode 2 kebalikannya.
    # Disimpan sebagai 1/0 agar rata-rata pada rentang waktu tetap bermakna:
    # 0,3 berarti 30% waktu itu beban disuplai PLN.
    grid_active = 1.0 if registers[0x0A] == 1 else 0.0

    metrics: dict[str, Any] = {
        "grid_active": grid_active,
        "grid_voltage_v": registers[0x00] / 10,
        "grid_frequency_hz": registers[0x08] / 10,
        # SOC versi inverter, murni turunan linear dari tegangan baterai
        # (SOC% = 30 x V - 716). Untuk LiFePO4 yang kurvanya datar angka ini
        # jauh kurang akurat dibanding SOC BMS, jadi dipisahkan namanya.
        "inverter_soc_percent": float(registers[0x16]),
        "ac_output_voltage_v": registers[0x01] / 10,
        "battery_voltage_v": registers[0x02] / 10,
        "ac_output_current_a": registers[0x03] / 10,
        "load_percent": float(registers[0x04]),
        # Nama field dipertahankan untuk kompatibilitas database/API existing.
        # Validasi lapangan menunjukkan 0x3005 mengikuti load% dan mendekati VA,
        # bukan pengukuran watt aktif dari energy meter.
        "ac_output_power_w": float(registers[0x05]),
        "inverter_temperature_c": float(registers[0x09]),
        "pv_current_a": registers[0x10] / 10,
        "pv_voltage_v": registers[0x12] / 10,
    }
    metrics["pv_power_w"] = round(metrics["pv_voltage_v"] * metrics["pv_current_a"], 2)
    return metrics, raw
