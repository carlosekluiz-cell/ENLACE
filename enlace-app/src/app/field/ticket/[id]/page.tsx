"use client";

// /field/ticket/[id] — ticket detail: agent evidence + ALWAYS-VISIBLE
// assumptions, priority/SLA, lifecycle state (ack info, assignment), the
// persisted close-out form (note + confirm), the server-derived location
// card (distance estimate / map when real coordinates exist / honest empty
// state), and share-to-WhatsApp dispatch (Wave C1/C2).
// Data: GET /api/tickets (role-scoped rows) — never shipped JSON.
// Deep links: ?audit=<row id> pins the audit so a WhatsApp link opens the
// exact ticket even after newer audits land.

import { Suspense, useMemo, useState, type FormEvent } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, CheckCircle2, ExternalLink, MapPin, Share2 } from "lucide-react";
import { RoleGuard, useAuth } from "@/lib/auth";
import { daysUntil, fmtDate, fmtMoney, severityColor, slaDue } from "@/lib/format";
import { roleAtLeast } from "@/lib/roles";
import type { TicketListResponse, TicketLocation, TicketWithState } from "@/lib/opsTypes";
import { googleMapsUrl } from "@/lib/shareTicket";
import { closeTicketAction, useTicketList } from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import AssumptionBadge from "@/components/AssumptionBadge";
import NoAuditState from "@/components/NoAuditState";
import ShareTicketActions from "@/components/ShareTicketActions";
import TicketStatusPill from "@/components/TicketStatusPill";

// maplibre touches browser APIs — load it client-side only, and only when a
// ticket genuinely has coordinates.
const TicketLocationMap = dynamic(
  () => import("@/components/TicketLocationMap"),
  { ssr: false },
);

/**
 * Location card driven by the SERVER-derived location object. Three honest
 * shapes: real coordinates → map + Google Maps link; ONT ranging data →
 * distance estimate labeled as an estimate; nothing → say so.
 */
