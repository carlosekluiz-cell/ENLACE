"use client";

import type { AuditResult } from "@/lib/audit-types";

interface FindingsSidebarProps {
  result: AuditResult;
  activeFilter: string | null;
  onFilterChange: (filter: string | null) => void;
}

interface FindingCategory {
  key: string;
  label: string;
  count: number;
  severity: "critical" | "warning" | "info";
  subtitle: string;
}

function barColor(severity: "critical" | "warning" | "info"): string {
  if (severity === "critical") return "#ef4444";
  if (severity === "warning") return "#f59e0b";
  return "var(--text-on-dark-muted)";
}

export default function FindingsSidebar({
  result,
  activeFilter,
  onFilterChange,
}: FindingsSidebarProps) {
  const categories: FindingCategory[] = [];

  if (result.faults.length > 0) {
    const byType: Record<string, number> = {};
    for (const f of result.faults) {
      const t = f.fault_type || "unknown";
      byType[t] = (byType[t] || 0) + 1;
    }
    const sub = Object.entries(byType)
      .map(([t, c]) => `${c} ${t}`)
      .join(", ");
    categories.push({
      key: "faults",
      label: "Fault Events",
      count: result.faults.length,
      severity: "critical",
      subtitle: sub,
    });
  }

  if (result.churn_risk.length > 0) {
    const high = result.churn_risk.filter(
      (c) => c.churn_probability_90day > 0.5
    ).length;
    categories.push({
      key: "churn_risk",
      label: "Signal Degrading",
      count: result.churn_risk.length,
      severity: "warning",
      subtitle: high > 0 ? `${high} high risk` : "monitoring",
    });
  }

  if (result.ghosts.length > 0) {
    categories.push({
      key: "ghosts",
      label: "Ghost Customers",
      count: result.ghosts.length,
      severity: "warning",
      subtitle: `revenue leakage detected`,
    });
  }

  if (result.capacity.length > 0) {
    const critical = result.capacity.filter(
      (c) => c.utilisation_pct >= 90
    ).length;
    const warning = result.capacity.filter(
      (c) => c.utilisation_pct >= 80 && c.utilisation_pct < 90
    ).length;
    const parts: string[] = [];
    if (critical > 0) parts.push(`${critical} critical`);
    if (warning > 0) parts.push(`${warning} warning`);
    categories.push({
      key: "capacity",
      label: "PON Capacity",
      count: result.capacity.length,
      severity: critical > 0 ? "critical" : "warning",
      subtitle: parts.join(", ") || "at capacity",
    });
  }

  if (result.flapping.length > 0) {
    categories.push({
      key: "flapping",
      label: "Flapping ONTs",
      count: result.flapping.length,
      severity: "warning",
      subtitle: "unstable connections",
    });
  }

  if (result.weather_correlation.length > 0) {
    categories.push({
      key: "weather_correlation",
      label: "Weather Correlation",
      count: result.weather_correlation.length,
      severity: "info",
      subtitle: "environment-linked faults",
    });
  }

  if (result.reflectance.length > 0) {
    categories.push({
      key: "reflectance",
      label: "Reflectance",
      count: result.reflectance.length,
      severity: "warning",
      subtitle: "connector issues",
    });
  }

  if (result.optical_budget.length > 0) {
    categories.push({
      key: "optical_budget",
      label: "Optical Budget",
      count: result.optical_budget.length,
      severity: "warning",
      subtitle: "low margin links",
    });
  }

  return (
    <div
      className="w-full md:w-[300px] shrink-0 overflow-y-auto"
      style={{ maxHeight: "calc(100vh - 14rem)" }}
    >
      <p
        className="font-mono text-xs uppercase tracking-widest mb-3 px-1"
        style={{ color: "var(--text-on-dark-muted)" }}
      >
        Findings
      </p>

      {/* Clear filter */}
      {activeFilter && (
        <button
          onClick={() => onFilterChange(null)}
          className="w-full text-left mb-2 px-3 py-2 font-mono text-xs"
          style={{
            backgroundColor: "var(--bg-dark-subtle)",
            color: "var(--accent)",
            border: "1px solid var(--accent)",
          }}
        >
          Clear filter
        </button>
      )}

      <div className="flex flex-col gap-2">
        {categories.map((cat) => {
          const isActive = activeFilter === cat.key;
          return (
            <button
              key={cat.key}
              onClick={() => onFilterChange(isActive ? null : cat.key)}
              className="w-full text-left flex gap-0 transition-colors duration-150"
              style={{
                backgroundColor: isActive
                  ? "var(--bg-dark-subtle)"
                  : "var(--bg-dark-surface)",
                border: `1px solid ${isActive ? "var(--accent)" : "var(--border-dark-strong)"}`,
              }}
            >
              {/* Colored bar */}
              <div
                className="w-[3px] shrink-0"
                style={{ backgroundColor: barColor(cat.severity) }}
              />
              <div className="flex-1 px-3 py-3">
                <div className="flex items-center justify-between mb-1">
                  <span
                    className="font-mono text-sm font-semibold"
                    style={{ color: "var(--text-on-dark)" }}
                  >
                    {cat.label}
                  </span>
                  <span
                    className="font-mono text-sm font-bold"
                    style={{ color: barColor(cat.severity) }}
                  >
                    {cat.count}
                  </span>
                </div>
                <p
                  className="font-mono text-xs"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {cat.subtitle}
                </p>
              </div>
            </button>
          );
        })}

        {categories.length === 0 && (
          <div className="px-3 py-6 text-center">
            <p
              className="font-mono text-sm"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              No findings
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
