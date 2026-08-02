import { HistoryClient } from "@/components/history-client";

export default function HistoryPage() {
  return <HistoryClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

