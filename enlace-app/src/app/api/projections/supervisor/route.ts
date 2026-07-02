// GET /api/projections/supervisor?audit=<id> — dispatch-board lens: full
// ticket queue (with state + SLA aging) and the dispatchable team
// (tenant users with role viewer/analyst).
//
// Auth: manager+ (cross-team queues, dispatch).

import { NextRequest, NextResponse } from "next/server";
import { supervisorProjection } from "@/lib/projections";
import { authzResponse, requireRole, requireSession } from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "manager");
    const body = supervisorProjection(
      session,
      req.nextUrl.searchParams.get("audit"),
    );
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
