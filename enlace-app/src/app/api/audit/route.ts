// POST /api/audit — server-side proxy to the pulso-agent audit server.
//
// The agent binds 127.0.0.1 and requires a bearer token; both stay on this
// side of the wire. The browser only ever talks to this route.

import { NextRequest, NextResponse } from "next/server";

const AUDIT_SERVER =
  process.env.PULSO_AUDIT_SERVER ?? "http://127.0.0.1:8080";

export async function POST(req: NextRequest) {
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
