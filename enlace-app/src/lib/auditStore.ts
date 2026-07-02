// ── Server-side audit persistence helpers ──
//
// The audits row is the system of record (agent's TTL store is a cache).
// result_json is stored and returned VERBATIM — these helpers parse it only
// to EXTRACT (list summaries, projections); they never mutate or re-store it.
// Provenance (source/uploader/agent_version) is read from the row, per
// ARCHITECTURE-TENANCY.md §3.1.2.
//
// Server-only: imports the DB. Never import from client components.

import { randomUUID } from "node:crypto";
import { and, desc, eq, or } from "drizzle-orm";
import { db, tables } from "@/db";
import demoAuditJson from "@/demo/audit-demo.json";
import { DEMO_PROVENANCE } from "@/lib/api";
import type { AuditResult } from "@/lib/types";
import type {
  AuditListEntry,
  AuditListSummary,
  AuditProvenance,
} from "@/lib/opsTypes";

export interface AuditRow {
  id: string;
  tenantId: string;
  auditId: string;
  source: "live" | "audit" | "demo";
  uploaderUserId: string | null;
  agentVersion: string | null;
  createdAt: string;
  resultJson: string;
}

/** Stable agent-side id for the bundled demo fixture (idempotent insert). */
export const DEMO_AUDIT_ID = `demo-fixture-${DEMO_PROVENANCE.generatedAt}`;

function uploaderName(userId: string | null): string | null {
  if (!userId) return null;
  const rows = db
    .select({ name: tables.users.name })
    .from(tables.users)
    .where(eq(tables.users.id, userId))
    .all();
  return rows[0]?.name ?? null;
}

export function provenanceOf(row: AuditRow): AuditProvenance {
  return {
    id: row.id,
    audit_id: row.auditId,
    source: row.source,
    uploader_name: uploaderName(row.uploaderUserId),
    agent_version: row.agentVersion,
    created_at: row.createdAt,
  };
}

/** Parse the stored JSON. Null on failure — an integrity error, surfaced honestly. */
export function parseResult(row: AuditRow): AuditResult | null {
  try {
    return JSON.parse(row.resultJson) as AuditResult;
  } catch {
    console.error(`[auditStore] audits row ${row.id} has unparseable result_json`);
    return null;
  }
}

/** Small extract for listings — read-only over the verbatim JSON. */
export function extractListSummary(result: AuditResult | null): AuditListSummary | null {
  if (!result) return null;
  const s = result.summary;
  const findingCount =
    (result.ghosts?.length ?? 0) +
    (result.flapping?.length ?? 0) +
    (result.reflectance?.length ?? 0) +
    (result.fec_health?.findings?.length ?? 0) +
    (result.laser_health?.predictions?.length ?? 0) +
    (result.rogue?.length ?? 0) +
    (result.churn_risk?.length ?? 0);
  return {
    health_score: s.health_score,
    total_onts: s.total_onts,
    online: s.online,
    offline: s.offline,
    unknown: s.unknown,
    fault_count: result.faults?.length ?? 0,
    ticket_count: result.tickets?.length ?? 0,
    finding_count: findingCount,
  };
}

/** Tenant-scoped listing, newest first. */
export function listAudits(tenantId: string): AuditListEntry[] {
  const rows = db
    .select()
    .from(tables.audits)
    .where(eq(tables.audits.tenantId, tenantId))
    .orderBy(desc(tables.audits.createdAt))
    .all() as AuditRow[];
  return rows.map((row) => ({
    ...provenanceOf(row),
    summary: extractListSummary(parseResult(row)),
  }));
}

/** Find by row id OR agent audit_id — always tenant-scoped. */
export function findAuditRow(tenantId: string, idOrAuditId: string): AuditRow | null {
  const rows = db
    .select()
    .from(tables.audits)
    .where(
      and(
        eq(tables.audits.tenantId, tenantId),
        or(
          eq(tables.audits.id, idOrAuditId),
          eq(tables.audits.auditId, idOrAuditId),
        ),
      ),
    )
    .limit(1)
    .all() as AuditRow[];
  return rows[0] ?? null;
}

export function latestAuditRow(tenantId: string): AuditRow | null {
  const rows = db
    .select()
    .from(tables.audits)
    .where(eq(tables.audits.tenantId, tenantId))
    .orderBy(desc(tables.audits.createdAt))
    .limit(1)
    .all() as AuditRow[];
  return rows[0] ?? null;
}

/** "Current audit" resolution: explicit ?audit= wins, else most recent. */
export function resolveAuditRow(
  tenantId: string,
  requested: string | null | undefined,
): AuditRow | null {
  if (requested) return findAuditRow(tenantId, requested);
  return latestAuditRow(tenantId);
}

/**
 * Insert the bundled demo fixture (real agent output, unedited) as an audits
 * row with source='demo'. Idempotent per tenant via the (tenant_id, audit_id)
 * unique index — re-loading returns the existing row.
 */
export function insertDemoAudit(
  tenantId: string,
  uploaderUserId: string | null,
): { row: AuditRow; created: boolean } {
  const existing = findAuditRow(tenantId, DEMO_AUDIT_ID);
  if (existing) return { row: existing, created: false };

  db.insert(tables.audits)
    .values({
      id: randomUUID(),
      tenantId,
      auditId: DEMO_AUDIT_ID,
      source: "demo",
      uploaderUserId,
      agentVersion: `bundled demo run ${DEMO_PROVENANCE.generatedAt}`,
      createdAt: new Date().toISOString(),
      resultJson: JSON.stringify(demoAuditJson),
    })
    .onConflictDoNothing()
    .run();

  const row = findAuditRow(tenantId, DEMO_AUDIT_ID);
  if (!row) throw new Error("demo audit insert failed");
  return { row, created: true };
}
