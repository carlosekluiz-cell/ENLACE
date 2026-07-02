// GET /api/tickets?audit=<id> — tickets for the current audit: agent ticket
// data (verbatim) JOINed with the ticket_state overlay. Tenant-scoped.
//
// Role scoping trims ROWS, never fields (ONTOLOGY.md §5): viewer sees only
// tickets assigned to them; analyst+ sees all. ?audit= accepts the audits
// row id or agent audit_id; default is the tenant's most recent audit.

import { NextRequest, NextResponse } from "next/server";
import { provenanceOf, resolveAuditRow, parseResult } from "@/lib/auditStore";
import { ticketsWithState } from "@/lib/ticketStore";
import { authzResponse, requireSession } from "@/lib/serverAuth";
import { roleAtLeast } from "@/lib/roles";
import type { ProjectionUnavailable, TicketListResponse } from "@/lib/opsTypes";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    const requested = req.nextUrl.searchParams.get("audit");

    const row = resolveAuditRow(session.tenant_id, requested);
    if (!row) {
      const body: ProjectionUnavailable = {
        available: false,
        reason: requested
          ? `no persisted audit "${requested}" for this tenant`
          : "no audit persisted for this tenant yet — upload a CSV or load the demo audit",
      };
      return NextResponse.json(body, { status: requested ? 404 : 200 });
    }

    const seeAll = roleAtLeast(session.role, "analyst");
    const tickets = ticketsWithState(
      row,
      seeAll ? undefined : { assignee: session.sub },
    );

    const body: TicketListResponse = {
      available: true,
      provenance: provenanceOf(row),
      import_report: parseResult(row)?.import_report ?? null,
      tickets,
    };
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
