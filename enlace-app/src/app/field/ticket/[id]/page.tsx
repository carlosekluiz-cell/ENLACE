"use client";

// /field/ticket/[id] — ticket detail for a field engineer: evidence,
// priority/SLA, recommended action, and a location section that shows real
// coordinates + a Google Maps link when the ticket has geo — and an honest
// "no location data" state when it doesn't (telemetry has no coordinates;
// geo arrives when customer records are joined).

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, CheckCircle2, MapPin } from "lucide-react";
import { RoleGuard } from "@/lib/auth";
import { useAuditFeed } from "@/lib/useAuditFeed";
import { daysUntil, fmtDate, fmtMoney, severityColor, slaDue } from "@/lib/format";
import type { EnrichedTicket } from "@/lib/types";
import AppShell from "@/components/AppShell";
import AssumptionBadge from "@/components/AssumptionBadge";

function LocationSection({ ticket }: { ticket: EnrichedTicket }) {
  if (!ticket.geo) {
    return (
      <div className="op-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <MapPin size={14} style={{ color: "var(--text-on-dark-muted)" }} />
          <span className="op-label">location</span>
        </div>
        <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          No location data in this audit — telemetry carries no coordinates.
          Geo appears here once customer records are joined to ONT serials.
        </p>
      </div>
    );
  }

  const { lat, lon, label } = ticket.geo;
  return (
    <div className="op-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <MapPin size={14} style={{ color: "var(--accent)" }} />
        <span className="op-label">location</span>
      </div>
      <p className="font-mono text-sm mb-2" style={{ color: "var(--text-on-dark)" }}>
        {lat.toFixed(6)}, {lon.toFixed(6)}
        {label ? ` — ${label}` : ""}
      </p>
      <a
        href={`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`}
        target="_blank"
        rel="noopener noreferrer"
        className="enlace-btn-ghost"
        style={{ height: 34 }}
      >
        Directions in Google Maps
      </a>
    </div>
  );
}

function TicketDetail() {
  const params = useParams<{ id: string }>();
  const { feed, loading, error } = useAuditFeed();
  const [closedOut, setClosedOut] = useState(false);

  const ticket = useMemo<EnrichedTicket | undefined>(() => {
    const id = decodeURIComponent(params.id ?? "");
    // Tickets come straight from the agent; geo would be an app-layer join
    // (none wired yet — LocationSection renders the honest empty state).
    return feed?.audit.tickets.find((t) => t.ticket_id === id);
  }, [feed, params.id]);

  return (
    <AppShell title="Ticket" feed={feed}>
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
      {feed && !ticket && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          Ticket not found in the current audit feed.
        </p>
      )}

      {ticket && (
        <div className="flex flex-col gap-4 max-w-xl">
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

          <LocationSection ticket={ticket} />

          {/* Close-out (session-local until ticket persistence is wired) */}
          <button
            type="button"
            onClick={() => setClosedOut((v) => !v)}
            className="enlace-btn-primary"
            style={
              closedOut
                ? { backgroundColor: "var(--status-online)", color: "var(--bg-dark)" }
                : undefined
            }
          >
            <CheckCircle2 size={16} className="mr-2" />
            {closedOut ? "Closed out (local only — persistence not wired)" : "Close out ticket"}
          </button>
        </div>
      )}
    </AppShell>
  );
}

export default function TicketPage() {
  return (
    <RoleGuard minRole="viewer">
      <TicketDetail />
    </RoleGuard>
  );
}
