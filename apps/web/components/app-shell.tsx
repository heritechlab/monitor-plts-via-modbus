"use client";

import {
  Activity,
  BarChart3,
  Binary,
  CalendarDays,
  Database,
  Gauge,
  History,
  Radio,
  Settings2,
  SunMedium,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/theme-toggle";

const links = [
  { href: "/", label: "Ringkasan", icon: Gauge },
  { href: "/history", label: "Riwayat", icon: History },
  { href: "/daily", label: "Harian", icon: CalendarDays },
  { href: "/monthly", label: "Bulanan", icon: BarChart3 },
  { href: "/settings", label: "Register", icon: Binary },
  { href: "/live-register", label: "Live", icon: Radio, desktopOnly: true },
  { href: "/data-quality", label: "Kualitas data", icon: Activity, desktopOnly: true },
  { href: "/devices", label: "Perangkat", icon: Settings2, desktopOnly: true },
];

function NavLinks({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();
  return links
    .filter((item) => !mobile || !item.desktopOnly)
    .map(({ href, label, icon: Icon }) => (
      <Link
        className={`nav-link ${pathname === href ? "active" : ""}`}
        href={href}
        key={href}
      >
        <Icon size={17} />
        <span>{label}</span>
      </Link>
    ));
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><SunMedium size={20} /></div>
          <div><strong>PLTS Monitor</strong><span>Rumah • PRIME</span></div>
        </div>
        <nav className="nav-list"><NavLinks /></nav>
        <div style={{ bottom: 24, left: 30, position: "absolute", color: "var(--muted)", fontSize: 10 }}>
          <Database size={13} style={{ display: "inline", marginRight: 7 }} />
          Local-first • v0.1.0
        </div>
      </aside>
      <main className="main-content">{children}</main>
      <nav className="mobile-nav"><NavLinks mobile /></nav>
      <ThemeToggle />
    </div>
  );
}
