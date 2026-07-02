"use client";

// Ticket lifecycle status pill: open → acked → dispatched → closed.

import type { TicketStatus } from "@/lib/opsTypes";

export function ticketStatusColor(status: TicketStatus): string {
  switch (status) {
    case "open":
      return "var(--status-warn)";
    case "acked":
      return "var(--accent)";
    case "dispatched":
      return "var(--status-unknown)";
    case "closed":
      return "var(--status-online)";
  }
}

export default function TicketStatusPill({ status }: { status: TicketStatus }) {
  const color = ticketStatusColor(status);
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider"
      style={{ color, border: `1px solid ${color}` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      {status}
    </span>
  );
}
