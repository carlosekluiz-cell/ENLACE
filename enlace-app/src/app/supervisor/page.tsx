"use client";

// /supervisor — ticket queue grouped by team, SLA breach highlighting.

import { useMemo } from "react";
import Link from "next/link";
import { RoleGuard } from "@/lib/auth";
import { useAuditFeed } from "@/lib/useAuditFeed";
import { daysUntil, fmtMoney, severityColor, slaDue } from "@/lib/format";
import type { Ticket } from "@/lib/types";
import AppShell from "@/components/AppShell";
import AssumptionBadge from "@/components/AssumptionBadge";
import ImportReportBanner from "@/components/ImportReportBanner";
import StatCard from "@/components/StatCard";

function TeamQueue({ team, tickets }: { team: string; tickets: Ticket[] }) {
  return (
    <section>
      <h2 className="op-label mb-2">
        team {team} — {tickets.length} ticket{tickets.length === 1 ? "" : "s"}
      </h2>
      <div className="op-card overflow-x-auto">
        <table className="op-table w-full border-collapse">
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Priority</th>
              <th>Type</th>
              <th>ONTs</th>
              <th>SLA</th>
              <th>Due</th>
              <th>Rev at risk /yr</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => {
              const due = slaDue(ticket.generated_at, ticket.sla_days);
              const days = daysUntil(due);
              const breached = days < 0;
              return (
                <tr
                  key={ticket.ticket_id}
                  style={
                    breached
                      ? { backgroundColor: "rgba(239, 68, 68, 0.08)" }
                      : undefined
                  }
                >
                  <td className="font-mono">
                    <Link
                      href={`/field/ticket/${encodeURIComponent(ticket.ticket_id)}`}
                      style={{ color: "var(--accent-hover)" }}
                    >
                      {ticket.ticket_id}
                    </Link>
                  </td>
                  <td
                    className="font-mono font-semibold"
                    style={{ color: severityColor(ticket.priority) }}
                  >
                    {ticket.priority}
                  </td>
                  <td>{ticket.fault_type}</td>
                  <td className="font-mono">{ticket.affected_ont_count}</td>
                  <td className="font-mono">{ticket.sla_days}d</td>
                  <td
                    className="font-mono"
                    style={{
                      color: breached ? "var(--status-offline)" : "var(--text-on-dark-secondary)",
                    }}
                  >
                    {breached ? `${-days}d OVERDUE` : `in ${days}d`}
                  </td>
                  <td className="font-mono">
                    <span className="inline-flex items-center gap-2">
                      {fmtMoney(ticket.estimated_revenue_at_risk_annual)}
                      <AssumptionBadge assumptions={ticket.assumptions} />
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SupervisorQueue() {
  const { feed, loading, error } = useAuditFeed();

  const teams = useMemo(() => {
    const byTeam = new Map<string, Ticket[]>();
    for (const ticket of feed?.audit.tickets ?? []) {
      const list = byTeam.get(ticket.team) ?? [];
      list.push(ticket);
      byTeam.set(ticket.team, list);
    }
    for (const list of byTeam.values()) {
      list.sort((a, b) => a.priority.localeCompare(b.priority));
    }
    return [...byTeam.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [feed]);

  const breaches =
    feed?.audit.tickets.filter(
      (t) => daysUntil(slaDue(t.generated_at, t.sla_days)) < 0,
    ).length ?? 0;

  return (
    <AppShell title="Ticket Queue" feed={feed}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading queue…
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
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="open tickets" value={feed.audit.tickets.length} />
            <StatCard
              label="sla breaches"
              value={breaches}
              color={breaches > 0 ? "var(--status-offline)" : "var(--status-online)"}
            />
            <StatCard label="teams" value={teams.length} />
            <StatCard
              label="p1 / p2"
              value={
                feed.audit.tickets.filter((t) => t.priority === "P1" || t.priority === "P2")
                  .length
              }
              color="var(--status-warn)"
            />
          </div>
          {teams.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
              No tickets generated from this audit.
            </p>
          ) : (
            teams.map(([team, tickets]) => (
              <TeamQueue key={team} team={team} tickets={tickets} />
            ))
          )}
        </>
      )}
    </AppShell>
  );
}

export default function SupervisorPage() {
  return (
    <RoleGuard minRole="manager">
      <SupervisorQueue />
    </RoleGuard>
  );
}
