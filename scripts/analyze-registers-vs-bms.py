"""Cari arti register inverter dengan membandingkannya ke pengukuran BMS.

register_analysis bawaan hanya mengkorelasikan register terhadap metrik yang sudah
kita decode dari inverter itu sendiri, jadi ia buta terhadap besaran yang belum
punya pembanding sama sekali. Sejak BMS terpasang kita punya sumber kebenaran
independen (SOC, arus pack, daya pack) -- di situlah kandidat register baterai bisa
dibuktikan atau digugurkan.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\analyze-registers-vs-bms.py --hours 24
"""

import argparse
import asyncio
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.db.models import BmsTelemetry, InverterTelemetry
from app.db.session import SessionLocal
from sqlalchemy import select

BMS_METRICS = {
    "soc_percent": "SOC baterai (%)",
    "pack_current_a": "arus pack (A)",
    "pack_voltage_v": "tegangan pack (V)",
    "pack_power_w": "daya pack (W)",
}
# Inverter lazim melaporkan arus baterai sebagai besaran tanpa tanda plus flag
# charge/discharge terpisah. Tanpa pembanding nilai mutlak, register semacam itu
# lolos dari deteksi karena korelasinya terhadap arus bertanda hampir nol.
DERIVED_METRICS = {
    "abs_pack_current_a": ("pack_current_a", "|arus pack| (A)"),
    "abs_pack_power_w": ("pack_power_w", "|daya pack| (W)"),
}
ALL_LABELS = {**BMS_METRICS, **{key: label for key, (_src, label) in DERIVED_METRICS.items()}}
# Kedua gateway memoll tiap 5 detik tapi tidak serempak, jadi sampel disatukan
# ke ember waktu supaya bisa dipasangkan tanpa mengasumsikan stempel waktu sama.
BUCKET_SECONDS = 30


def bucket(moment: datetime) -> int:
    return int(moment.replace(tzinfo=moment.tzinfo or UTC).timestamp()) // BUCKET_SECONDS


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 5:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    num = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    den = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return None if den == 0 else num / den


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)

    async with SessionLocal() as session:
        inverter_rows = (
            await session.execute(
                select(InverterTelemetry.recorded_at, InverterTelemetry.raw_registers)
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()
        bms_rows = (
            await session.execute(
                select(
                    BmsTelemetry.recorded_at,
                    *[getattr(BmsTelemetry, name) for name in BMS_METRICS],
                )
                .where(BmsTelemetry.recorded_at >= since)
                .order_by(BmsTelemetry.recorded_at)
            )
        ).all()

    print(f"Sampel inverter: {len(inverter_rows):,} | sampel BMS: {len(bms_rows):,}")
    if not inverter_rows or not bms_rows:
        print("Data belum cukup pada rentang ini.")
        return

    # Rata-ratakan tiap ember waktu supaya jitter antar-gateway tidak jadi derau.
    reg_buckets: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for recorded_at, registers in inverter_rows:
        key = bucket(recorded_at)
        for address, value in (registers or {}).items():
            reg_buckets[key][address].append(float(value))

    bms_buckets: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in bms_rows:
        key = bucket(row.recorded_at)
        for name in BMS_METRICS:
            value = getattr(row, name)
            if value is not None:
                bms_buckets[key][name].append(float(value))
        for name, (source, _label) in DERIVED_METRICS.items():
            value = getattr(row, source)
            if value is not None:
                bms_buckets[key][name].append(abs(float(value)))

    shared = sorted(set(reg_buckets) & set(bms_buckets))
    print(f"Ember waktu yang berpasangan: {len(shared):,} ({BUCKET_SECONDS} detik per ember)\n")
    if len(shared) < 5:
        print("Terlalu sedikit pasangan untuk disimpulkan.")
        return

    addresses = sorted(
        {address for key in shared for address in reg_buckets[key]},
        key=lambda value: int(value, 16),
    )

    findings = []
    for address in addresses:
        for metric, label in ALL_LABELS.items():
            xs, ys = [], []
            for key in shared:
                reg_values = reg_buckets[key].get(address)
                bms_values = bms_buckets[key].get(metric)
                if reg_values and bms_values:
                    xs.append(sum(reg_values) / len(reg_values))
                    ys.append(sum(bms_values) / len(bms_values))
            coefficient = pearson(xs, ys)
            if coefficient is not None:
                findings.append((abs(coefficient), address, label, coefficient, xs, ys))

    findings.sort(reverse=True, key=lambda item: item[0])

    print(f"{'ADDR':8}{'METRIK BMS':22}{'r':>8}   RENTANG REGISTER -> RENTANG BMS")
    print("-" * 78)
    for _strength, address, label, coefficient, xs, ys in findings[:20]:
        span = f"{min(xs):.0f}..{max(xs):.0f}  ->  {min(ys):.1f}..{max(ys):.1f}"
        print(f"{address:8}{label:22}{coefficient:>8.3f}   {span}")

    print("\nCatatan: r mendekati +1/-1 berarti bergerak seiring, bukan bukti mutlak.")
    print("Dua besaran bisa berkorelasi tanpa satu menyebabkan lainnya.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    asyncio.run(main(parser.parse_args().hours))
