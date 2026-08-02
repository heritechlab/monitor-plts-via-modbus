def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def append_crc(data: bytes) -> bytes:
    return data + modbus_crc16(data).to_bytes(2, "little")


def validate_crc(frame: bytes) -> bool:
    return len(frame) >= 4 and modbus_crc16(frame[:-2]) == int.from_bytes(
        frame[-2:], "little"
    )
