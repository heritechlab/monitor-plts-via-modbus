"""Periksa apakah inverter mematuhi ambang tegangan yang Anda setel.

Anda pernah mengeluh: saat input PLN dicolok, beban langsung pindah ke PLN
walau tegangan baterai belum turun sampai ambang yang disetel. Sampai kini itu
baru kesan; sekarang bisa diuji, karena kita punya dua sisi datanya:

  - ambang setelan, terbaca dari blok 0x4000 dan dikonfirmasi lewat menu:
        A7 = 25,0 V  ambang pindah ke PLN
        A6 = 25,8 V  ambang kembali ke baterai
  - riwayat telemetri: tegangan baterai dan sumber aktif tiap 5 detik

Skrip mencari tiap saat sumber berpindah, lalu mencatat tegangan baterai pada
detik itu. Pindah ke PLN saat tegangan masih jauh di atas A7 berarti inverter
memutuskan berdasarkan hal lain -- bukan sekadar ambang tegangan.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\audit-source-switch-thresholds.py --hours 168
"""

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import select

from app.db.models import InverterTelemetry
from app.db.session import SessionLocal

JAKARTA = ZoneInfo("Asia/Jakarta")
# Terbaca dari 0x4013 dan 0x400F/0x4012, dikonfirmasi lewat menu inverter.
TO_GRID_THRESHOLD = 25.0
TO_BATTERY_THRESHOLD = 25.8
# Selisih yang dianggap layak disorot; di bawah ini masih wajar sebagai
# histeresis atau perbedaan titik ukur.
TOLERANCE_V = 0.3


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    InverterTelemetry.recorded_at,
                    InverterTelemetry.grid_active,
                    InverterTelemetry.battery_voltage_v,
                    InverterTelemetry.grid_voltage_v,
                    InverterTelemetry.pv_power_w,
                    InverterTelemetry.load_percent,
                )
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    samples = [
        row
        for row in rows
        if row.grid_active is not None and row.battery_voltage_v is not None
    ]
    print(f"Sampel: {len(samples):,} dari {hours} jam terakhir")
    print(f"Ambang setelan: A7 (ke PLN) = {TO_GRID_THRESHOLD} V | "
          f"A6 (ke baterai) = {TO_BATTERY_THRESHOLD} V\n")
    if len(samples) < 100:
        print("Data terlalu sedikit pada rentang ini.")
        return

    switches = []
    for previous, current in zip(samples, samples[1:], strict=False):
        if previous.grid_active == current.grid_active:
            continue
        # Abaikan kedipan 1-2 sampel: 0x300A sempat menunjukkan nilai transisi
        # sesaat yang bukan perpindahan sungguhan.
        switches.append((previous, current))

    if not switches:
        print("Tidak ada perpindahan sumber pada rentang ini.")
        return

    to_grid = [(p, c) for p, c in switches if c.grid_active == 1]
    to_battery = [(p, c) for p, c in switches if c.grid_active == 0]

    print("=" * 78)
    print(f"PINDAH KE PLN  ({len(to_grid)} kejadian)")
    print("=" * 78)
    print(f"Setelan bilang pindah saat baterai turun ke {TO_GRID_THRESHOLD} V.\n")
    if to_grid:
        print(f"   {'waktu (Jakarta)':22}{'baterai':>9}{'selisih':>10}"
              f"{'PLN':>8}{'PV':>8}  catatan")
        print("   " + "-" * 66)
        early = 0
        for _previous, current in to_grid[:20]:
            voltage = current.battery_voltage_v
            delta = voltage - TO_GRID_THRESHOLD
            note = ""
            if delta > TOLERANCE_V:
                note = "di atas ambang"
                early += 1
            print(
                f"   {current.recorded_at.astimezone(JAKARTA):%Y-%m-%d %H:%M:%S}  "
                f"{voltage:>8.2f}V{delta:>+9.2f}V"
                f"{current.grid_voltage_v or 0:>7.0f}V{current.pv_power_w or 0:>7.0f}W"
                f"  {note}"
            )
        if len(to_grid) > 20:
            print(f"   ... dan {len(to_grid) - 20} kejadian lain")

        voltages = [c.battery_voltage_v for _p, c in to_grid]
        above = sum(1 for v in voltages if v - TO_GRID_THRESHOLD > TOLERANCE_V)
        print(f"\n   tegangan saat pindah: median={statistics.median(voltages):.2f} V "
              f"min={min(voltages):.2f} V max={max(voltages):.2f} V")
        print(f"   pindah saat masih DI ATAS ambang: {above} dari {len(to_grid)}")

    print("\n" + "=" * 78)
    print(f"PINDAH KE BATERAI  ({len(to_battery)} kejadian)")
    print("=" * 78)
    if to_battery:
        voltages = [c.battery_voltage_v for _p, c in to_battery]
        above = sum(1 for v in voltages if v >= TO_BATTERY_THRESHOLD - TOLERANCE_V)
        print(f"   tegangan saat pindah: median={statistics.median(voltages):.2f} V "
              f"min={min(voltages):.2f} V max={max(voltages):.2f} V")
        print(f"   pindah saat sudah di atas {TO_BATTERY_THRESHOLD} V: "
              f"{above} dari {len(to_battery)}")

    print("\n" + "=" * 78)
    print("BACAAN")
    print("=" * 78)
    if to_grid:
        voltages = [c.battery_voltage_v for _p, c in to_grid]
        above = sum(1 for v in voltages if v - TO_GRID_THRESHOLD > TOLERANCE_V)
        if above > len(to_grid) / 2:
            print("Sebagian besar perpindahan ke PLN terjadi saat tegangan baterai")
            print("masih di atas ambang A7. Ini mendukung keluhan Anda: inverter")
            print("tidak memakai ambang itu sebagai satu-satunya penentu.")
            print()
            print("Kemungkinan penyebab: setelan A0=D3 (prioritas) membuat inverter")
            print("langsung memakai PLN begitu tersedia, dan ambang A7 hanya berlaku")
            print("pada mode prioritas lain. Membandingkan dengan manual akan")
            print("memastikannya.")
        else:
            print("Perpindahan ke PLN umumnya terjadi di sekitar atau di bawah ambang")
            print("A7, jadi inverter tampak mematuhi setelannya.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=168)
    asyncio.run(main(parser.parse_args().hours))
