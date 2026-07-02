// POST /api/auth/login — { email, password } → httpOnly session cookie.
//
// In-house JWT issuer (ARCHITECTURE-TENANCY.md §2.4): argon2id-hashed
// passwords in the app DB, HS256 JWT via jose, jti recorded in the sessions
// table so logout can revoke. tenant_id comes from the user row — never
// from the request.

import { randomUUID } from "node:crypto";
import { eq } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import {
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  signSessionToken,
  type SessionClaims,
} from "@/lib/jwt";
import { verifyPassword } from "@/lib/password";
import { type PersonaId, type Role } from "@/lib/roles";

export async function POST(req: NextRequest) {
  let body: { email?: unknown; password?: unknown };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "expected JSON body" }, { status: 400 });
  }
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const password = typeof body.password === "string" ? body.password : "";
  if (!email || !password) {
    return NextResponse.json(
      { error: "email and password are required" },
      { status: 400 },
    );
  }

  // Single-tenant deploy: email lookup is global (unique per tenant; one
  // tenant per deploy). Shape 2 adds a tenant discriminator here.
  const user = db
    .select()
    .from(tables.users)
    .where(eq(tables.users.email, email))
    .all()[0];

  // Uniform error for unknown email vs wrong password.
  const invalid = NextResponse.json(
    { error: "invalid email or password" },
    { status: 401 },
  );
  if (!user || user.disabled) return invalid;
  if (!(await verifyPassword(user.passwordHash, password))) return invalid;

  const now = new Date();
  const jti = randomUUID();
  const expiresAt = new Date(now.getTime() + SESSION_TTL_SECONDS * 1000);

  db.insert(tables.sessions)
    .values({
      jti,
      userId: user.id,
      tenantId: user.tenantId,
      createdAt: now.toISOString(),
      expiresAt: expiresAt.toISOString(),
      revokedAt: null,
    })
    .run();
  db.insert(tables.auditLog)
    .values({
      tenantId: user.tenantId,
      userId: user.id,
      action: "auth.login",
      subject: email,
      at: now.toISOString(),
    })
    .run();

  const claims: SessionClaims = {
    sub: user.id,
    name: user.name,
    tenant_id: user.tenantId,
    role: user.role as Role,
    persona: user.persona as PersonaId,
    jti,
  };
  const token = await signSessionToken(claims);

  const res = NextResponse.json({
    session: {
      sub: claims.sub,
      name: claims.name,
      tenant_id: claims.tenant_id,
      role: claims.role,
      persona: claims.persona,
    },
  });
  res.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return res;
}
