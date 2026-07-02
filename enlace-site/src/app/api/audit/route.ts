// POST /api/audit — server-side proxy to the pulso-agent audit server.
//
// The audit server requires `Authorization: Bearer <PULSO_AUDIT_TOKEN>` and
// binds 127.0.0.1 by default, so browsers can't (and must not) call it
// directly: the token stays on this server and never reaches the client.

import {
  MAX_BODY_BYTES,
  auditServerUrl,
  authHeaders,
  jsonError,
  passThroughJson,
  payloadTooLarge,
} from "@/lib/audit-proxy";

export async function POST(request: Request) {
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("multipart/form-data")) {
    return jsonError(
      400,
      "invalid_content_type",
      "Expected a multipart/form-data upload"
    );
  }

  // Mirror the audit server's 50 MB body cap. Check the declared length
  // first so oversized uploads fail fast, then verify the actual bytes.
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    return payloadTooLarge();
  }

  let body: ArrayBuffer;
  try {
    body = await request.arrayBuffer();
  } catch {
    return jsonError(400, "read_error", "Could not read the upload body");
  }
  if (body.byteLength > MAX_BODY_BYTES) {
    return payloadTooLarge();
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${auditServerUrl()}/audit`, {
      method: "POST",
      // Forward the original content-type so the multipart boundary survives.
      headers: { "content-type": contentType, ...authHeaders() },
      body,
      cache: "no-store",
    });
  } catch {
    return jsonError(
      502,
      "audit_service_unreachable",
      "Could not reach the audit service. Please try again shortly."
    );
  }

  return passThroughJson(upstream);
}
