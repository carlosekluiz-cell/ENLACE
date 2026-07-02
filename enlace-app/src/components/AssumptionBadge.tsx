"use client";

// Honesty rule 1: every estimated_* figure renders next to one of these.
// Hover/tap reveals the declared assumptions that produced the number.

import { useState } from "react";
import { Info } from "lucide-react";

export default function AssumptionBadge({
  assumptions,
}: {
  assumptions: string[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest cursor-pointer"
        style={{
          border: "1px dashed var(--status-warn)",
          color: "var(--status-warn)",
        }}
        aria-label="This figure is an estimate based on declared assumptions"
      >
        <Info size={10} />
        estimate
      </button>
      {open && (
        <span
          className="absolute z-20 top-full right-0 mt-1 w-72 p-3 text-left"
          style={{
            backgroundColor: "var(--bg-dark-subtle)",
            border: "1px solid var(--border-dark-strong)",
          }}
        >
          <span className="op-label block mb-2">Assumptions behind this figure</span>
          {assumptions.length === 0 ? (
            <span
              className="block text-xs"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              No assumptions declared by the agent for this figure.
            </span>
          ) : (
            assumptions.map((a) => (
              <span
                key={a}
                className="block text-xs leading-relaxed"
                style={{ color: "var(--text-on-dark-secondary)" }}
              >
                • {a}
              </span>
            ))
          )}
        </span>
      )}
    </span>
  );
}
