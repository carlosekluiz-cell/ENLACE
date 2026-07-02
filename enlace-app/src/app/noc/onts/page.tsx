"use client";

// /noc/onts — the ONT fleet table, from the server-side NOC projection of
// the persisted audit. Filter by status (Unknown included as a first-class
// filter), search, rx-power coloring.

import { RoleGuard } from "@/lib/auth";
import type { NocProjection } from "@/lib/opsTypes";
import { useProjection } from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import ImportReportBanner from "@/components/ImportReportBanner";
import NoAuditState from "@/components/NoAuditState";
import OntTable from "@/components/OntTable";

function OntFleet() {
  const { data, unavailable, meta, loading, error } =
    useProjection<NocProjection>("noc");

  return (
    <AppShell title="ONT Fleet" meta={meta}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading NOC projection…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      {unavailable && <NoAuditState reason={unavailable.reason} />}
      {data && (
        <>
          <ImportReportBanner report={data.import_report ?? undefined} />
          <OntTable onts={data.onts} />
        </>
      )}
    </AppShell>
  );
}

export default function OntsPage() {
  return (
    <RoleGuard minRole="analyst">
      <OntFleet />
    </RoleGuard>
  );
}
