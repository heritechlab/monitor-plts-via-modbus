import struct
import time
from collections.abc import Iterable
from typing import Any, Self

import serial
from crc import append_crc, validate_crc
from serial.tools import list_ports


class ModbusError(RuntimeError):
    pass


class ModbusTimeout(ModbusError):
    pass


class ModbusCrcError(ModbusError):
    pass


def _is_ch340(port: Any) -> bool:
    description = " ".join(
        str(value or "")
        for value in (
            getattr(port, "description", ""),
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
            getattr(port, "hwid", ""),
        )
    ).lower()
    return getattr(port, "vid", None) == 0x1A86 or any(
        marker in description for marker in ("ch340", "ch341", "usb-serial")
    )


def resolve_serial_port(
    configured_port: str,
    detected_ports: Iterable[Any] | None = None,
) -> str:
    """Resolve a configured COM port and safely fall back to one CH340 adapter."""

    ports = list(detected_ports if detected_ports is not None else list_ports.comports())
    configured = configured_port.strip()
    automatic = configured.lower() == "auto"

    if not automatic:
        for port in ports:
            device = str(getattr(port, "device", ""))
            if device.lower() == configured.lower():
                return device

    ch340_ports = [port for port in ports if _is_ch340(port)]
    if len(ch340_ports) == 1:
        return str(ch340_ports[0].device)
    if automatic and len(ports) == 1:
        return str(ports[0].device)

    available = ", ".join(str(getattr(port, "device", "?")) for port in ports)
    if len(ch340_ports) > 1:
        raise ModbusError(
            "Lebih dari satu adaptor CH340 terdeteksi; tetapkan SERIAL_PORT secara eksplisit"
        )
    if automatic:
        raise ModbusError(
            f"Adaptor USB-RS485 belum terdeteksi (port tersedia: {available or 'tidak ada'})"
        )
    raise ModbusError(
        f"Port {configured} tidak ditemukan dan fallback CH340 tidak tersedia "
        f"(port tersedia: {available or 'tidak ada'})"
    )


class JkBmsModbusReader:
    """Read-only JK BMS (JK-BD6A24S8P) client. Emits FC03 only.

    Empirically confirmed (via manual register sweep) that this device only answers
    single-register (count=1) reads at specific even addresses — a multi-register block
    read spanning its unmapped odd addresses cannot be assumed to work, so every register
    is fetched individually rather than as a contiguous block.
    """

    FUNCTION_CODE = 0x03

    def __init__(self, port: str, baudrate: int, slave_id: int, timeout: float) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("Slave ID harus 1..247")
        self.configured_port = port
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.timeout = timeout
        self._serial: serial.Serial | None = None

    def open(self) -> None:
        resolved_port = resolve_serial_port(self.configured_port)
        if (
            self._serial
            and self._serial.is_open
            and self.port.lower() == resolved_port.lower()
        ):
            return
        self.close()
        self.port = resolved_port
        self._serial = serial.Serial(
            port=resolved_port,
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

    def read_registers(self, addresses: list[int]) -> dict[int, int]:
        """Read each address individually. Returns {address: raw_uint16}."""
        self.open()
        return {address: self._read_single(address) for address in addresses}

    def _read_single(self, address: int) -> int:
        assert self._serial is not None
        request = append_crc(
            struct.pack(">BBHH", self.slave_id, self.FUNCTION_CODE, address, 1)
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
            raise ModbusError(f"Modbus exception code 0x{third:02X} pada 0x{address:04X}")
        if function != self.FUNCTION_CODE:
            raise ModbusError(f"Function code tidak sesuai: 0x{function:02X}")
        if third != 2:
            raise ModbusError(f"Byte count {third}, seharusnya 2")
        frame = header + self._read_exact(4)
        if not validate_crc(frame):
            raise ModbusCrcError("CRC response tidak valid")
        return struct.unpack(">H", frame[3:5])[0]

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
