"""One-off probe: what exactly are 0x300E, 0x3015, 0x300B, 0x3013, 0x3007, 0x300D?

Read-only. Prints raw relationships instead of pass/fail so we can see shape.
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


def r(s, a):
    v = s.get(a)
    return None if v is None else float(v)


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
    samples = [(t, reg) for t, reg in rows if reg]
    print(f"samples: {len(samples):,}\n")

    # --- 0x300E vs battery voltage: is it offset, or a different scale? ---
    print("=" * 70)
    print("0x300E vs 0x3002 (battery voltage raw)")
    print("=" * 70)
    diffs = []
    pairs = []
    for _t, s in samples:
        a, b = r(s, "0x300E"), r(s, "0x3002")
        if a is not None and b is not None and b > 0:
            diffs.append(a - b)
            pairs.append((b, a))
    print(f"  0x300E - 0x3002: min={min(diffs):.0f} max={max(diffs):.0f} "
          f"median={statistics.median(diffs):.0f} stdev={statistics.pstdev(diffs):.2f}")
    # linear fit a = m*b + c
    n = len(pairs)
    mb = sum(p[0] for p in pairs) / n
    ma = sum(p[1] for p in pairs) / n
    num = sum((p[0] - mb) * (p[1] - ma) for p in pairs)
    den = sum((p[0] - mb) ** 2 for p in pairs)
    m = num / den if den else 0
    c = ma - m * mb
    resid = [p[1] - (m * p[0] + c) for p in pairs]
    print(f"  fit 0x300E = {m:.5f} * 0x3002 + {c:.3f}")
    print(
        f"  residual: max|r|={max(abs(x) for x in resid):.2f} "
        f"stdev={statistics.pstdev(resid):.3f}"
    )
    lo = [p for p in pairs if p[0] < statistics.median([q[0] for q in pairs])]
    hi = [p for p in pairs if p[0] >= statistics.median([q[0] for q in pairs])]
    if lo and hi:
        print(f"  low-batt  ratio median: {statistics.median([p[1]/p[0] for p in lo]):.5f}")
        print(f"  high-batt ratio median: {statistics.median([p[1]/p[0] for p in hi]):.5f}")

    # --- 0x3015 as temperature: check the -37 outlier ---
    print("\n" + "=" * 70)
    print("0x3015 vs 0x3009 (known inverter temp)")
    print("=" * 70)
    vals, d2 = [], []
    night, day = [], []
    for _t, s in samples:
        a, b, pv = r(s, "0x3015"), r(s, "0x3009"), r(s, "0x3012")
        if a is not None and b is not None:
            vals.append(a)
            d2.append(a - b)
            (day if (pv or 0) > 200 else night).append(a)
    print(f"  0x3015: min={min(vals):.0f} max={max(vals):.0f} median={statistics.median(vals):.0f}")
    print(f"  distinct values: {len(set(vals))}")
    print(f"  diff vs temp: median={statistics.median(d2):.0f} stdev={statistics.pstdev(d2):.2f}")
    if night and day:
        print(f"  when PV OFF: median={statistics.median(night):.1f} n={len(night)}")
        print(f"  when PV ON : median={statistics.median(day):.1f} n={len(day)}")
    print(f"  0x3009 range: {min(r(s,'0x3009') for _t,s in samples):.0f}.."
          f"{max(r(s,'0x3009') for _t,s in samples):.0f}")

    # --- PV-side registers: look at actual values during a bright moment ---
    print("\n" + "=" * 70)
    print("PV-side registers at peak PV (top 5 samples by PV voltage*current)")
    print("=" * 70)
    scored = []
    for _t, s in samples:
        v, i = r(s, "0x3012"), r(s, "0x3010")
        if v and i:
            scored.append((v / 10 * i / 10, _t, s))
    scored.sort(reverse=True, key=lambda x: x[0])
    print(f"  {'time':20}{'PVpwr':>8}{'0x300B':>9}{'0x3013':>9}{'0x3015':>9}"
          f"{'0x3007':>9}{'0x300D':>9}{'0x3005':>8}{'0x3004':>7}")
    for pwr, t, s in scored[:5]:
        print(f"  {str(t)[:19]:20}{pwr:>8.0f}{r(s,'0x300B') or 0:>9.0f}{r(s,'0x3013') or 0:>9.0f}"
              f"{r(s,'0x3015') or 0:>9.0f}{r(s,'0x3007') or 0:>9.0f}{r(s,'0x300D') or 0:>9.0f}"
              f"{r(s,'0x3005') or 0:>8.0f}{r(s,'0x3004') or 0:>7.0f}")
    print("\n  and at PV off (5 samples):")
    dark = [(t, s) for t, s in samples if (r(s, "0x3012") or 0) < 50][:5]
    for t, s in dark:
        print(f"  {str(t)[:19]:20}{0:>8}{r(s,'0x300B') or 0:>9.0f}{r(s,'0x3013') or 0:>9.0f}"
              f"{r(s,'0x3015') or 0:>9.0f}{r(s,'0x3007') or 0:>9.0f}{r(s,'0x300D') or 0:>9.0f}"
              f"{r(s,'0x3005') or 0:>8.0f}{r(s,'0x3004') or 0:>7.0f}")

    # --- 0x300B / 0x3013 / 0x3015 relationships to each other ---
    print("\n" + "=" * 70)
    print("Are 0x300B / 0x3013 / 0x3015 related to each other?")
    print("=" * 70)
    for x, y in (("0x300B", "0x3013"), ("0x300B", "0x3015"), ("0x3013", "0x3015")):
        rr = [r(s, x) / r(s, y) for _t, s in samples
              if r(s, x) is not None and r(s, y) not in (None, 0)]
        if len(rr) > 100:
            med = statistics.median(rr)
            within = sum(1 for v in rr if abs(v - med) / abs(med) <= 0.02) / len(rr)
            print(f"  {x}/{y}: median={med:.4f} within2%={within*100:.1f}% n={len(rr)}")

    # --- 0x300D: what is it? big numbers ~1530-1748 ---
    print("\n" + "=" * 70)
    print("0x300D shape")
    print("=" * 70)
    dvals = [r(s, "0x300D") for _t, s in samples if r(s, "0x300D") is not None]
    nz = [v for v in dvals if v != 0]
    print(f"  zero: {len(dvals)-len(nz)} / {len(dvals)}")
    if nz:
        print(f"  nonzero: min={min(nz):.0f} max={max(nz):.0f} median={statistics.median(nz):.0f}")
    # does it track grid voltage when grid present?
    gr = [(r(s, "0x300D"), r(s, "0x3000")) for _t, s in samples
          if r(s, "0x300D") not in (None, 0) and (r(s, "0x3000") or 0) > 1000]
    if len(gr) > 50:
        rr = [a / b for a, b in gr]
        med = statistics.median(rr)
        within = sum(1 for v in rr if abs(v - med) / abs(med) <= 0.02) / len(rr)
        print(
            f"  vs grid voltage (grid present): median={med:.4f} "
            f"within2%={within * 100:.1f}% n={len(gr)}"
        )
    print(f"  0x300A distinct: {sorted({r(s,'0x300A') for _t,s in samples})}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=int, default=48)
    asyncio.run(main(p.parse_args().hours))
