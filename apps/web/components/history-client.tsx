"use client";

import { useCallback, useEffect, useState } from "react";

import { PowerChart } from "@/components/power-chart";
import { apiGet } from "@/lib/api";
import { dateTime, number } from "@/lib/format";
import type { HistoryResponse } from "@/lib/types";

const ranges = {
  "1j": { hours: 1, resolution: "1m" },
  "6j": { hours: 6, resolution: "5m" },
  "24j": { hours: 24, resolution: "5m" },
  "7h": { hours: 24 * 7, resolution: "15m" },
  "30h": { hours: 24 * 30, resolution: "1h" },
};

export function HistoryClient({ deviceSlug }: { deviceSlug: string }) {
  const [range, setRange] = useState<keyof typeof ranges>("6j");
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const selected = ranges[range];
    const end = new Date();
    const start = new Date(end.getTime() - selected.hours * 3600_000);
    try {
      setData(
        await apiGet(
          `/api/v1/devices/${deviceSlug}/telemetry?from=${encodeURIComponent(start.toISOString())}` +
            `&to=${encodeURIComponent(end.toISOString())}&resolution=${selected.resolution}`,
        ),
      );
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Gagal mengambil data");
    }
  }, [deviceSlug, range]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div>
      <header className="page-header">
        <div><p className="eyebrow">Telemetry</p><h1>Riwayat performa.</h1><p className="subtitle">Bandingkan produksi PV dan output inverter.</p></div>
      </header>
      <div className="controls" style={{ marginBottom: 14 }}>
        {(Object.keys(ranges) as (keyof typeof ranges)[]).map((key) => (
          <button className={`control-button ${range === key ? "active" : ""}`} key={key} onClick={() => setRange(key)}>{key}</button>
        ))}
      </div>
      <article className="panel chart-panel">
        <div className="panel-title-row"><h2>Daya PV vs output AC</h2><span className="panel-note">{data ? `${dateTime(data.from)} — ${dateTime(data.to)}` : "Memuat"}</span></div>
        {error ? <div className="error-state">{error}</div> : <PowerChart points={data?.points ?? []} />}
      </article>
      <article className="panel section-gap">
        <div className="panel-title-row"><h2>Data terbaru pada rentang</h2><span className="panel-note">{number(data?.points.length, 0)} titik</span></div>
        <div className="table-wrap"><table><thead><tr><th>Waktu</th><th>PV</th><th>Output</th><th>Baterai</th><th>Beban</th><th>Suhu</th></tr></thead><tbody>
          {(data?.points ?? []).slice(-20).reverse().map((point) => <tr key={point.recorded_at}><td>{dateTime(point.recorded_at)}</td><td>{number(point.pv_power_w, 1)} W</td><td>{number(point.ac_output_power_w, 1)} W</td><td>{number(point.battery_voltage_v, 1)} V</td><td>{number(point.load_percent, 0)}%</td><td>{number(point.inverter_temperature_c, 0)} °C</td></tr>)}
        </tbody></table></div>
      </article>
    </div>
  );
}
