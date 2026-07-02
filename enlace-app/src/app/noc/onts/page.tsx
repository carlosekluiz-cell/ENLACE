"use client";

// /noc/onts — the ONT fleet table. Filter by status (Unknown included as a
// first-class filter), search, rx-power coloring.

import { RoleGuard } from "@/lib/auth";
import { useAuditFeed } from "@/lib/useAuditFeed";
import AppShell from "@/components/AppShell";
import ImportReportBanner from "@/components/ImportReportBanner";
import OntTable from "@/components/OntTable";

function OntFleet() {
  const { feed, loading, error } = useAuditFeed();

  return (
    <AppShell title="ONT Fleet" feed={feed}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading audit feed…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      {feed && (
        <>
          <ImportReportBanner report={feed.audit.import_report} />
          <OntTable onts={feed.audit.onts} />
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
