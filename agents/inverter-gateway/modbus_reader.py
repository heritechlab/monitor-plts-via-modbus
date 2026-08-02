import struct
import time
from typing import Self

import serial

from crc import append_crc, validate_crc


class ModbusError(RuntimeError):
    pass


class ModbusTimeout(ModbusError):
    pass


class ModbusCrcError(ModbusError):
    pass


class PrimeModbusReader:
    """Read-only PRIME inverter client. The only emitted function code is FC04."""

    START_ADDRESS = 0x3000
    REGISTER_COUNT = 32
    FUNCTION_CODE = 0x04

    def __init__(self, port: str, baudrate: int, slave_id: int, timeout: float) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("Slave ID harus 1..247")
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.timeout = timeout
        self._serial: serial.Serial | None = None

    def open(self) -> None:
        if self._serial and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            write_timeout=self.timeout,
            exclusive=True,
        )

    def close(self) -> None:
        if self._serial:
            self._serial.close()
            self._serial = None

    def read_prime_registers(self) -> list[int]:
        self.open()
        assert self._serial is not None
        request = append_crc(
            struct.pack(
                ">BBHH",
                self.slave_id,
                self.FUNCTION_CODE,
                self.START_ADDRESS,
                self.REGISTER_COUNT,
            )
        )
        self._serial.reset_input_buffer()
        self._serial.write(request)
        self._serial.flush()

        header = self._read_exact(3)
        slave, function, third = header
        if slave != self.slave_id:
            raise ModbusError(f"Slave response tidak sesuai: {slave}")
        if function == (self.FUNCTION_CODE | 0x80):
            frame = header + self._read_exact(2)
            if not validate_crc(frame):
                raise ModbusCrcError("CRC exception response tidak valid")
            raise ModbusError(f"Modbus exception code 0x{third:02X}")
        if function != self.FUNCTION_CODE:
            raise ModbusError(f"Function code tidak sesuai: 0x{function:02X}")
        expected_bytes = self.REGISTER_COUNT * 2
        if third != expected_bytes:
            raise ModbusError(f"Byte count {third}, seharusnya {expected_bytes}")
        frame = header + self._read_exact(expected_bytes + 2)
        if not validate_crc(frame):
            raise ModbusCrcError("CRC response tidak valid")
        return list(struct.unpack(f">{self.REGISTER_COUNT}H", frame[3:-2]))

    def _read_exact(self, count: int) -> bytes:
        assert self._serial is not None
        result = bytearray()
        deadline = time.monotonic() + self.timeout
        while len(result) < count and time.monotonic() < deadline:
            chunk = self._serial.read(count - len(result))
            if chunk:
                result.extend(chunk)
        if len(result) != count:
            raise ModbusTimeout(f"Timeout: menerima {len(result)} dari {count} byte")
        return bytes(result)

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *_args) -> None:
        self.close()
