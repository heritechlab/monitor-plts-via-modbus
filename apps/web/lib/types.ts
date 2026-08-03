export type MetricName =
  | "pv_voltage_v"
  | "pv_current_a"
  | "pv_power_w"
  | "battery_voltage_v"
  | "ac_output_voltage_v"
  | "ac_output_current_a"
  | "ac_output_power_w"
  | "load_percent"
  | "inverter_temperature_c";

export type Metrics = Record<MetricName, number | null>;

export interface LatestResponse {
  device: { slug: string; name: string; timezone: string };
  status: "online" | "degraded" | "offline";
  telemetry_status: "online" | "degraded" | "offline";
  gateway_age_seconds: number | null;
  telemetry_age_seconds: number | null;
  gateway: {
    serial_status: string;
    queue_depth: number | null;
    last_contact_at: string | null;
    last_serial_success_at: string | null;
  };
  telemetry: null | {
    sample_id: string;
    recorded_at: string;
    received_at: string;
    metrics: Metrics;
    quality_flags: string[];
    quality_details: Record<string, unknown>;
    raw_registers: Record<string, number>;
    gateway_version: string | null;
    source: string;
  };
  server_time: string;
}

export interface HistoryPoint extends Partial<Record<MetricName, number | null>> {
  recorded_at: string;
  quality_flags?: string[];
}

export interface HistoryResponse {
  device_slug: string;
  from: string;
  to: string;
  resolution: string;
  points: HistoryPoint[];
}

export interface DailySummary {
  date: string;
  timezone: string;
  pv_energy_kwh: number;
  ac_load_estimate_kvah: number;
  ac_output_energy_kwh: null;
  estimated_surplus_kwh: null;
  equivalent_saving_idr: number;
  peak_pv_raw_w: number | null;
  peak_pv_1m_avg_w: number | null;
  peak_ac_load_estimate_raw_va: number | null;
  peak_ac_load_estimate_1m_avg_va: number | null;
  peak_output_raw_w: null;
  peak_output_1m_avg_w: null;
  max_temperature_c: number | null;
  min_battery_voltage_v: number | null;
  max_battery_voltage_v: number | null;
  pv_above_500_minutes: number;
  pv_above_800_minutes: number;
  pv_above_1000_minutes: number;
  sample_count: number;
  invalid_sample_count: number;
  pv_coverage_percent: number;
  ac_coverage_percent: number;
  ac_load_coverage_percent: number;
  first_sample_at: string | null;
  last_sample_at: string | null;
  gaps: { from: string; to: string; seconds: number }[];
}

export interface MonthlySummary {
  month: string;
  pv_energy_kwh: number;
  ac_load_estimate_kvah: number;
  ac_output_energy_kwh: null;
  estimated_surplus_kwh: null;
  average_daily_pv_kwh: number;
  equivalent_saving_idr: number;
  days_with_data: number;
  best_day: DailySummary | null;
  lowest_day: DailySummary | null;
  days: DailySummary[];
}
