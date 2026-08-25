"""Cek cepat: apakah port ini BMS JK-BD6A24S8P yang sama protokolnya dengan pack pertama.

Dipakai saat pack fisik kedua baru dicolok dan Device Manager menunjukkan port
CH340 baru. Membaca lewat JkBmsModbusReader yang sama persis dengan gateway
produksi (bukan sweep dari nol), supaya hasilnya langsung bisa dibandingkan
dengan angka pack pertama.

Read-only (FC03 baca saja, tidak ada tulis).

Pemakaian:
    .venv\\Scripts\\python.exe probe_new_pack.py --port COM5
"""

import argparse
import sys

from decoder import ALL_ADDRESSES, decode_registers
from modbus_reader import JkBmsModbusReader, ModbusError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mis. COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    reader = JkBmsModbusReader(args.port, args.baud, args.slave, args.timeout)

    try:
        try:
            registers = reader.read_registers(ALL_ADDRESSES)
        except ModbusError as reason:
            print(f"Gagal membaca {args.port}: {reason}")
            print("\nKemungkinan: bukan JK-BD6A24S8P, baud/slave beda, atau kabel/ID salah.")
            print("Kalau ini terjadi, jalankan bms_scan.py (di agents/inverter-gateway)")
            print("untuk sweep protokol dari nol -- itu tidak berasumsi apa pun.")
            return 1
    finally:
        reader.close()

    metrics, raw = decode_registers(registers)

    print(f"Port {args.port} menjawab sebagai JK-BD6A24S8P.\n")
    print(f"{'metrik':24}{'nilai':>12}")
    print("-" * 36)
    for key, value in metrics.items():
        if key == "cell_voltages_mv":
            continue
        print(f"{key:24}{value!s:>12}")
    if "cell_voltages_mv" in metrics:
        cells = metrics["cell_voltages_mv"]
        print(f"\ncell_voltages_mv: {cells}")
        print(f"selisih sel tertinggi-terendah: {max(cells) - min(cells)} mV")

    print(f"\nregister mentah terbaca: {len(raw)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
