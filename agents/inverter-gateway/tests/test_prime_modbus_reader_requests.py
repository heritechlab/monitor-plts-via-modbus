"""Exercise PrimeModbusReader's request/response handling against a fake
serial device, covering both the telemetry block (0x3000, FC04) and the
settings block (0x4000, FC03) added when read_settings_registers() was
introduced.

Uses a FakeSerial rather than real hardware, matching the approach already
used in tests/test_inverter_address_scan.py and
tests/test_inverter_block_watch.py for the standalone diagnostic scripts --
this file covers the same request/response contract inside the production
gateway class itself.
"""

import struct

import pytest
from crc import append_crc
from modbus_reader import ModbusCrcError, ModbusError, ModbusTimeout, PrimeModbusReader


class FakeSerial:
    def __init__(self, slave_id: int, blocks: dict[tuple[int, int], list[int]]) -> None:
        self.slave_id = slave_id
        self.blocks = blocks
        self.buffer = b""
        self.requests: list[bytes] = []
        self.is_open = True

    def reset_input_buffer(self) -> None:
        self.buffer = b""

    def flush(self) -> None:
        pass

    def write(self, frame: bytes) -> None:
        self.requests.append(frame)
        slave, function, address, count = struct.unpack(">BBHH", frame[:6])
        values = self.blocks.get((function, address))
        if values is None or len(values) < count:
            self.buffer = append_crc(bytes([slave, function | 0x80, 0x02]))
            return
        payload = b"".join(struct.pack(">H", v) for v in values[:count])
        self.buffer = append_crc(bytes([slave, function, len(payload)]) + payload)

    def read(self, size: int) -> bytes:
        chunk, self.buffer = self.buffer[:size], self.buffer[size:]
        return chunk

    def close(self) -> None:
        self.is_open = False


def _wired(blocks: dict[tuple[int, int], list[int]]) -> PrimeModbusReader:
    reader = PrimeModbusReader("COM_FAKE", 9600, 1, 1.0)
    fake = FakeSerial(1, blocks)
    reader._serial = fake
    reader.port = "COM_FAKE"
    # Skip resolve_serial_port(): open() would try to hit the real OS port list.
    reader.open = lambda: None
    return reader


def test_read_prime_registers_returns_telemetry_block() -> None:
    values = list(range(32))
    reader = _wired({(0x04, 0x3000): values})
    assert reader.read_prime_registers() == values


def test_read_settings_registers_returns_settings_block() -> None:
    values = [100 + i for i in range(32)]
    reader = _wired({(0x03, 0x4000): values})
    assert reader.read_settings_registers() == values


def test_settings_read_does_not_disturb_telemetry_block() -> None:
    """Both blocks share one connection; reading one must not corrupt the other."""
    telemetry = list(range(32))
    settings = [200 + i for i in range(32)]
    reader = _wired({(0x04, 0x3000): telemetry, (0x03, 0x4000): settings})
    assert reader.read_prime_registers() == telemetry
    assert reader.read_settings_registers() == settings
    assert reader.read_prime_registers() == telemetry


def test_settings_exception_response_raises_modbus_error() -> None:
    reader = _wired({(0x04, 0x3000): list(range(32))})  # settings block absent
    with pytest.raises(ModbusError, match="exception code"):
        reader.read_settings_registers()


def test_wrong_byte_count_raises_modbus_error() -> None:
    reader = _wired({(0x03, 0x4000): [1, 2]})  # fewer than the 32 requested
    with pytest.raises(ModbusError):
        reader.read_settings_registers()


def test_timeout_when_device_silent() -> None:
    reader = _wired({})
    reader._serial.write = lambda _frame: None  # device never answers
    with pytest.raises(ModbusTimeout):
        reader.read_settings_registers()


def test_bad_crc_is_rejected() -> None:
    reader = _wired({(0x03, 0x4000): list(range(32))})

    def corrupt_write(frame: bytes) -> None:
        slave, function, _address, count = struct.unpack(">BBHH", frame[:6])
        payload = b"".join(struct.pack(">H", v) for v in range(count))
        # Valid header/payload, deliberately wrong CRC trailer.
        reader._serial.buffer = bytes([slave, function, len(payload)]) + payload + b"\x00\x00"

    reader._serial.write = corrupt_write
    with pytest.raises(ModbusCrcError):
        reader.read_settings_registers()


def test_only_read_function_codes_are_ever_emitted() -> None:
    """Safety net: neither read path may emit a write function code
    (0x05/0x06/0x0F/0x10), on this device or the settings block, ever."""
    reader = _wired(
        {(0x04, 0x3000): list(range(32)), (0x03, 0x4000): list(range(32))}
    )
    reader.read_prime_registers()
    reader.read_settings_registers()
    emitted = {frame[1] for frame in reader._serial.requests}
    assert emitted <= {0x03, 0x04}
