from crc import append_crc, modbus_crc16, validate_crc


def test_standard_crc_vector() -> None:
    assert modbus_crc16(b"123456789") == 0x4B37


def test_prime_request_is_fc04_and_valid() -> None:
    frame = append_crc(bytes.fromhex("01 04 30 00 00 20"))
    assert frame[1] == 0x04
    assert validate_crc(frame)
