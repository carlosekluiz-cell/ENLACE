// POST /api/tickets/[ref]/close — close out with a mandatory close_note.
//
// Auth (permission matrix §2.2): the ASSIGNEE may close their OWN ticket at
// any role (ownership check, not role rank — field-engineer close-out);
// anyone else needs analyst+. Transition: acked|dispatched → closed.
// open → closed only with { ack: true } (NOC ack+close in one flow), which
// itself requires analyst+ (ack privilege). Writes audit_log.
//
// Body: { audit?: string, note: string, ack?: boolean }.

import { NextRequest, NextResponse } from "next/server";
import { resolveAuditRow } from "@/lib/auditStore";
import { closeTicket, currentState, TicketError } from "@/lib/ticketStore";
import {
  authzResponse,
  AuthzError,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";
import { roleAtLeast } from "@/lib/roles";
import type { TicketActionResponse } from "@/lib/opsTypes";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ ref: string }> },
) {
  try {
    const session = await requireSession(req);
    const { ref } = await ctx.params;

    const body = (await req.json().catch(() => ({}))) as {
      audit?: unknown;
      note?: unknown;
      ack?: unknown;
    };
    const note = typeof body.note === "string" ? body.note : "";
    const ackFirst = body.ack === true;
    const requested = typeof body.audit === "string" ? body.audit : null;

    const row = resolveAuditRow(session.tenant_id, requested);
    if (!row) {
      return NextResponse.json(
        { error: "no persisted audit to act on" },
        { status: 404 },
      );
    }

    // Ownership check: assignee may close their own ticket regardless of
    // role rank; everyone else needs analyst+.
    const state = currentState(row, ref);
    const isAssignee = state.assigned_user_id === session.sub;
    if (!isAssignee) requireRole(session, "analyst");
    // ack+close in one flow exercises the ack privilege → analyst+.
    if (ackFirst && !roleAtLeast(session.role, "analyst")) {
      throw new AuthzError(403, "ack+close requires role analyst or above");
    }

    const next = closeTicket(row, ref, session.sub, note, ackFirst);
    logAction(session, "ticket.close", `${row.id}/${ref}`);

    const res: TicketActionResponse = { ticket_ref: ref, state: next };
    return NextResponse.json(res);
  } catch (err) {
    if (err instanceof TicketError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return authzResponse(err);
  }
}
