"use client";

import {
  Activity,
  BatteryCharging,
  BatteryMedium,
  PlugZap,
  Bolt,
  CircuitBoard,
  Clock3,
  Gauge,
  HousePlug,
  SunMedium,
  Thermometer,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MetricCard } from "@/components/metric-card";
import { PowerChart } from "@/components/power-chart";
import { PowerGauge } from "@/components/power-gauge";
import { apiGet } from "@/lib/api";
import {
  apparentEnergy,
  apparentPower,
  dateTime,
  localDateInput,
  number,
  power,
} from "@/lib/format";
import type {
  BmsDeviceSummary,
  BmsLatestResponse,
  DailySummary,
  HistoryResponse,
  LatestResponse,
} from "@/lib/types";

interface BmsPackSummary {
  slug: string;
  name: string;
  socPercent: number | null;
  packVoltageV: number | null;
  packCurrentA: number | null;
  packPowerW: number | null;
  status: "online" | "degraded" | "offline";
}

function useBmsPacks() {
  const [packs, setPacks] = useState<BmsPackSummary[]>([]);

  const load = useCallback(async () => {
    try {
      const { devices } = await apiGet<{ devices: BmsDeviceSummary[] }>("/api/v1/bms-devices", {
        cacheTtlSeconds: 30,
      });
      const results = await Promise.all(
        devices.map(async (device) => {
          try {
            const latest = await apiGet<BmsLatestResponse>(
              `/api/v1/bms-devices/${device.slug}/latest`,
            );
            return {
              slug: device.slug,
              name: device.name,
              socPercent: latest.telemetry?.metrics.soc_percent ?? null,
              packVoltageV: latest.telemetry?.metrics.pack_voltage_v ?? null,
              packCurrentA: latest.telemetry?.metrics.pack_current_a ?? null,
              packPowerW: latest.telemetry?.metrics.pack_power_w ?? null,
              status: latest.telemetry_status,
            };
          } catch {
            return {
              slug: device.slug,
              name: device.name,
              socPercent: null,
              packVoltageV: null,
              packCurrentA: null,
              packPowerW: null,
              status: "offline" as const,
            };
          }
        }),
      );
      setPacks(results);
    } catch {
      // Daftar BMS opsional — dashboard utama tetap jalan tanpa panel baterai.
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [load]);

  return packs;
}

function useRatedCapacity(deviceSlug: string) {
  const [rated, setRated] = useState<{ pvRatedWp: number; inverterRatedW: number } | null>(null);

  useEffect(() => {
    apiGet<{ pv_rated_wp: number; inverter_rated_w: number }>(`/api/v1/devices/${deviceSlug}`, {
      cacheTtlSeconds: 300,
    })
      .then((detail) =>
        setRated({ pvRatedWp: detail.pv_rated_wp, inverterRatedW: detail.inverter_rated_w }),
      )
      .catch(() => undefined);
  }, [deviceSlug]);

  return rated;
}

export function DashboardClient({ deviceSlug }: { deviceSlug: string }) {
  const [latest, setLatest] = useState<LatestResponse | null>(null);
  const [daily, setDaily] = useState<DailySummary | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bmsPacks = useBmsPacks();
  const rated = useRatedCapacity(deviceSlug);

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
        { cacheTtlSeconds: 30 },
      ),
      apiGet<HistoryResponse>(
        `/api/v1/devices/${deviceSlug}/telemetry?from=${encodeURIComponent(from.toISOString())}` +
          `&to=${encodeURIComponent(now.toISOString())}&resolution=5m` +
          "&fields=pv_power_w,ac_output_power_w",
        { cacheTtlSeconds: 30 },
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
  const gridActive = metrics?.grid_active;
  const onGrid = gridActive === null || gridActive === undefined ? null : gridActive >= 0.5;
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
      {
        label: "SOC inverter",
        value: number(metrics?.inverter_soc_percent, 0),
        unit: "%",
        caption: "Estimasi dari tegangan • bukan coulomb counting",
        icon: BatteryMedium,
      },
      // Kartu PLN selalu tampil begitu gateway mengirim field ini (bukan hanya saat
      // aktif) supaya jelas ini kondisi "PLN memang tidak terpasang", bukan sekadar
      // sedang tidak dipakai. Saat tidak aktif nilainya dipaksa 0 — pembacaan mentah
      // inverter untuk tegangan PLN saat kabel dicabut adalah tegangan bocoran ~9V
      // yang tidak berarti apa-apa, jadi ditampilkan sebagai 0 seperti panel inverter.
      ...(onGrid !== null
        ? [
            {
              label: "Tegangan PLN",
              value: number(onGrid ? metrics?.grid_voltage_v : 0, 1),
              unit: "V",
              caption: onGrid ? undefined : "PLN tidak terpasang",
              icon: PlugZap,
              muted: !onGrid,
            },
            {
              label: "Frekuensi PLN",
              value: number(onGrid ? metrics?.grid_frequency_hz : 0, 1),
              unit: "Hz",
              caption: onGrid ? undefined : "PLN tidak terpasang",
              icon: Activity,
              muted: !onGrid,
            },
          ]
        : []),
    ],
    [daily, metrics, onGrid, output, pv],
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
        <div className="header-status">
          {onGrid !== null && (
            <div className={`source-pill ${onGrid ? "on-grid" : "on-battery"}`}>
              {onGrid ? <PlugZap size={15} /> : <BatteryMedium size={15} />}
              <div>
                <strong>{onGrid ? "PLN" : "Baterai"}</strong>
                <span>
                  {onGrid
                    ? `${number(metrics?.grid_voltage_v, 1)} V • ${number(metrics?.grid_frequency_hz, 1)} Hz`
                    : "PLN tidak terpasang • full inverter"}
                </span>
              </div>
            </div>
          )}
          <div className={`status-pill ${latest?.telemetry_status ?? "offline"}`}>
            <span className="status-dot" />
            {error ?? (latest?.telemetry_status === "online" ? "Data langsung" : latest?.telemetry_status ?? "Menghubungkan")}
          </div>
        </div>
      </header>

      <section className="grid metric-grid">
        {cards.map((card) => <MetricCard {...card} key={card.label} />)}
      </section>

      {bmsPacks.length > 0 && (
        <section className="panel section-gap">
          <div className="panel-title-row">
            <h2>Status baterai (BMS)</h2>
            <Link className="panel-note" href="/battery">Lihat detail sel →</Link>
          </div>
          <div className="grid metric-grid">
            {bmsPacks.map((pack) => {
              const charging = pack.packCurrentA !== null && pack.packCurrentA >= 0;
              const directionClass = pack.packCurrentA === null ? "" : charging ? "good" : "danger";
              return (
                <article className="metric-card" key={pack.slug}>
                  <div className="metric-label">
                    <span>{pack.name}</span>
                    <BatteryCharging className="metric-icon" size={16} />
                  </div>
                  <div className="metric-value">
                    {number(pack.socPercent, 0)}<span className="metric-unit">%</span>
                  </div>
                  <div className="metric-caption">
                    {number(pack.packVoltageV, 1)} V • {pack.status === "online" ? "online" : pack.status}
                  </div>
                  <div className="metric-caption" style={{ marginTop: 4 }}>
                    <span className={directionClass}>
                      {number(pack.packCurrentA, 2)} A ({charging ? "mengisi" : "discharge"})
                    </span>
                    {" • "}
                    <span className={directionClass}>{number(pack.packPowerW, 0)} W</span>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

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
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <PowerGauge label="Daya PV" max={rated?.pvRatedWp ?? 1200} unit="W" value={metrics?.pv_power_w ?? null} />
            <PowerGauge label="Beban AC" max={rated?.inverterRatedW ?? 1000} unit="VA" value={metrics?.ac_output_power_w ?? null} />
          </div>
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
