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

export interface RegisterCorrelation {
  metric: MetricName;
  label: string;
  coefficient: number;
}

export interface RegisterAnalysisItem {
  address: string;
  status: "known" | "candidate" | "unknown";
  name: string | null;
  unit: string | null;
  scale: string | null;
  latest_raw: number | null;
  decoded_value: number | null;
  min_raw: number;
  max_raw: number;
  distinct_values: number;
  changes: number;
  activity: "zero" | "stable" | "dynamic";
  strongest_correlation: RegisterCorrelation | null;
}

export interface BmsMetrics {
  cell_voltages_mv: number[];
  pack_voltage_v: number | null;
  pack_power_w: number | null;
  pack_current_a: number | null;
  temperature_1_c: number | null;
  temperature_2_c: number | null;
  soc_percent: number | null;
  remaining_capacity_ah: number | null;
  full_capacity_ah: number | null;
  cycle_count: number | null;
  balance_current_a: number | null;
  alarm_flags: number | null;
}

export interface BmsLatestResponse {
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
    cell_count: number | null;
    metrics: BmsMetrics;
    quality_flags: string[];
    raw_registers: Record<string, number>;
    gateway_version: string | null;
    source: string;
  };
  server_time: string;
}

export interface RegisterAnalysisResponse {
  device_slug: string;
  hours: number;
  from: string | null;
  to: string | null;
  sample_count: number;
  analyzed_sample_count: number;
  latest_recorded_at: string | null;
  register_map_version: string | null;
  decoder_version: string | null;
  read_mode: "database-only";
  serial_requests_added: number;
  summary: { known: number; candidate: number; unknown: number };
  registers: RegisterAnalysisItem[];
}
