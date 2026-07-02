// GET /api/audit/[id] — server-side proxy to the pulso-agent audit server,
// injecting the bearer token. Token and bind address never reach the browser.

import { NextRequest, NextResponse } from "next/server";

const AUDIT_SERVER =
  process.env.PULSO_AUDIT_SERVER ?? "http://127.0.0.1:8080";

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const token = process.env.PULSO_AUDIT_TOKEN;
  if (!token) {
    return NextResponse.json(
      {
        available: false,
        error: "audit server not configured — set PULSO_AUDIT_TOKEN in the app environment",
      },
      { status: 503 },
    );
  }

  const { id } = await ctx.params;
  if (!/^[A-Za-z0-9-]{1,64}$/.test(id)) {
    return NextResponse.json({ error: "invalid audit id" }, { status: 400 });
  }

  try {
    const res = await fetch(`${AUDIT_SERVER}/audit/${encodeURIComponent(id)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await res.text();
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
