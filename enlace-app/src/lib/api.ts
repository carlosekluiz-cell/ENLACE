// ── Client data helpers ──
//
// Wave B: views no longer resolve "current audit" from localStorage or from
// a bundled demo import — they call the server-side persona projection
// endpoints (/api/projections/*), which read the PERSISTED audit row for the
// tenant (see src/lib/useOps.ts). This module keeps the small shared pieces:
// the provenance vocabulary, the demo-fixture provenance record, the CSV
// upload helper, and the live-feed status fetch.
//
// Provenance is part of the data: every view renders the SourceBadge, and if
// the live feed is unavailable the UI says so — it never fakes liveness.

import type { AuditResult, NocSummaryResponse } from "@/lib/types";

export type DataSource = "live" | "audit" | "demo";

/** Exact command that produced src/demo/audit-demo.json (real agent output). */
export const DEMO_PROVENANCE = {
  command:
    "cargo run --manifest-path pulso-agent/Cargo.toml -- --audit-csv enlace-telemetry/samples/community_fibre_adtran_sdx6320.csv",
  sample: "enlace-telemetry/samples/community_fibre_adtran_sdx6320.csv",
  generatedAt: "2026-07-02",
} as const;

/** Honest live-feed status from the server route — never assumed. */
export async function fetchNocSummary(): Promise<NocSummaryResponse> {
  try {
    const res = await fetch("/api/noc/summary");
    if (!res.ok) {
      return { available: false, reason: `summary route returned ${res.status}` };
    }
    return (await res.json()) as NocSummaryResponse;
  } catch {
    return { available: false, reason: "app server unreachable" };
  }
}

/**
 * Upload a CSV to the agent through the server-side proxy. The route
 * persists the result in the app DB (system of record) — every colleague's
 * audit list picks it up; nothing is remembered browser-locally anymore.
 */
export async function uploadAuditCsv(
  file: File,
): Promise<{ audit_id: string; result: AuditResult }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/audit", { method: "POST", body: form });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new Error(body?.error ?? `upload failed (${res.status})`);
  }
  return (await res.json()) as { audit_id: string; result: AuditResult };
}
