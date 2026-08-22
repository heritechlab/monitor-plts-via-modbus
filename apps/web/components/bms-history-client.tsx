"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { BmsPowerChart } from "@/components/bms-power-chart";
import { apiGet } from "@/lib/api";
import { dateTime, localDateInput, number } from "@/lib/format";
import {
  buildCustomHourWindow,
  buildHistoryWindow,
  historyRanges,
  resolutionForDuration,
  type HistoryRangeKey,
} from "@/lib/history-range";
import type { BmsHistoryPoint, BmsHistoryResponse } from "@/lib/types";

const PAGE_SIZE_OPTIONS = [50, 100];

type SortKey = "recorded_at" | "soc_percent" | "pack_voltage_v" | "pack_current_a" | "temperature_1_c";
type SortDirection = "asc" | "desc";

interface SortHeaderProps {
  label: string;
  targetKey: SortKey;
  currentKey: SortKey;
  direction: SortDirection;
  onSort: (key: SortKey) => void;
}

function SortHeader({ label, targetKey, currentKey, direction, onSort }: SortHeaderProps) {
  const active = currentKey === targetKey;
  return (
    <button
      type="button"
      onClick={() => onSort(targetKey)}
      style={{
        background: "none",
        border: "none",
        color: "inherit",
        cursor: "pointer",
        font: "inherit",
        padding: 0,
      }}
    >
      {label}
      {active && (direction === "asc" ? " ↑" : " ↓")}
    </button>
  );
}

type RangeMode = "custom" | "preset";

export function BmsHistoryClient({ deviceSlug }: { deviceSlug: string }) {
  const today = localDateInput();
  const [selectedDate, setSelectedDate] = useState(today);
  const [range, setRange] = useState<HistoryRangeKey>("6h");
  const [mode, setMode] = useState<RangeMode>("custom");
  const [customStart, setCustomStart] = useState("06:00");
  const [customEnd, setCustomEnd] = useState("18:00");
  const [data, setData] = useState<BmsHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("recorded_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setData(null);
    setError(null);

    try {
      const { start, end } =
        mode === "custom"
          ? buildCustomHourWindow(selectedDate, customStart, customEnd)
          : buildHistoryWindow(selectedDate, range);
      const resolution =
        mode === "custom" ? resolutionForDuration(end.getTime() - start.getTime()) : historyRanges[range].resolution;
      setData(
        await apiGet<BmsHistoryResponse>(
          `/api/v1/bms-devices/${deviceSlug}/telemetry?from=${encodeURIComponent(start.toISOString())}` +
            `&to=${encodeURIComponent(end.toISOString())}&resolution=${resolution}`,
          { signal, cacheTtlSeconds: 30 },
        ),
      );
      setPage(0);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "Gagal mengambil data");
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, [deviceSlug, mode, range, selectedDate, customStart, customEnd]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  const displayPoints = useMemo(() => data?.points ?? [], [data]);

  const sortedPoints = useMemo(() => {
    const points = [...displayPoints];
    points.sort((left: BmsHistoryPoint, right: BmsHistoryPoint) => {
      let leftValue: number;
      let rightValue: number;
      if (sortKey === "recorded_at") {
        leftValue = Date.parse(left.recorded_at);
        rightValue = Date.parse(right.recorded_at);
      } else {
        leftValue = left[sortKey] ?? -Infinity;
        rightValue = right[sortKey] ?? -Infinity;
      }
      if (Number.isNaN(leftValue)) leftValue = -Infinity;
      if (Number.isNaN(rightValue)) rightValue = -Infinity;
      if (leftValue === rightValue) return 0;
      const order = sortDirection === "asc" ? 1 : -1;
      return (leftValue < rightValue ? -1 : 1) * order;
    });
    return points;
  }, [displayPoints, sortKey, sortDirection]);

  const totalPoints = sortedPoints.length;
  const totalPages = Math.max(1, Math.ceil(totalPoints / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const startIndex = safePage * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalPoints);
  const paginatedPoints = useMemo(
    () => sortedPoints.slice(startIndex, endIndex),
    [sortedPoints, startIndex, endIndex],
  );

  const handleSort = useCallback((key: SortKey) => {
    setPage(0);
    if (sortKey === key) {
      setSortDirection((previous) => (previous === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  }, [sortKey]);

  return (
    <div>
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
          <span>Mode rentang</span>
          <div className="controls">
            <button
              className={`control-button ${mode === "custom" ? "active" : ""}`}
              type="button"
              aria-pressed={mode === "custom"}
              onClick={() => setMode("custom")}
            >
              Jam tertentu
            </button>
            <button
              className={`control-button ${mode === "preset" ? "active" : ""}`}
              type="button"
              aria-pressed={mode === "preset"}
              onClick={() => setMode("preset")}
            >
              Rentang relatif
            </button>
          </div>
        </div>
        {mode === "custom" ? (
          <>
            <label className="history-filter-group">
              <span>Jam mulai</span>
              <input
                aria-label="Jam mulai"
                className="control"
                type="time"
                value={customStart}
                onChange={(event) => setCustomStart(event.target.value)}
              />
            </label>
            <label className="history-filter-group">
              <span>Jam akhir</span>
              <input
                aria-label="Jam akhir"
                className="control"
                type="time"
                value={customEnd}
                onChange={(event) => setCustomEnd(event.target.value)}
              />
            </label>
          </>
        ) : (
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
        )}
      </div>
      <article className="panel chart-panel">
        <div className="panel-title-row"><h2>State of charge</h2><span className="panel-note">{data ? `${dateTime(data.from)} — ${dateTime(data.to)}` : loading ? "Memuat..." : "—"}</span></div>
        {error ? <div className="error-state">{error}</div> : loading ? <div className="empty">Memuat riwayat...</div> : <BmsPowerChart points={data?.points ?? []} />}
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
        <div className="table-wrap"><table><thead><tr><th><SortHeader label="Waktu" targetKey="recorded_at" currentKey={sortKey} direction={sortDirection} onSort={handleSort} /></th><th><SortHeader label="SOC" targetKey="soc_percent" currentKey={sortKey} direction={sortDirection} onSort={handleSort} /></th><th><SortHeader label="Tegangan pack" targetKey="pack_voltage_v" currentKey={sortKey} direction={sortDirection} onSort={handleSort} /></th><th><SortHeader label="Arus pack" targetKey="pack_current_a" currentKey={sortKey} direction={sortDirection} onSort={handleSort} /></th><th><SortHeader label="Suhu 1" targetKey="temperature_1_c" currentKey={sortKey} direction={sortDirection} onSort={handleSort} /></th><th>Suhu 2</th></tr></thead><tbody>
          {paginatedPoints.map((point) => <tr key={point.recorded_at}><td>{dateTime(point.recorded_at)}</td><td>{number(point.soc_percent, 0)}%</td><td>{number(point.pack_voltage_v, 2)} V</td><td>{number(point.pack_current_a, 2)} A</td><td>{number(point.temperature_1_c, 1)} °C</td><td>{number(point.temperature_2_c, 1)} °C</td></tr>)}
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
