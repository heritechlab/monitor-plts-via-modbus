"use client";

import { useEffect, useState } from "react";

import { BmsHistoryClient } from "@/components/bms-history-client";
import { HistoryClient } from "@/components/history-client";
import { apiGet } from "@/lib/api";
import type { BmsDeviceSummary } from "@/lib/types";

export function HistoryTabs({ inverterDeviceSlug }: { inverterDeviceSlug: string }) {
  const [bmsDevices, setBmsDevices] = useState<BmsDeviceSummary[]>([]);
  const [selected, setSelected] = useState<string>("inverter");

  useEffect(() => {
    apiGet<{ devices: BmsDeviceSummary[] }>("/api/v1/bms-devices", { cacheTtlSeconds: 30 })
      .then((response) => setBmsDevices(response.devices))
      .catch(() => undefined);
  }, []);

  const selectedBmsDevice = bmsDevices.find((device) => device.slug === selected);

  return (
    <div>
      <header className="page-header">
        <div>
          <p className="eyebrow">Telemetry</p>
          <h1>Riwayat performa.</h1>
          <p className="subtitle">
            {selectedBmsDevice
              ? `Riwayat SOC dan tegangan pack ${selectedBmsDevice.name}.`
              : "Bandingkan produksi PV dan output inverter."}
          </p>
        </div>
      </header>

      {bmsDevices.length > 0 && (
        <div className="controls" style={{ marginBottom: 14 }}>
          <button
            className={`control-button ${selected === "inverter" ? "active" : ""}`}
            onClick={() => setSelected("inverter")}
            type="button"
          >
            Inverter
          </button>
          {bmsDevices.map((device) => (
            <button
              className={`control-button ${selected === device.slug ? "active" : ""}`}
              key={device.slug}
              onClick={() => setSelected(device.slug)}
              type="button"
            >
              {device.name}
            </button>
          ))}
        </div>
      )}

      {selected === "inverter" || !selectedBmsDevice ? (
        <HistoryClient deviceSlug={inverterDeviceSlug} />
      ) : (
        <BmsHistoryClient deviceSlug={selectedBmsDevice.slug} key={selectedBmsDevice.slug} />
      )}
    </div>
  );
}
