"""Sapu alamat Modbus inverter untuk mencari blok register di luar 0x3000.

Gateway selama ini hanya membaca FC04 di 0x3000 sebanyak 32 register. Sensor
suhu heatsink MPPT terlihat ada secara fisik pada unitnya, jadi kalau ia tidak
muncul di 32 register itu berarti ia berada di alamat lain yang belum pernah
kita baca -- bukan tidak ada.

Skrip ini menyapu rentang alamat dan mencatat mana yang dijawab inverter.
Inverter Modbus lazim menolak alamat yang tidak ia punya dengan exception
code 0x02 (illegal data address), jadi alamat yang MENJAWAB adalah petunjuk
adanya blok data di sana.

PENTING -- port serial dipakai eksklusif oleh gateway:
    Hentikan gateway dulu sebelum menjalankan skrip ini, lalu nyalakan lagi.
    Selama skrip berjalan, telemetri inverter berhenti terekam.

    Stop-ScheduledTask -TaskName "PLTS Inverter Gateway"
    .venv\\Scripts\\python.exe inverter_address_scan.py --port COM3
    Start-ScheduledTask -TaskName "PLTS Inverter Gateway"

Skrip ini hanya MEMBACA (FC03/FC04). Tidak ada satu pun perintah tulis, jadi
tidak ada pengaturan inverter yang bisa berubah karenanya.
"""

import argparse
import struct
import sys
import time

import serial
from crc import append_crc, validate_crc

# Blok yang lazim dipakai inverter merek ini dan sejenisnya. 0x3000 disertakan
# sebagai kontrol: ia HARUS menjawab, dan kalau tidak berarti ada yang salah
# dengan kabel/port, bukan dengan alamatnya.
DEFAULT_BLOCKS = [
    (0x0000, "holding klasik"),
    (0x1000, "blok 0x1000"),
    (0x2000, "blok 0x2000"),
    (0x3000, "blok kerja kita (kontrol)"),
    (0x4000, "blok 0x4000"),
    (0x5000, "blok 0x5000"),
    (0x9000, "blok 0x9000"),
    (0xF000, "blok 0xF000"),
]
EXCEPTION_NAMES = {
    0x01: "illegal function",
    0x02: "illegal data address",
    0x03: "illegal data value",
    0x04: "device failure",
    0x06: "device busy",
}


class ScanError(RuntimeError):
    pass


def read_block(
    connection: serial.Serial,
    slave_id: int,
    function_code: int,
    address: int,
    count: int,
) -> list[int]:
    request = append_crc(
        struct.pack(">BBHH", slave_id, function_code, address, count)
    )
    connection.reset_input_buffer()
    connection.write(request)
    connection.flush()
    # Jeda ini sudah terbukti perlu pada dongle CH340 di rig ini: tanpa jeda,
    # pembacaan kadang kembali kosong walau perangkatnya menjawab.
    time.sleep(0.03)

    header = connection.read(3)
    if len(header) < 3:
        raise ScanError("timeout")
    slave, function, third = header
    if slave != slave_id:
        raise ScanError(f"slave {slave} bukan {slave_id}")
    if function == (function_code | 0x80):
        tail = connection.read(2)
        if not validate_crc(header + tail):
            raise ScanError("CRC exception tidak valid")
        name = EXCEPTION_NAMES.get(third, f"0x{third:02X}")
        raise ScanError(f"exception: {name}")
    if function != function_code:
        raise ScanError(f"function 0x{function:02X} tidak sesuai")

    payload = connection.read(third)
    if len(payload) < third:
        raise ScanError("payload terpotong")
    tail = connection.read(2)
    if not validate_crc(header + payload + tail):
        raise ScanError("CRC data tidak valid")
    return [
        struct.unpack(">H", payload[i : i + 2])[0] for i in range(0, len(payload), 2)
    ]


def scan_connection(connection, slave_id: int, count: int, blocks: list) -> None:
    """Sapu semua blok pada koneksi yang sudah terbuka.

    Dipisah dari scan() supaya alur cetaknya bisa diuji dengan perangkat palsu,
    tanpa perlu port serial sungguhan.
    """
    for function_code in (0x04, 0x03):
        label = "FC04 (input register)" if function_code == 0x04 else "FC03 (holding register)"
        print("=" * 78)
        print(label)
        print("=" * 78)
        for address, note in blocks:
            try:
                values = read_block(connection, slave_id, function_code, address, count)
            except ScanError as reason:
                print(f"   0x{address:04X}  --  {str(reason):<34}  {note}")
                continue
            nonzero = sum(1 for v in values if v)
            preview = " ".join(f"{v:5d}" for v in values[:8])
            print(
                f"   0x{address:04X}  OK  {nonzero:2d}/{len(values)} tidak nol"
                f"{'':<16}  {note}"
            )
            print(f"            {preview}")
        print()


def scan(port: str, baud: int, slave_id: int, count: int, blocks: list) -> None:
    print(f"Port {port} | baud {baud} | slave {slave_id} | {count} register per blok\n")
    with serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
        write_timeout=1.0,
        exclusive=True,
    ) as connection:
        scan_connection(connection, slave_id, count, blocks)

    print("=" * 78)
    print("BACAAN")
    print("=" * 78)
    print("Blok 0x3000 harus OK -- itu yang dipakai gateway sehari-hari. Kalau ia")
    print("gagal juga, masalahnya di kabel/port, bukan di alamat.")
    print()
    print("Blok lain yang menjawab OK layak ditelusuri: catat nilainya, lalu")
    print("bandingkan saat MPPT dingin (malam) dan panas (siang terik). Register")
    print("suhu MPPT akan naik-turun mengikuti produksi PV.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mis. COM3")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument(
        "--address",
        type=lambda v: int(v, 0),
        help="sapu satu alamat saja, mis. --address 0x2000",
    )
    args = parser.parse_args()

    blocks = (
        [(args.address, "alamat pilihan")] if args.address is not None else DEFAULT_BLOCKS
    )
    try:
        scan(args.port, args.baud, args.slave, args.count, blocks)
    except serial.SerialException as reason:
        print(f"Gagal membuka {args.port}: {reason}")
        print("\nKalau pesannya 'access is denied', gateway masih memegang port itu.")
        print('Hentikan dulu: Stop-ScheduledTask -TaskName "PLTS Inverter Gateway"')
        sys.exit(1)


if __name__ == "__main__":
    main()
