import { HistoryTabs } from "@/components/history-tabs";

export default function HistoryPage() {
  return <HistoryTabs inverterDeviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}
