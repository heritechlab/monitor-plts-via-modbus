"""Tampilkan blok setelan inverter (0x4000, FC03) beserta tafsiran skalanya.

Pengamatan blok membuktikan seluruh 32 register 0x4000 tidak bergerak sama
sekali selama pengamatan -- itu blok setelan, bukan pengukuran. Beberapa
nilainya sudah cocok dengan yang kita ketahui: 0x4003=1000 (rating inverter),
0x4005=220 (tegangan nominal), 0x4004=50 (frekuensi).

Kelompok 0x4008-0x4013 bernilai 119-170. Dibagi 10 hasilnya 11,9-17,0 V, yang
untuk sistem 24 V terlihat seperti setelan disimpan dalam satuan 12 V; dikali
dua hasilnya 23,8-34,0 V -- rentang yang wajar untuk ambang baterai.

TAFSIRAN SKALA DI BAWAH INI MASIH DUGAAN. Cara membuktikannya ada pada Anda,
bukan pada skrip ini: buka menu setelan di layar inverter, lalu cocokkan
angkanya dengan kolom yang dicetak. Yang cocok berarti terbukti; yang tidak
cocok berarti dugaan skalanya keliru dan harus dibuang.

PENTING -- port serial dipakai eksklusif oleh gateway:
    Stop-ScheduledTask -TaskName "PLTS Inverter Gateway"
    .venv\\Scripts\\python.exe inverter_settings_dump.py --port COM3
    Start-ScheduledTask -TaskName "PLTS Inverter Gateway"

Skrip ini hanya MEMBACA (FC03). Tidak ada perintah tulis sama sekali.
Blok holding memang lazimnya bisa ditulis, jadi jangan pernah memakai alat
lain untuk menulis ke sini tanpa tahu persis arti tiap register -- salah tulis
bisa mengubah ambang kerja inverter Anda.
"""

import argparse
import sys

import serial
from inverter_address_scan import ScanError, read_block

SETTINGS_ADDRESS = 0x4000
SETTINGS_COUNT = 32

# Yang sudah cocok dengan besaran yang kita ketahui dari sisi lain.
CONFIRMED = {
    0x4003: ("Rating daya inverter", 1, "W"),
    0x4004: ("Frekuensi nominal", 1, "Hz"),
    0x4005: ("Tegangan nominal AC", 1, "V"),
}
# Dugaan: setelan tegangan baterai disimpan per-12V, jadi dikali 2 untuk 24V.
BATTERY_GUESS = range(0x4008, 0x4014)


def render(values: list[int]) -> None:
    print("=" * 78)
    print("BLOK SETELAN 0x4000 (FC03)")
    print("=" * 78)
    print(f"   {'ADDR':8}{'raw':>7}   tafsiran")
    print("   " + "-" * 62)

    for index, value in enumerate(values):
        address = SETTINGS_ADDRESS + index
        if address in CONFIRMED:
            label, scale, unit = CONFIRMED[address]
            reading = f"{value / scale:g} {unit}  <- cocok dengan data kita"
        elif value == 0:
            # Nol tidak masuk akal sebagai ambang tegangan; jangan dipaksa
            # ditafsirkan hanya karena alamatnya berada di kelompok itu.
            reading = "-"
        elif address in BATTERY_GUESS:
            reading = (
                f"DUGAAN ambang baterai: {value / 10 * 2:.1f} V "
                f"(kalau disimpan per-12V)"
            )
        else:
            reading = f"/10={value / 10:g}  /100={value / 100:g}"
        print(f"   0x{address:04X}  {value:>6}   {reading}")

    print()
    print("=" * 78)
    print("CARA MEMBUKTIKAN")
    print("=" * 78)
    print("Buka menu setelan di layar inverter, lalu cocokkan angkanya dengan")
    print("kolom di atas. Yang perlu dicari terutama:")
    print()
    print("  - ambang tegangan balik ke PLN (yang Anda keluhkan tidak dipatuhi)")
    print("  - ambang tegangan potong/low battery")
    print("  - ambang tegangan selesai charge")
    print("  - prioritas sumber (setelan A0 yang Anda sebut D3)")
    print()
    print("Kalau ada angka menu yang cocok persis dengan salah satu baris di atas,")
    print("kita dapat satu register terbukti. Kalau tidak ada yang cocok, dugaan")
    print("skala per-12V itu keliru dan kita cari pola lain.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mis. COM3")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--slave", type=int, default=1)
    args = parser.parse_args()

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
        try:
            values = read_block(
                connection, args.slave, 0x03, SETTINGS_ADDRESS, SETTINGS_COUNT
            )
        except ScanError as reason:
            print(f"Gagal membaca blok setelan: {reason}")
            sys.exit(1)

    render(values)


if __name__ == "__main__":
    main()
