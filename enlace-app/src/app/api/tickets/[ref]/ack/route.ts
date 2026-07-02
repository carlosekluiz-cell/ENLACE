// POST /api/tickets/[ref]/ack — acknowledge a ticket (open → acked).
//
// Auth: analyst+ (permission matrix §2.2 — acknowledge incident).
// Body: { audit: <audits row id or agent audit_id> } (optional — defaults to
// the most recent audit). Illegal transitions are 409, validated server-side.
// Writes audit_log.

import { NextRequest, NextResponse } from "next/server";
import { resolveAuditRow } from "@/lib/auditStore";
import { ackTicket, TicketError } from "@/lib/ticketStore";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";
import type { TicketActionResponse } from "@/lib/opsTypes";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ ref: string }> },
) {
  try {
    const session = await requireSession(req);
    requireRole(session, "analyst");
    const { ref } = await ctx.params;

    const body = (await req.json().catch(() => ({}))) as { audit?: unknown };
    const requested = typeof body.audit === "string" ? body.audit : null;

    const row = resolveAuditRow(session.tenant_id, requested);
    if (!row) {
      return NextResponse.json(
        { error: "no persisted audit to act on" },
        { status: 404 },
      );
    }

    const state = ackTicket(row, ref, session.sub);
    logAction(session, "ticket.ack", `${row.id}/${ref}`);

    const res: TicketActionResponse = { ticket_ref: ref, state };
    return NextResponse.json(res);
  } catch (err) {
    if (err instanceof TicketError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return authzResponse(err);
  }
}
