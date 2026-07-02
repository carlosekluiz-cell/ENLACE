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
    const severe = result.churn_risk.filter(
      (c) => c.impact === "Severe" || c.estimated_churn_probability_90day > 0.3
    ).length;
    categories.push({
      key: "churn_risk",
      label: "Churn Risk",
      count: result.churn_risk.length,
      severity: "warning",
      subtitle: severe > 0 ? `${severe} severe (assumed model)` : "monitoring",
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
    const alerting = result.capacity.filter((c) => c.alert_level !== "Ok");
    const critical = alerting.filter(
      (c) => c.alert_level === "Critical"
    ).length;
    const maxUtil = Math.max(...result.capacity.map((c) => c.utilisation_pct));
    categories.push({
      key: "capacity",
      label: "PON Capacity",
      count: alerting.length > 0 ? alerting.length : result.capacity.length,
      severity:
        critical > 0 ? "critical" : alerting.length > 0 ? "warning" : "info",
      subtitle:
        alerting.length > 0
          ? `${alerting.length} port${alerting.length === 1 ? "" : "s"} alerting`
          : `${result.capacity.length} ports tracked · peak ${maxUtil.toFixed(0)}%`,
    });
  }

  {
    const trending = result.sfp_health.filter(
      (s) => s.severity !== "Healthy" && s.severity !== "Ok"
    );
    if (trending.length > 0) {
      const critical = trending.filter(
        (s) => s.severity === "Critical"
      ).length;
      categories.push({
        key: "sfp_health",
        label: "PON-wide Trend",
        count: trending.length,
        severity: critical > 0 ? "critical" : "warning",
        subtitle: "shared-plant degradation",
      });
    }
  }

  if ((result.rogue?.length ?? 0) > 0) {
    categories.push({
      key: "rogue",
      label: "Rogue ONT Suspects",
      count: result.rogue!.length,
      severity: "critical",
      subtitle: "needs vendor confirmation",
    });
  }

  if (result.tickets.length > 0) {
    categories.push({
      key: "tickets",
      label: "Tickets Raised",
      count: result.tickets.length,
      severity: "info",
      subtitle: result.tickets
        .map((t) => `${t.priority} ${t.fault_type}`)
        .join(", "),
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

  {
    // Only marginal/critical budgets are findings; "Excellent" is a pass.
    const lowMargin = result.optical_budget.filter(
      (o) => o.budget_status !== "Excellent" && o.budget_status !== "Good"
    );
    if (lowMargin.length > 0) {
      categories.push({
        key: "optical_budget",
        label: "Optical Budget",
        count: lowMargin.length,
        severity: "warning",
        subtitle: `of ${result.optical_budget.length} links assessed`,
      });
    }
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
