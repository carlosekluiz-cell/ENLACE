// ── WhatsApp job dispatch: deep link + share text (Wave C1) ──
//
// HONESTY: this is *share-to-WhatsApp* via the public wa.me URL scheme —
// it opens the sender's own WhatsApp with a prefilled message. It is NOT
// the WhatsApp Business API (no server-side sending, no delivery receipts).
// Label it as such wherever it appears.
//
// Pure module (no DOM, no DB, no next imports): used by the supervisor
// board, the field ticket page, and server-side e2e assertions alike.

import type { TicketLocation, TicketWithState } from "@/lib/opsTypes";

/**
 * Public base URL of this deployment, for links that leave the app (WhatsApp
 * messages open on a phone, not in this browser). Build-time inlined on the
 * client (NEXT_PUBLIC_*); defaults to the dev origin. Documented in
 * .env.example.
 */
export function appBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  return raw.replace(/\/+$/, "");
}

/**
 * Shareable deep link to a ticket: pins BOTH the ticket ref and the audit
 * row id, so the link opens the same ticket regardless of which audit is
 * "latest" by the time the engineer taps it. Unauthenticated opens go
 * through login and land back here (middleware `next=` redirect).
 */
export function ticketDeepLink(
  ticketRef: string,
  auditRowId: string,
  baseUrl: string = appBaseUrl(),
): string {
  return `${baseUrl}/field/ticket/${encodeURIComponent(ticketRef)}?audit=${encodeURIComponent(auditRowId)}`;
}

export function googleMapsUrl(lat: number, lon: number): string {
  return `https://maps.google.com/?q=${lat},${lon}`;
}

/**
 * The location line for the share message — or null when the audit honestly
 * has no location data (the message then omits the line rather than padding
 * it with a guess).
 */
export function shareLocationLine(location: TicketLocation): string | null {
  if (location.kind === "coordinates" && location.coordinates) {
    const { lat, lon } = location.coordinates;
    return `Location: ${googleMapsUrl(lat, lon)}`;
  }
  if (location.kind === "distance-estimate" && location.distance_m_range) {
    const { min, max } = location.distance_m_range;
    const range = min === max ? `~${min} m` : `~${min}–${max} m`;
    const port = location.pon_port ? ` on ${location.pon_port}` : "";
    return `Location: est. ${range} of fibre from the OLT${port} (ONT ranging estimate)`;
  }
  return null;
}

/**
 * The dispatch message: ticket ref, priority + SLA, fault type, short
 * summary, location line (omitted when unknown), and the deep link.
 */
export function ticketShareText(t: TicketWithState, deepLink: string): string {
  const { ticket } = t;
  const due = new Date(t.sla_due);
  const dueStr = Number.isNaN(due.getTime())
    ? null
    : due.toLocaleDateString("en-GB");

  const lines: string[] = [
    `ENLACE job dispatch — ${t.ticket_ref}`,
    `Priority ${ticket.priority} · SLA ${ticket.sla_days} day${ticket.sla_days === 1 ? "" : "s"}${dueStr ? ` (due ${dueStr})` : ""}`,
    `Fault: ${ticket.fault_type} · ${ticket.affected_ont_count} ONT${ticket.affected_ont_count === 1 ? "" : "s"} affected · team ${ticket.team}`,
    ticket.recommended_action,
  ];

  const locationLine = shareLocationLine(t.location);
  if (locationLine) lines.push(locationLine);

  lines.push(`Open job: ${deepLink}`);
  return lines.join("\n");
}

/**
 * wa.me share URL. With a phone number the chat opens directly with that
 * engineer; without one, WhatsApp asks the sender to pick a contact.
 * (Share-to-WhatsApp, not the Business API.)
 */
export function waShareUrl(text: string, phone?: string | null): string {
  const digits = phone ? phone.replace(/\D/g, "") : "";
  const base = digits ? `https://wa.me/${digits}` : "https://wa.me/";
  return `${base}?text=${encodeURIComponent(text)}`;
}
