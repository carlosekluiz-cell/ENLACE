"use client";

// /field — mobile-first ticket list for a field engineer. Tickets come
// straight from the agent's audit output. Assignment isn't wired yet, so
// this is honestly labeled as the unassigned queue.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { RoleGuard } from "@/lib/auth";
import { useAuditFeed } from "@/lib/useAuditFeed";
import { daysUntil, severityColor, slaDue } from "@/lib/format";
import AppShell from "@/components/AppShell";
import ImportReportBanner from "@/components/ImportReportBanner";

function FieldQueue() {
  const { feed, loading, error } = useAuditFeed();

  return (
    <AppShell title="My Tickets" feed={feed}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading tickets…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
      {feed && (
        <>
          <ImportReportBanner report={feed.audit.import_report} />
          <p className="font-mono text-[11px]" style={{ color: "var(--text-on-dark-muted)" }}>
            showing the unassigned queue — per-engineer assignment isn&apos;t wired yet
          </p>
          {feed.audit.tickets.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
              No tickets generated from this audit.
            </p>
          ) : (
            <div className="flex flex-col gap-3 max-w-xl">
              {feed.audit.tickets.map((ticket) => {
                const due = slaDue(ticket.generated_at, ticket.sla_days);
                const days = daysUntil(due);
                const overdue = days < 0;
                return (
                  <Link
                    key={ticket.ticket_id}
                    href={`/field/ticket/${encodeURIComponent(ticket.ticket_id)}`}
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
                          {ticket.ticket_id}
                        </span>
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
                        {overdue ? `${-days}d overdue` : `due in ${days}d`} (
                        {due.toLocaleDateString("en-GB")})
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
