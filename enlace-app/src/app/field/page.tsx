"use client";

// /field — mobile-first "my jobs" list for a field engineer: tickets
// ASSIGNED TO THE LOGGED-IN USER from the server-side field projection
// (rows are filtered server-side; evidence and assumptions never are).

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { RoleGuard } from "@/lib/auth";
import { severityColor } from "@/lib/format";
import type { FieldProjection } from "@/lib/opsTypes";
import { useProjection } from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import AutoClosedBadge from "@/components/AutoClosedBadge";
import ImportReportBanner from "@/components/ImportReportBanner";
import NoAuditState from "@/components/NoAuditState";
import TicketStatusPill from "@/components/TicketStatusPill";

function FieldQueue() {
  const { data, unavailable, meta, loading, error } =
    useProjection<FieldProjection>("field");

  return (
    <AppShell title="My Tickets" meta={meta}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading my tickets…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      {unavailable && <NoAuditState reason={unavailable.reason} />}
      {data && (
        <>
          <ImportReportBanner report={data.import_report ?? undefined} />
          {data.tickets.length === 0 ? (
            <div className="op-card p-5 max-w-xl">
              <p className="text-sm mb-1" style={{ color: "var(--text-on-dark-secondary)" }}>
                No tickets assigned to you in this audit.
              </p>
              <p className="text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                Jobs land here when a supervisor dispatches a ticket to you
                from the dispatch board.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3 max-w-xl">
              {data.tickets.map(({ ticket, ticket_ref, state, days_to_sla, sla_due }) => {
                const overdue = days_to_sla < 0;
                return (
                  <Link
                    key={ticket_ref}
                    href={`/field/ticket/${encodeURIComponent(ticket_ref)}`}
                    className="op-card p-4 flex items-center gap-3"
                    style={{
                      borderLeft: `3px solid ${severityColor(ticket.priority)}`,
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className="font-mono text-xs font-semibold"
                          style={{ color: severityColor(ticket.priority) }}
                        >
                          {ticket.priority}
                        </span>
                        <span className="font-mono text-xs" style={{ color: "var(--text-on-dark)" }}>
                          {ticket_ref}
                        </span>
                        <TicketStatusPill status={state.status} />
                        {state.status === "closed" && state.closed_by_system && (
                          <AutoClosedBadge />
                        )}
                      </div>
                      <p className="text-sm mb-1" style={{ color: "var(--text-on-dark-secondary)" }}>
                        {ticket.fault_type} · {ticket.affected_ont_count} ONT
                        {ticket.affected_ont_count === 1 ? "" : "s"} · team {ticket.team}
                      </p>
                      <p
                        className="font-mono text-[11px]"
                        style={{
                          color: overdue ? "var(--status-offline)" : "var(--text-on-dark-muted)",
                        }}
                      >
                        SLA {ticket.sla_days}d ·{" "}
                        {overdue ? `${-days_to_sla}d overdue` : `due in ${days_to_sla}d`} (
                        {new Date(sla_due).toLocaleDateString("en-GB")})
                      </p>
                    </div>
                    <ChevronRight size={16} style={{ color: "var(--text-on-dark-muted)" }} />
                  </Link>
                );
              })}
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}

export default function FieldPage() {
  return (
    <RoleGuard minRole="viewer">
      <FieldQueue />
    </RoleGuard>
  );
}
