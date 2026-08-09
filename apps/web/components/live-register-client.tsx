"use client";

import { Activity, Pause, Play, Radio } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import { dateTime, number } from "@/lib/format";
import type { LatestResponse } from "@/lib/types";

const AVAILABLE_REGISTERS: { address: string; label: string; group: string }[] = [
  // Kandidat utama
  { address: "0x3016", label: "Kandidat arus baterai", group: "Kandidat" },
  { address: "0x300D", label: "Kandidat bus/internal", group: "Kandidat" },
  { address: "0x3006", label: "Kandidat beban A", group: "Kandidat" },
  { address: "0x3007", label: "Kandidat beban B", group: "Kandidat" },
  { address: "0x3000", label: "Kandidat PV", group: "Kandidat" },
  { address: "0x300E", label: "Kandidat arus PV B", group: "Kandidat" },
  // Register yang sudah dikenal (untuk referensi)
  { address: "0x3001", label: "Tegangan AC", group: "Dikenal" },
  { address: "0x3002", label: "Tegangan baterai", group: "Dikenal" },
  { address: "0x3003", label: "Arus AC", group: "Dikenal" },
  { address: "0x3004", label: "Beban %", group: "Dikenal" },
  { address: "0x3005", label: "Beban estimasi VA", group: "Dikenal" },
  { address: "0x3009", label: "Suhu inverter", group: "Dikenal" },
  { address: "0x3010", label: "Arus PV", group: "Dikenal" },
  { address: "0x3012", label: "Tegangan PV", group: "Dikenal" },
];

const DEFAULT_SELECTED = [
  "0x3016",
  "0x300D",
  "0x3006",
  "0x3007",
  "0x3000",
  "0x300E",
];

const REFRESH_INTERVAL_MS = 1000;

