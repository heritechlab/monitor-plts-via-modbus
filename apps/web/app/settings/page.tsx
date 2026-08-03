import { SettingsClient } from "@/components/settings-client";

export default function SettingsPage() {
  return <SettingsClient deviceSlug={process.env.DEVICE_SLUG ?? "prime-rumah-01"} />;
}
