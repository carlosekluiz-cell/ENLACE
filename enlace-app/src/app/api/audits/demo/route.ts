// POST /api/audits/demo — persist the bundled demo fixture as an audits row.
//
// The fixture (src/demo/audit-demo.json) is REAL agent output, unedited
// (see DEMO_PROVENANCE). Inserting it with source='demo' lets every view run
// entirely on persisted data while the source badge stays honest: DEMO.
// Idempotent per tenant — re-posting returns the existing row.
//
// Auth: analyst+ (same floor as uploading an audit).

import { NextRequest, NextResponse } from "next/server";
import { insertDemoAudit, provenanceOf } from "@/lib/auditStore";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";

export async function POST(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "analyst");

    const { row, created } = insertDemoAudit(session.tenant_id, session.sub);
    if (created) logAction(session, "audit.load_demo", row.id);

    return NextResponse.json(
      { created, provenance: provenanceOf(row) },
      { status: created ? 201 : 200 },
    );
  } catch (err) {
    return authzResponse(err);
  }
}
