// GET /api/audits — tenant-scoped audit listing (any authenticated session).
//
// Replaces the localStorage last-audit-id hack: "current audit" is resolved
// from this list (most recent by default, selectable via the audit picker).
// Each entry carries stored provenance (source/uploader/agent_version) and a
// small summary EXTRACTED server-side from result_json — the stored JSON is
// never mutated.

import { NextRequest, NextResponse } from "next/server";
import { listAudits } from "@/lib/auditStore";
import { authzResponse, requireSession } from "@/lib/serverAuth";
import type { AuditListResponse } from "@/lib/opsTypes";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    const body: AuditListResponse = { audits: listAudits(session.tenant_id) };
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
