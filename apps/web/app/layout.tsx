import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "PLTS Monitor Rumah",
  description: "Dashboard monitoring inverter PRIME melalui Modbus RTU",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id">
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}

