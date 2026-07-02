"use client";

import type { AuditSummary } from "@/lib/audit-types";

interface HealthScoreProps {
  summary: AuditSummary;
  faultsCount: number;
  degradingCount: number;
  ghostsCount: number;
  ponAtCapacityCount: number;
  healthyCount: number;
}

function scoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

function scoreLabel(score: number): string {
  if (score >= 80) return "HEALTHY";
  if (score >= 50) return "NEEDS ATTENTION";
  return "CRITICAL";
}

export default function HealthScore({
  summary,
  faultsCount,
  degradingCount,
  ghostsCount,
  ponAtCapacityCount,
  healthyCount,
}: HealthScoreProps) {
  const color = scoreColor(summary.health_score);

  const stats = [
    {
      value: faultsCount,
      label: "Faults",
      color: faultsCount > 0 ? "#ef4444" : "var(--text-on-dark-muted)",
    },
    {
      value: degradingCount,
      label: "Degrading",
      color: degradingCount > 0 ? "#f59e0b" : "var(--text-on-dark-muted)",
    },
    {
      value: ghostsCount,
      label: "Ghost ONTs",
      color: ghostsCount > 0 ? "#f59e0b" : "var(--text-on-dark-muted)",
    },
    {
      value: ponAtCapacityCount,
      label: "PON 80%+",
      color: ponAtCapacityCount > 0 ? "var(--accent)" : "var(--text-on-dark-muted)",
    },
    {
      value: healthyCount,
      label: "Healthy",
      color: healthyCount > 0 ? "#22c55e" : "var(--text-on-dark-muted)",
    },
    {
      value: `${summary.avg_rx_dbm.toFixed(1)}`,
      label: "Avg Rx dBm",
      color: "var(--text-on-dark-secondary)",
    },
  ];

  return (
    <div
      className="w-full p-6"
      style={{
        backgroundColor: "var(--bg-dark-surface)",
        borderBottom: "1px solid var(--border-dark-strong)",
      }}
    >
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        {/* Left: score */}
        <div className="flex items-center gap-5">
          <div
            className="flex items-center justify-center w-20 h-20"
            style={{ border: `3px solid ${color}` }}
          >
            <span
              className="font-mono text-4xl font-bold"
              style={{ color }}
            >
              {summary.health_score}
            </span>
          </div>
          <div>
            <p
              className="font-mono text-xs uppercase tracking-widest mb-1"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              Fleet Health Score
            </p>
            <p
              className="font-mono text-sm font-semibold uppercase tracking-wider"
              style={{ color }}
            >
              {scoreLabel(summary.health_score)}
            </p>
          </div>
        </div>

        {/* Right: stat boxes */}
        <div className="flex flex-wrap gap-3">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col items-center px-4 py-3 min-w-[80px]"
              style={{
                backgroundColor: "var(--bg-dark-subtle)",
              }}
            >
              <span
                className="font-mono text-xl font-bold"
                style={{ color: stat.color }}
              >
                {stat.value}
              </span>
              <span
                className="font-mono text-[10px] uppercase tracking-widest mt-1"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
