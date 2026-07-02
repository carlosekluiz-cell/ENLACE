// POST /api/audit — server-side proxy to the pulso-agent audit server.
//
// The agent binds 127.0.0.1 and requires a bearer token; both stay on this
// side of the wire. The browser only ever talks to this route.
//
// Auth: analyst+ (ARCHITECTURE-TENANCY.md §2.2 — the NOC operator is the
// person with the OLT export in hand). On success the AuditResult is
// persisted VERBATIM in the app DB keyed (tenant_id, audit_id): the agent's
// in-memory store is a hot cache with a TTL; the DB row is the system of
// record, and provenance (source/uploader/agent_version) is a stored fact,
// not a UI guess. Nothing strips assumptions[] or import_report.

import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { db, tables } from "@/db";
import {
  authzResponse,
  logAction,
  requireRole,
  requireSession,
} from "@/lib/serverAuth";
import type { SessionClaims } from "@/lib/jwt";

const AUDIT_SERVER =
  process.env.PULSO_AUDIT_SERVER ?? "http://127.0.0.1:8080";

/** Best-effort agent version from GET /healthz — null when unreachable. */
async function agentVersion(): Promise<string | null> {
  try {
    const res = await fetch(`${AUDIT_SERVER}/healthz`);
    if (!res.ok) return null;
    const body = (await res.json()) as { version?: unknown };
    return typeof body.version === "string" ? body.version : null;
  } catch {
    return null;
  }
}

function persistAudit(
  session: SessionClaims,
  auditId: string,
  resultJson: string,
  version: string | null,
): void {
  db.insert(tables.audits)
    .values({
      id: randomUUID(),
      tenantId: session.tenant_id,
      auditId,
      source: "audit",
      uploaderUserId: session.sub,
      agentVersion: version,
      createdAt: new Date().toISOString(),
      resultJson,
    })
    .onConflictDoNothing()
    .run();
}

export async function POST(req: NextRequest) {
  let session: SessionClaims;
  try {
    session = await requireSession(req);
    requireRole(session, "analyst");
  } catch (err) {
    return authzResponse(err);
  }

  const token = process.env.PULSO_AUDIT_TOKEN;
  if (!token) {
    return NextResponse.json(
      {
        available: false,
        error:
          "audit server not configured — set PULSO_AUDIT_TOKEN (and PULSO_AUDIT_SERVER) in the app environment",
      },
      { status: 503 },
    );
  }

  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "expected multipart form data with a `file` field" },
      { status: 400 },
    );
  }
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "missing `file` field" }, { status: 400 });
  }

  const upstream = new FormData();
  upstream.append("file", file, file.name);

  try {
    const res = await fetch(`${AUDIT_SERVER}/audit`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: upstream,
    });
    const body = await res.text();

    if (res.ok) {
      // Persist verbatim: parse only to find audit_id / the result slice;
      // never reshape the agent's JSON.
      try {
        const parsed = JSON.parse(body) as { audit_id?: unknown; result?: unknown };
        if (typeof parsed.audit_id === "string" && parsed.result !== undefined) {
          persistAudit(
            session,
            parsed.audit_id,
            JSON.stringify(parsed.result),
            await agentVersion(),
          );
          logAction(session, "audit.upload", parsed.audit_id);
        }
      } catch (e) {
        // The upload itself succeeded — don't fail the response, but say so.
        console.error("[api/audit] failed to persist audit result:", e);
      }
    }

    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: `audit server unreachable at ${AUDIT_SERVER}` },
      { status: 502 },
    );
  }
}
