import { LiveRegisterClient } from "@/components/live-register-client";

export default function LiveRegisterPage() {
  return <LiveRegisterClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}
