// POST /api/hooks/agent-events — pulso-agent incident-update ingress (P88).
//
// The agent's generic webhook POSTs the serialized IncidentUpdate (see
// pulso-agent src/output/webhook.rs format_generic / fault/detector.rs
// IncidentUpdate): { action: "open"|"resolve", incident_id, scope, opened_at,
// resolved_at, ports[], classification, ...flattened FaultEvent (olt_id,
// pon_port, fault_type, severity, affected_onts[{serial_number,…}], …) }.
//
// Auth: shared bearer token ENLACE_HOOK_TOKEN — a MACHINE credential
// (agent → app), the mirror of PULSO_AUDIT_TOKEN (app → agent). NOT session
// auth: the caller is the agent, not a person. 401 without/with a wrong
// token; 503 when the env is unset (hook disabled). The path is listed in
// PUBLIC_PATHS so the session middleware doesn't intercept it.
//
// Tenant resolution: ENLACE_HOOK_TENANT env when set; otherwise the sole
// tenants row (single-tenant deploys, ARCHITECTURE-TENANCY.md §1.2). With
// more than one tenant and no mapping the event is rejected (422) — never
// guess whose network recovered.
//
// On action == "resolve", tickets of the tenant's CURRENT (latest) audit in
// open|acked|dispatched whose ONT serials intersect the event's recovered
// affected_onts are considered:
//   - FULL coverage (every ticket serial recovered) → auto-close: status
//     closed, closed_by NULL + closed_by_system, audit_log `ticket.autoclose`.
//   - PARTIAL coverage → NOT closed; logged once per (ticket, incident) as
//     audit_log `ticket.autoclose.partial_skip` (honesty: partial recovery
//     never closes a ticket).
//   - Already-closed tickets are never touched (idempotent — a human close
//     is never overwritten; re-posting the same event is a no-op).

import { createHash, timingSafeEqual } from "node:crypto";
import { and, eq } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import { latestAuditRow } from "@/lib/auditStore";
import { autoCloseTicket, ticketsWithState } from "@/lib/ticketStore";

/** Constant-time bearer comparison (hash both sides to a fixed length). */
function tokenMatches(presented: string, configured: string): boolean {
  const a = createHash("sha256").update(presented).digest();
  const b = createHash("sha256").update(configured).digest();
  return timingSafeEqual(a, b);
}

/**
 * ENLACE_HOOK_TENANT when set (must exist); else the sole tenants row.
 * Returns an error string when the mapping is ambiguous or wrong.
 */
function resolveHookTenant(): { tenantId: string } | { error: string } {
  const rows = db.select({ id: tables.tenants.id }).from(tables.tenants).all();
  const configured = process.env.ENLACE_HOOK_TENANT;
  if (configured) {
    if (!rows.some((r) => r.id === configured)) {
      return { error: `ENLACE_HOOK_TENANT "${configured}" is not a known tenant` };
    }
    return { tenantId: configured };
  }
  if (rows.length === 1) return { tenantId: rows[0].id };
  if (rows.length === 0) return { error: "no tenants provisioned" };
  return {
    error:
      "multiple tenants exist — set ENLACE_HOOK_TENANT to map agent events to a tenant",
  };
}

/** Append-only system trail entry (no user — the actor is telemetry). */
function logSystemAction(tenantId: string, action: string, subject: string): void {
  try {
    db.insert(tables.auditLog)
      .values({
        tenantId,
        userId: null,
        action,
        subject,
        at: new Date().toISOString(),
      })
      .run();
  } catch (e) {
    console.warn("[agent-events] audit_log write failed:", e);
  }
}

/** True when an identical trail entry already exists (idempotent re-posts). */
function alreadyLogged(tenantId: string, action: string, subject: string): boolean {
  const rows = db
    .select({ id: tables.auditLog.id })
    .from(tables.auditLog)
    .where(
      and(
        eq(tables.auditLog.tenantId, tenantId),
        eq(tables.auditLog.action, action),
        eq(tables.auditLog.subject, subject),
      ),
    )
    .limit(1)
    .all();
  return rows.length > 0;
}

interface IncidentEventBody {
  action: string;
  incident_id: string;
  resolvedAt: string;
  serials: Set<string>;
}

