"use client";

import { BarChart3, CalendarDays, Coins, SunMedium, Trophy, TrendingDown } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { MetricCard } from "@/components/metric-card";
import { apiGet } from "@/lib/api";
import { currency, dayLabel, localDateInput, number } from "@/lib/format";
import type { MonthlySummary } from "@/lib/types";

export function MonthlyClient({ deviceSlug }: { deviceSlug: string }) {
  const [month, setMonth] = useState(localDateInput().slice(0, 7));
  const [data, setData] = useState<MonthlySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await apiGet(`/api/v1/devices/${deviceSlug}/analytics/monthly?month=${month}`, { cacheTtlSeconds: 300 }));
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
    { label: "Beban AC estimasi", value: number(data?.ac_load_estimate_kvah, 2), unit: "kVAh", caption: "Bukan energi aktif", icon: BarChart3 },
    { label: "Rata-rata harian", value: number(data?.average_daily_pv_kwh, 2), unit: "kWh", icon: CalendarDays },
    { label: "Nilai produksi PV", value: currency(data?.equivalent_saving_idr), unit: "", caption: "Estimasi dari energi PV • bukan audit PLN", icon: Coins },
    { label: "Hari terbaik", value: number(data?.best_day?.pv_energy_kwh, 3), unit: "kWh", caption: dayLabel(data?.best_day?.date), icon: Trophy },
    { label: "Hari terendah", value: number(data?.lowest_day?.pv_energy_kwh, 3), unit: "kWh", caption: dayLabel(data?.lowest_day?.date), icon: TrendingDown },
  ];
  // Terbaru dulu, supaya produksi hari-hari terakhir langsung terlihat tanpa scroll.
  const daysNewestFirst = useMemo(() => [...(data?.days ?? [])].reverse(), [data]);
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
          {data?.days.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.days} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(value) => value.slice(-2)} stroke="var(--muted)" tickLine={false} axisLine={false} fontSize={10} />
                  <YAxis stroke="var(--muted)" tickLine={false} axisLine={false} fontSize={10} />
                  <Tooltip
                    formatter={(value) => [`${number(Number(value), 3)} kWh`, "Produksi PV"]}
                    contentStyle={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface-raised)", fontSize: 11 }}
                  />
                  <Bar dataKey="pv_energy_kwh" fill="var(--green)" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty">Belum ada data bulan ini.</div>
          )}
        </article>
        <article className="panel section-gap">
          <div className="panel-title-row">
            <h2>Rincian per hari</h2>
            <span className="panel-note">Terbaru di atas</span>
          </div>
          {daysNewestFirst.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Tanggal</th>
                    <th>Produksi PV</th>
                    <th>Beban AC estimasi</th>
                    <th>Cakupan data</th>
                  </tr>
                </thead>
                <tbody>
                  {daysNewestFirst.map((day) => (
                    <tr key={day.date}>
                      <td>{dayLabel(day.date)}</td>
                      <td className={day.sample_count > 0 ? undefined : "warning"}>
                        {day.sample_count > 0 ? `${number(day.pv_energy_kwh, 3)} kWh` : "Belum ada data"}
                      </td>
                      <td>{day.sample_count > 0 ? `${number(day.ac_load_estimate_kvah, 3)} kVAh` : "—"}</td>
                      <td>{day.sample_count > 0 ? `${number(day.pv_coverage_percent, 0)}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="compact-empty">Belum ada data bulan ini.</div>
          )}
        </article>
      </>}
    </div>
  );
}
