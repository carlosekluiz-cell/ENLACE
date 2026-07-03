"use client";

import { useState } from "react";
import type { AuditResult } from "@/lib/audit-types";
import HealthScore from "@/components/report/HealthScore";
import FindingsSidebar from "@/components/report/FindingsSidebar";
import OntTable from "@/components/report/OntTable";
import { useI18n } from "@/lib/i18n";

interface ReportExplorerProps {
  result: AuditResult;
}

// Read-only, interactive showcase of a single audit result.
// Wires the report components together with local filter state.
// No network calls — the data is bundled in by the caller.
export default function ReportExplorer({ result }: ReportExplorerProps) {
  const { t } = useI18n();
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const faultsCount = result.faults.length;
  const degradingCount = result.churn_risk.length;
  const ghostsCount = result.ghosts.length;
  const ponAtCapacityCount = result.capacity.filter(
    (c) => c.utilisation_pct >= 80
  ).length;

  const issueSerials = new Set<string>();
  for (const f of result.faults) {
    for (const a of f.affected_onts ?? []) issueSerials.add(a.serial_number);
  }
  for (const g of result.ghosts) issueSerials.add(g.ont_serial);
  for (const c of result.churn_risk) issueSerials.add(c.ont_serial);
  for (const f of result.flapping) {
    if (f.ont_serial) issueSerials.add(f.ont_serial);
  }
  for (const r of result.reflectance) {
    if (r.ont_serial) issueSerials.add(r.ont_serial);
  }
  for (const o of result.optical_budget) {
    // Only marginal/critical budgets are issues; "Excellent" is a pass.
    if (o.budget_status !== "Excellent" && o.budget_status !== "Good") {
      issueSerials.add(o.ont_serial);
    }
  }
  for (const r of result.rogue ?? []) {
    for (const c of r.candidates) issueSerials.add(c.serial_number);
  }
  const healthyCount = result.onts.filter(
    (ont) => !issueSerials.has(ont.serial_number)
  ).length;

  // Coverage honesty: what the engine analysed vs what the data allowed.
  const fec = result.fec_health;
  const laser = result.laser_health;
  const rogueCount = result.rogue?.length ?? 0;

  return (
    <div
      className="flex flex-col"
      style={{
        border: "1px solid var(--border-dark-strong)",
        backgroundColor: "var(--bg-dark)",
      }}
    >
      <HealthScore
        summary={result.summary}
        faultsCount={faultsCount}
        degradingCount={degradingCount}
        ghostsCount={ghostsCount}
        ponAtCapacityCount={ponAtCapacityCount}
        healthyCount={healthyCount}
      />

      <div className="flex flex-col md:flex-row gap-4 p-4">
        <FindingsSidebar
          result={result}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
        />
        <OntTable result={result} filter={activeFilter} />
      </div>

      {/* Coverage & honesty — what was analysed vs what the data allowed */}
      {(fec || laser || result.rogue) && (
        <div
          className="px-4 pb-4"
          style={{ borderTop: "1px solid var(--border-dark-strong)" }}
        >
          <p
            className="font-mono text-xs uppercase tracking-widest mt-4 mb-3"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            {t("report.cover.title")}
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {fec && (
              <div
                className="p-3"
                style={{
                  backgroundColor: "var(--bg-dark-surface)",
                  border: "1px solid var(--border-dark-strong)",
                }}
              >
                <p
                  className="font-mono text-xs font-semibold mb-1"
                  style={{ color: "var(--text-on-dark)" }}
                >
                  {t("report.cover.fec", {
                    a: fec.onts_with_fec_data,
                    b: fec.total_onts,
                  })}
                </p>
                <p
                  className="font-mono text-xs leading-relaxed"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {fec.coverage_note}
                </p>
              </div>
            )}
            {laser && (
              <div
                className="p-3"
                style={{
                  backgroundColor: "var(--bg-dark-surface)",
                  border: "1px solid var(--border-dark-strong)",
                }}
              >
                <p
                  className="font-mono text-xs font-semibold mb-1"
                  style={{ color: "var(--text-on-dark)" }}
                >
                  {t("report.cover.laser", {
                    a: laser.coverage.onts_with_bias,
                    b: laser.coverage.onts_total,
                  })}
                </p>
                <p
                  className="font-mono text-xs leading-relaxed"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {laser.coverage.onts_with_bias === 0
                    ? t("report.cover.laser.none")
                    : t("report.cover.laser.some", {
                        analyzed: laser.coverage.onts_analyzed,
                        flagged: laser.coverage.onts_flagged,
                        detrended: laser.coverage.onts_temperature_detrended,
                      })}
                </p>
              </div>
            )}
            {result.rogue && (
              <div
                className="p-3"
                style={{
                  backgroundColor: "var(--bg-dark-surface)",
                  border: "1px solid var(--border-dark-strong)",
                }}
              >
                <p
                  className="font-mono text-xs font-semibold mb-1"
                  style={{ color: "var(--text-on-dark)" }}
                >
                  {t(
                    rogueCount === 1
                      ? "report.cover.rogue.one"
                      : "report.cover.rogue",
                    { n: rogueCount }
                  )}
                </p>
                <p
                  className="font-mono text-xs leading-relaxed"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {t("report.cover.rogue.intro")}
                  {rogueCount === 0
                    ? t("report.cover.rogue.none")
                    : t("report.cover.rogue.some")}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
