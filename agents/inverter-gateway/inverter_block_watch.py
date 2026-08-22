"""Petakan luas blok register dan amati mana yang berubah dari waktu ke waktu.

Sapuan alamat menemukan blok 0x4000 menjawab lewat FC03, tapi nilai awalnya
(100, 500, 1000, 50, 220) berpola bulat -- ciri setelan, bukan hasil ukur.
Sensor suhu tidak akan pernah bernilai bulat begitu, dan yang lebih menentukan:
sensor BERUBAH, setelan tidak.

Skrip ini melakukan dua hal:
  1. Mencari sampai di mana tiap blok sebenarnya membentang, dengan menambah
     jumlah register sampai inverter menolak. Sapuan sebelumnya hanya membaca
     16 register, padahal blok 0x3000 saja kita tahu berisi 32.
  2. Membaca ulang beberapa kali dengan jeda, lalu melaporkan register mana
     yang nilainya bergerak. Register yang bergerak dalam hitungan detik hampir
     pasti pengukuran; yang diam kemungkinan setelan.

Untuk menemukan suhu MPPT, jalankan sekali saat MPPT dingin (malam / PV mati)
dan sekali saat panas (siang terik), lalu bandingkan angkanya.

PENTING -- port serial dipakai eksklusif oleh gateway:
    Stop-ScheduledTask -TaskName "PLTS Inverter Gateway"
    .venv\\Scripts\\python.exe inverter_block_watch.py --port COM3
    Start-ScheduledTask -TaskName "PLTS Inverter Gateway"

Skrip ini hanya MEMBACA (FC03/FC04). Tidak ada perintah tulis sama sekali,
jadi setelan inverter tidak mungkin berubah karenanya. Ini penting khusus
untuk 0x4000: blok holding lazimnya BISA ditulis, jadi jangan pernah pakai
alat lain yang menulis ke sana tanpa tahu persis artinya.
"""

import argparse
import statistics
import sys
import time

import serial
from inverter_address_scan import ScanError, read_block

# Blok yang terbukti menjawab pada sapuan alamat, dengan function code-nya.
TARGETS = [
    (0x3000, 0x04, "blok kerja (FC04)"),
    (0x4000, 0x03, "blok baru (FC03)"),
]
PROBE_SIZES = (8, 16, 32, 48, 64, 96, 125)


def measure_extent(
    connection: serial.Serial, slave_id: int, function_code: int, address: int
) -> int:
    """Cari jumlah register terbesar yang masih dijawab inverter."""
    largest = 0
    for size in PROBE_SIZES:
        try:
            read_block(connection, slave_id, function_code, address, size)
        except ScanError:
            break
        largest = size
        time.sleep(0.05)
    return largest


def sample_block(
    connection: serial.Serial,
    slave_id: int,
    function_code: int,
    address: int,
    count: int,
    rounds: int,
    gap: float,
) -> list[list[int]]:
    readings = []
    for index in range(rounds):
        for attempt in range(3):
            try:
                readings.append(
                    read_block(connection, slave_id, function_code, address, count)
                )
                break
            except ScanError as reason:
                if attempt == 2:
                    print(f"   (pembacaan {index + 1} gagal: {reason})")
                time.sleep(0.2)
        if index < rounds - 1:
            time.sleep(gap)
    return readings


def report(address: int, label: str, readings: list[list[int]]) -> None:
    print("=" * 78)
    print(f"0x{address:04X} -- {label}  ({len(readings)} pembacaan)")
    print("=" * 78)
    if not readings:
        print("   Tidak ada pembacaan berhasil.\n")
        return

    count = min(len(r) for r in readings)
    print(f"   {'ADDR':9}{'nilai':>28}  {'berubah?':<10}")
    print("   " + "-" * 60)
    moving = []
    for index in range(count):
        series = [r[index] for r in readings]
        distinct = sorted(set(series))
        changed = len(distinct) > 1
        if changed:
            moving.append((f"0x{address + index:04X}", series))
        shown = " ".join(f"{v:5d}" for v in series[:5])
        marker = "BERUBAH" if changed else "tetap"
        print(f"   0x{address + index:04X}   {shown:>28}  {marker:<10}")

    print(f"\n   Ringkas: {len(moving)} dari {count} register berubah.")
    if moving:
        print("\n   Register yang bergerak (kandidat pengukuran):")
        for name, series in moving:
            spread = max(series) - min(series)
            print(
                f"      {name}: min={min(series)} max={max(series)} "
                f"rentang={spread} median={statistics.median(series):.0f}"
            )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mis. COM3")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--rounds", type=int, default=6, help="jumlah pembacaan")
    parser.add_argument("--gap", type=float, default=5.0, help="jeda antar pembacaan (detik)")
    args = parser.parse_args()

    total = args.rounds * args.gap
    print(f"Port {args.port} | slave {args.slave}")
    print(f"{args.rounds} pembacaan, jeda {args.gap} detik (total ~{total:.0f} detik)\n")

    try:
        connection = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            write_timeout=1.0,
            exclusive=True,
        )
    except serial.SerialException as reason:
        print(f"Gagal membuka {args.port}: {reason}")
        print("\nKalau 'access is denied', gateway masih memegang port itu.")
        print('Hentikan dulu: Stop-ScheduledTask -TaskName "PLTS Inverter Gateway"')
        sys.exit(1)

    with connection:
        print("=" * 78)
        print("LUAS TIAP BLOK")
        print("=" * 78)
        extents = {}
        for address, function_code, label in TARGETS:
            extent = measure_extent(connection, args.slave, function_code, address)
            extents[address] = extent
            fc_name = "FC04" if function_code == 0x04 else "FC03"
            if extent:
                print(f"   0x{address:04X} ({fc_name}): sampai {extent} register  -- {label}")
            else:
                print(f"   0x{address:04X} ({fc_name}): tidak menjawab  -- {label}")
        print()

        for address, function_code, label in TARGETS:
            extent = extents.get(address, 0)
            if not extent:
                continue
            readings = sample_block(
                connection,
                args.slave,
                function_code,
                address,
                min(extent, 32),
                args.rounds,
                args.gap,
            )
            report(address, label, readings)

    print("=" * 78)
    print("BACAAN")
    print("=" * 78)
    print("Register yang BERUBAH dalam hitungan detik adalah pengukuran.")
    print("Yang tetap kemungkinan setelan -- termasuk angka bulat seperti")
    print("100/500/1000/220 yang terlihat di 0x4000.")
    print()
    print("Untuk suhu MPPT: jalankan sekali malam hari (MPPT dingin) dan sekali")
    print("siang terik (MPPT panas), lalu bandingkan. Suhu MPPT akan jauh berbeda")
    print("antara keduanya, sementara setelan tetap sama.")


if __name__ == "__main__":
    main()
