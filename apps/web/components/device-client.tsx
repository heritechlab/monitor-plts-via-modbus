"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import { dateTime, number } from "@/lib/format";

interface DeviceDetail {
  slug: string;
  name: string;
  location: string | null;
  timezone: string;
  inverter_model: string | null;
  inverter_rated_w: number;
  pv_rated_wp: number;
  battery_nominal_v: number | null;
  battery_capacity_ah: number | null;
  tariff_idr_per_kwh: number;
  gateway: { version: string | null; source: string | null; queue_depth: number | null; serial_status: string; last_contact_at: string | null; last_serial_success_at: string | null };
}

export function DeviceClient({ deviceSlug }: { deviceSlug: string }) {
  const [data, setData] = useState<DeviceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiGet<DeviceDetail>(`/api/v1/devices/${deviceSlug}`, { cacheTtlSeconds: 60 }).then(setData).catch((reason) => setError(String(reason))); }, [deviceSlug]);
  return <div><header className="page-header"><div><p className="eyebrow">Hardware</p><h1>Perangkat.</h1><p className="subtitle">Identitas inverter dan kesehatan gateway lokal.</p></div></header>{error ? <div className="error-state panel">{error}</div> : <section className="grid two-column"><article className="panel"><div className="panel-title-row"><h2>Inverter dan array PV</h2></div><div className="grid summary-grid"><div className="summary-item"><span>Nama</span><strong>{data?.name ?? "—"}</strong></div><div className="summary-item"><span>Model</span><strong>{data?.inverter_model ?? "—"}</strong></div><div className="summary-item"><span>Rated inverter</span><strong>{number(data?.inverter_rated_w, 0)} W</strong></div><div className="summary-item"><span>Array PV</span><strong>{number(data?.pv_rated_wp, 0)} Wp</strong></div><div className="summary-item"><span>Baterai</span><strong>{number(data?.battery_nominal_v, 0)} V / {number(data?.battery_capacity_ah, 0)} Ah</strong></div><div className="summary-item"><span>Timezone</span><strong>{data?.timezone ?? "—"}</strong></div></div></article><article className="panel"><div className="panel-title-row"><h2>Gateway</h2><span className={`status-pill ${data?.gateway.serial_status === "ok" ? "online" : "degraded"}`}><span className="status-dot" />{data?.gateway.serial_status ?? "unknown"}</span></div><div className="grid summary-grid"><div className="summary-item"><span>Versi</span><strong>{data?.gateway.version ?? "—"}</strong></div><div className="summary-item"><span>Sumber</span><strong>{data?.gateway.source ?? "—"}</strong></div><div className="summary-item"><span>Antrean</span><strong>{number(data?.gateway.queue_depth, 0)}</strong></div><div className="summary-item"><span>Kontak terakhir</span><strong>{dateTime(data?.gateway.last_contact_at)}</strong></div><div className="summary-item"><span>Serial terakhir</span><strong>{dateTime(data?.gateway.last_serial_success_at)}</strong></div><div className="summary-item"><span>Device slug</span><strong>{data?.slug ?? "—"}</strong></div></div></article></section>}</div>;
}

