"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { PowerChart } from "@/components/power-chart";
import { apiGet } from "@/lib/api";
import { dateTime, localDateInput, number } from "@/lib/format";
import {
  buildHistoryWindow,
  historyRanges,
  type HistoryRangeKey,
} from "@/lib/history-range";
import type { HistoryResponse } from "@/lib/types";

const PAGE_SIZE_OPTIONS = [50, 100];

export function HistoryClient({ deviceSlug }: { deviceSlug: string }) {
  const today = localDateInput();
  const [selectedDate, setSelectedDate] = useState(today);
  const [range, setRange] = useState<HistoryRangeKey>("6h");
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setData(null);
    setError(null);

    try {
      const selected = historyRanges[range];
      const { start, end } = buildHistoryWindow(selectedDate, range);
      setData(
        await apiGet(
          `/api/v1/devices/${deviceSlug}/telemetry?from=${encodeURIComponent(start.toISOString())}` +
            `&to=${encodeURIComponent(end.toISOString())}&resolution=${selected.resolution}`,
          signal,
        ),
      );
      setPage(0);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "Gagal mengambil data");
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, [deviceSlug, range, selectedDate]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  const displayPoints = useMemo(
    () => [...(data?.points ?? [])].sort(
      (left, right) => Date.parse(right.recorded_at) - Date.parse(left.recorded_at),
    ),
    [data],
  );

  const totalPoints = displayPoints.length;
  const totalPages = Math.max(1, Math.ceil(totalPoints / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const startIndex = safePage * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalPoints);
  const paginatedPoints = useMemo(
    () => displayPoints.slice(startIndex, endIndex),
    [displayPoints, startIndex, endIndex],
  );

  return (
    <div>
      <header className="page-header">
        <div><p className="eyebrow">Telemetry</p><h1>Riwayat performa.</h1><p className="subtitle">Bandingkan produksi PV dan output inverter.</p></div>
      </header>
      <div className="history-filters">
        <label className="history-filter-group">
          <span>Tanggal</span>
          <input
            aria-label="Tanggal riwayat"
            className="control"
            type="date"
            value={selectedDate}
            max={today}
            onChange={(event) => setSelectedDate(event.target.value)}
          />
        </label>
        <div className="history-filter-group">
          <span>Rentang</span>
          <div className="controls">
            {(Object.keys(historyRanges) as HistoryRangeKey[]).map((key) => (
              <button
                className={`control-button ${range === key ? "active" : ""}`}
                key={key}
                type="button"
                aria-pressed={range === key}
                onClick={() => setRange(key)}
              >
                {historyRanges[key].label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <article className="panel chart-panel">
        <div className="panel-title-row"><h2>Daya PV vs beban AC estimasi</h2><span className="panel-note">{data ? `${dateTime(data.from)} — ${dateTime(data.to)}` : loading ? "Memuat..." : "—"}</span></div>
        {error ? <div className="error-state">{error}</div> : loading ? <div className="empty">Memuat riwayat...</div> : <PowerChart points={data?.points ?? []} />}
      </article>
      <article className="panel section-gap">
        <div className="panel-title-row">
          <h2>Data pada rentang</h2>
          <span className="panel-note">
            {totalPoints > 0
              ? `${startIndex + 1}–${endIndex} dari ${number(totalPoints, 0)} titik`
              : `${number(totalPoints, 0)} titik`}
          </span>
        </div>
        <div className="table-wrap"><table><thead><tr><th>Waktu</th><th>PV</th><th>Beban estimasi</th><th>Baterai</th><th>Beban</th><th>Suhu</th></tr></thead><tbody>
          {paginatedPoints.map((point) => <tr key={point.recorded_at}><td>{dateTime(point.recorded_at)}</td><td>{number(point.pv_power_w, 1)} W</td><td>{number(point.ac_output_power_w, 1)} VA</td><td>{number(point.battery_voltage_v, 1)} V</td><td>{number(point.load_percent, 0)}%</td><td>{number(point.inverter_temperature_c, 0)} °C</td></tr>)}
          {!loading && !error && paginatedPoints.length === 0 && <tr><td className="table-empty" colSpan={6}>Belum ada data pada rentang ini.</td></tr>}
        </tbody></table></div>
        {totalPoints > 0 && (
          <div className="history-filters" style={{ marginTop: 14 }}>
            <div className="history-filter-group">
              <span>Per halaman</span>
              <div className="controls">
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <button
                    key={size}
                    className={`control-button ${pageSize === size ? "active" : ""}`}
                    type="button"
                    aria-pressed={pageSize === size}
                    onClick={() => { setPageSize(size); setPage(0); }}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>
            <div className="history-filter-group">
              <span>Halaman {safePage + 1} dari {totalPages}</span>
              <div className="controls">
                <button
                  className="control-button"
                  type="button"
                  disabled={safePage === 0}
                  onClick={() => setPage((previous) => previous - 1)}
                >
                  Sebelumnya
                </button>
                <button
                  className="control-button"
                  type="button"
                  disabled={safePage >= totalPages - 1}
                  onClick={() => setPage((previous) => previous + 1)}
                >
                  Berikutnya
                </button>
              </div>
            </div>
          </div>
        )}
      </article>
    </div>
  );
}
