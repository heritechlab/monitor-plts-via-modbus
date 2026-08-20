"""Bandingkan perilaku register sebelum dan sesudah suatu perubahan kondisi.

Berguna untuk menguji hipotesis semacam "register nol ini milik input PLN":
nyalakan input PLN, catat waktunya, lalu jalankan skrip ini. Register yang tadinya
nol lalu ikut bergerak akan tampil sebagai BANGUN.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial, inverter, maupun BMS.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\compare-registers-before-after.py --at "2026-08-21 14:30"
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.db.models import InverterTelemetry
from app.db.session import SessionLocal
from sqlalchemy import select

ZONE = ZoneInfo("Asia/Jakarta")


def as_utc(value: datetime) -> datetime:
    """SQLite mengembalikan datetime tanpa info zona; perlakukan itu sebagai UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def summarise(values: list[float]) -> str:
    if not values:
        return "tidak ada data"
    return f"{min(values):.0f}..{max(values):.0f} ({len(set(values))} nilai)"


async def main(at: datetime, window_minutes: int) -> None:
    span = timedelta(minutes=window_minutes)
    # Bandingkan semuanya dalam UTC supaya tidak bergantung zona waktu mesin.
    pivot = at.astimezone(UTC)

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(InverterTelemetry.recorded_at, InverterTelemetry.raw_registers)
                .where(
                    InverterTelemetry.recorded_at >= pivot - span,
                    InverterTelemetry.recorded_at <= pivot + span,
                )
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    before: dict[str, list[float]] = defaultdict(list)
    after: dict[str, list[float]] = defaultdict(list)
    count_before = 0
    for recorded_at, registers in rows:
        is_before = as_utc(recorded_at) < pivot
        count_before += is_before
        target = before if is_before else after
        for address, value in (registers or {}).items():
            target[address].append(float(value))

    print(f"Titik acuan   : {at:%Y-%m-%d %H:%M} WIB (jendela +/- {window_minutes} menit)")
    print(f"Sampel sebelum: {count_before:,} | sesudah: {len(rows) - count_before:,}\n")
    if not count_before or count_before == len(rows):
        print("Salah satu sisi kosong. Pastikan waktu acuan benar dan data sudah terkumpul.")
        return

    addresses = sorted(set(before) | set(after), key=lambda value: int(value, 16))
    woke = []
    print(f"{'ADDR':8}{'SEBELUM':24}{'SESUDAH':24}STATUS")
    print("-" * 72)
    for address in addresses:
        was_flat_zero = set(before.get(address, [])) <= {0.0}
        now_nonzero = bool(set(after.get(address, [])) - {0.0})
        status = ""
        if was_flat_zero and now_nonzero:
            status = "<== BANGUN"
            woke.append(address)
        elif not was_flat_zero and not now_nonzero and after.get(address):
            status = "<== MATI"
        print(
            f"{address:8}{summarise(before.get(address, [])):24}"
            f"{summarise(after.get(address, [])):24}{status}"
        )

    print()
    if woke:
        print(f"Register yang bangun setelah perubahan: {', '.join(woke)}")
        print("Kuat dugaan register ini memang milik fungsi yang baru diaktifkan.")
    else:
        print("Tidak ada register nol yang ikut bergerak.")
        print("Berarti register nol itu bukan milik fungsi yang baru diaktifkan.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", required=True, help='Waktu perubahan WIB, mis. "2026-08-21 14:30"')
    parser.add_argument("--window", type=int, default=30, help="Menit sebelum & sesudah")
    args = parser.parse_args()
    moment = datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=ZONE)
    asyncio.run(main(moment, args.window))