/** Validate the agent payload; string on failure (→ 400). */
function parseEvent(raw: unknown): IncidentEventBody | string {
  if (typeof raw !== "object" || raw === null) return "body must be a JSON object";
  const b = raw as Record<string, unknown>;
  if (typeof b.action !== "string") return "missing `action`";
  if (typeof b.incident_id !== "string" || !b.incident_id) {
    return "missing `incident_id`";
  }
  if (!Array.isArray(b.affected_onts)) return "missing `affected_onts` array";
  const serials = new Set<string>();
  for (const ont of b.affected_onts) {
    const serial = (ont as Record<string, unknown> | null)?.serial_number;
    if (typeof serial !== "string" || !serial) {
      return "every affected_onts entry needs a `serial_number`";
    }
    serials.add(serial);
  }
  // Event time: resolved_at is set on resolve updates; the flattened event
  // `timestamp` equals it. Require one — never invent the recovery time.
  const resolvedAt =
    typeof b.resolved_at === "string"
      ? b.resolved_at
      : typeof b.timestamp === "string"
        ? b.timestamp
        : null;
  if (b.action === "resolve" && !resolvedAt) {
    return "resolve event without `resolved_at`/`timestamp`";
  }
  return {
    action: b.action,
    incident_id: b.incident_id,
    resolvedAt: resolvedAt ?? "",
    serials,
  };
}

export async function POST(req: NextRequest) {
  const configured = process.env.ENLACE_HOOK_TOKEN;
  if (!configured) {
    return NextResponse.json(
      { error: "agent-events hook is not configured (ENLACE_HOOK_TOKEN unset)" },
      { status: 503 },
    );
  }
  const auth = req.headers.get("authorization") ?? "";
  const presented = auth.startsWith("Bearer ") ? auth.slice("Bearer ".length) : "";
  if (!presented || !tokenMatches(presented, configured)) {
    return NextResponse.json({ error: "invalid hook token" }, { status: 401 });
  }

  const raw = await req.json().catch(() => null);
  const event = parseEvent(raw);
  if (typeof event === "string") {
    return NextResponse.json({ error: event }, { status: 400 });
  }

  const tenant = resolveHookTenant();
  if ("error" in tenant) {
    return NextResponse.json({ error: tenant.error }, { status: 422 });
  }
  const { tenantId } = tenant;

  // Only resolve events act on tickets; opens are acknowledged and dropped
  // (the audit/NOC pipeline is the system of record for new faults).
  if (event.action !== "resolve") {
    return NextResponse.json({
      received: true,
      action: event.action,
      incident_id: event.incident_id,
      ignored: "only `resolve` events auto-close tickets",
    });
  }

  const auditRow = latestAuditRow(tenantId);
  if (!auditRow) {
    return NextResponse.json({
      received: true,
      action: "resolve",
      incident_id: event.incident_id,
      audit: null,
      closed: [],
      partial_skipped: [],
      already_closed: [],
      note: "no persisted audit for this tenant — nothing to close",
    });
  }

  const closed: string[] = [];
  const partialSkipped: string[] = [];
  const alreadyClosed: string[] = [];

  for (const entry of ticketsWithState(auditRow)) {
    const ticketSerials = entry.ticket.affected_ont_serials;
    // No serials on the ticket → coverage is unverifiable → never auto-close.
    if (ticketSerials.length === 0) continue;
    const covered = ticketSerials.filter((s) => event.serials.has(s));
    if (covered.length === 0) continue;

    if (entry.state.status === "closed") {
      // Idempotent: never touch a close (human or prior auto-close).
      alreadyClosed.push(entry.ticket_ref);
      continue;
    }

    const subject = `${auditRow.id}/${entry.ticket_ref} incident=${event.incident_id}`;

    if (covered.length === ticketSerials.length) {
      autoCloseTicket(
        auditRow,
        entry.ticket_ref,
        `Auto-resolved: telemetry confirmed recovery at ${event.resolvedAt} (incident ${event.incident_id})`,
      );
      logSystemAction(tenantId, "ticket.autoclose", subject);
      closed.push(entry.ticket_ref);
    } else {
      // Partial recovery must NOT close the ticket — record the observation
      // once per (ticket, incident) as a comment-style trail entry.
      const partialSubject = `${subject} recovered=${covered.length}/${ticketSerials.length} ONTs — not closed`;
      if (!alreadyLogged(tenantId, "ticket.autoclose.partial_skip", partialSubject)) {
        logSystemAction(tenantId, "ticket.autoclose.partial_skip", partialSubject);
      }
      partialSkipped.push(entry.ticket_ref);
    }
  }

  return NextResponse.json({
    received: true,
    action: "resolve",
    incident_id: event.incident_id,
    audit: auditRow.id,
    closed,
    partial_skipped: partialSkipped,
    already_closed: alreadyClosed,
  });
}
