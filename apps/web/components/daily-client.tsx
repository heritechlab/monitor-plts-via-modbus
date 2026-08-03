"use client";

import { BatteryMedium, Clock3, Gauge, SunMedium, Thermometer, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { MetricCard } from "@/components/metric-card";
import { apiGet } from "@/lib/api";
import { dateTime, localDateInput, number } from "@/lib/format";
import type { DailySummary } from "@/lib/types";

export function DailyClient({ deviceSlug }: { deviceSlug: string }) {
  const [date, setDate] = useState(localDateInput());
  const [data, setData] = useState<DailySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await apiGet(`/api/v1/devices/${deviceSlug}/analytics/daily?date=${date}`));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Gagal mengambil ringkasan");
    }
  }, [date, deviceSlug]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const cards = [
    { label: "Produksi PV", value: number(data?.pv_energy_kwh, 3), unit: "kWh", caption: `Cakupan ${number(data?.pv_coverage_percent, 1)}%`, icon: SunMedium },
    { label: "Beban AC estimasi", value: number(data?.ac_load_estimate_kvah, 3), unit: "kVAh", caption: `Cakupan ${number(data?.ac_load_coverage_percent, 1)}% • bukan kWh aktif`, icon: Zap },
    { label: "Peak PV 1 menit", value: number(data?.peak_pv_1m_avg_w, 0), unit: "W", caption: `Raw ${number(data?.peak_pv_raw_w, 0)} W`, icon: Gauge },
    { label: "Suhu maksimum", value: number(data?.max_temperature_c, 0), unit: "°C", icon: Thermometer },
    { label: "Baterai minimum", value: number(data?.min_battery_voltage_v, 1), unit: "V", caption: `Maks ${number(data?.max_battery_voltage_v, 1)} V`, icon: BatteryMedium },
    { label: "Peak beban estimasi", value: number(data?.peak_ac_load_estimate_1m_avg_va, 0), unit: "VA", caption: "Rata-rata 1 menit", icon: Zap },
  ];
  return (
    <div>
      <header className="page-header">
        <div><p className="eyebrow">Daily insight</p><h1>Ringkasan harian.</h1><p className="subtitle">Produksi PV dalam kWh; beban inverter adalah estimasi daya semu dalam kVAh.</p></div>
        <input className="control" type="date" value={date} max={localDateInput()} onChange={(event) => setDate(event.target.value)} />
      </header>
      {error && <div className="error-state panel">{error}</div>}
      {!error && <>
        <section className="grid metric-grid">{cards.map((card) => <MetricCard {...card} key={card.label} />)}</section>
        <section className="grid two-column section-gap">
          <article className="panel">
            <div className="panel-title-row"><h2>Durasi produksi</h2><Clock3 size={16} color="var(--muted)" /></div>
            <div className="grid summary-grid">
              <div className="summary-item"><span>PV di atas 500 W</span><strong>{number(data?.pv_above_500_minutes, 1)} menit</strong></div>
              <div className="summary-item"><span>PV di atas 800 W</span><strong>{number(data?.pv_above_800_minutes, 1)} menit</strong></div>
              <div className="summary-item"><span>PV di atas 1.000 W</span><strong>{number(data?.pv_above_1000_minutes, 1)} menit</strong></div>
              <div className="summary-item"><span>Nilai energi ekuivalen</span><strong>Rp {number(data?.equivalent_saving_idr, 0)}</strong></div>
            </div>
          </article>
          <article className="panel">
            <div className="panel-title-row"><h2>Kualitas pencatatan</h2><span className="panel-note">{data?.gaps.length ?? 0} gap</span></div>
            <div className="grid summary-grid">
              <div className="summary-item"><span>Sampel</span><strong>{number(data?.sample_count, 0)}</strong></div>
              <div className="summary-item"><span>Sampel ber-flag</span><strong className={data?.invalid_sample_count ? "warning" : "good"}>{number(data?.invalid_sample_count, 0)}</strong></div>
              <div className="summary-item"><span>Pertama</span><strong>{dateTime(data?.first_sample_at)}</strong></div>
              <div className="summary-item"><span>Terakhir</span><strong>{dateTime(data?.last_sample_at)}</strong></div>
            </div>
          </article>
        </section>
        <article className="panel section-gap">
          <div className="panel-title-row"><h2>Gap data</h2><span className="panel-note">Interval lebih dari 60 detik tidak dihitung sebagai energi</span></div>
          {data?.gaps.length ? <div className="table-wrap"><table><thead><tr><th>Mulai</th><th>Selesai</th><th>Durasi</th></tr></thead><tbody>{data.gaps.map((gap) => <tr key={gap.from}><td>{dateTime(gap.from)}</td><td>{dateTime(gap.to)}</td><td>{number(gap.seconds / 60, 1)} menit</td></tr>)}</tbody></table></div> : <div className="empty">Tidak ada gap besar pada tanggal ini.</div>}
        </article>
      </>}
    </div>
  );
}
