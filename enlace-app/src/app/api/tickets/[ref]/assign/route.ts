// POST /api/tickets/[ref]/assign — dispatch: assign to a tenant user
// (open|acked|dispatched → dispatched; reassignment allowed; closed → 409).
//
// Auth: manager+ (permission matrix §2.2 — reassign/dispatch). Assignee must
// be an active user of the SAME tenant (validated in ticketStore). Assigning
// an un-acked ticket records the ack too (dispatch implies acknowledgement).
// Body: { audit?: string, assignee: string }. Writes audit_log.

import { NextRequest, NextResponse } from "next/server";
import { resolveAuditRow } from "@/lib/auditStore";
import { assignTicket, TicketError } from "@/lib/ticketStore";
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
    requireRole(session, "manager");
    const { ref } = await ctx.params;

    const body = (await req.json().catch(() => ({}))) as {
      audit?: unknown;
      assignee?: unknown;
    };
    if (typeof body.assignee !== "string" || !body.assignee) {
      return NextResponse.json(
        { error: "missing `assignee` (tenant user id)" },
        { status: 400 },
      );
    }
    const requested = typeof body.audit === "string" ? body.audit : null;

    const row = resolveAuditRow(session.tenant_id, requested);
    if (!row) {
      return NextResponse.json(
        { error: "no persisted audit to act on" },
        { status: 404 },
      );
    }

    const state = assignTicket(row, ref, session.sub, body.assignee);
    logAction(session, "ticket.assign", `${row.id}/${ref} → ${body.assignee}`);

    const res: TicketActionResponse = { ticket_ref: ref, state };
    return NextResponse.json(res);
  } catch (err) {
    if (err instanceof TicketError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return authzResponse(err);
  }
}
