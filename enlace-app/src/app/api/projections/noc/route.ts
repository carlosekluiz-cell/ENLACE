// GET /api/projections/noc?audit=<id> — NOC lens over the persisted audit.
//
// Auth: analyst+ (fleet visibility). Computed server-side from the app-DB
// row — never from client-shipped JSON. Includes faults, the ONT table,
// the frontier sections (fec_health / laser_health / rogue) with their
// coverage notes, all tickets with state (ack from the fault list), and
// import_report banner data. See src/lib/projections.ts for the invariants.

import { NextRequest, NextResponse } from "next/server";
import { nocProjection } from "@/lib/projections";
import { authzResponse, requireRole, requireSession } from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "analyst");
    const body = nocProjection(session, req.nextUrl.searchParams.get("audit"));
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
