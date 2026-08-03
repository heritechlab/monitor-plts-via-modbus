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
