// GET /api/auth/session — current verified claims for the client.
//
// Public path in the middleware (the login page needs to ask "am I logged
// in?" before a session exists), but the answer itself is fully verified:
// JWT signature + expiry + sessions-table revocation check.

import { NextRequest, NextResponse } from "next/server";
import { readSession } from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  const session = await readSession(req);
  if (!session) {
    return NextResponse.json({ error: "no active session" }, { status: 401 });
  }
  return NextResponse.json({
    session: {
      sub: session.sub,
      name: session.name,
      tenant_id: session.tenant_id,
      role: session.role,
      persona: session.persona,
    },
  });
}
