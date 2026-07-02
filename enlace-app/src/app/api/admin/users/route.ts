// /api/admin/users — tenant user administration (admin only).
//
//   GET  → list tenant users (never returns password hashes).
//   POST → create/invite: { email, name, role, persona } — the server
//          generates a temp password, returns it ONCE, stores only the hash.
//
// Tenant-scoped from the session claims (never from the request); every
// mutation writes audit_log (this is the accountability trail /admin/activity
// renders).

import { randomBytes, randomUUID } from "node:crypto";
import { asc, eq } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import { toAdminUserEntry, type AdminUsersResponse } from "@/lib/adminTypes";
import { hashPassword } from "@/lib/password";
import { personaById, ROLES, type Role } from "@/lib/roles";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");

    const rows = db
      .select()
      .from(tables.users)
      .where(eq(tables.users.tenantId, session.tenant_id))
      .orderBy(asc(tables.users.createdAt), asc(tables.users.email))
      .all();

    const res: AdminUsersResponse = { users: rows.map(toAdminUserEntry) };
    return NextResponse.json(res);
  } catch (err) {
    return authzResponse(err);
  }
}

export async function POST(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");

    const body = (await req.json().catch(() => ({}))) as {
      email?: unknown;
      name?: unknown;
      role?: unknown;
      persona?: unknown;
    };
    const email =
      typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
    const name = typeof body.name === "string" ? body.name.trim() : "";
    const role = typeof body.role === "string" ? body.role : "";
    const persona = typeof body.persona === "string" ? body.persona : "";

    if (!email || !email.includes("@")) {
      return NextResponse.json({ error: "a valid email is required" }, { status: 400 });
    }
    if (!name) {
      return NextResponse.json({ error: "name is required" }, { status: 400 });
    }
    if (!(ROLES as readonly string[]).includes(role)) {
      return NextResponse.json(
        { error: `role must be one of: ${ROLES.join(", ")}` },
        { status: 400 },
      );
    }
    if (!personaById(persona)) {
      return NextResponse.json({ error: `unknown persona "${persona}"` }, { status: 400 });
    }

    const duplicate = db
      .select({ id: tables.users.id })
      .from(tables.users)
      .where(eq(tables.users.email, email))
      .all()[0];
    if (duplicate) {
      return NextResponse.json(
        { error: `a user with email ${email} already exists` },
        { status: 409 },
      );
    }

    // Temp password: shown once in the response, stored only as a hash.
    const tempPassword = `enlace-${randomBytes(9).toString("base64url")}`;
    const passwordHash = await hashPassword(tempPassword);
    const now = new Date().toISOString();
    const id = `u-${randomUUID()}`;

    db.insert(tables.users)
      .values({
        id,
        tenantId: session.tenant_id,
        email,
        name,
        passwordHash,
        role: role as Role,
        persona,
        createdAt: now,
        disabled: 0,
      })
      .run();

    logAction(session, "admin.user.create", `${email} role=${role} persona=${persona}`);

    const row = db.select().from(tables.users).where(eq(tables.users.id, id)).all()[0];
    return NextResponse.json(
      { user: toAdminUserEntry(row), temp_password: tempPassword },
      { status: 201 },
    );
  } catch (err) {
    return authzResponse(err);
  }
}
