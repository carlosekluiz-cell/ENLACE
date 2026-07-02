// GET /api/audits/[id] — full stored AuditResult + provenance envelope.
//
// Returns { provenance: {…}, result: <verbatim AuditResult> } from the app
// DB (system of record), tenant-scoped. Accepts the audits row id or the
// agent audit_id. The result is the stored JSON, untouched: assumptions[],
// import_report and coverage notes always travel with it.

import { NextRequest, NextResponse } from "next/server";
import { findAuditRow, provenanceOf } from "@/lib/auditStore";
import { authzResponse, requireSession } from "@/lib/serverAuth";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  try {
    const session = await requireSession(req);
    const { id } = await ctx.params;

    const row = findAuditRow(session.tenant_id, id);
    if (!row) {
      return NextResponse.json(
        { error: `no persisted audit "${id}" for this tenant` },
        { status: 404 },
      );
    }

    // Splice the verbatim stored JSON into the envelope without re-parsing.
    const envelope = `{"provenance":${JSON.stringify(provenanceOf(row))},"result":${row.resultJson}}`;
    return new NextResponse(envelope, {
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    return authzResponse(err);
  }
}
