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

# Cocok dengan besaran yang kita ketahui dari sisi lain.
CONFIRMED = {
    0x4003: ("Rating daya inverter", 1, "W"),
    0x4004: ("Frekuensi nominal", 1, "Hz"),
    0x4005: ("Tegangan nominal AC", 1, "V"),
}
# Skala per-12V TERBUKTI dua kali: operator mencocokkan menu inverternya
# (2026-08-23), dan manual menyatakannya eksplisit -- "The voltage value in this
# manual is the voltage of a single battery, the 24V system is 2 batteries".
# Jadi nilai register disimpan per-12V dan dikali 2 untuk sistem 24 V.
#
# Urutan register TIDAK mengikuti urutan kode A di menu; percobaan menggeser
# alamat tidak pernah mencocokkan A8=500/A9=220 milik manual, jadi pemetaan di
# bawah ini murni dari kecocokan nilai yang dikonfirmasi operator.
MENU_CONFIRMED = {
    0x4008: "A2 -- constant charge, batas atas/full",
    0x4013: "A7 -- inverter pindah ke PLN (mode d3)",
}
# A6 (kembali ke baterai, 25,8 V) cocok dengan DUA register bernilai sama,
# jadi mana yang benar belum bisa dipastikan dari nilainya saja.
MENU_AMBIGUOUS = {
    0x400F: "A6? -- kembali ke baterai (nilai sama dengan 0x4012)",
    0x4012: "A6? -- kembali ke baterai (nilai sama dengan 0x400F)",
}
# Sisanya masih dugaan: ikut skala per-12V yang sudah terbukti, tapi arti
# tiap alamatnya belum dicocokkan ke menu.
BATTERY_SCALE = range(0x4008, 0x4014)


def render(values: list[int]) -> None:
    print("=" * 78)
    print("BLOK SETELAN 0x4000 (FC03)")
    print("=" * 78)
    print(f"   {'ADDR':8}{'raw':>7}   tafsiran")
    print("   " + "-" * 62)

    for index, value in enumerate(values):
        address = SETTINGS_ADDRESS + index
        if address in CONFIRMED:
            _label, scale, unit = CONFIRMED[address]
            reading = f"{value / scale:g} {unit}  <- cocok dengan data kita"
        elif value == 0:
            # Nol tidak masuk akal sebagai ambang tegangan; jangan dipaksa
            # ditafsirkan hanya karena alamatnya berada di kelompok itu.
            reading = "-"
        elif address in MENU_CONFIRMED:
            reading = f"{value / 10 * 2:.1f} V  <- TERBUKTI: {MENU_CONFIRMED[address]}"
        elif address in MENU_AMBIGUOUS:
            reading = f"{value / 10 * 2:.1f} V  <- {MENU_AMBIGUOUS[address]}"
        elif address in BATTERY_SCALE:
            reading = f"{value / 10 * 2:.1f} V  (skala terbukti, arti belum)"
        else:
            reading = f"/10={value / 10:g}  /100={value / 100:g}"
        print(f"   0x{address:04X}  {value:>6}   {reading}")

    print()
    print("=" * 78)
    print("STATUS")
    print("=" * 78)
    print("Skala per-12V TERBUKTI. Manual menyatakannya eksplisit: nilai di menu")
    print("adalah tegangan satu baterai, dan sistem 24 V memakai dua baterai.")
    print("Cocok dengan menu inverter yang dibaca operator:")
    print("   A2 = 28,2 V  -> 0x4008 = 141")
    print("   A7 = 25,0 V  -> 0x4013 = 125")
    print()
    print("A6 = 25,8 V cocok dengan DUA register (0x400F dan 0x4012, sama-sama")
    print("129), jadi mana yang benar belum bisa dipastikan dari nilainya saja.")
    print("Cara memisahkannya: ubah A6 di menu ke angka lain, baca ulang, lihat")
    print("register mana yang ikut berubah. Yang diam berarti bukan A6.")
    print()
    print("Urutan register tidak mengikuti urutan kode A, jadi alamat lain di")
    print("0x4008-0x4013 belum bisa dipetakan hanya dengan menggeser posisi.")


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
