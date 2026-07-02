// ── Server-side ticket lifecycle ──
//
// The agent's AuditResult.tickets are the source tickets (ticket_ref =
// the agent's stable ticket_id within the audit). ticket_state rows overlay
// operational state; the agent JSON is never touched.
//
// State machine: open → acked → dispatched → closed.
//   ack     open → acked
//   assign  open|acked|dispatched → dispatched (assigning an un-acked
//           ticket records the acknowledgement too — dispatch implies ack)
//   close   acked|dispatched → closed (close_note REQUIRED);
//           open → closed only when the caller asked for ack+close in one
//           flow (NOC convenience) — never silently.
// Illegal moves are 409s, validated HERE, server-side.

import { randomUUID } from "node:crypto";
import { and, eq, inArray } from "drizzle-orm";
import { db, tables } from "@/db";
import type { AuditRow } from "@/lib/auditStore";
import { parseResult } from "@/lib/auditStore";
import { deriveTicketLocation } from "@/lib/ticketLocation";
import type { Ticket } from "@/lib/types";
import type {
  TicketStateInfo,
  TicketStatus,
  TicketWithState,
} from "@/lib/opsTypes";

export class TicketError extends Error {
  constructor(
    public readonly status: 400 | 403 | 404 | 409,
    message: string,
  ) {
    super(message);
    this.name = "TicketError";
  }
}

interface StateRow {
  id: string;
  status: TicketStatus;
  assignedUserId: string | null;
  ackedBy: string | null;
  ackedAt: string | null;
  closedBy: string | null;
  closedAt: string | null;
  closeNote: string | null;
  updatedAt: string;
}

/** Default overlay for a ticket nobody has touched yet. */
const OPEN_STATE: TicketStateInfo = {
  status: "open",
  assigned_user_id: null,
  assigned_user_name: null,
  acked_by: null,
  acked_by_name: null,
  acked_at: null,
  closed_by: null,
  closed_by_name: null,
  closed_at: null,
  close_note: null,
  updated_at: null,
};

function userNames(ids: Array<string | null>): Map<string, string> {
  const wanted = [...new Set(ids.filter((v): v is string => v !== null))];
  if (wanted.length === 0) return new Map();
  const rows = db
    .select({ id: tables.users.id, name: tables.users.name })
    .from(tables.users)
    .where(inArray(tables.users.id, wanted))
    .all();
  return new Map(rows.map((r) => [r.id, r.name]));
}

function toStateInfo(row: StateRow, names: Map<string, string>): TicketStateInfo {
  return {
    status: row.status,
    assigned_user_id: row.assignedUserId,
    assigned_user_name: row.assignedUserId
      ? (names.get(row.assignedUserId) ?? null)
      : null,
    acked_by: row.ackedBy,
    acked_by_name: row.ackedBy ? (names.get(row.ackedBy) ?? null) : null,
    acked_at: row.ackedAt,
    closed_by: row.closedBy,
    closed_by_name: row.closedBy ? (names.get(row.closedBy) ?? null) : null,
    closed_at: row.closedAt,
    close_note: row.closeNote,
    updated_at: row.updatedAt,
  };
}

function stateRowFor(
  tenantId: string,
  auditRowId: string,
  ticketRef: string,
): StateRow | null {
  const rows = db
    .select()
    .from(tables.ticketState)
    .where(
      and(
        eq(tables.ticketState.tenantId, tenantId),
        eq(tables.ticketState.auditId, auditRowId),
        eq(tables.ticketState.ticketRef, ticketRef),
      ),
    )
    .limit(1)
    .all();
  return (rows[0] as StateRow | undefined) ?? null;
}

/** SLA due = generated_at + sla_days (derived schedule, not a measurement). */
function slaOf(ticket: Ticket): { sla_due: string; days_to_sla: number } {
  const due = new Date(ticket.generated_at);
  due.setDate(due.getDate() + ticket.sla_days);
  return {
    sla_due: due.toISOString(),
    days_to_sla: Math.ceil((due.getTime() - Date.now()) / 86_400_000),
  };
}

/**
 * JOIN agent ticket data (verbatim) with the ticket_state overlay.
 * `assignee` filters rows to that user's tickets (field-engineer lens) —
 * rows are subset; ticket objects are never trimmed.
 */
export function ticketsWithState(
  auditRow: AuditRow,
  opts?: { assignee?: string },
): TicketWithState[] {
  const result = parseResult(auditRow);
  const agentTickets = result?.tickets ?? [];

  const stateRows = db
    .select()
    .from(tables.ticketState)
    .where(
      and(
        eq(tables.ticketState.tenantId, auditRow.tenantId),
        eq(tables.ticketState.auditId, auditRow.id),
      ),
    )
    .all() as Array<StateRow & { ticketRef: string }>;

  const byRef = new Map(stateRows.map((r) => [r.ticketRef, r]));
  const names = userNames(
    stateRows.flatMap((r) => [r.assignedUserId, r.ackedBy, r.closedBy]),
  );

  const all = agentTickets.map((ticket) => {
    const row = byRef.get(ticket.ticket_id);
    return {
      ticket_ref: ticket.ticket_id,
      ticket,
      state: row ? toStateInfo(row, names) : OPEN_STATE,
      ...slaOf(ticket),
      // Derived fault location (C2) — honest `none` when the audit has no
      // distance/geo data for the affected ONTs. Server-derived once, so the
      // tickets API + field/supervisor projections render it without
      // recomputing client-side.
      location: deriveTicketLocation(result, ticket),
    };
  });

  if (opts?.assignee) {
    return all.filter((t) => t.state.assigned_user_id === opts.assignee);
  }
  return all;
}

