// GET /api/reports/audit/[id].pdf — server-rendered executive audit report.
//
// Auth: manager+ (exec lens), tenant-scoped: the id (audits row id or agent
// audit_id, with or without the .pdf suffix) resolves ONLY within the
// session's tenant. Each generation is logged to audit_log.
//
// The PDF is built from the persisted AuditResult + provenance + the
// ticket_state overlay (src/lib/report.ts) — honesty invariants included:
// estimate labels, coverage notes, and the mandatory Data honesty page.

import { NextRequest, NextResponse } from "next/server";
import { findAuditRow, parseResult, provenanceOf } from "@/lib/auditStore";
import { buildAuditReport } from "@/lib/report";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";
import { getTenantInfo, tenantAssumptionLines } from "@/lib/tenantSettings";
import { ticketsWithState } from "@/lib/ticketStore";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  try {
    const session = await requireSession(req);
    requireRole(session, "manager");

    const { id: rawId } = await ctx.params;
    const id = rawId.replace(/\.pdf$/i, "");
    if (!id) {
      return NextResponse.json({ error: "audit id required" }, { status: 400 });
    }

    const row = findAuditRow(session.tenant_id, id);
    if (!row) {
      return NextResponse.json(
        { error: `no persisted audit "${id}" for this tenant` },
        { status: 404 },
      );
    }
    const result = parseResult(row);
    if (!result) {
      return NextResponse.json(
        { error: `stored audit ${row.id} failed to parse — integrity error` },
        { status: 500 },
      );
    }

    const tenant = getTenantInfo(session.tenant_id);
    const pdf = await buildAuditReport({
      tenantName: tenant?.name ?? session.tenant_id,
      tenantAssumptionLines: tenant ? tenantAssumptionLines(tenant.assumptions) : [],
      provenance: provenanceOf(row),
      result,
      tickets: ticketsWithState(row),
      generatedBy: session.name,
      generatedAt: new Date().toISOString(),
    });

    logAction(session, "report.generate", `${row.id} (${pdf.length} bytes)`);

    const safeName = row.auditId.replace(/[^A-Za-z0-9._-]+/g, "-");
    return new NextResponse(new Uint8Array(pdf), {
      status: 200,
      headers: {
        "content-type": "application/pdf",
        "content-length": String(pdf.length),
        "content-disposition": `attachment; filename="enlace-audit-${safeName}.pdf"`,
        "cache-control": "no-store",
      },
    });
  } catch (err) {
    return authzResponse(err);
  }
}
