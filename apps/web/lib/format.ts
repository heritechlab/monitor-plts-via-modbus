export function number(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("id-ID", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(value);
}

export function power(value: number | null | undefined): { value: string; unit: string } {
  if (value === null || value === undefined) return { value: "—", unit: "W" };
  if (Math.abs(value) >= 1000) return { value: number(value / 1000, 2), unit: "kW" };
  return { value: number(value, 0), unit: "W" };
}

export function apparentPower(value: number | null | undefined): { value: string; unit: string } {
  if (value === null || value === undefined) return { value: "—", unit: "VA" };
  if (Math.abs(value) >= 1000) return { value: number(value / 1000, 2), unit: "kVA" };
  return { value: number(value, 0), unit: "VA" };
}

export function apparentEnergy(value: number | null | undefined): string {
  return `${number(value, 3)} kVAh`;
}

export function energy(value: number | null | undefined): string {
  return `${number(value, 3)} kWh`;
}

export function currency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "Belum ada data";
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Jakarta",
  }).format(new Date(value));
}

export function timeOnly(value: string): string {
  return new Intl.DateTimeFormat("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(new Date(value));
}

export function localDateInput(date = new Date()): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Jakarta" }).format(date);
}
