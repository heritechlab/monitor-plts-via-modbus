import { BatteryPanel } from "@/components/battery-panel";

export default function BatteryPage() {
  return <BatteryPanel deviceSlug={process.env.BMS_DEVICE_SLUG ?? "prime-rumah-01-bms"} />;
}
