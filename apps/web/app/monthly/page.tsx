import { MonthlyClient } from "@/components/monthly-client";

export default function MonthlyPage() {
  return <MonthlyClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

