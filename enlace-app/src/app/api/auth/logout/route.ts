// POST /api/auth/logout — revoke the session (jti denylist) + clear cookie.
//
// Idempotent and forgiving: an absent or invalid cookie still gets a
// cleared cookie and a 200 (the caller's goal is "be logged out").

import { eq } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/jwt";

export async function POST(req: NextRequest) {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    const claims = await verifySessionToken(token);
    if (claims) {
      const now = new Date().toISOString();
      db.update(tables.sessions)
        .set({ revokedAt: now })
        .where(eq(tables.sessions.jti, claims.jti))
        .run();
      db.insert(tables.auditLog)
        .values({
          tenantId: claims.tenant_id,
          userId: claims.sub,
          action: "auth.logout",
          subject: null,
          at: now,
        })
        .run();
    }
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return res;
}
