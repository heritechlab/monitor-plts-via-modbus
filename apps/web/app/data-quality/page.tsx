import { DataQualityClient } from "@/components/data-quality-client";

export default function DataQualityPage() {
  return <DataQualityClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

