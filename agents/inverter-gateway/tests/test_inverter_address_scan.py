import struct

import pytest
from crc import append_crc
from inverter_address_scan import ScanError, read_block, scan_connection


class FakeSerial:
    """Perangkat Modbus palsu: menjawab satu blok, menolak sisanya.

    Cukup untuk memastikan skrip menyusun frame yang benar dan membedakan
    jawaban data dari exception -- tanpa menyentuh inverter sungguhan.
    """

    def __init__(self, slave_id: int, known_address: int, values: list[int]) -> None:
        self.slave_id = slave_id
        self.known_address = known_address
        self.values = values
        self.buffer = b""
        self.requests: list[bytes] = []

    def reset_input_buffer(self) -> None:
        self.buffer = b""

    def flush(self) -> None:
        pass

    def write(self, frame: bytes) -> None:
        self.requests.append(frame)
        slave, function, address, count = struct.unpack(">BBHH", frame[:6])
        if address == self.known_address:
            payload = b"".join(struct.pack(">H", v) for v in self.values[:count])
            self.buffer = append_crc(
                bytes([slave, function, len(payload)]) + payload
            )
        else:
            # 0x02 = illegal data address, jawaban lazim untuk alamat tak dikenal.
            self.buffer = append_crc(bytes([slave, function | 0x80, 0x02]))

    def read(self, size: int) -> bytes:
        chunk, self.buffer = self.buffer[:size], self.buffer[size:]
        return chunk


def test_known_address_returns_values() -> None:
    device = FakeSerial(1, 0x3000, [11, 22, 33, 44])
    assert read_block(device, 1, 0x04, 0x3000, 4) == [11, 22, 33, 44]


def test_request_frame_matches_modbus_layout() -> None:
    device = FakeSerial(1, 0x3000, [0] * 4)
    read_block(device, 1, 0x04, 0x3000, 4)
    slave, function, address, count = struct.unpack(">BBHH", device.requests[0][:6])
    assert (slave, function, address, count) == (1, 0x04, 0x3000, 4)


def test_unknown_address_reports_illegal_data_address() -> None:
    device = FakeSerial(1, 0x3000, [1, 2])
    with pytest.raises(ScanError, match="illegal data address"):
        read_block(device, 1, 0x04, 0x2000, 2)


def test_timeout_when_device_silent() -> None:
    device = FakeSerial(1, 0x3000, [1, 2])
    device.write = lambda frame: None  # perangkat diam, tak ada jawaban
    with pytest.raises(ScanError, match="timeout"):
        read_block(device, 1, 0x04, 0x3000, 2)


def test_scan_never_emits_a_write_function_code() -> None:
    """Pengaman: skrip ini tidak boleh bisa mengubah setelan inverter."""
    device = FakeSerial(1, 0x3000, [0] * 4)
    for function_code in (0x03, 0x04):
        read_block(device, 1, function_code, 0x3000, 4)
    emitted = {frame[1] for frame in device.requests}
    assert emitted <= {0x03, 0x04}


def test_full_sweep_prints_both_answered_and_rejected(capsys) -> None:
    """Satu blok menjawab, sisanya menolak -- keduanya harus tercetak rapi.

    Menjaga agar exception yang diformat tidak meledak di tengah sapuan,
    yang akan menyembunyikan blok-blok setelahnya.
    """
    device = FakeSerial(1, 0x3000, list(range(220, 236)))
    blocks = [(0x2000, "blok uji"), (0x3000, "kontrol")]
    scan_connection(device, 1, 8, blocks)

    output = capsys.readouterr().out
    assert "illegal data address" in output
    assert "0x2000" in output
    assert "0x3000  OK" in output
    # Kedua function code harus dicoba pada tiap blok.
    assert output.count("0x2000") == 2
