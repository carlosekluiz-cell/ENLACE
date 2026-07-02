// ── Data layer: one interface, two adapters ──
//
// LiveAdapter  — talks to Next server routes (/api/audit, /api/audit/[id],
//                /api/noc/summary). Those routes inject the pulso-agent
//                bearer token / ES credentials server-side; the browser
//                never sees a secret.
// DemoAdapter  — bundled AuditResult produced by ACTUALLY RUNNING the agent
//                (see DEMO_PROVENANCE). Not handwritten, not massaged.
//
// Provenance is part of the data: every feed carries `source`, and the UI
// must render it (SourceBadge). If the live feed is unavailable the UI says
// so — it never fakes liveness.

import type { AuditResult, NocSummaryResponse } from "@/lib/types";
import demoAuditJson from "@/demo/audit-demo.json";

export type DataSource = "live" | "audit" | "demo";

export interface AuditFeed {
  source: DataSource;
  audit: AuditResult;
  /** Agent-assigned id when the audit came through POST /audit. */
  auditId: string | null;
  /** Live Elasticsearch feed status — honest availability, never assumed. */
  live: NocSummaryResponse;
  fetchedAt: string;
}

export interface DataAdapter {
  /** Resolve an audit feed, or null when this adapter has nothing. */
  load(): Promise<AuditFeed | null>;
}

/** Exact command that produced src/demo/audit-demo.json. */
export const DEMO_PROVENANCE = {
  command:
    "cargo run --manifest-path pulso-agent/Cargo.toml -- --audit-csv enlace-telemetry/samples/community_fibre_adtran_sdx6320.csv",
  sample: "enlace-telemetry/samples/community_fibre_adtran_sdx6320.csv",
  generatedAt: "2026-07-02",
} as const;

const LAST_AUDIT_KEY = "enlace.last_audit_id";

const LIVE_NOT_CHECKED: NocSummaryResponse = {
  available: false,
  reason: "live feed not checked in demo mode",
};

export class DemoAdapter implements DataAdapter {
  async load(): Promise<AuditFeed> {
    return {
      source: "demo",
      audit: demoAuditJson as unknown as AuditResult,
      auditId: null,
      live: LIVE_NOT_CHECKED,
      fetchedAt: new Date().toISOString(),
    };
  }
}

export class LiveAdapter implements DataAdapter {
  async load(): Promise<AuditFeed | null> {
    const live = await this.nocSummary();

    // An earlier upload through POST /api/audit leaves its id behind; the
    // agent retains results for a TTL (default 1 h).
    const auditId =
      typeof window !== "undefined"
        ? window.localStorage.getItem(LAST_AUDIT_KEY)
        : null;

    if (auditId) {
      try {
        const res = await fetch(`/api/audit/${encodeURIComponent(auditId)}`);
        if (res.ok) {
          const body = (await res.json()) as { audit_id: string; result: AuditResult };
          return {
            source: live.available ? "live" : "audit",
            audit: body.result,
            auditId: body.audit_id,
            live,
            fetchedAt: new Date().toISOString(),
          };
        }
        if (res.status === 404) {
          // expired from the agent's result store — forget it
          window.localStorage.removeItem(LAST_AUDIT_KEY);
        }
      } catch {
        // audit server unreachable — fall through to null
      }
    }
    return null;
  }

  async nocSummary(): Promise<NocSummaryResponse> {
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
}

/**
 * Upload a CSV to the agent through the server-side proxy. On success the
 * audit id is remembered so LiveAdapter serves the real upload next load.
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
  const body = (await res.json()) as { audit_id: string; result: AuditResult };
  window.localStorage.setItem(LAST_AUDIT_KEY, body.audit_id);
  return body;
}

/** Live first, demo fallback — the source field says which one you got. */
export async function loadAuditFeed(): Promise<AuditFeed> {
  const liveAdapter = new LiveAdapter();
  const fromLive = await liveAdapter.load();
  if (fromLive) return fromLive;

  const demo = await new DemoAdapter().load();
  // Even in demo mode, report the real live-feed status so the UI can say
  // "live feed not connected — showing audit data" with the actual reason.
  demo.live = await liveAdapter.nocSummary();
  return demo;
}