function LocationSection({ location }: { location: TicketLocation }) {
  return (
    <div className="op-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <MapPin size={14} style={{ color: "var(--text-on-dark-muted)" }} />
        <span className="op-label">location</span>
        {location.kind === "distance-estimate" && (
          <span
            className="font-mono text-[10px] px-1.5 py-0.5"
            style={{ border: "1px dashed var(--status-warn)", color: "var(--status-warn)" }}
          >
            estimated
          </span>
        )}
      </div>

      {location.kind === "coordinates" && location.coordinates && (
        <div className="flex flex-col gap-2">
          <TicketLocationMap
            lat={location.coordinates.lat}
            lon={location.coordinates.lon}
            label={location.coordinates.label}
          />
          <p className="text-sm" style={{ color: "var(--text-on-dark-secondary)" }}>
            {location.summary}
          </p>
          <a
            href={googleMapsUrl(location.coordinates.lat, location.coordinates.lon)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-xs"
            style={{ color: "var(--accent-hover)" }}
          >
            <ExternalLink size={12} />
            Open in Google Maps
          </a>
        </div>
      )}

      {location.kind === "distance-estimate" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm" style={{ color: "var(--text-on-dark-secondary)" }}>
            {location.summary}
          </p>
          {location.evidence.length > 0 && (
            <ul className="flex flex-col gap-1">
              {location.evidence.map((line) => (
                <li
                  key={line}
                  className="font-mono text-[11px]"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {line}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {location.kind === "none" && (
        <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          {location.summary}
        </p>
      )}
    </div>
  );
}

/** Share-to-WhatsApp dispatch + copy link (honest: not the Business API). */
function ShareSection({
  t,
  auditRowId,
}: {
  t: TicketWithState;
  auditRowId: string;
}) {
  return (
    <div className="op-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <Share2 size={14} style={{ color: "var(--text-on-dark-muted)" }} />
        <span className="op-label">share job</span>
      </div>
      <ShareTicketActions t={t} auditRowId={auditRowId} />
      <p className="mt-2 font-mono text-[10px]" style={{ color: "var(--text-on-dark-muted)" }}>
        opens your WhatsApp with the dispatch message prefilled
        (share-to-WhatsApp, not the Business API) — the link pins this ticket
        and audit, and survives login
      </p>
    </div>
  );
}

/** Lifecycle state card: who acked, who it's assigned to, close record. */
function StateSection({ t }: { t: TicketWithState }) {
  const s = t.state;
  return (
    <div className="op-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="op-label">lifecycle</span>
        <TicketStatusPill status={s.status} />
      </div>
      <div className="flex flex-col gap-1 font-mono text-[11px]" style={{ color: "var(--text-on-dark-secondary)" }}>
        <span>
          acknowledged:{" "}
          {s.acked_at
            ? `${s.acked_by_name ?? s.acked_by} · ${fmtDate(s.acked_at)}`
            : "not yet"}
        </span>
        <span>
          assigned to:{" "}
          {s.assigned_user_id ? (s.assigned_user_name ?? s.assigned_user_id) : "unassigned"}
        </span>
        {s.status === "closed" && (
          <>
            <span style={{ color: "var(--status-online)" }}>
              closed: {s.closed_by_name ?? s.closed_by} ·{" "}
              {s.closed_at ? fmtDate(s.closed_at) : ""}
            </span>
            <span style={{ color: "var(--text-on-dark)" }}>
              close-out note: {s.close_note}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

/** Persisted close-out form: note + confirm. */
function CloseOutForm({
  t,
  auditRowId,
  canClose,
  isOpenNeedsAck,
}: {
  t: TicketWithState;
  auditRowId: string;
  canClose: boolean;
  isOpenNeedsAck: boolean;
}) {
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (t.state.status === "closed") return null;

  if (!canClose) {
    return (
      <p className="font-mono text-[11px]" style={{ color: "var(--text-on-dark-muted)" }}>
        close-out is available to the assigned engineer (own ticket) or to
        analyst+ roles — this ticket is{" "}
        {t.state.assigned_user_name
          ? `assigned to ${t.state.assigned_user_name}`
          : "unassigned"}
      </p>
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    closeTicketAction(t.ticket_ref, auditRowId, note, isOpenNeedsAck).catch(
      (err: unknown) => {
        setError(err instanceof Error ? err.message : "close failed");
        setBusy(false);
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="op-card p-4 flex flex-col gap-3">
      <span className="op-label">close out ticket</span>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        required
        rows={3}
        placeholder="What was found and done on site? (required close-out note)"
        className="enlace-input-dark font-mono text-xs"
        style={{ resize: "vertical" }}
      />
      <label
        className="flex items-center gap-2 text-xs cursor-pointer"
        style={{ color: "var(--text-on-dark-secondary)" }}
      >
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        I confirm the work is complete and the note above is accurate
      </label>
      {error && (
        <p className="font-mono text-xs" style={{ color: "var(--danger)" }} role="alert">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy || !note.trim() || !confirmed}
        className="enlace-btn-primary disabled:opacity-50"
      >
        <CheckCircle2 size={16} className="mr-2" />
        {busy
          ? "closing…"
          : isOpenNeedsAck
            ? "Acknowledge & close out"
            : "Close out ticket"}
      </button>
    </form>
  );
}

function TicketDetail() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const { session } = useAuth();
  // ?audit= (from a shared deep link) pins the audit explicitly.
  const { data, unavailable, meta, loading, error } =
    useTicketList<TicketListResponse>(searchParams.get("audit"));

  const entry = useMemo(() => {
    const id = decodeURIComponent(params.id ?? "");
    return data?.tickets.find((t) => t.ticket_ref === id);
  }, [data, params.id]);

  const canClose =
    !!entry &&
    !!session &&
    (entry.state.assigned_user_id === session.sub ||
      roleAtLeast(session.role, "analyst"));

  return (
    <AppShell title="Ticket" meta={meta}>
      <Link
        href="/field"
        className="inline-flex items-center gap-1 font-mono text-xs"
        style={{ color: "var(--text-on-dark-muted)" }}
      >
        <ArrowLeft size={12} /> back to queue
      </Link>

      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading ticket…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      {unavailable && <NoAuditState reason={unavailable.reason} />}
      {data && !entry && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          Ticket not found in the current audit (or not assigned to you — the
          list is role-scoped: viewers see only their own tickets).
        </p>
      )}

      {data && entry && (
        <div className="flex flex-col gap-4 max-w-xl">
          {(() => {
            const ticket = entry.ticket;
            return (
              <>
                {/* Header */}
                <div
                  className="op-card p-4"
                  style={{ borderLeft: `3px solid ${severityColor(ticket.priority)}` }}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-sm" style={{ color: "var(--text-on-dark)" }}>
                      {ticket.ticket_id}
                    </span>
                    <span
                      className="font-mono text-xs font-semibold"
                      style={{ color: severityColor(ticket.priority) }}
                    >
                      {ticket.priority}
                    </span>
                  </div>
                  <p className="text-sm mb-2" style={{ color: "var(--text-on-dark-secondary)" }}>
                    {ticket.fault_type} · routed to <strong>{ticket.team}</strong> · generated{" "}
                    {fmtDate(ticket.generated_at)}
                  </p>
                  {(() => {
                    const due = slaDue(ticket.generated_at, ticket.sla_days);
                    const days = daysUntil(due);
                    return (
                      <p
                        className="font-mono text-xs"
                        style={{ color: days < 0 ? "var(--status-offline)" : "var(--status-warn)" }}
                      >
                        SLA {ticket.sla_days} days —{" "}
                        {days < 0 ? `${-days}d OVERDUE` : `due in ${days}d`} (
                        {due.toLocaleDateString("en-GB")})
                      </p>
                    );
                  })()}
                </div>

                <StateSection t={entry} />

                {/* Evidence — measured facts from the agent */}
                <div className="op-card p-4">
                  <span className="op-label block mb-2">evidence ({ticket.evidence.length})</span>
                  <ul className="flex flex-col gap-1.5">
                    {ticket.evidence.map((line) => (
                      <li
                        key={line}
                        className="font-mono text-xs leading-relaxed"
                        style={{ color: "var(--text-on-dark-secondary)" }}
                      >
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Recommended action */}
                <div className="op-card p-4">
                  <span className="op-label block mb-2">recommended action</span>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-on-dark-secondary)" }}>
                    {ticket.recommended_action}
                  </p>
                </div>

                {/* Assumptions — always visible, not just behind a badge */}
                <div className="op-card p-4" style={{ border: "1px dashed var(--status-warn)" }}>
                  <span className="op-label block mb-2" style={{ color: "var(--status-warn)" }}>
                    assumptions behind the estimates ({ticket.assumptions.length})
                  </span>
                  <ul className="flex flex-col gap-1">
                    {ticket.assumptions.map((a) => (
                      <li
                        key={a}
                        className="font-mono text-[11px] leading-relaxed"
                        style={{ color: "var(--text-on-dark-secondary)" }}
                      >
                        • {a}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Financials — estimates, badged as such */}
                <div className="op-card p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="op-label">financials</span>
                    <AssumptionBadge assumptions={ticket.assumptions} />
                  </div>
                  <div className="grid grid-cols-3 gap-3 font-mono text-sm">
                    <div>
                      <p className="op-label mb-1">rev at risk /yr</p>
                      <p style={{ color: "var(--status-warn)" }}>
                        {fmtMoney(ticket.estimated_revenue_at_risk_annual)}
                      </p>
                    </div>
                    <div>
                      <p className="op-label mb-1">fix cost</p>
                      <p style={{ color: "var(--text-on-dark)" }}>{fmtMoney(ticket.fix_cost_estimate)}</p>
                    </div>
                    <div>
                      <p className="op-label mb-1">est. roi</p>
                      <p style={{ color: "var(--text-on-dark)" }}>{ticket.estimated_roi.toFixed(1)}×</p>
                    </div>
                  </div>
                </div>

                {/* Affected ONTs */}
                <div className="op-card p-4">
                  <span className="op-label block mb-2">
                    affected onts ({ticket.affected_ont_count})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {ticket.affected_ont_serials.map((serial) => (
                      <span
                        key={serial}
                        className="font-mono text-[11px] px-1.5 py-0.5"
                        style={{
                          border: "1px solid var(--border-dark-strong)",
                          color: "var(--text-on-dark-secondary)",
                        }}
                      >
                        {serial}
                      </span>
                    ))}
                  </div>
                </div>

                <LocationSection location={entry.location} />

                <ShareSection t={entry} auditRowId={data.provenance.id} />

                <CloseOutForm
                  t={entry}
                  auditRowId={data.provenance.id}
                  canClose={canClose}
                  isOpenNeedsAck={entry.state.status === "open"}
                />
              </>
            );
          })()}
        </div>
      )}
    </AppShell>
  );
}

export default function TicketPage() {
  // Suspense: useSearchParams (deep-link ?audit=) requires a boundary.
  return (
    <RoleGuard minRole="viewer">
      <Suspense fallback={null}>
        <TicketDetail />
      </Suspense>
    </RoleGuard>
  );
}
