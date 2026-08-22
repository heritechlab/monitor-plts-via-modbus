import struct

from crc import append_crc
from inverter_block_watch import measure_extent, report, sample_block


class BlockDevice:
    """Perangkat palsu dengan dua blok berbeda sifat.

    0x3000 bergerak tiap pembacaan (meniru pengukuran), 0x4000 diam (meniru
    setelan). Keduanya punya batas lebar yang berbeda, supaya penelusuran luas
    blok ikut teruji.
    """

    def __init__(self) -> None:
        self.buffer = b""
        self.tick = 0
        self.blocks = {
            (0x3000, 0x04): (32, "moving"),
            (0x4000, 0x03): (16, "static"),
        }

    def reset_input_buffer(self) -> None:
        self.buffer = b""

    def flush(self) -> None:
        pass

    def write(self, frame: bytes) -> None:
        slave, function, address, count = struct.unpack(">BBHH", frame[:6])
        entry = self.blocks.get((address, function))
        if entry is None or count > entry[0]:
            self.buffer = append_crc(bytes([slave, function | 0x80, 0x02]))
            return
        width, kind = entry
        if kind == "moving":
            self.tick += 1
            values = [100 + self.tick + i for i in range(count)]
        else:
            values = [100, 500, 1000, 220][: count] + [7] * max(0, count - 4)
        payload = b"".join(struct.pack(">H", v & 0xFFFF) for v in values[:count])
        self.buffer = append_crc(bytes([slave, function, len(payload)]) + payload)

    def read(self, size: int) -> bytes:
        chunk, self.buffer = self.buffer[:size], self.buffer[size:]
        return chunk


def test_extent_stops_at_device_limit() -> None:
    device = BlockDevice()
    assert measure_extent(device, 1, 0x04, 0x3000) == 32
    assert measure_extent(device, 1, 0x03, 0x4000) == 16


def test_extent_zero_when_block_absent() -> None:
    assert measure_extent(BlockDevice(), 1, 0x04, 0x9000) == 0


def test_sampling_collects_requested_rounds() -> None:
    readings = sample_block(BlockDevice(), 1, 0x04, 0x3000, 4, rounds=3, gap=0)
    assert len(readings) == 3
    assert all(len(r) == 4 for r in readings)


def test_moving_block_is_reported_as_changed(capsys) -> None:
    readings = sample_block(BlockDevice(), 1, 0x04, 0x3000, 4, rounds=3, gap=0)
    report(0x3000, "uji", readings)
    output = capsys.readouterr().out
    assert "BERUBAH" in output
    assert "4 dari 4 register berubah" in output


def test_static_block_is_reported_as_unchanged(capsys) -> None:
    readings = sample_block(BlockDevice(), 1, 0x03, 0x4000, 4, rounds=3, gap=0)
    report(0x4000, "uji", readings)
    output = capsys.readouterr().out
    assert "0 dari 4 register berubah" in output
    assert "BERUBAH" not in output


def test_probe_never_emits_a_write_function_code() -> None:
    """Pengaman: 0x4000 adalah holding register yang lazimnya bisa ditulis."""
    device = BlockDevice()
    emitted = []
    original = device.write

    def spy(frame: bytes) -> None:
        emitted.append(frame[1])
        original(frame)

    device.write = spy
    measure_extent(device, 1, 0x03, 0x4000)
    sample_block(device, 1, 0x03, 0x4000, 4, rounds=2, gap=0)
    assert set(emitted) <= {0x03, 0x04}
