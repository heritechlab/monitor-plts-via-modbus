"""Perbesar beberapa menit di sekitar tiap perpindahan sumber.

Operator punya penjelasan yang masuk akal untuk kejadian 21 Agu 23:31 (baterai
tercatat 26,00 V, di atas ambang A7=25,0 V): beban kejut (mis. kompresor
kulkas start) bisa membuat tegangan turun sesaat ~2 V, lalu pulih dalam
hitungan detik. Sampel kita berjarak 5 detik -- sag sesaat semacam itu bisa
saja terjadi PERSIS di antara dua sampel dan tidak pernah tertangkap.

Skrip ini tidak bisa membuktikan sag itu terjadi (datanya memang tidak
tersimpan), tapi bisa memeriksa jejak tidak langsungnya: apakah ada lonjakan
beban tepat sebelum perpindahan. Beban tinggi adalah prasyarat fisik untuk
sag tegangan -- kalau beban saat itu justru rendah, teori beban-kejut tidak
didukung data, dan penyebabnya harus dicari di tempat lain.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\inspect-switch-vicinity.py --hours 168
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import select

from app.db.models import InverterTelemetry
from app.db.session import SessionLocal

JAKARTA = ZoneInfo("Asia/Jakarta")
WINDOW_BEFORE = timedelta(minutes=3)
WINDOW_AFTER = timedelta(minutes=1)


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    InverterTelemetry.recorded_at,
                    InverterTelemetry.grid_active,
                    InverterTelemetry.battery_voltage_v,
                    InverterTelemetry.load_percent,
                    InverterTelemetry.ac_output_power_w,
                )
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    samples = [row for row in rows if row.grid_active is not None]
    print(f"Sampel: {len(samples):,} dari {hours} jam terakhir\n")
    if len(samples) < 20:
        print("Data terlalu sedikit pada rentang ini.")
        return

    switches = []
    for previous, current in zip(samples, samples[1:], strict=False):
        if previous.grid_active != current.grid_active:
            switches.append((previous, current))

    to_grid = [(p, c) for p, c in switches if c.grid_active == 1]
    if not to_grid:
        print("Tidak ada perpindahan ke PLN pada rentang ini.")
        return

    print(f"Memeriksa {len(to_grid)} perpindahan ke PLN.\n")

    for _previous, current in to_grid:
        window_start = current.recorded_at - WINDOW_BEFORE
        window_end = current.recorded_at + WINDOW_AFTER
        vicinity = [
            row for row in samples if window_start <= row.recorded_at <= window_end
        ]

        local_time = current.recorded_at.astimezone(JAKARTA)
        print("=" * 78)
        print(f"Perpindahan ke PLN pada {local_time:%Y-%m-%d %H:%M:%S}")
        print(f"   tegangan baterai saat tercatat: {current.battery_voltage_v:.2f} V")
        print("=" * 78)

        if len(vicinity) < 2:
            print("   Tidak cukup sampel di sekitarnya untuk diperiksa.\n")
            continue

        before_switch = [row for row in vicinity if row.recorded_at < current.recorded_at]
        loads = [row.load_percent for row in before_switch if row.load_percent is not None]
        peak_load = max(loads) if loads else None
        baseline_load = loads[0] if loads else None

        print(f"   {'waktu':10}{'baterai':>9}{'beban':>7}{'daya':>8}   sumber")
        print("   " + "-" * 48)
        for row in vicinity:
            marker = " <-- pindah" if row.recorded_at == current.recorded_at else ""
            source = "PLN" if row.grid_active == 1 else "baterai"
            local = row.recorded_at.astimezone(JAKARTA)
            voltage = f"{row.battery_voltage_v:.2f}V" if row.battery_voltage_v else "-"
            load = f"{row.load_percent:.0f}%" if row.load_percent is not None else "-"
            power = f"{row.ac_output_power_w:.0f}W" if row.ac_output_power_w else "-"
            print(f"   {local:%H:%M:%S}  {voltage:>8}{load:>7}{power:>8}   {source}{marker}")

        print()
        if peak_load is not None and baseline_load is not None and peak_load - baseline_load >= 20:
            print(
                f"   Beban melonjak dari ~{baseline_load:.0f}% ke {peak_load:.0f}% "
                "sebelum berpindah -- konsisten dengan teori beban kejut."
            )
        elif peak_load is not None:
            print(
                f"   Beban di sekitar kejadian ini stabil (~{peak_load:.0f}% puncak) --"
                " tidak ada lonjakan mencolok dalam data yang tersimpan."
            )
        print()

    print("=" * 78)
    print("BATASAN")
    print("=" * 78)
    print("Ini tidak bisa membuktikan sag tegangan sesaat, karena sampel kita")
    print("berjarak 5 detik dan sag semacam itu bisa lebih pendek dari itu.")
    print("Yang bisa dilihat hanya jejak tidak langsungnya lewat pola beban.")
    print()
    print("Kalau ingin bukti langsung, satu-satunya cara adalah polling lebih")
    print("rapat untuk sementara (mis. tiap 1 detik) saat menunggu beban kejut")
    print("terjadi secara alami -- bukan sesuatu yang bisa digali dari data lama.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=168)
    asyncio.run(main(parser.parse_args().hours))
