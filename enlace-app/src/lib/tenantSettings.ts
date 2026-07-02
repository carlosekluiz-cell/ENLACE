// ── Server-side tenant settings helpers ──
//
// tenants.settings is a JSON blob; the `assumptions` object inside it holds
// the admin-editable constants (ARPU, truck-roll cost, currency) that
// parameterize `estimated_*` figures. Reading tolerates missing/partial
// JSON (null constants — "not set", never a silent default); writing merges
// only the known keys and preserves everything else in the blob.
//
// Server-only: imports the DB. Never import from client components.

import { eq } from "drizzle-orm";
import { db, tables } from "@/db";
import type { TenantAssumptions } from "@/lib/adminTypes";

export interface TenantInfo {
  id: string;
  name: string;
  /** Full parsed settings blob (unknown keys preserved). */
  settings: Record<string, unknown>;
  assumptions: TenantAssumptions;
}

function numOrNull(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function strOrNull(v: unknown): string | null {
  return typeof v === "string" && v.trim() !== "" ? v : null;
}

function parseAssumptions(settings: Record<string, unknown>): TenantAssumptions {
  const a =
    settings.assumptions && typeof settings.assumptions === "object"
      ? (settings.assumptions as Record<string, unknown>)
      : {};
  return {
    arpu_gbp_month: numOrNull(a.arpu_gbp_month),
    truck_roll_cost_gbp: numOrNull(a.truck_roll_cost_gbp),
    currency: strOrNull(a.currency),
    ...(typeof a.note === "string" ? { note: a.note } : {}),
  };
}

export function getTenantInfo(tenantId: string): TenantInfo | null {
  const row = db
    .select()
    .from(tables.tenants)
    .where(eq(tables.tenants.id, tenantId))
    .all()[0];
  if (!row) return null;

  let settings: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(row.settings);
    if (parsed && typeof parsed === "object") {
      settings = parsed as Record<string, unknown>;
    }
  } catch {
    console.error(`[tenantSettings] tenants row ${tenantId} has unparseable settings JSON`);
  }

  return {
    id: row.id,
    name: row.name,
    settings,
    assumptions: parseAssumptions(settings),
  };
}

export interface AssumptionPatch {
  arpu_gbp_month?: number;
  truck_roll_cost_gbp?: number;
  currency?: string;
}

/**
 * Merge the patch into settings.assumptions (other blob keys untouched)
 * and persist. Returns the updated info. The CALLER writes the audit_log
 * entry — changing estimate constants is an admin act.
 */
export function updateTenantAssumptions(
  tenantId: string,
  patch: AssumptionPatch,
): TenantInfo | null {
  const info = getTenantInfo(tenantId);
  if (!info) return null;

  const existing =
    info.settings.assumptions && typeof info.settings.assumptions === "object"
      ? (info.settings.assumptions as Record<string, unknown>)
      : {};
  const nextSettings = {
    ...info.settings,
    assumptions: { ...existing, ...patch },
  };

  db.update(tables.tenants)
    .set({ settings: JSON.stringify(nextSettings) })
    .where(eq(tables.tenants.id, tenantId))
    .run();

  return getTenantInfo(tenantId);
}

/**
 * Human-readable assumption lines for projections/reports — each line is
 * explicitly labeled as a tenant SETTING (admin-editable), distinct from the
 * assumptions the agent declared inside a persisted audit.
 */
export function tenantAssumptionLines(a: TenantAssumptions): string[] {
  const cur = a.currency ?? "";
  const lines: string[] = [];
  lines.push(
    a.arpu_gbp_month === null
      ? "Tenant setting — assumed monthly ARPU: not set"
      : `Tenant setting — assumed monthly ARPU: ${a.arpu_gbp_month} ${cur}`.trimEnd(),
  );
  lines.push(
    a.truck_roll_cost_gbp === null
      ? "Tenant setting — assumed truck-roll cost: not set"
      : `Tenant setting — assumed truck-roll cost: ${a.truck_roll_cost_gbp} ${cur}`.trimEnd(),
  );
  return lines;
}
