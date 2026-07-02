// GET /api/audit/[id] — server-side proxy to the pulso-agent audit server.
//
// Fetches a previously computed audit result. Auth token is attached here,
// server-side, so it never ships to the browser.

import {
  auditServerUrl,
  authHeaders,
  jsonError,
  passThroughJson,
} from "@/lib/audit-proxy";

// Audit ids are UUIDs; reject anything else before it touches the upstream.
const AUDIT_ID_RE = /^[0-9a-fA-F-]{1,64}$/;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!AUDIT_ID_RE.test(id)) {
    return jsonError(400, "invalid_id", "Malformed audit id");
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${auditServerUrl()}/audit/${encodeURIComponent(id)}`,
      {
        headers: authHeaders(),
        cache: "no-store",
      }
    );
  } catch {
    return jsonError(
      502,
      "audit_service_unreachable",
      "Could not reach the audit service. Please try again shortly."
    );
  }

  return passThroughJson(upstream);
}
