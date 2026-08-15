"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

function getSnapshot(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getServerSnapshot(): Theme | null {
  return null;
}

function subscribe(callback: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributeFilter: ["data-theme"], attributes: true });
  media.addEventListener("change", callback);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", callback);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  if (theme === null) {
    return <button aria-label="Ganti tema" className="theme-toggle" disabled type="button" />;
  }

  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      aria-label={`Ganti ke tema ${next === "dark" ? "gelap" : "terang"}`}
      className="theme-toggle"
      onClick={() => {
        document.documentElement.setAttribute("data-theme", next);
        try {
          localStorage.setItem(STORAGE_KEY, next);
        } catch {
          // localStorage unavailable (private browsing) — theme still applies for this session
        }
      }}
      type="button"
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
