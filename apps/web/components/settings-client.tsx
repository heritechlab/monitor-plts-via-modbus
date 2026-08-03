"use client";

import {
  CheckCircle2,
  CircleHelp,
  Database,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MetricCard } from "@/components/metric-card";
import { apiGet } from "@/lib/api";
import { dateTime, number } from "@/lib/format";
import type { RegisterAnalysisItem, RegisterAnalysisResponse } from "@/lib/types";

const ranges = [1, 6, 12, 24] as const;

function rawRange(item: RegisterAnalysisItem): string {
  return item.min_raw === item.max_raw
    ? number(item.min_raw, 0)
    : `${number(item.min_raw, 0)} — ${number(item.max_raw, 0)}`;
}

function correlation(item: RegisterAnalysisItem): string {
  const value = item.strongest_correlation;
  if (!value) return "—";
  return `${value.label} (r=${number(value.coefficient, 3)})`;
}

function RegisterTable({
  items,
  mode,
}: {
  items: RegisterAnalysisItem[];
  mode: "known" | "candidate" | "unknown";
}) {
  if (!items.length) {
    return <div className="compact-empty">Tidak ada register pada kategori ini.</div>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Alamat</th>
            {mode === "known" && <th>Informasi</th>}
            <th>Raw terbaru</th>
            {mode === "known" && <th>Nilai terdecode</th>}
            <th>Rentang raw</th>
            <th>Perubahan</th>
            {mode !== "known" && <th>Korelasi terkuat</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.address}>
              <td className="register-address">{item.address}</td>
              {mode === "known" && <td><strong>{item.name}</strong><span className="register-detail">{item.scale}</span></td>}
              <td>{number(item.latest_raw, 0)}</td>
              {mode === "known" && <td>{number(item.decoded_value, 1)} {item.unit}</td>}
              <td>{rawRange(item)}</td>
              <td>{number(item.changes, 0)}× <span className="register-detail">{item.activity}</span></td>
              {mode !== "known" && <td>{correlation(item)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SettingsClient({ deviceSlug }: { deviceSlug: string }) {
  const [hours, setHours] = useState<(typeof ranges)[number]>(6);
  const [data, setData] = useState<RegisterAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await apiGet<RegisterAnalysisResponse>(
          `/api/v1/devices/${deviceSlug}/register-analysis?hours=${hours}`,
          signal,
        ),
      );
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "Gagal menganalisis register");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [deviceSlug, hours]);

  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(() => void load(controller.signal), 0);
    const refresh = window.setInterval(() => void load(controller.signal), 60_000);
    return () => {
      controller.abort();
      window.clearTimeout(initial);
      window.clearInterval(refresh);
    };
  }, [load]);

  const grouped = useMemo(() => ({
    known: data?.registers.filter((item) => item.status === "known") ?? [],
    candidate: data?.registers.filter((item) => item.status === "candidate") ?? [],
    unknown: data?.registers.filter((item) => item.status === "unknown") ?? [],
  }), [data]);

  const cards = [
    { label: "Sampel tersimpan", value: number(data?.sample_count, 0), unit: "", caption: `${number(data?.analyzed_sample_count, 0)} dianalisis`, icon: Database },
    { label: "Register dikenal", value: number(data?.summary.known, 0), unit: "", caption: "Mapping terverifikasi", icon: CheckCircle2 },
    { label: "Kandidat", value: number(data?.summary.candidate, 0), unit: "", caption: "Korelasi statistik ≥ 0,8", icon: Search },
    { label: "Belum dikenal", value: number(data?.summary.unknown, 0), unit: "", caption: "Tetap disimpan sebagai raw", icon: CircleHelp },
  ];

  return (
    <div>
      <header className="page-header">
        <div>
          <p className="eyebrow">Read-only inspector</p>
          <h1>Register inverter.</h1>
          <p className="subtitle">Analisis FC04 dari telemetry tersimpan tanpa scan atau request serial tambahan.</p>
        </div>
        <div className="status-pill online"><span className="status-dot" />Publik • read-only</div>
      </header>

      <div className="controls" style={{ marginBottom: 14 }}>
        {ranges.map((range) => (
          <button
            className={`control-button ${hours === range ? "active" : ""}`}
            key={range}
            type="button"
            aria-pressed={hours === range}
            onClick={() => setHours(range)}
          >
            {range} jam
          </button>
        ))}
        <button className="control-button" type="button" disabled={loading} onClick={() => void load()}>
          <RefreshCw size={13} style={{ display: "inline", marginRight: 6 }} />
          Perbarui
        </button>
      </div>

      <article className="panel register-safety">
        <ShieldCheck size={19} color="var(--green)" />
        <div><strong>Mode aman: database-only</strong><span>Tambahan request serial: {data?.serial_requests_added ?? 0}. Dashboard live tidak diperlambat.</span></div>
        <div className="panel-note">Terakhir: {dateTime(data?.latest_recorded_at)}</div>
      </article>

      {error && <div className="error-state panel section-gap">{error}</div>}
      {!error && <>
        <section className="grid metric-grid section-gap">{cards.map((card) => <MetricCard {...card} key={card.label} />)}</section>

        <article className="panel section-gap">
          <div className="panel-title-row"><h2>Register dikenal</h2><span className="panel-note">{data?.register_map_version ?? "—"} • {data?.decoder_version ?? "—"}</span></div>
          <RegisterTable items={grouped.known} mode="known" />
        </article>

        <article className="panel section-gap">
          <div className="panel-title-row"><h2>Kandidat informasi baru</h2><span className="panel-note">Korelasi bukan bukti mapping</span></div>
          <RegisterTable items={grouped.candidate} mode="candidate" />
        </article>

        <article className="panel section-gap">
          <div className="panel-title-row"><h2>Register belum dikenal</h2><span className="panel-note">Raw value dipertahankan untuk validasi berikutnya</span></div>
          <RegisterTable items={grouped.unknown} mode="unknown" />
        </article>
      </>}
    </div>
  );
}
