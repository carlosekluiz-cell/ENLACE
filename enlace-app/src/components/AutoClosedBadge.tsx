"use client";

// Badge for system-actored closes (P88): the ticket was closed by the
// agent-events hook after telemetry confirmed FULL recovery of its ONTs —
// closed_by is null and state.closed_by_system is true. Render only then.

export default function AutoClosedBadge() {
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider"
      style={{
        border: "1px dashed var(--status-online)",
        color: "var(--status-online)",
      }}
      title="Closed automatically: the agent's resolve event covered every ONT on this ticket"
    >
      auto-closed by telemetry
    </span>
  );
}
