// PATCH /api/admin/users/[id] — mutate one tenant user (admin only).
//
// Body (any subset):
//   { disabled: boolean }        disable/enable (self-lockout blocked;
//                                disabling also revokes the user's sessions)
//   { reset_password: true }     new temp password, returned ONCE
//   { role: Role }               role change (self-demotion blocked)
//
// Tenant-scoped; every mutation writes audit_log. Password hashes never
// leave the server.

import { randomBytes } from "node:crypto";
import { and, eq, isNull } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import {
  toAdminUserEntry,
  type AdminUserMutationResponse,
} from "@/lib/adminTypes";
import { hashPassword } from "@/lib/password";
import { ROLES, type Role } from "@/lib/roles";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");
    const { id } = await ctx.params;

    const user = db
      .select()
      .from(tables.users)
      .where(
        and(eq(tables.users.id, id), eq(tables.users.tenantId, session.tenant_id)),
      )
      .all()[0];
    if (!user) {
      return NextResponse.json({ error: "no such user in this tenant" }, { status: 404 });
    }

    const body = (await req.json().catch(() => ({}))) as {
      disabled?: unknown;
      reset_password?: unknown;
      role?: unknown;
    };

    let tempPassword: string | undefined;
    const actions: string[] = [];

    if (typeof body.disabled === "boolean") {
      if (user.id === session.sub && body.disabled) {
        return NextResponse.json(
          { error: "you cannot disable your own account" },
          { status: 400 },
        );
      }
      db.update(tables.users)
        .set({ disabled: body.disabled ? 1 : 0 })
        .where(eq(tables.users.id, user.id))
        .run();
      if (body.disabled) {
        // Kill active sessions so the disable takes effect immediately.
        db.update(tables.sessions)
          .set({ revokedAt: new Date().toISOString() })
          .where(
            and(
              eq(tables.sessions.userId, user.id),
              isNull(tables.sessions.revokedAt),
            ),
          )
          .run();
      }
      const action = body.disabled ? "admin.user.disable" : "admin.user.enable";
      logAction(session, action, user.email);
      actions.push(action);
    }

    if (body.reset_password === true) {
      tempPassword = `enlace-${randomBytes(9).toString("base64url")}`;
      const passwordHash = await hashPassword(tempPassword);
      db.update(tables.users)
        .set({ passwordHash })
        .where(eq(tables.users.id, user.id))
        .run();
      logAction(session, "admin.user.reset_password", user.email);
      actions.push("admin.user.reset_password");
    }

    if (typeof body.role === "string") {
      if (!(ROLES as readonly string[]).includes(body.role)) {
        return NextResponse.json(
          { error: `role must be one of: ${ROLES.join(", ")}` },
          { status: 400 },
        );
      }
      if (user.id === session.sub && body.role !== "admin") {
        return NextResponse.json(
          { error: "you cannot remove your own admin role" },
          { status: 400 },
        );
      }
      db.update(tables.users)
        .set({ role: body.role as Role })
        .where(eq(tables.users.id, user.id))
        .run();
      logAction(session, "admin.user.role", `${user.email} → ${body.role}`);
      actions.push("admin.user.role");
    }

    if (actions.length === 0) {
      return NextResponse.json(
        { error: "nothing to do — send disabled, reset_password and/or role" },
        { status: 400 },
      );
    }

    const updated = db
      .select()
      .from(tables.users)
      .where(eq(tables.users.id, user.id))
      .all()[0];
    const res: AdminUserMutationResponse = {
      user: toAdminUserEntry(updated),
      ...(tempPassword ? { temp_password: tempPassword } : {}),
    };
    return NextResponse.json(res);
  } catch (err) {
    return authzResponse(err);
  }
}
