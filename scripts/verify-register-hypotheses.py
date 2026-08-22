"""Uji hipotesis arti register terhadap data produksi yang sudah tersimpan.

Halaman Register memberi peringkat korelasi, tapi korelasi saja sudah pernah
menyesatkan kita (0x300A sempat terlihat "mengikuti" beban padahal ia kode
sumber daya). Skrip ini melangkah lebih jauh: tiap hipotesis dinyatakan sebagai
hubungan yang bisa GAGAL -- rasio yang harus konstan, nilai yang harus cocok
dengan metrik lain dalam toleransi, atau himpunan nilai yang harus terbatas.
Hipotesis yang tidak lolos dilaporkan gagal, bukan dipaksa masuk.

Skrip ini hanya MEMBACA database. Tidak menyentuh serial maupun inverter.

Pemakaian (dari apps/api, memakai venv-nya):
    .venv\\Scripts\\python.exe ..\\..\\scripts\\verify-register-hypotheses.py --hours 48
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

# Register yang sudah dipakai decoder, untuk jadi pembanding.
KNOWN = {
    "grid_voltage_v": ("0x3000", 10),
    "ac_output_voltage_v": ("0x3001", 10),
    "battery_voltage_v": ("0x3002", 10),
    "ac_output_current_a": ("0x3003", 10),
    "load_percent": ("0x3004", 1),
    "ac_output_va": ("0x3005", 1),
    "grid_frequency_hz": ("0x3008", 10),
    "inverter_temperature_c": ("0x3009", 1),
    "grid_active_code": ("0x300A", 1),
    "pv_current_a": ("0x3010", 10),
    "pv_voltage_v": ("0x3012", 10),
    "inverter_soc_percent": ("0x3016", 1),
}


def reg(sample: dict[str, int], address: str) -> float | None:
    value = sample.get(address)
    return None if value is None else float(value)


def derived(sample: dict[str, int], name: str) -> float | None:
    address, scale = KNOWN[name]
    value = reg(sample, address)
    return None if value is None else value / scale


def summarize(values: list[float]) -> str:
    if not values:
        return "tidak ada data"
    if len(values) == 1:
        return f"{values[0]:.4g}"
    return (
        f"min={min(values):.4g} max={max(values):.4g} "
        f"median={statistics.median(values):.4g} n={len(values)}"
    )


def check_ratio(
    samples: list[dict[str, int]],
    address: str,
    metric: str,
    *,
    require_nonzero_metric: bool = True,
) -> tuple[bool, str]:
    """Hipotesis: register ini adalah metric dikali suatu konstanta tetap.

    Kalau benar, rasio register/metric harus stabil. Rasio yang berhamburan
    menggugurkan hipotesis, dan itu justru informasi yang berguna.
    """
    ratios = []
    for sample in samples:
        raw = reg(sample, address)
        value = derived(sample, metric)
        if raw is None or value is None:
            continue
        if require_nonzero_metric and abs(value) < 1e-6:
            continue
        ratios.append(raw / value)
    if len(ratios) < 20:
        return False, f"sampel valid terlalu sedikit ({len(ratios)})"
    median = statistics.median(ratios)
    if abs(median) < 1e-9:
        return False, "rasio median nol"
    spread = [abs(r - median) / abs(median) for r in ratios]
    within_2pct = sum(1 for s in spread if s <= 0.02) / len(spread)
    ok = within_2pct >= 0.90
    verdict = "LOLOS" if ok else "GAGAL"
    return ok, (
        f"{verdict} rasio median={median:.4f} "
        f"({within_2pct * 100:.1f}% sampel dalam +-2%) n={len(ratios)}"
    )


def check_distinct_values(
    samples: list[dict[str, int]], address: str, max_distinct: int = 8
) -> tuple[bool, str]:
    """Hipotesis: register ini kode status, bukan besaran ukur.

    Kode status hanya punya sedikit nilai berbeda walau kondisi berubah-ubah.
    """
    values = [v for v in (reg(sample, address) for sample in samples) if v is not None]
    if not values:
        return False, "tidak ada data"
    distinct = sorted(set(values))
    ok = 1 < len(distinct) <= max_distinct
    verdict = "LOLOS" if ok else "GAGAL"
    return ok, f"{verdict} {len(distinct)} nilai unik: {distinct[:10]} n={len(values)}"


def check_always_zero(samples: list[dict[str, int]], address: str) -> tuple[bool, str]:
    values = [v for v in (reg(sample, address) for sample in samples) if v is not None]
    if not values:
        return False, "tidak ada data"
    nonzero = [v for v in values if v != 0]
    ok = not nonzero
    verdict = "SELALU NOL" if ok else "PERNAH TIDAK NOL"
    detail = "" if ok else f" contoh nilai: {sorted(set(nonzero))[:8]}"
    return ok, f"{verdict} n={len(values)}{detail}"


def check_tracks_temperature(samples: list[dict[str, int]], address: str) -> tuple[bool, str]:
    """Hipotesis: register ini suhu kedua (mis. MPPT/heatsink) dalam degC.

    Suhu apa pun di dalam kotak yang sama harus berada di rentang wajar dan
    bergerak searah dengan suhu inverter yang sudah kita decode.
    """
    pairs = []
    for sample in samples:
        raw = reg(sample, address)
        known_temp = derived(sample, "inverter_temperature_c")
        if raw is not None and known_temp is not None:
            pairs.append((raw, known_temp))
    if len(pairs) < 20:
        return False, f"sampel terlalu sedikit ({len(pairs)})"
    raws = [p[0] for p in pairs]
    plausible = sum(1 for r in raws if 5 <= r <= 120) / len(raws)
    diffs = [p[0] - p[1] for p in pairs]
    ok = plausible >= 0.95 and statistics.pstdev(diffs) < 8
    verdict = "MUNGKIN SUHU" if ok else "BUKAN SUHU"
    return ok, (
        f"{verdict} {plausible * 100:.1f}% nilai di 5..120 degC, "
        f"selisih thd suhu inverter: {summarize(diffs)}"
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

    samples = [registers for _recorded_at, registers in rows if registers]
    print(f"Rentang: {hours} jam terakhir | sampel dengan raw register: {len(samples):,}\n")
    if len(samples) < 50:
        print("Data mentah terlalu sedikit. Ingat prune-raw mengosongkan raw_registers lama.")
        return

    daylight = [s for s in samples if (derived(s, "pv_voltage_v") or 0) > 20]
    print(f"Sampel saat PV aktif (tegangan PV > 20 V): {len(daylight):,}\n")

    print("=" * 78)
    print("KANDIDAT YANG DISOROT HALAMAN REGISTER")
    print("=" * 78)

    print("\n-- 0x3006 (korelasi kuat ke beban inverter, r=0,938)")
    for metric in ("ac_output_va", "load_percent", "ac_output_current_a"):
        _ok, detail = check_ratio(samples, "0x3006", metric)
        print(f"   vs {metric:22} {detail}")

    print("\n-- 0x300D (korelasi ke arus AC, r=0,842)")
    for metric in ("ac_output_current_a", "ac_output_va", "load_percent"):
        _ok, detail = check_ratio(samples, "0x300D", metric)
        print(f"   vs {metric:22} {detail}")
    _ok, detail = check_distinct_values(samples, "0x300D", max_distinct=12)
    print(f"   sebagai kode status?   {detail}")

    print("\n-- 0x300E (korelasi ke tegangan baterai, r=0,804)")
    for metric in ("battery_voltage_v", "inverter_soc_percent", "pv_voltage_v"):
        _ok, detail = check_ratio(samples, "0x300E", metric)
        print(f"   vs {metric:22} {detail}")

    print("\n-- 0x3007 (korelasi ke tegangan AC, r=0,778)")
    for metric in ("ac_output_voltage_v", "grid_voltage_v", "ac_output_va"):
        _ok, detail = check_ratio(samples, "0x3007", metric)
        print(f"   vs {metric:22} {detail}")
    _ok, detail = check_distinct_values(samples, "0x3007", max_distinct=12)
    print(f"   sebagai kode status?   {detail}")

    print("\n-- 0x300B / 0x3013 / 0x3015 (dikaitkan ke arus PV)")
    for address in ("0x300B", "0x3013", "0x3015"):
        print(f"   {address}:")
        for metric in ("pv_current_a", "pv_voltage_v"):
            _ok, detail = check_ratio(daylight, address, metric)
            print(f"      vs {metric:20} {detail}")
        # Daya PV tidak ada di KNOWN karena ia hasil perkalian, jadi diuji manual.
        ratios = []
        for sample in daylight:
            raw = reg(sample, address)
            v = derived(sample, "pv_voltage_v")
            i = derived(sample, "pv_current_a")
            if raw is None or v is None or i is None:
                continue
            power = v * i
            if power > 20:
                ratios.append(raw / power)
        if len(ratios) >= 20:
            median = statistics.median(ratios)
            if abs(median) < 1e-9:
                # Register diam di nol walau daya PV berubah: bukan skala daya PV.
                print(f"      vs daya PV (V*I)     GAGAL register nol n={len(ratios)}")
            else:
                within = sum(
                    1 for r in ratios if abs(r - median) / abs(median) <= 0.02
                ) / len(ratios)
                verdict = "LOLOS" if within >= 0.90 else "GAGAL"
                print(
                    f"      vs daya PV (V*I)     {verdict} rasio median={median:.4f} "
                    f"({within * 100:.1f}% dalam +-2%) n={len(ratios)}"
                )

    print("\n" + "=" * 78)
    print("APAKAH ADA REGISTER SUHU KEDUA (MPPT / HEATSINK)?")
    print("=" * 78)
    print("Suhu inverter yang sudah dikenal ada di 0x3009.")
    print("Kandidat suhu kedua harus masuk rentang wajar dan bergerak searah:\n")
    candidates = [
        f"0x{0x3000 + offset:04X}"
        for offset in range(0x20)
        if f"0x{0x3000 + offset:04X}" not in {addr for addr, _ in KNOWN.values()}
    ]
    any_temp = False
    for address in candidates:
        zero_ok, zero_detail = check_always_zero(samples, address)
        if zero_ok:
            continue  # register mati, dilaporkan di bagian bawah
        ok, detail = check_tracks_temperature(samples, address)
        if ok:
            any_temp = True
            print(f"   {address}: {detail}")
    if not any_temp:
        print("   Tidak ada kandidat yang lolos uji suhu.")

    print("\n" + "=" * 78)
    print("REGISTER YANG SELALU NOL SEPANJANG RENTANG INI")
    print("=" * 78)
    dead = []
    for address in candidates:
        ok, detail = check_always_zero(samples, address)
        if ok:
            dead.append(address)
    print(f"   {', '.join(dead) if dead else '(tidak ada)'}")
    print(
        "\n   Register mati sepanjang rentang belum tentu tidak terpakai; ia bisa"
        "\n   baru hidup pada kondisi yang belum pernah terjadi (seperti 0x3008 dulu"
        "\n   yang baru muncul saat input PLN dicolok)."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=48)
    asyncio.run(main(parser.parse_args().hours))
