import { DailyClient } from "@/components/daily-client";

export default function DailyPage() {
  return <DailyClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

