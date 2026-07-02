// ── Wave B shared types: audit listing, ticket lifecycle, projections ──
//
// Shared between server routes and client views (no server imports here).
// The agent-shaped types live in src/lib/types.ts and are NEVER reshaped;
// everything below is app-layer envelope/overlay around verbatim agent data.
//
// Honesty invariants (ONTOLOGY.md §5, ARCHITECTURE-TENANCY.md §3.3):
// projections may subset ROWS, never strip assumptions[], import_report,
// coverage notes, or estimate labels. Provenance comes from the DB row.

import type {
  AuditResult,
  AuditSummary,
  CapacityEntry,
  ChurnRisk,
  FaultEvent,
  FecHealthReport,
  Impact,
  ImportReportSummary,
  LaserHealthReport,
  OntData,
  RoguePortFinding,
  Ticket,
} from "@/lib/types";

// ── Audit persistence / listing ──

export type AuditSource = "live" | "audit" | "demo";

/** Stored provenance of a persisted audit — a DB record, not a UI guess. */
export interface AuditProvenance {
  /** audits row id (primary key) — what pickers and ?audit= use. */
  id: string;
  /** Agent-assigned audit id (UUID from POST /audit, or the demo fixture id). */
  audit_id: string;
  source: AuditSource;
  uploader_name: string | null;
  agent_version: string | null;
  created_at: string;
}

/** Small server-side extract from result_json — the stored JSON is never mutated. */
export interface AuditListSummary {
  health_score: number;
  total_onts: number;
  online: number;
  offline: number;
  unknown: number;
  fault_count: number;
  ticket_count: number;
  /** Findings across detection modules (ghosts, flapping, reflectance, fec, laser, rogue, churn). */
  finding_count: number;
}

export interface AuditListEntry extends AuditProvenance {
  /** null only if the stored JSON failed to parse (integrity error, surfaced honestly). */
  summary: AuditListSummary | null;
}

export interface AuditListResponse {
  audits: AuditListEntry[];
}

/** GET /api/audits/[id] — full stored AuditResult, verbatim, with provenance. */
export interface AuditDetailResponse {
  provenance: AuditProvenance;
  result: AuditResult;
}

// ── Ticket lifecycle ──
// State machine: open → acked → dispatched → closed.
//   ack      (analyst+)              open → acked
//   assign   (manager+)              open|acked|dispatched → dispatched
//                                    (assigning an un-acked ticket records the ack too)
//   close    (assignee, any role, own ticket; else analyst+)
//                                    acked|dispatched → closed (close_note required);
//                                    open → closed only with ack:true (NOC one-flow, analyst+)

export type TicketStatus = "open" | "acked" | "dispatched" | "closed";

export interface TicketStateInfo {
  status: TicketStatus;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  acked_by: string | null;
  acked_by_name: string | null;
  acked_at: string | null;
  closed_by: string | null;
  closed_by_name: string | null;
  closed_at: string | null;
  close_note: string | null;
  updated_at: string | null;
}

/** Agent ticket VERBATIM + operational state overlay + derived SLA schedule. */
export interface TicketWithState {
  /** Stable reference = the agent's ticket_id within this audit. */
  ticket_ref: string;
  ticket: Ticket;
  state: TicketStateInfo;
  /** generated_at + sla_days (derived scheduling data, not a measurement). */
  sla_due: string;
  days_to_sla: number;
}

export interface TicketListResponse {
  available: true;
  provenance: AuditProvenance;
  import_report: ImportReportSummary | null;
  /** Role-scoped rows: viewer sees own assigned tickets; analyst+ sees all. */
  tickets: TicketWithState[];
}

export interface TicketActionResponse {
  ticket_ref: string;
  state: TicketStateInfo;
}

// ── Projections ──
// All computed server-side from the persisted audit row. Every projection
// carries provenance + import_report (banner data) — never stripped.

export interface ProjectionUnavailable {
  available: false;
  /** Honest reason: "no audit persisted for this tenant yet", bad id, … */
  reason: string;
}

export interface ProjectionBase {
  available: true;
  provenance: AuditProvenance;
  import_report: ImportReportSummary | null;
}

/** Fault-level lens for the NOC operator (analyst+). */
export interface NocProjection extends ProjectionBase {
  summary: AuditSummary;
  faults: FaultEvent[];
  onts: OntData[];
  /** Frontier sections — always the full report objects incl. coverage notes. */
  fec_health: FecHealthReport;
  laser_health: LaserHealthReport;
  rogue: RoguePortFinding[];
  /** All tickets with state so the NOC can ack where tickets exist. */
  tickets: TicketWithState[];
}

/** "My jobs" lens for the field engineer (viewer+): assigned to me only. */
export interface FieldProjection extends ProjectionBase {
  tickets: TicketWithState[];
}

export interface TeamMember {
  id: string;
  name: string;
  role: string;
  persona: string;
}

/** Dispatch-board lens (manager+): full queue + dispatchable team. */
export interface SupervisorProjection extends ProjectionBase {
  queue: TicketWithState[];
  /** Tenant users assignable as engineers (role viewer/analyst). */
  team: TeamMember[];
}

export interface ExecRevenueAtRisk {
  /** Sum of ticket estimated_revenue_at_risk_annual — an ESTIMATE. */
  estimated_total_annual: number;
  /** Estimate label carried through — render with the assumption badge. */
  label: "estimate";
  /** Union of the declared assumptions behind the figure. */
  assumptions: string[];
  ticket_count: number;
}

export interface ExecTrendPlaceholder {
  available: false;
  reason: string;
}

/** Rollup lens for exec personas (manager+). */
export interface ExecProjection extends ProjectionBase {
  summary: AuditSummary;
  revenue_at_risk: ExecRevenueAtRisk;
  ticket_counts: {
    total: number;
    by_status: Record<TicketStatus, number>;
    by_priority: Record<string, number>;
  };
  capacity: CapacityEntry[];
  churn_risk: ChurnRisk[];
  impact: Impact;
  /** Honest-empty until multi-audit trending is built. */
  trend: ExecTrendPlaceholder;
}

export type Projection<T extends ProjectionBase> = T | ProjectionUnavailable;
