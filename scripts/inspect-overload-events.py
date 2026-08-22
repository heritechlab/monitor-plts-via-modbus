"""Periksa seberapa sering inverter melewati kapasitasnya, dan apa dampaknya.

Data 48 jam menunjukkan beban pernah mencapai 112% dan daya keluar 1125 VA pada
inverter 1000 W, sementara suhu menyentuh 55 C. Angka puncak sendiri belum
berarti masalah -- lonjakan sesaat saat motor start itu normal. Yang menentukan
adalah BERAPA LAMA dan SESERING APA, serta apakah suhu ikut naik mengikutinya.

Skrip ini mengelompokkan sampel beban tinggi yang berurutan menjadi "kejadian",
lalu melaporkan durasi tiap kejadian dan suhu tertinggi selama kejadian itu.
Lonjakan 5 detik berbeda maknanya dari beban 95% yang bertahan sejam.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\inspect-overload-events.py --hours 48
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
# Ambang dipisah supaya lonjakan sesaat tidak tercampur dengan beban menetap.
THRESHOLDS = (80, 100)
# Jeda maksimum antar sampel yang masih dianggap satu kejadian. Gateway memoll
# tiap ~5 detik; jeda lebih panjang berarti kejadian terpisah.
MAX_GAP_SECONDS = 30


def summarize(values: list[float], unit: str) -> str:
    if not values:
        return "-"
    return (
        f"median={statistics.median(values):.0f}{unit} "
        f"max={max(values):.0f}{unit}"
    )


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    InverterTelemetry.recorded_at,
                    InverterTelemetry.load_percent,
                    InverterTelemetry.ac_output_power_w,
                    InverterTelemetry.inverter_temperature_c,
                    InverterTelemetry.grid_active,
                )
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    samples = [row for row in rows if row.load_percent is not None]
    print(f"Sampel: {len(samples):,} dari {hours} jam terakhir\n")
    if len(samples) < 100:
        print("Data terlalu sedikit pada rentang ini.")
        return

    loads = [row.load_percent for row in samples]
    temps = [row.inverter_temperature_c for row in samples if row.inverter_temperature_c]
    print("=" * 78)
    print("SEBARAN BEBAN")
    print("=" * 78)
    ordered = sorted(loads)

    def percentile(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]

    print(f"   median   : {statistics.median(loads):>6.0f}%")
    print(f"   p90      : {percentile(0.90):>6.0f}%")
    print(f"   p99      : {percentile(0.99):>6.0f}%")
    print(f"   maksimum : {max(loads):>6.0f}%")
    for threshold in THRESHOLDS:
        count = sum(1 for value in loads if value >= threshold)
        share = count / len(loads) * 100
        print(f"   >= {threshold}% : {count:>6,} sampel ({share:5.2f}% waktu)")

    print("\n" + "=" * 78)
    print("KEJADIAN BEBAN TINGGI")
    print("=" * 78)
    print("Sampel berurutan digabung jadi satu kejadian; lonjakan sesaat dan")
    print("beban menetap ditampilkan terpisah karena dampaknya berbeda.\n")

    for threshold in THRESHOLDS:
        events = []
        current: list = []
        for row in samples:
            if row.load_percent >= threshold:
                if current and (
                    row.recorded_at - current[-1].recorded_at
                ).total_seconds() > MAX_GAP_SECONDS:
                    events.append(current)
                    current = []
                current.append(row)
            elif current:
                events.append(current)
                current = []
        if current:
            events.append(current)

        print(f"-- Beban >= {threshold}%: {len(events)} kejadian")
        if not events:
            print("   (tidak ada)\n")
            continue

        durations = [
            (event[-1].recorded_at - event[0].recorded_at).total_seconds()
            for event in events
        ]
        brief = sum(1 for d in durations if d <= 10)
        print(f"   durasi: {summarize(durations, ' detik')}")
        print(f"   kejadian <= 10 detik (lonjakan sesaat): {brief} dari {len(events)}")

        longest = sorted(
            zip(events, durations, strict=True), key=lambda pair: pair[1], reverse=True
        )[:5]
        print(f"\n   {'mulai (Jakarta)':22}{'durasi':>9}{'beban max':>11}"
              f"{'VA max':>9}{'suhu max':>10}  sumber")
        print("   " + "-" * 68)
        for event, duration in longest:
            peak_load = max(r.load_percent for r in event)
            peak_va = max(
                (r.ac_output_power_w for r in event if r.ac_output_power_w), default=0
            )
            peak_temp = max(
                (r.inverter_temperature_c for r in event if r.inverter_temperature_c),
                default=0,
            )
            on_grid = sum(1 for r in event if r.grid_active == 1)
            source = "PLN" if on_grid > len(event) / 2 else "baterai"
            start = event[0].recorded_at.astimezone(JAKARTA)
            print(
                f"   {start:%Y-%m-%d %H:%M:%S}   {duration:>7.0f}s"
                f"{peak_load:>10.0f}%{peak_va:>9.0f}{peak_temp:>9.0f}C  {source}"
            )
        print()

    print("=" * 78)
    print("SUHU vs BEBAN")
    print("=" * 78)
    if temps:
        print(f"   suhu: median={statistics.median(temps):.0f}C max={max(temps):.0f}C")
        bands = [(0, 50), (50, 80), (80, 100), (100, 999)]
        print(f"\n   {'beban':16}{'n':>8}{'suhu median':>14}{'suhu max':>11}")
        print("   " + "-" * 49)
        for low, high in bands:
            subset = [
                row.inverter_temperature_c
                for row in samples
                if low <= row.load_percent < high and row.inverter_temperature_c
            ]
            if subset:
                label = f"{low}-{high}%" if high < 999 else f">= {low}%"
                print(
                    f"   {label:16}{len(subset):>8,}"
                    f"{statistics.median(subset):>13.0f}C{max(subset):>10.0f}C"
                )

    print("\n" + "=" * 78)
    print("BACAAN")
    print("=" * 78)
    print("Lonjakan pendek di atas 100% wajar untuk beban bermotor (kulkas, pompa)")
    print("dan biasanya ditoleransi inverter. Yang perlu diperhatikan adalah beban")
    print("tinggi yang bertahan lama, apalagi kalau suhu ikut naik mengikutinya.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=48)
    asyncio.run(main(parser.parse_args().hours))
