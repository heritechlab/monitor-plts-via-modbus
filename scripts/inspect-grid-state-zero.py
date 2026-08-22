"""Cari tahu arti 0x300A = 0.

Decoder saat ini menganggap 0x300A: 1 = PLN, selain itu = baterai. Kesimpulan
itu diambil saat uji colok-lepas PLN, di mana kita hanya pernah melihat nilai
1 dan 2. Belakangan nilai 0 ikut muncul, jadi cabang "selain itu" sekarang
menampung dua kondisi berbeda -- dan indikator sumber daya di dashboard bisa
menyesatkan kalau 0 ternyata bukan "pakai baterai".

Skrip ini memeriksa apa yang terjadi bersamaan dengan tiap nilai: tegangan PLN,
frekuensi, beban, tegangan keluaran. Kalau saat 0 semuanya nol/mati, artinya
inverter sedang tidak mengeluarkan daya sama sekali -- kondisi yang layak
ditampilkan berbeda dari "pakai baterai".

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\inspect-grid-state-zero.py --hours 48
"""

import argparse
import asyncio
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import select

from app.db.models import InverterTelemetry
from app.db.session import SessionLocal

JAKARTA = ZoneInfo("Asia/Jakarta")
STATE = "0x300A"
# Besaran pendamping yang sudah terbukti artinya, dengan pembaginya.
CONTEXT = {
    "tegangan PLN (V)": ("0x3000", 10),
    "tegangan keluar (V)": ("0x3001", 10),
    "tegangan baterai (V)": ("0x3002", 10),
    "arus keluar (A)": ("0x3003", 10),
    "beban (%)": ("0x3004", 1),
    "daya keluar (VA)": ("0x3005", 1),
    "frekuensi PLN (Hz)": ("0x3008", 10),
    "suhu inverter (C)": ("0x3009", 1),
    "tegangan PV (V)": ("0x3012", 10),
    "arus PV (A)": ("0x3010", 10),
}


def value(sample: dict[str, int], address: str, scale: int) -> float | None:
    raw = sample.get(address)
    return None if raw is None else raw / scale


def describe(values: list[float]) -> str:
    if not values:
        return "        -         -         -"
    return (
        f"{statistics.median(values):>9.1f}"
        f"{min(values):>10.1f}{max(values):>10.1f}"
    )


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(InverterTelemetry.recorded_at, InverterTelemetry.raw_registers)
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    samples = [(t, reg) for t, reg in rows if reg and reg.get(STATE) is not None]
    print(f"Sampel: {len(samples):,} dari {hours} jam terakhir\n")
    if len(samples) < 100:
        print("Data terlalu sedikit. Ingat prune-raw mengosongkan raw_registers lama.")
        return

    counts = Counter(s[STATE] for _t, s in samples)
    total = sum(counts.values())
    print("=" * 78)
    print(f"SEBARAN NILAI {STATE}")
    print("=" * 78)
    for state, count in sorted(counts.items()):
        share = count / total * 100
        print(f"   {STATE} = {state}: {count:>8,} sampel ({share:5.1f}%)")

    print("\n" + "=" * 78)
    print("KONDISI SAAT TIAP NILAI")
    print("=" * 78)
    for state in sorted(counts):
        subset = [s for _t, s in samples if s[STATE] == state]
        print(f"\n-- {STATE} = {state}  (n={len(subset):,})")
        print(f"   {'besaran':24}{'median':>9}{'min':>10}{'max':>10}")
        print("   " + "-" * 53)
        for label, (address, scale) in CONTEXT.items():
            values = [
                v
                for v in (value(s, address, scale) for s in subset)
                if v is not None
            ]
            print(f"   {label:24}{describe(values)}")

    print("\n" + "=" * 78)
    print("KAPAN NILAI 0 MUNCUL (waktu Jakarta)")
    print("=" * 78)
    zero_times = [t.astimezone(JAKARTA) for t, s in samples if s[STATE] == 0]
    if not zero_times:
        print("   Nilai 0 tidak muncul pada rentang ini.")
    else:
        by_hour = Counter(t.hour for t in zero_times)
        print("   sebaran per jam:")
        line = "   "
        for hour in range(24):
            line += f"{hour:02d}h={by_hour.get(hour, 0):<6}"
            if hour % 6 == 5:
                print(line)
                line = "   "
        if line.strip():
            print(line)
        print(f"\n   paling awal: {zero_times[0]:%Y-%m-%d %H:%M:%S}")
        print(f"   paling akhir: {zero_times[-1]:%Y-%m-%d %H:%M:%S}")

    print("\n" + "=" * 78)
    print("PERALIHAN NILAI (10 pertama)")
    print("=" * 78)
    print("Melihat urutan peralihan membantu membedakan kondisi sementara")
    print("(mis. jeda saat pindah sumber) dari kondisi yang bertahan lama.\n")
    shown = 0
    previous = None
    run_start = None
    for t, s in samples:
        state = s[STATE]
        if state != previous:
            if previous is not None and run_start is not None and shown < 10:
                duration = (t - run_start).total_seconds()
                print(
                    f"   {run_start.astimezone(JAKARTA):%m-%d %H:%M:%S} "
                    f"{STATE}={previous} bertahan {duration:>8.0f} detik "
                    f"-> berubah ke {state}"
                )
                shown += 1
            previous = state
            run_start = t

    print("\n" + "=" * 78)
    print("BACAAN")
    print("=" * 78)
    print("Kalau saat 0 tegangan keluar dan beban ikut nol, inverter sedang tidak")
    print("menyuplai apa pun -- itu bukan 'pakai baterai', dan decoder sebaiknya")
    print("membedakannya. Kalau saat 0 beban tetap jalan, 0 kemungkinan varian")
    print("dari kondisi baterai dan decoder sekarang sudah benar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=48)
    asyncio.run(main(parser.parse_args().hours))
