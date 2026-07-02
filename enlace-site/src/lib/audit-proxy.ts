// Server-side helpers for the /api/audit proxy routes.
//
// IMPORTANT: this module reads PULSO_AUDIT_TOKEN and must only ever be
// imported from route handlers / server code — never from client components.

/** Mirrors the audit server's default body cap (PULSO_AUDIT_BODY_LIMIT_MB = 50). */
export const MAX_BODY_BYTES = 50 * 1024 * 1024;

/** Base URL of the pulso-agent audit server (loopback by default). */
export function auditServerUrl(): string {
  return (
    process.env.AUDIT_SERVER_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8080"
  );
}

/** Bearer-token header for the upstream audit server, if configured. */
export function authHeaders(): Record<string, string> {
  const token = process.env.PULSO_AUDIT_TOKEN;
  return token ? { authorization: `Bearer ${token}` } : {};
}

/** Clean JSON error response. Never include upstream/internal detail here. */
export function jsonError(
  status: number,
  error: string,
  message: string
): Response {
  return Response.json({ error, message }, { status });
}

export function payloadTooLarge(): Response {
  return jsonError(
    413,
    "payload_too_large",
    "File exceeds the 50 MB upload limit"
  );
}

/**
 * Pass an upstream response through with its status code, keeping only the
 * JSON body. If the upstream body is not valid JSON (proxy error pages,
 * etc.), replace it with a generic message so nothing internal leaks.
 */
export async function passThroughJson(upstream: Response): Promise<Response> {
  let text: string;
  try {
    text = await upstream.text();
  } catch {
    return jsonError(
      502,
      "upstream_error",
      "The audit service returned an unreadable response"
    );
  }

  try {
    JSON.parse(text);
  } catch {
    return jsonError(
      upstream.ok ? 502 : upstream.status,
      "upstream_error",
      "The audit service returned an unexpected response"
    );
  }

  return new Response(text, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
