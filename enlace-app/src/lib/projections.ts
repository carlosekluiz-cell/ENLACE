// ── Server-side persona projections ──
//
// One persisted audit, four lenses (ARCHITECTURE-TENANCY.md §3.2). All are
// computed from the app-DB audit row — never from client-shipped JSON.
//
// Honesty invariants enforced here (ONTOLOGY.md §5):
//   - projections SUBSET rows (field engineer sees own tickets), they never
//     strip assumptions[], import_report, coverage notes or estimate labels;
//   - the frontier sections (fec_health, laser_health, rogue) travel as the
//     agent's FULL report objects, coverage counters and notes included —
//     absence of a finding is not evidence of health;
//   - import_report banner data is included in EVERY projection (null when
//     the audit was not CSV-fed — stated, not hidden).

import { eq } from "drizzle-orm";
import { db, tables } from "@/db";
import {
  parseResult,
  provenanceOf,
  resolveAuditRow,
  type AuditRow,
} from "@/lib/auditStore";
import { ticketsWithState } from "@/lib/ticketStore";
import { getTenantInfo, tenantAssumptionLines } from "@/lib/tenantSettings";
import type { SessionClaims } from "@/lib/jwt";
import type {
  ExecProjection,
  FieldProjection,
  NocProjection,
  Projection,
  ProjectionBase,
  ProjectionUnavailable,
  SupervisorProjection,
  TicketStatus,
} from "@/lib/opsTypes";
import type { AuditResult } from "@/lib/types";

const NO_AUDIT: ProjectionUnavailable = {
  available: false,
  reason:
    "no audit persisted for this tenant yet — upload a CSV (POST /api/audit) or load the demo audit (POST /api/audits/demo)",
};

interface Resolved {
  row: AuditRow;
  result: AuditResult;
  base: ProjectionBase;
}

/** Resolve ?audit= (or latest) into a parsed row + shared envelope. */
function resolve(
  session: SessionClaims,
  requested: string | null,
): Resolved | ProjectionUnavailable {
  const row = resolveAuditRow(session.tenant_id, requested);
  if (!row) {
    return requested
      ? {
          available: false,
          reason: `no persisted audit "${requested}" for this tenant`,
        }
      : NO_AUDIT;
  }
  const result = parseResult(row);
  if (!result) {
    return {
      available: false,
      reason: `stored audit ${row.id} failed to parse — integrity error`,
    };
  }
  return {
    row,
    result,
    base: {
      available: true,
      provenance: provenanceOf(row),
      import_report: result.import_report ?? null,
    },
  };
}

/** NOC lens: fault-level view + ONT table + frontier sections + tickets. */
export function nocProjection(
  session: SessionClaims,
  requested: string | null,
): Projection<NocProjection> {
  const r = resolve(session, requested);
  if ("available" in r && r.available === false) return r;
  const { result, row, base } = r as Resolved;
  return {
    ...base,
    summary: result.summary,
    faults: result.faults,
    onts: result.onts,
    fec_health: result.fec_health,
    laser_health: result.laser_health,
    rogue: result.rogue,
    tickets: ticketsWithState(row),
  };
}

/** Field lens: MY tickets only (row subset), each with full evidence. */
export function fieldProjection(
  session: SessionClaims,
  requested: string | null,
): Projection<FieldProjection> {
  const r = resolve(session, requested);
  if ("available" in r && r.available === false) return r;
  const { row, base } = r as Resolved;
  return {
    ...base,
    tickets: ticketsWithState(row, { assignee: session.sub }),
  };
}

/** Supervisor lens: full queue + dispatchable team (viewer/analyst users). */
export function supervisorProjection(
  session: SessionClaims,
  requested: string | null,
): Projection<SupervisorProjection> {
  const r = resolve(session, requested);
  if ("available" in r && r.available === false) return r;
  const { row, base } = r as Resolved;

  const team = db
    .select({
      id: tables.users.id,
      name: tables.users.name,
      role: tables.users.role,
      persona: tables.users.persona,
      phone: tables.users.phone,
    })
    .from(tables.users)
    .where(eq(tables.users.tenantId, session.tenant_id))
    .all()
    .filter((u) => u.role === "viewer" || u.role === "analyst");

  return {
    ...base,
    queue: ticketsWithState(row),
    team,
  };
}

/** Exec lens: health rollups + estimates WITH labels and assumptions. */
export function execProjection(
  session: SessionClaims,
  requested: string | null,
): Projection<ExecProjection> {
  const r = resolve(session, requested);
  if ("available" in r && r.available === false) return r;
  const { result, row, base } = r as Resolved;

  const tickets = ticketsWithState(row);
  const byStatus: Record<TicketStatus, number> = {
    open: 0,
    acked: 0,
    dispatched: 0,
    closed: 0,
  };
  const byPriority: Record<string, number> = {};
  for (const t of tickets) {
    byStatus[t.state.status] += 1;
    byPriority[t.ticket.priority] = (byPriority[t.ticket.priority] ?? 0) + 1;
  }

  // Tenant assumption constants (admin-editable) — surfaced ALONGSIDE the
  // agent-declared assumptions, never merged into them: this audit's figures
  // were computed by the agent with the assumptions echoed in the result;
  // settings changes feed future estimate math (the agent seam).
  const tenant = getTenantInfo(session.tenant_id);
  const a = tenant?.assumptions ?? {
    arpu_gbp_month: null,
    truck_roll_cost_gbp: null,
    currency: null,
  };

  return {
    ...base,
    summary: result.summary,
    revenue_at_risk: {
      estimated_total_annual: result.tickets.reduce(
        (sum, t) => sum + t.estimated_revenue_at_risk_annual,
        0,
      ),
      label: "estimate",
      // Union of declared assumptions — carried through, never stripped.
      assumptions: [...new Set(result.tickets.flatMap((t) => t.assumptions))],
      ticket_count: result.tickets.length,
    },
    ticket_counts: {
      total: tickets.length,
      by_status: byStatus,
      by_priority: byPriority,
    },
    capacity: result.capacity,
    churn_risk: result.churn_risk,
    impact: result.impact,
    trend: {
      available: false,
      reason:
        "health-score trend not available yet — trending needs multiple audits over time; this view renders one persisted audit",
    },
    tenant_assumptions: {
      source: "tenant settings (admin-editable)",
      arpu_gbp_month: a.arpu_gbp_month,
      truck_roll_cost_gbp: a.truck_roll_cost_gbp,
      currency: a.currency,
      lines: tenantAssumptionLines(a),
      note: "These constants feed FUTURE estimate math (agent runs). This audit's estimated_* figures carry the assumptions the agent declared at audit time and are never retroactively recomputed.",
    },
  };
}
