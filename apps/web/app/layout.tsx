import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "PLTS Monitor Rumah",
  description: "Dashboard monitoring inverter PRIME melalui Modbus RTU",
};

const THEME_BOOT_SCRIPT = `(function () {
  try {
    var stored = localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

