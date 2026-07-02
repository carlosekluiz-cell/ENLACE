// ── Display helpers ──
// Honesty rules live here too: null renders as "—" (missing is missing),
// and Unknown status has its own color, never Offline's red.

import type { OntStatus } from "@/lib/types";

/** Missing values render as an em-dash, never as 0. */
export function dash<T>(value: T | null | undefined, fmt: (v: T) => string): string {
  return value === null || value === undefined ? "—" : fmt(value);
}

export function fmtDbm(v: number | null | undefined): string {
  return dash(v, (n) => `${n.toFixed(1)} dBm`);
}

/** Rx power severity color (thresholds mirror diagnostics: -28 crit, -25 low). */
export function rxColor(rx: number | null | undefined): string {
  if (rx === null || rx === undefined) return "var(--text-on-dark-muted)";
  if (rx <= -28) return "var(--status-offline)";
  if (rx <= -25) return "var(--status-warn)";
  return "var(--status-online)";
}

/** Status colors. Unknown is violet — its own state, never lumped with red. */
export function statusColor(status: OntStatus | string): string {
  switch (status) {
    case "Online":
      return "var(--status-online)";
    case "LowSignal":
    case "Dying":
      return "var(--status-warn)";
    case "Offline":
    case "PowerFail":
    case "FiberCut":
      return "var(--status-offline)";
    case "Unknown":
    default:
      return "var(--status-unknown)";
  }
}

export function severityColor(severity: string): string {
  const s = severity.toLowerCase();
  if (s.includes("critical") || s === "red" || s === "p1") return "var(--status-offline)";
  if (s.includes("warn") || s === "yellow" || s === "p2") return "var(--status-warn)";
  if (s.includes("healthy") || s === "green" || s === "ok") return "var(--status-online)";
  return "var(--text-on-dark-muted)";
}

/** Currency for ARPU-based estimates. The agent's ARPU is unit-agnostic. */
export function fmtMoney(v: number): string {
  return v.toLocaleString("en-GB", { maximumFractionDigits: 0 });
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

/** SLA due date = generated_at + sla_days. */
export function slaDue(generatedAt: string, slaDays: number): Date {
  const d = new Date(generatedAt);
  d.setDate(d.getDate() + slaDays);
  return d;
}

export function daysUntil(date: Date): number {
  return Math.ceil((date.getTime() - Date.now()) / 86_400_000);
}
