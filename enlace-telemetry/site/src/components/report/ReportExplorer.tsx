"use client";

import { useState } from "react";
import type { AuditResult } from "@/lib/audit-types";
import HealthScore from "@/components/report/HealthScore";
import FindingsSidebar from "@/components/report/FindingsSidebar";
import OntTable from "@/components/report/OntTable";

interface ReportExplorerProps {
  result: AuditResult;
}

// Read-only, interactive showcase of a single audit result.
// Wires the report components together with local filter state.
// No network calls — the data is bundled in by the caller.
export default function ReportExplorer({ result }: ReportExplorerProps) {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const faultsCount = result.faults.length;
  const degradingCount = result.churn_risk.length;
  const ghostsCount = result.ghosts.length;
  const ponAtCapacityCount = result.capacity.filter(
    (c) => c.utilisation_pct >= 80
  ).length;

  const issueSerials = new Set<string>();
  for (const f of result.faults) {
    if (f.affected_onts) {
      for (const s of f.affected_onts) issueSerials.add(s);
    }
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
    if (o.ont_serial) issueSerials.add(o.ont_serial);
  }
  const healthyCount = result.onts.filter(
    (ont) => !issueSerials.has(ont.serial_number)
  ).length;

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
    </div>
  );
}