export function LiveRegisterClient({ deviceSlug }: { deviceSlug: string }) {
  const [isLive, setIsLive] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set(DEFAULT_SELECTED));
  const [latest, setLatest] = useState<LatestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await apiGet<LatestResponse>(`/api/v1/devices/${deviceSlug}/latest`);
      setLatest(response);
      setLastUpdated(new Date());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Gagal mengambil data");
    }
  }, [deviceSlug]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void load(), 0);
    if (!isLive) {
      return () => window.clearTimeout(initialTimer);
    }
    const timer = window.setInterval(() => void load(), REFRESH_INTERVAL_MS);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [isLive, load]);

  const toggleRegister = (address: string) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(address)) {
        next.delete(address);
      } else {
        next.add(address);
      }
      return next;
    });
  };

  const visible = AVAILABLE_REGISTERS.filter((item) => selected.has(item.address));
  const rawRegisters = latest?.telemetry?.raw_registers ?? {};
  const recordedAt = latest?.telemetry?.recorded_at;
  const telemetryStatus = latest?.telemetry_status ?? "offline";

  return (
    <div>
      <header className="page-header">
        <div>
          <p className="eyebrow">Raw register</p>
          <h1>Monitor live.</h1>
          <p className="subtitle">
            Pantau nilai raw register secara realtime untuk validasi dengan BMS atau smart plug.
          </p>
        </div>
        <div className={`status-pill ${telemetryStatus === "online" ? "online" : "degraded"}`}>
          <span className="status-dot" />
          {isLive ? "Live 1 detik" : "Dijeda"}
        </div>
      </header>

      <section className="panel section-gap">
        <div className="panel-title-row">
          <h2>Kontrol</h2>
          <span className="panel-note">Update terakhir: {lastUpdated ? dateTime(lastUpdated.toISOString()) : "—"}</span>
        </div>
        <div className="history-filters" style={{ marginBottom: 8 }}>
          <div className="history-filter-group">
            <span>Mode</span>
            <div className="controls">
              <button
                className={`control-button ${isLive ? "active" : ""}`}
                type="button"
                onClick={() => setIsLive(true)}
              >
                <Radio size={14} style={{ marginRight: 6 }} />
                Live
              </button>
              <button
                className={`control-button ${!isLive ? "active" : ""}`}
                type="button"
                onClick={() => setIsLive(false)}
              >
                <Pause size={14} style={{ marginRight: 6 }} />
                Pause
              </button>
            </div>
          </div>
          <div className="history-filter-group">
            <span>Aksi</span>
            <div className="controls">
              <button className="control-button" type="button" onClick={() => void load()} disabled={isLive}>
                <Play size={14} style={{ marginRight: 6 }} />
                Refresh sekali
              </button>
            </div>
          </div>
        </div>
        <p className="panel-note">
          Pilih register yang ingin dipantau. Gunakan mode Pause saat tidak dibutuhkan untuk menghemat beban server.
        </p>
      </section>

      <section className="panel section-gap">
        <div className="panel-title-row">
          <h2>Register yang dipantau</h2>
          <span className="panel-note">{visible.length} register</span>
        </div>
        <div className="register-selector">
          {AVAILABLE_REGISTERS.map((item) => {
            const active = selected.has(item.address);
            return (
              <label key={item.address} className={`register-chip ${active ? "active" : ""}`}>
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggleRegister(item.address)}
                />
                <span>{item.address}</span>
                <small>{item.label}</small>
              </label>
            );
          })}
        </div>
      </section>

      {error ? (
        <div className="error-state panel section-gap">{error}</div>
      ) : (
        <section className="grid metric-grid section-gap">
          {visible.map((item) => {
            const value = rawRegisters[item.address];
            return (
              <article className="panel register-live-card" key={item.address}>
                <div className="panel-title-row">
                  <div>
                    <h2>{item.address}</h2>
                    <span className="panel-note">{item.label}</span>
                  </div>
                  <Activity size={16} color="var(--muted)" />
                </div>
                <div className="register-live-value">
                  {value !== undefined ? number(value, 0) : "—"}
                </div>
                <div className="panel-note">Raw value</div>
              </article>
            );
          })}
          {visible.length === 0 && (
            <div className="panel empty" style={{ gridColumn: "1 / -1" }}>
              Pilih minimal satu register untuk dipantau.
            </div>
          )}
        </section>
      )}

      <section className="panel section-gap">
        <div className="panel-title-row">
          <h2>Metadata sampel terakhir</h2>
          <span className="panel-note">{recordedAt ? dateTime(recordedAt) : "—"}</span>
        </div>
        <div className="grid summary-grid">
          <div className="summary-item">
            <span>Telemetry status</span>
            <strong className={telemetryStatus === "online" ? "good" : "warning"}>{telemetryStatus}</strong>
          </div>
          <div className="summary-item">
            <span>Gateway queue</span>
            <strong>{number(latest?.gateway.queue_depth, 0)}</strong>
          </div>
          <div className="summary-item">
            <span>Serial status</span>
            <strong className={latest?.gateway.serial_status === "ok" ? "good" : "warning"}>
              {latest?.gateway.serial_status ?? "—"}
            </strong>
          </div>
          <div className="summary-item">
            <span>Sampel recorded_at</span>
            <strong>{recordedAt ? dateTime(recordedAt) : "—"}</strong>
          </div>
        </div>
      </section>

      <style jsx>{`
        .register-selector {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .register-chip {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 10px;
          border-radius: 999px;
          border: 1px solid rgba(184, 235, 201, 0.12);
          background: rgba(184, 235, 201, 0.04);
          cursor: pointer;
          font-size: 12px;
          color: var(--muted);
          transition: background 0.15s, border-color 0.15s;
        }
        .register-chip.active {
          background: rgba(126, 242, 154, 0.12);
          border-color: rgba(126, 242, 154, 0.35);
          color: var(--foreground);
        }
        .register-chip input {
          accent-color: var(--green);
          cursor: pointer;
        }
        .register-chip span {
          font-family: monospace;
          font-weight: 600;
        }
        .register-chip small {
          opacity: 0.8;
        }
        .register-live-card {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .register-live-value {
          font-size: 32px;
          font-weight: 700;
          font-family: monospace;
          color: var(--green);
        }
      `}</style>
    </div>
  );
}
