import { DashboardClient } from "@/components/dashboard-client";

export default function HomePage() {
  return <DashboardClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

