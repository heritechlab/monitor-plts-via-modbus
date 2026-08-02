import { DeviceClient } from "@/components/device-client";

export default function DevicesPage() {
  return <DeviceClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}

