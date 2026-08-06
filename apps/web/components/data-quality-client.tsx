"use client";

import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import { dateTime, localDateInput, number } from "@/lib/format";
import type { DailySummary, LatestResponse } from "@/lib/types";

interface QualityResponse {
  summary: DailySummary;
  anomalies: NonNullable<LatestResponse["telemetry"]>[];
}

export function DataQualityClient({ deviceSlug }: { deviceSlug: string }) {
  const [date, setDate] = useState(localDateInput());
  const [data, setData] = useState<QualityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => apiGet<QualityResponse>(`/api/v1/devices/${deviceSlug}/data-quality?date=${date}`, { cacheTtlSeconds: 60 }).then((value) => { setData(value); setError(null); }).catch((reason) => setError(String(reason))), [date, deviceSlug]);
  useEffect(() => { void load(); }, [load]);
  return <div><header className="page-header"><div><p className="eyebrow">Observability</p><h1>Kualitas data.</h1><p className="subtitle">Anomali tetap disimpan, tetapi tidak mencemari perhitungan energi terkait.</p></div><input className="control" type="date" value={date} max={localDateInput()} onChange={(event) => setDate(event.target.value)} /></header>{error ? <div className="error-state panel">{error}</div> : <><section className="grid summary-grid panel"><div className="summary-item"><span>Total sampel</span><strong>{number(data?.summary.sample_count, 0)}</strong></div><div className="summary-item"><span>Ber-flag</span><strong className={data?.summary.invalid_sample_count ? "warning" : "good"}>{number(data?.summary.invalid_sample_count, 0)}</strong></div><div className="summary-item"><span>Gap</span><strong>{number(data?.summary.gaps.length, 0)}</strong></div><div className="summary-item"><span>Cakupan PV</span><strong>{number(data?.summary.pv_coverage_percent, 1)}%</strong></div></section><article className="panel section-gap"><div className="panel-title-row"><h2>Anomali terakhir</h2><span className="panel-note">maksimal 100 sampel</span></div>{data?.anomalies.length ? data.anomalies.map((sample) => <details className="summary-item" key={sample.sample_id}><summary><span className="warning" style={{ display: "inline", marginRight: 12 }}>{sample.quality_flags.join(", ")}</span>{dateTime(sample.recorded_at)}</summary><div className="raw-grid" style={{ marginTop: 12 }}>{Object.entries(sample.raw_registers ?? {}).map(([address, value]) => <div className="raw-cell" key={address}><span>{address}</span><strong>{value}</strong></div>)}</div></details>) : <div className="empty">Tidak ada anomali pada tanggal ini.</div>}</article></>}</div>;
}

