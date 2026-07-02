"use client";

// Audit picker — replaces the localStorage last-audit-id hack. "Current
// audit" resolves from the tenant-scoped listing: most recent by default,
// any persisted audit selectable. Each option carries date + source badge +
// health score so provenance is visible before you even switch.

import { fmtDate } from "@/lib/format";
import { setSelectedAudit, useAuditList, useOpsSnapshot } from "@/lib/useOps";

export default function AuditPicker() {
  const { audits, loading } = useAuditList();
  const { selectedAuditId } = useOpsSnapshot();

  if (loading || audits.length === 0) return null;

  const current = selectedAuditId ?? audits[0].id;

  return (
    <select
      value={current}
      onChange={(e) => setSelectedAudit(e.target.value)}
      className="bg-transparent font-mono text-[11px] px-2 py-1 cursor-pointer max-w-[280px]"
      style={{
        color: "var(--text-on-dark-secondary)",
        border: "1px solid var(--border-dark-strong)",
      }}
      aria-label="Select audit"
      title="Persisted audits for this tenant — most recent is the default"
    >
      {audits.map((a) => (
        <option key={a.id} value={a.id} style={{ color: "black" }}>
          {fmtDate(a.created_at)} · {a.source.toUpperCase()} · health{" "}
          {a.summary ? a.summary.health_score : "—"}
        </option>
      ))}
    </select>
  );
}
