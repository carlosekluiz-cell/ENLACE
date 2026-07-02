// GET /api/projections/exec?audit=<id> — executive rollup lens: health
// score, status triple, revenue-at-risk WITH its estimate label and the
// declared assumptions, capacity, churn cohort, and an honest-empty trend
// placeholder. import_report travels with it, as everywhere.
//
// Auth: manager+ (network manager / director lens).

import { NextRequest, NextResponse } from "next/server";
import { execProjection } from "@/lib/projections";
import { authzResponse, requireRole, requireSession } from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "manager");
    const body = execProjection(session, req.nextUrl.searchParams.get("audit"));
    return NextResponse.json(body);
  } catch (err) {
    return authzResponse(err);
  }
}
