// GET /api/projections/field?audit=<id> — "my jobs" lens: tickets assigned
// to the logged-in user, each with full evidence and assumptions (rows are
// subset; fields never are).
//
// Auth: any authenticated session (viewer+ — the field engineer's own lens).

import { NextRequest, NextResponse } from "next/server";
import { fieldProjection } from "@/lib/projections";
import { authzResponse, requireSession } from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    const body = fieldProjection(session, req.nextUrl.searchParams.get("audit"));
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
