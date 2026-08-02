"use client";

import { BarChart3, CalendarDays, Coins, SunMedium } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { MetricCard } from "@/components/metric-card";
import { apiGet } from "@/lib/api";
import { currency, energy, localDateInput, number } from "@/lib/format";
import type { MonthlySummary } from "@/lib/types";

export function MonthlyClient({ deviceSlug }: { deviceSlug: string }) {
  const [month, setMonth] = useState(localDateInput().slice(0, 7));
  const [data, setData] = useState<MonthlySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await apiGet(`/api/v1/devices/${deviceSlug}/analytics/monthly?month=${month}`));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Gagal mengambil data bulanan");
    }
  }, [deviceSlug, month]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const cards = [
    { label: "Produksi bulan", value: number(data?.pv_energy_kwh, 2), unit: "kWh", icon: SunMedium },
    { label: "Output bulan", value: number(data?.ac_output_energy_kwh, 2), unit: "kWh", icon: BarChart3 },
    { label: "Rata-rata harian", value: number(data?.average_daily_pv_kwh, 2), unit: "kWh", icon: CalendarDays },
    { label: "Nilai ekuivalen", value: currency(data?.equivalent_saving_idr), unit: "", caption: "Bukan audit tagihan PLN", icon: Coins },
  ];
  return (
    <div>
      <header className="page-header">
        <div><p className="eyebrow">Monthly insight</p><h1>Produksi bulanan.</h1><p className="subtitle">Pola energi per hari dan estimasi nilai energi.</p></div>
        <input className="control" type="month" value={month} max={localDateInput().slice(0, 7)} onChange={(event) => setMonth(event.target.value)} />
      </header>
      {error ? <div className="error-state panel">{error}</div> : <>
        <section className="grid metric-grid">{cards.map((card) => <MetricCard {...card} key={card.label} />)}</section>
        <article className="panel chart-panel section-gap">
          <div className="panel-title-row"><h2>Produksi per tanggal</h2><span className="panel-note">{data?.days_with_data ?? 0} hari dengan data</span></div>
          {data?.days.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.days} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}><CartesianGrid stroke="rgba(184,235,201,.07)" vertical={false} /><XAxis dataKey="date" tickFormatter={(value) => value.slice(-2)} stroke="#65756b" tickLine={false} axisLine={false} fontSize={10} /><YAxis stroke="#65756b" tickLine={false} axisLine={false} fontSize={10} /><Tooltip formatter={(value) => [`${number(Number(value), 3)} kWh`, "Produksi PV"]} contentStyle={{ border: "1px solid rgba(184,235,201,.12)", borderRadius: 12, background: "#0c120f", fontSize: 11 }} /><Bar dataKey="pv_energy_kwh" fill="#7ef29a" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div> : <div className="empty">Belum ada data bulan ini.</div>}
        </article>
        <section className="grid two-column section-gap">
          <article className="panel"><div className="panel-title-row"><h2>Hari terbaik</h2></div><div className="summary-item"><span>{data?.best_day?.date ?? "—"}</span><strong>{energy(data?.best_day?.pv_energy_kwh)}</strong></div></article>
          <article className="panel"><div className="panel-title-row"><h2>Hari terendah</h2></div><div className="summary-item"><span>{data?.lowest_day?.date ?? "—"}</span><strong>{energy(data?.lowest_day?.pv_energy_kwh)}</strong></div></article>
        </section>
      </>}
    </div>
  );
}
