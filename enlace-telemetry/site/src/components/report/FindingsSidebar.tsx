"use client";

import type { AuditResult } from "@/lib/audit-types";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
  const categories: FindingCategory[] = [];

  if (result.faults.length > 0) {
    const byType: Record<string, number> = {};
    for (const f of result.faults) {
      const ft = f.fault_type || "unknown";
      byType[ft] = (byType[ft] || 0) + 1;
    }
    // Fault-type tokens come straight from the engine output — kept verbatim.
    const sub = Object.entries(byType)
      .map(([ft, c]) => `${c} ${ft}`)
      .join(", ");
    categories.push({
      key: "faults",
      label: t("report.cat.faults"),
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
      label: t("report.cat.churn"),
      count: result.churn_risk.length,
      severity: "warning",
      subtitle:
        severe > 0
          ? t("report.sub.severe", { n: severe })
          : t("report.sub.monitoring"),
    });
  }

  if (result.ghosts.length > 0) {
    categories.push({
      key: "ghosts",
      label: t("report.cat.ghosts"),
      count: result.ghosts.length,
      severity: "warning",
      subtitle: t("report.sub.ghosts"),
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
      label: t("report.cat.capacity"),
      count: alerting.length > 0 ? alerting.length : result.capacity.length,
      severity:
        critical > 0 ? "critical" : alerting.length > 0 ? "warning" : "info",
      subtitle:
        alerting.length > 0
          ? t(
              alerting.length === 1
                ? "report.sub.capacity.alerting.one"
                : "report.sub.capacity.alerting",
              { n: alerting.length }
            )
          : t("report.sub.capacity.tracked", {
              n: result.capacity.length,
              peak: maxUtil.toFixed(0),
            }),
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
        label: t("report.cat.sfp"),
        count: trending.length,
        severity: critical > 0 ? "critical" : "warning",
        subtitle: t("report.sub.sfp"),
      });
    }
  }

  if ((result.rogue?.length ?? 0) > 0) {
    categories.push({
      key: "rogue",
      label: t("report.cat.rogue"),
      count: result.rogue!.length,
      severity: "critical",
      subtitle: t("report.sub.rogue"),
    });
  }

  if (result.tickets.length > 0) {
    categories.push({
      key: "tickets",
      label: t("report.cat.tickets"),
      count: result.tickets.length,
      severity: "info",
      // Priority + fault-type tokens come straight from the engine output.
      subtitle: result.tickets
        .map((tk) => `${tk.priority} ${tk.fault_type}`)
        .join(", "),
    });
  }

  if (result.flapping.length > 0) {
    categories.push({
      key: "flapping",
      label: t("report.cat.flapping"),
      count: result.flapping.length,
      severity: "warning",
      subtitle: t("report.sub.flapping"),
    });
  }

  if (result.weather_correlation.length > 0) {
    categories.push({
      key: "weather_correlation",
      label: t("report.cat.weather"),
      count: result.weather_correlation.length,
      severity: "info",
      subtitle: t("report.sub.weather"),
    });
  }

  if (result.reflectance.length > 0) {
    categories.push({
      key: "reflectance",
      label: t("report.cat.reflectance"),
      count: result.reflectance.length,
      severity: "warning",
      subtitle: t("report.sub.reflectance"),
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
        label: t("report.cat.optical"),
        count: lowMargin.length,
        severity: "warning",
        subtitle: t("report.sub.optical", { n: result.optical_budget.length }),
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
        {t("report.findings")}
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
          {t("report.clearFilter")}
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
              {t("report.noFindings")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
