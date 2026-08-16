"use client";

import {
  BatteryCharging,
  Gauge,
  Recycle,
  Thermometer,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MetricCard } from "@/components/metric-card";
import { apiGet } from "@/lib/api";
import { number } from "@/lib/format";
import type { BmsDeviceSummary, BmsLatestResponse } from "@/lib/types";

// Selisih di atas ambang ini (mV) dari rata-rata pack dianggap tidak seimbang.
const IMBALANCE_THRESHOLD_MV = 20;

export function BatteryPanel() {
  const [devices, setDevices] = useState<BmsDeviceSummary[] | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ devices: BmsDeviceSummary[] }>("/api/v1/bms-devices", { cacheTtlSeconds: 30 })
      .then((response) => {
        setDevices(response.devices);
        setSelectedSlug((current) => current ?? response.devices[0]?.slug ?? null);
        setListError(null);
      })
      .catch((reason) => setListError(reason instanceof Error ? reason.message : "API tidak dapat dihubungi"));
  }, []);

  if (listError) {
    return (
      <div>
        <header className="page-header">
          <div>
            <p className="eyebrow">Baterai</p>
            <h1>Sel baterai.</h1>
          </div>
        </header>
        <div className="error-state panel">{listError}</div>
      </div>
    );
  }

  if (devices !== null && devices.length === 0) {
    return (
      <div>
        <header className="page-header">
          <div>
            <p className="eyebrow">Baterai</p>
            <h1>Sel baterai.</h1>
            <p className="subtitle">Belum ada BMS terdaftar.</p>
          </div>
        </header>
        <div className="empty panel">
          Daftarkan BMS lewat CLI (<code>ensure-device --device-type bms</code>) lalu pasang gateway-nya.
        </div>
      </div>
    );
  }

  return (
    <div>
      {devices && devices.length > 1 && (
        <div className="controls" style={{ marginBottom: 14 }}>
          {devices.map((device) => (
            <button
              className={`control-button ${device.slug === selectedSlug ? "active" : ""}`}
              key={device.slug}
              onClick={() => setSelectedSlug(device.slug)}
              type="button"
            >
              {device.name}
            </button>
          ))}
        </div>
      )}
      {selectedSlug && devices ? (
        <BatteryDevicePanel
          deviceName={devices.find((device) => device.slug === selectedSlug)?.name ?? selectedSlug}
          deviceSlug={selectedSlug}
          key={selectedSlug}
        />
      ) : (
        <div className="empty panel">Memuat daftar baterai…</div>
      )}
    </div>
  );
}

function BatteryDevicePanel({ deviceSlug, deviceName }: { deviceSlug: string; deviceName: string }) {
  const [latest, setLatest] = useState<BmsLatestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLatest(await apiGet<BmsLatestResponse>(`/api/v1/bms-devices/${deviceSlug}/latest`));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "API tidak dapat dihubungi");
    }
  }, [deviceSlug]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [load]);

  const metrics = latest?.telemetry?.metrics;
  const cells = useMemo(() => metrics?.cell_voltages_mv ?? [], [metrics]);
  const cellAverage = cells.length ? cells.reduce((sum, v) => sum + v, 0) / cells.length : null;
  const cellData = useMemo(
    () =>
      cells.map((mv, index) => ({
        cell: `${index + 1}`,
        mv,
        imbalanced:
          cellAverage !== null && Math.abs(mv - cellAverage) > IMBALANCE_THRESHOLD_MV,
      })),
    [cells, cellAverage],
  );
  const domain = useMemo((): [number, number] => {
    if (!cells.length) return [0, 4000];
    const min = Math.min(...cells);
    const max = Math.max(...cells);
    const pad = Math.max(10, Math.round((max - min) * 0.4));
    return [min - pad, max + pad];
  }, [cells]);

  const cards = useMemo(
    () => [
      { label: "SOC", value: number(metrics?.soc_percent, 0), unit: "%", caption: "State of charge", icon: BatteryCharging },
      { label: "Tegangan pack", value: number(metrics?.pack_voltage_v, 2), unit: "V", icon: Zap },
      { label: "Arus pack", value: number(metrics?.pack_current_a, 2), unit: "A", caption: "Negatif = discharge", icon: Gauge },
      { label: "Daya pack", value: number(metrics?.pack_power_w, 0), unit: "W", icon: Zap },
      { label: "Suhu 1", value: number(metrics?.temperature_1_c, 1), unit: "°C", icon: Thermometer },
      { label: "Suhu 2", value: number(metrics?.temperature_2_c, 1), unit: "°C", icon: Thermometer },
      { label: "Siklus", value: number(metrics?.cycle_count, 0), unit: "x", icon: Recycle },
      { label: "Arus balance", value: number(metrics?.balance_current_a, 3), unit: "A", icon: Gauge },
    ],
    [metrics],
  );

  return (
    <div>
      <header className="page-header">
        <div>
          <p className="eyebrow">Baterai</p>
          <h1>{deviceName}.</h1>
          <p className="subtitle">Pembaruan otomatis setiap 5 detik</p>
        </div>
        <div className={`status-pill ${latest?.telemetry_status ?? "offline"}`}>
          <span className="status-dot" />
          {error ?? (latest?.telemetry_status === "online" ? "Data langsung" : latest?.telemetry_status ?? "Menghubungkan")}
        </div>
      </header>

      <section className="grid metric-grid">
        {cards.map((card) => (
          <MetricCard {...card} key={card.label} />
        ))}
      </section>

      <section className="panel chart-panel section-gap">
        <div className="panel-title-row">
          <div>
            <h2>Tegangan tiap sel</h2>
            <span className="panel-note">
              {cells.length ? `${cells.length} sel • rata-rata ${number(cellAverage ?? undefined, 0)} mV` : "Menunggu data"}
            </span>
          </div>
        </div>
        {cellData.length ? (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cellData} margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
                <XAxis
                  dataKey="cell"
                  tickFormatter={(value) => `#${value}`}
                  stroke="var(--muted)"
                  tickLine={false}
                  axisLine={false}
                  fontSize={10}
                />
                <YAxis
                  domain={domain}
                  stroke="var(--muted)"
                  tickLine={false}
                  axisLine={false}
                  fontSize={10}
                />
                <Tooltip
                  formatter={(value) => [`${number(Number(value), 0)} mV`, "Tegangan"]}
                  labelFormatter={(value) => `Sel #${value}`}
                  contentStyle={{
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    background: "var(--surface-raised)",
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="mv" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  <LabelList
                    dataKey="mv"
                    position="top"
                    fontSize={10}
                    fill="var(--muted)"
                    formatter={(value: unknown) => number(Number(value), 0)}
                  />
                  {cellData.map((entry) => (
                    <Cell
                      fill={entry.imbalanced ? "var(--amber)" : "var(--green)"}
                      key={entry.cell}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty">Belum ada data sel baterai.</div>
        )}
      </section>
    </div>
  );
}