/** The agent ticket for a ref — 404 when the audit has no such ticket. */
export function requireAgentTicket(auditRow: AuditRow, ref: string): Ticket {
  const result = parseResult(auditRow);
  const ticket = result?.tickets.find((t) => t.ticket_id === ref);
  if (!ticket) {
    throw new TicketError(404, `no ticket "${ref}" in audit ${auditRow.id}`);
  }
  return ticket;
}

function upsertState(
  tenantId: string,
  auditRowId: string,
  ticketRef: string,
  existing: StateRow | null,
  set: Partial<{
    status: TicketStatus;
    assignedUserId: string | null;
    ackedBy: string | null;
    ackedAt: string | null;
    closedBy: string | null;
    closedAt: string | null;
    closeNote: string | null;
  }>,
): TicketStateInfo {
  const updatedAt = new Date().toISOString();
  if (existing) {
    db.update(tables.ticketState)
      .set({ ...set, updatedAt })
      .where(eq(tables.ticketState.id, existing.id))
      .run();
  } else {
    db.insert(tables.ticketState)
      .values({
        id: randomUUID(),
        tenantId,
        auditId: auditRowId,
        ticketRef,
        status: set.status ?? "open",
        assignedUserId: set.assignedUserId ?? null,
        ackedBy: set.ackedBy ?? null,
        ackedAt: set.ackedAt ?? null,
        closedBy: set.closedBy ?? null,
        closedAt: set.closedAt ?? null,
        closeNote: set.closeNote ?? null,
        updatedAt,
      })
      .run();
  }
  const row = stateRowFor(tenantId, auditRowId, ticketRef);
  if (!row) throw new Error("ticket_state upsert failed");
  return toStateInfo(
    row,
    userNames([row.assignedUserId, row.ackedBy, row.closedBy]),
  );
}

/** open → acked. */
export function ackTicket(
  auditRow: AuditRow,
  ref: string,
  actorUserId: string,
): TicketStateInfo {
  requireAgentTicket(auditRow, ref);
  const existing = stateRowFor(auditRow.tenantId, auditRow.id, ref);
  const status = existing?.status ?? "open";
  if (status !== "open") {
    throw new TicketError(
      409,
      `cannot ack a ${status} ticket (only open → acked)`,
    );
  }
  const now = new Date().toISOString();
  return upsertState(auditRow.tenantId, auditRow.id, ref, existing, {
    status: "acked",
    ackedBy: actorUserId,
    ackedAt: now,
  });
}

/**
 * open|acked|dispatched → dispatched. Assignee must be an active user of the
 * same tenant. Assigning an un-acked ticket records the ack (dispatch implies
 * acknowledgement — recorded to the dispatching actor, honestly).
 */
export function assignTicket(
  auditRow: AuditRow,
  ref: string,
  actorUserId: string,
  assigneeUserId: string,
): TicketStateInfo {
  requireAgentTicket(auditRow, ref);

  const assignee = db
    .select({ id: tables.users.id, disabled: tables.users.disabled })
    .from(tables.users)
    .where(
      and(
        eq(tables.users.id, assigneeUserId),
        eq(tables.users.tenantId, auditRow.tenantId),
      ),
    )
    .all()[0];
  if (!assignee || assignee.disabled) {
    throw new TicketError(400, "assignee is not an active user of this tenant");
  }

  const existing = stateRowFor(auditRow.tenantId, auditRow.id, ref);
  const status = existing?.status ?? "open";
  if (status === "closed") {
    throw new TicketError(409, "cannot assign a closed ticket");
  }
  const now = new Date().toISOString();
  return upsertState(auditRow.tenantId, auditRow.id, ref, existing, {
    status: "dispatched",
    assignedUserId: assigneeUserId,
    // dispatch implies acknowledgement; keep the original ack if it exists
    ackedBy: existing?.ackedBy ?? actorUserId,
    ackedAt: existing?.ackedAt ?? now,
  });
}

/**
 * acked|dispatched → closed; open → closed only with ackFirst (one-flow for
 * the NOC — the route gates ackFirst on analyst+). close_note required.
 */
export function closeTicket(
  auditRow: AuditRow,
  ref: string,
  actorUserId: string,
  note: string,
  ackFirst: boolean,
): TicketStateInfo {
  requireAgentTicket(auditRow, ref);
  if (!note.trim()) {
    throw new TicketError(400, "close_note is required to close a ticket");
  }

  const existing = stateRowFor(auditRow.tenantId, auditRow.id, ref);
  const status = existing?.status ?? "open";
  if (status === "closed") {
    throw new TicketError(409, "ticket is already closed");
  }
  if (status === "open" && !ackFirst) {
    throw new TicketError(
      409,
      "cannot close an un-acked ticket — acknowledge first (or pass ack: true for ack+close in one flow)",
    );
  }

  const now = new Date().toISOString();
  return upsertState(auditRow.tenantId, auditRow.id, ref, existing, {
    status: "closed",
    closedBy: actorUserId,
    closedAt: now,
    closeNote: note.trim(),
    ...(status === "open"
      ? { ackedBy: actorUserId, ackedAt: now }
      : {}),
  });
}

/** Current state (default open) — for route-level ownership checks. */
export function currentState(
  auditRow: AuditRow,
  ref: string,
): TicketStateInfo {
  const row = stateRowFor(auditRow.tenantId, auditRow.id, ref);
  if (!row) return OPEN_STATE;
  return toStateInfo(row, userNames([row.assignedUserId, row.ackedBy, row.closedBy]));
}
