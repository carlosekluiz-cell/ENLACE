"use client";

import type { ReactNode } from "react";

export default function StatCard({
  label,
  value,
  color,
  sub,
  badge,
}: {
  label: string;
  value: ReactNode;
  color?: string;
  sub?: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <div className="op-card px-4 py-3 flex flex-col gap-1 min-w-[120px]">
      <div className="flex items-center justify-between gap-2">
        <span className="op-label">{label}</span>
        {badge}
      </div>
      <span
        className="font-mono text-2xl font-bold"
        style={{ color: color ?? "var(--text-on-dark)" }}
      >
        {value}
      </span>
      {sub && (
        <span className="text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
          {sub}
        </span>
      )}
    </div>
  );
}
