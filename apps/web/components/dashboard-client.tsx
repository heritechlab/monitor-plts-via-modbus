"use client";

import {
  Activity,
  BatteryMedium,
  Bolt,
  CircuitBoard,
  Clock3,
  Gauge,
  HousePlug,
  SunMedium,
  Thermometer,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MetricCard } from "@/components/metric-card";
import { PowerChart } from "@/components/power-chart";
import { apiGet } from "@/lib/api";
import {
  apparentEnergy,
  apparentPower,
  dateTime,
  localDateInput,
  number,
  power,
} from "@/lib/format";
import type { DailySummary, HistoryResponse, LatestResponse } from "@/lib/types";

export function DashboardClient({ deviceSlug }: { deviceSlug: string }) {
  const [latest, setLatest] = useState<LatestResponse | null>(null);
  const [daily, setDaily] = useState<DailySummary | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadLatest = useCallback(async () => {
    try {
      setLatest(await apiGet<LatestResponse>(`/api/v1/devices/${deviceSlug}/latest`));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "API tidak dapat dihubungi");
    }
  }, [deviceSlug]);

  const loadCharts = useCallback(async () => {
    const now = new Date();
    const from = new Date(now.getTime() - 6 * 60 * 60 * 1000);
    const [dailyResult, historyResult] = await Promise.all([
      apiGet<DailySummary>(
        `/api/v1/devices/${deviceSlug}/analytics/daily?date=${localDateInput(now)}`,
      ),
      apiGet<HistoryResponse>(
        `/api/v1/devices/${deviceSlug}/telemetry?from=${encodeURIComponent(from.toISOString())}` +
          `&to=${encodeURIComponent(now.toISOString())}&resolution=5m` +
          "&fields=pv_power_w,ac_output_power_w",
      ),
    ]);
    setDaily(dailyResult);
    setHistory(historyResult);
  }, [deviceSlug]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => {
      void loadLatest();
      void loadCharts().catch(() => undefined);
    }, 0);
    const latestTimer = window.setInterval(() => void loadLatest(), 5000);
    const chartTimer = window.setInterval(() => void loadCharts().catch(() => undefined), 60000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(latestTimer);
      window.clearInterval(chartTimer);
    };
  }, [loadCharts, loadLatest]);

  const metrics = latest?.telemetry?.metrics;
  const pv = power(metrics?.pv_power_w);
  const output = apparentPower(metrics?.ac_output_power_w);
  const cards = useMemo(
    () => [
      { label: "Daya PV", ...pv, caption: "Tegangan × arus PV", icon: SunMedium },
      { label: "Beban AC estimasi", ...output, caption: "Register inverter • bukan watt aktif", icon: HousePlug },
      { label: "Produksi hari ini", value: number(daily?.pv_energy_kwh, 3), unit: "kWh", caption: `Cakupan ${number(daily?.pv_coverage_percent, 0)}%`, icon: Zap },
      { label: "Tegangan baterai", value: number(metrics?.battery_voltage_v, 1), unit: "V", caption: "Dari inverter", icon: BatteryMedium },
      { label: "Tegangan PV", value: number(metrics?.pv_voltage_v, 1), unit: "V", icon: Bolt },
      { label: "Arus PV", value: number(metrics?.pv_current_a, 1), unit: "A", icon: Activity },
      { label: "Tegangan AC", value: number(metrics?.ac_output_voltage_v, 1), unit: "V", icon: CircuitBoard },
      { label: "Beban inverter", value: number(metrics?.load_percent, 0), unit: "%", icon: Gauge },
      { label: "Suhu inverter", value: number(metrics?.inverter_temperature_c, 0), unit: "°C", icon: Thermometer },
    ],
    [daily, metrics, output, pv],
  );

  return (
    <div>
      <header className="page-header">
        <div>
          <p className="eyebrow">Live energy</p>
          <h1>Energi rumah, sekilas.</h1>
          <p className="subtitle">
            Inverter PRIME • pembaruan otomatis setiap 5 detik
          </p>
        </div>
        <div className={`status-pill ${latest?.telemetry_status ?? "offline"}`}>
          <span className="status-dot" />
          {error ?? (latest?.telemetry_status === "online" ? "Data langsung" : latest?.telemetry_status ?? "Menghubungkan")}
        </div>
      </header>

      <section className="grid metric-grid">
        {cards.map((card) => <MetricCard {...card} key={card.label} />)}
      </section>

      <section className="grid two-column section-gap">
        <article className="panel chart-panel">
          <div className="panel-title-row">
            <div><h2>Kurva daya</h2><span className="panel-note">6 jam terakhir • rata-rata 5 menit</span></div>
            <div className="status-pill"><span style={{ color: "var(--green)" }}>● PV (W)</span><span style={{ color: "var(--blue)" }}>● Beban estimasi (VA)</span></div>
          </div>
          <PowerChart points={history?.points ?? []} />
        </article>

        <article className="panel">
          <div className="panel-title-row"><h2>Aliran daya</h2><span className="panel-note">Beban inverter adalah estimasi VA</span></div>
          <div className="energy-flow">
            <div className="flow-node"><div className="flow-node-icon"><SunMedium size={19} /></div><strong>{pv.value} {pv.unit}</strong><span>Panel PV</span></div>
            <div className="flow-line" />
            <div className="flow-node"><div className="flow-node-icon"><CircuitBoard size={19} /></div><strong>Inverter</strong><span>PRIME</span></div>
            <div className="flow-line" />
            <div className="flow-node"><div className="flow-node-icon"><HousePlug size={19} /></div><strong>{output.value} {output.unit}</strong><span>Beban AC</span></div>
          </div>
          <div className="grid summary-grid" style={{ marginTop: 14 }}>
            <div className="summary-item"><span>Beban semu hari ini</span><strong>{apparentEnergy(daily?.ac_load_estimate_kvah)}</strong></div>
            <div className="summary-item"><span>Daya aktif</span><strong className="warning">Butuh meter eksternal</strong></div>
            <div className="summary-item"><span>Antrean lokal</span><strong>{number(latest?.gateway.queue_depth, 0)}</strong></div>
            <div className="summary-item"><span>Serial</span><strong className={latest?.gateway.serial_status === "ok" ? "good" : "warning"}>{latest?.gateway.serial_status ?? "—"}</strong></div>
          </div>
        </article>
      </section>

      <section className="panel section-gap">
        <div className="panel-title-row"><h2>Kesehatan sistem</h2><Clock3 size={16} color="var(--muted)" /></div>
        <div className="grid summary-grid">
          <div className="summary-item"><span>Telemetry terakhir</span><strong>{dateTime(latest?.telemetry?.recorded_at)}</strong></div>
          <div className="summary-item"><span>Gateway</span><strong className={latest?.status === "online" ? "good" : "warning"}>{latest?.status ?? "—"}</strong></div>
          <div className="summary-item"><span>Sampel hari ini</span><strong>{number(daily?.sample_count, 0)}</strong></div>
          <div className="summary-item"><span>Anomali hari ini</span><strong className={daily?.invalid_sample_count ? "warning" : "good"}>{number(daily?.invalid_sample_count, 0)}</strong></div>
        </div>
      </section>
    </div>
  );
}
