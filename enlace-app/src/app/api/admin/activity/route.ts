// GET /api/admin/activity — the audit_log, newest first (admin only).
//
// Query: ?action=<exact action> to filter, ?limit=<n> (default 200, max
// 1000). Returns entries with resolved user name/email plus the distinct
// action list for the filter dropdown. This is the accountability view:
// logins, uploads, ticket moves, user admin, settings changes, report
// generations — all in one tenant-scoped trail.

import { and, desc, eq, inArray } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import type { ActivityEntry, ActivityResponse } from "@/lib/adminTypes";
import {
  authzResponse,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";

export async function GET(req: NextRequest) {
  try {
    const session = await requireSession(req);
    requireRole(session, "admin");

    const actionFilter = req.nextUrl.searchParams.get("action");
    const limitRaw = Number(req.nextUrl.searchParams.get("limit") ?? "200");
    const limit = Number.isFinite(limitRaw)
      ? Math.min(Math.max(Math.trunc(limitRaw), 1), 1000)
      : 200;

    const where = actionFilter
      ? and(
          eq(tables.auditLog.tenantId, session.tenant_id),
          eq(tables.auditLog.action, actionFilter),
        )
      : eq(tables.auditLog.tenantId, session.tenant_id);

    const rows = db
      .select()
      .from(tables.auditLog)
      .where(where)
      .orderBy(desc(tables.auditLog.at), desc(tables.auditLog.id))
      .limit(limit)
      .all();

    // Resolve actor names in one query.
    const userIds = [...new Set(rows.map((r) => r.userId).filter((v): v is string => v !== null))];
    const users =
      userIds.length === 0
        ? []
        : db
            .select({
              id: tables.users.id,
              name: tables.users.name,
              email: tables.users.email,
            })
            .from(tables.users)
            .where(inArray(tables.users.id, userIds))
            .all();
    const byId = new Map(users.map((u) => [u.id, u]));

    // Distinct actions across the tenant (for the filter dropdown).
    const actionRows = db
      .selectDistinct({ action: tables.auditLog.action })
      .from(tables.auditLog)
      .where(eq(tables.auditLog.tenantId, session.tenant_id))
      .all();

    const entries: ActivityEntry[] = rows.map((r) => {
      const u = r.userId ? byId.get(r.userId) : undefined;
      return {
        id: r.id,
        user_id: r.userId,
        user_name: u?.name ?? null,
        user_email: u?.email ?? null,
        action: r.action,
        subject: r.subject,
        at: r.at,
      };
    });

    const res: ActivityResponse = {
      entries,
      actions: actionRows.map((a) => a.action).sort(),
      total: entries.length,
    };
    return NextResponse.json(res);
  } catch (err) {
    return authzResponse(err);
  }
}
