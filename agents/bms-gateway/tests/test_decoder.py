import pytest
from decoder import ALL_ADDRESSES, decode_registers

# Nilai ini adalah hasil scan register manual sungguhan dari perangkat JK-BD6A24S8P
# (8S LiFePO4, hampir penuh, idle) — dipakai sebagai golden fixture.
REAL_SAMPLE = {
    0x1200: 3472,
    0x1202: 3472,
    0x1204: 3472,
    0x1206: 3470,
    0x1208: 3472,
    0x120A: 3472,
    0x120C: 3472,
    0x120E: 3472,
    0x1290: 0,
    0x1292: 27775,
    0x1294: 0,
    0x1296: 0,
    0x1298: 0,
    0x129A: 0,
    0x129C: 301,
    0x129E: 300,
    0x12A0: 0,
    0x12A2: 0,
    0x12A4: 0,
    0x12A6: 100,
    0x12A8: 1,
    0x12AA: 34308,
    0x12AC: 1,
    0x12AE: 34464,
    0x12B0: 0,
    0x12B2: 0,
}


def test_decode_real_sample() -> None:
    metrics, raw = decode_registers(REAL_SAMPLE)
    assert metrics["cell_voltages_mv"] == [3472, 3472, 3472, 3470, 3472, 3472, 3472, 3472]
    assert metrics["pack_voltage_v"] == pytest.approx(27.775)
    assert metrics["pack_current_a"] == 0
    assert metrics["temperature_1_c"] == pytest.approx(30.1)
    assert metrics["temperature_2_c"] == pytest.approx(30.0)
    assert metrics["remaining_capacity_ah"] == pytest.approx(99.844)
    assert metrics["full_capacity_ah"] == pytest.approx(100.0)
    assert metrics["soc_percent"] == 100.0
    assert metrics["cycle_count"] == 0
    assert len(raw) == len(ALL_ADDRESSES)


def test_negative_pack_current_decodes_as_discharge() -> None:
    sample = dict(REAL_SAMPLE)
    # -5000 mA two's complement across the 32-bit (high, low) register pair.
    raw32 = (-5000) & 0xFFFF_FFFF
    sample[0x1298] = raw32 >> 16
    sample[0x129A] = raw32 & 0xFFFF
    metrics, _raw = decode_registers(sample)
    assert metrics["pack_current_a"] == pytest.approx(-5.0)


def test_decoder_rejects_missing_registers() -> None:
    incomplete = dict(REAL_SAMPLE)
    del incomplete[0x1290]
    with pytest.raises(ValueError, match="hilang"):
        decode_registers(incomplete)
