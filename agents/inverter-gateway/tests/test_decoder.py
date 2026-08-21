import pytest
from decoder import decode_registers


def test_decode_confirmed_registers() -> None:
    registers = [0] * 32
    registers[0x01] = 2175
    registers[0x02] = 272
    registers[0x03] = 11
    registers[0x04] = 24
    registers[0x05] = 240
    registers[0x09] = 37
    registers[0x10] = 122
    registers[0x12] = 799
    metrics, raw = decode_registers(registers)
    assert metrics["ac_output_voltage_v"] == 217.5
    assert metrics["battery_voltage_v"] == 27.2
    assert metrics["ac_output_power_w"] == 240
    assert metrics["pv_power_w"] == pytest.approx(974.78)
    assert len(raw) == 32


def test_decoder_rejects_partial_response() -> None:
    with pytest.raises(ValueError):
        decode_registers([0] * 31)


def _registers(**overrides: int) -> list[int]:
    registers = [0] * 32
    registers[0x01] = 2175
    registers[0x02] = 260
    registers[0x03] = 11
    registers[0x04] = 24
    registers[0x05] = 240
    registers[0x09] = 37
    registers[0x10] = 122
    registers[0x12] = 799
    for key, value in overrides.items():
        registers[int(key, 16)] = value
    return registers


def test_decodes_grid_source_when_on_pln() -> None:
    """Kombinasi nyata saat beban disuplai PLN (hasil uji colok input PLN)."""
    metrics, _raw = decode_registers(
        _registers(**{"0x00": 2240, "0x08": 500, "0x0A": 1, "0x16": 64})
    )
    assert metrics["grid_active"] == 1.0
    assert metrics["grid_voltage_v"] == pytest.approx(224.0)
    assert metrics["grid_frequency_hz"] == pytest.approx(50.0)
    assert metrics["inverter_soc_percent"] == 64.0


def test_decodes_grid_source_when_on_battery() -> None:
    """Kombinasi nyata saat PLN terputus: kode 2, tegangan sisa, frekuensi nol."""
    metrics, _raw = decode_registers(
        _registers(**{"0x00": 90, "0x08": 0, "0x0A": 2, "0x16": 64})
    )
    assert metrics["grid_active"] == 0.0
    assert metrics["grid_voltage_v"] == pytest.approx(9.0)
    assert metrics["grid_frequency_hz"] == 0.0


def test_inverter_soc_matches_measured_voltage_formula() -> None:
    """0x3016 terbukti = 3 x 0x3002 - 716 pada data lapangan."""
    for battery_raw, expected_soc in ((258, 58), (262, 70), (270, 94)):
        metrics, _raw = decode_registers(
            _registers(**{"0x02": battery_raw, "0x16": 3 * battery_raw - 716})
        )
        assert metrics["inverter_soc_percent"] == expected_soc
        assert metrics["battery_voltage_v"] == pytest.approx(battery_raw / 10)
