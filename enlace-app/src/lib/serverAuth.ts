// ── Server-side session helpers for API routes ──
//
// requireSession: cookie JWT → verified claims → sessions-table check
// (jti present, not revoked, not expired). requireRole: role floor on the
// claims. Both throw AuthzError; routes convert via authzResponse().
//
// Middleware already rejects unauthenticated requests, but routes re-check
// here because middleware cannot see the DB (revocation) and defense in
// depth is the point of server-side enforcement.

import { and, eq, isNull } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import { SESSION_COOKIE, verifySessionToken, type SessionClaims } from "@/lib/jwt";
import { roleAtLeast, type Role } from "@/lib/roles";

export class AuthzError extends Error {
  constructor(
    public readonly status: 401 | 403,
    message: string,
  ) {
    super(message);
    this.name = "AuthzError";
  }
}

/** Verified, non-revoked session or null — no throw. */
export async function readSession(
  req: NextRequest,
): Promise<SessionClaims | null> {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const claims = await verifySessionToken(token);
  if (!claims) return null;

  const rows = db
    .select({ expiresAt: tables.sessions.expiresAt })
    .from(tables.sessions)
    .where(
      and(
        eq(tables.sessions.jti, claims.jti),
        isNull(tables.sessions.revokedAt),
      ),
    )
    .all();
  const row = rows[0];
  if (!row) return null;
  if (new Date(row.expiresAt).getTime() <= Date.now()) return null;
  return claims;
}

export async function requireSession(req: NextRequest): Promise<SessionClaims> {
  const session = await readSession(req);
  if (!session) throw new AuthzError(401, "authentication required");
  return session;
}

export function requireRole(session: SessionClaims, min: Role): void {
  if (!roleAtLeast(session.role, min)) {
    throw new AuthzError(
      403,
      `requires role ${min} or above (session role: ${session.role})`,
    );
  }
}

/** Convert an unknown thrown value into a JSON error response. */
export function authzResponse(err: unknown): NextResponse {
  if (err instanceof AuthzError) {
    return NextResponse.json({ error: err.message }, { status: err.status });
  }
  return NextResponse.json({ error: "internal error" }, { status: 500 });
}

/** Append-only action trail. Best-effort: never fails the request. */
export function logAction(
  session: SessionClaims,
  action: string,
  subject?: string,
): void {
  try {
    db.insert(tables.auditLog)
      .values({
        tenantId: session.tenant_id,
        userId: session.sub,
        action,
        subject: subject ?? null,
        at: new Date().toISOString(),
      })
      .run();
  } catch (e) {
    console.warn("[enlace-auth] audit_log write failed:", e);
  }
}
