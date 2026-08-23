"""Cari register arus/daya PLN di antara register yang belum terpetakan.

Blok 0x3000-0x301F sudah disapu habis dan hanya memberi tegangan+frekuensi PLN
(0x3000, 0x3008) -- tidak ada arus atau daya di sisi input PLN. Skrip lain
sudah membuktikan register keluaran (0x3005) hanya mengikuti persen beban,
bukan watt-meter sungguhan.

Ini kemungkinan bukan sekadar register belum ditemukan -- banyak inverter
hybrid kelas menengah memakai relay bypass untuk mode PLN: arus PLN mengalir
langsung ke beban lewat relay, TIDAK lewat tahap konversi daya inverter yang
biasanya di situ sensor arus dipasang. Tapi sebelum menyimpulkan itu, layak
dicek dulu pakai data yang sudah tersimpan -- gratis, tidak perlu uji baru.

Metode: ambil semua sampel saat grid_active=1 (PLN sedang menyuplai), lalu uji
tiap register yang belum dipetakan terhadap arus/daya keluaran (ac_output_*)
sebagai proksi -- kalau PLN yang menyuplai beban, arus keluaran mestinya
mendekati arus PLN. Register yang RASIONYA konstan terhadap proksi itu adalah
kandidat kuat; yang diam saja padahal beban berubah-ubah bukan kandidat.

Ini uji hipotesis yang bisa GAGAL, bukan sekadar peringkat korelasi -- sama
seperti scripts/verify-register-hypotheses.py, supaya tidak mengulang
kesalahan 0x300A yang dulu terlihat meyakinkan dari korelasi saja.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\hunt-grid-power-register.py --hours 168
"""

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import select

from app.db.models import InverterTelemetry
from app.db.session import SessionLocal

# Register yang sudah punya arti; sisanya jadi kandidat.
KNOWN_ADDRESSES = {
    "0x3000", "0x3001", "0x3002", "0x3003", "0x3004", "0x3005",
    "0x3008", "0x3009", "0x300A", "0x3010", "0x3012", "0x3016",
}
MIN_SAMPLES = 30
MIN_LOAD_SPREAD_A = 0.3  # arus keluaran harus berubah-ubah, bukan datar


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 10:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return None if den == 0 else num / den


async def main(hours: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=hours)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    InverterTelemetry.recorded_at,
                    InverterTelemetry.grid_active,
                    InverterTelemetry.ac_output_current_a,
                    InverterTelemetry.ac_output_power_w,
                    InverterTelemetry.raw_registers,
                )
                .where(InverterTelemetry.recorded_at >= since)
                .order_by(InverterTelemetry.recorded_at)
            )
        ).all()

    on_grid = [
        row for row in rows
        if row.grid_active == 1.0
        and row.raw_registers
        and row.ac_output_current_a is not None
    ]
    print(
        f"Sampel total: {len(rows):,} | "
        f"sampel saat PLN aktif dengan raw register: {len(on_grid):,}\n"
    )

    if len(on_grid) < MIN_SAMPLES:
        print("Terlalu sedikit sampel PLN-aktif dengan raw_registers tersimpan.")
        print("Ingat prune-raw mengosongkan raw_registers lama -- coba --hours lebih kecil")
        print("kalau baru saja di-prune, atau tunggu lebih banyak waktu PLN aktif terekam.")
        return

    currents = [row.ac_output_current_a for row in on_grid]
    spread = max(currents) - min(currents)
    print(f"Arus keluaran saat PLN aktif: min={min(currents):.2f}A max={max(currents):.2f}A "
          f"rentang={spread:.2f}A")
    if spread < MIN_LOAD_SPREAD_A:
        print(f"\nRentang beban terlalu sempit (<{MIN_LOAD_SPREAD_A}A) untuk uji rasio yang")
        print("meyakinkan -- kalau beban nyaris konstan sepanjang waktu ini, register manapun")
        print("yang kebetulan juga konstan akan lolos palsu. Perlu data dari saat beban")
        print("benar-benar berubah (kulkas siklus, alat dinyalakan/dimatikan, dst).")
        print("Lanjut tetap dijalankan, tapi baca hasilnya dengan skeptis.\n")

    candidates = sorted(
        {addr for row in on_grid for addr in row.raw_registers if addr not in KNOWN_ADDRESSES},
        key=lambda v: int(v, 16),
    )

    print(f"\n{'ADDR':8}{'r thd arus':>12}{'rasio median':>14}{'konsisten':>11}  status")
    print("-" * 66)

    findings = []
    for addr in candidates:
        raws, amps, watts = [], [], []
        for row in on_grid:
            raw = row.raw_registers.get(addr)
            if raw is None:
                continue
            raws.append(float(raw))
            amps.append(row.ac_output_current_a)
            watts.append(row.ac_output_power_w or 0.0)
        if len(raws) < MIN_SAMPLES:
            continue

        distinct = len(set(raws))
        if distinct <= 2:
            continue  # diam total atau cuma kode on/off, bukan pengukuran kontinu

        correlation = pearson(amps, raws)

        # Rasio raw/arus harus stabil kalau register ini benar arus PLN dalam skala tetap.
        ratios = [r / a for r, a in zip(raws, amps, strict=True) if a > 0.2]
        if len(ratios) < MIN_SAMPLES:
            continue
        median_ratio = statistics.median(ratios)
        if abs(median_ratio) < 1e-6:
            continue
        within = sum(
            1 for r in ratios if abs(r - median_ratio) / abs(median_ratio) <= 0.05
        ) / len(ratios)

        strong = within >= 0.85 and correlation is not None and correlation >= 0.5
        status = "KANDIDAT KUAT" if strong else "-"
        if strong:
            findings.append((addr, median_ratio, within, correlation))
        corr_text = "n/a" if correlation is None else f"{correlation:+.2f}"
        print(f"{addr:8}{corr_text:>12}{median_ratio:>14.3f}{within * 100:>10.0f}%  {status}")

    print("\n" + "=" * 66)
    print("BACAAN")
    print("=" * 66)
    if findings:
        print("Ditemukan kandidat yang rasionya konsisten terhadap arus keluaran saat")
        print("PLN aktif. Ini PETUNJUK, bukan bukti final -- arus keluaran cuma proksi")
        print("(PV bisa saja ikut menyuplai beban bersamaan), jadi perlu dikonfirmasi")
        print("lewat uji terkendali: matikan PV (malam hari) atau tutup panel, pastikan")
        print("PLN benar-benar satu-satunya sumber, lalu ubah beban dan baca ulang.")
        for addr, ratio, within, correlation in findings:
            print(f"\n   {addr}: rasio raw/arus keluaran ~ {ratio:.2f}, "
                  f"konsisten {within * 100:.0f}% sampel, r={correlation:.2f}")
    else:
        print("Tidak ada register yang lolos uji rasio. Ini SEJALAN dengan dugaan bahwa")
        print("inverter tidak punya sensor arus di jalur bypass PLN -- bukan sekadar")
        print("register belum ditemukan. Kalau ingin benar-benar memastikan, satu-satunya")
        print("cara yang tersisa adalah meteran eksternal (CT clamp) di jalur PLN.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=168)
    asyncio.run(main(parser.parse_args().hours))
