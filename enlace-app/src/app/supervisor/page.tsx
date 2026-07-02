"use client";

// /supervisor — dispatch board on the server-side supervisor projection:
// ticket queue GROUPED BY LIFECYCLE STATUS with priority/SLA aging,
// assign-to-engineer control (tenant users with role viewer/analyst),
// ack and reassign. This is the work-order dispatch flow: an engineer
// receives the job in /field the moment it's assigned — and can get it on
// their phone via share-to-WhatsApp (wa.me prefilled message with the
// ticket deep link; NOT the Business API). When the assignee has a phone
// on file the chat opens directly with them.

import { useMemo, useState } from "react";
import Link from "next/link";
import { RoleGuard } from "@/lib/auth";
import { fmtMoney, severityColor } from "@/lib/format";
import type {
  SupervisorProjection,
  TeamMember,
  TicketStatus,
  TicketWithState,
} from "@/lib/opsTypes";
import {
  ackTicketAction,
  assignTicketAction,
  useProjection,
} from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import AssumptionBadge from "@/components/AssumptionBadge";
import ImportReportBanner from "@/components/ImportReportBanner";
import NoAuditState from "@/components/NoAuditState";
import ShareTicketActions from "@/components/ShareTicketActions";
import StatCard from "@/components/StatCard";
import { ticketStatusColor } from "@/components/TicketStatusPill";

const STATUS_ORDER: TicketStatus[] = ["open", "acked", "dispatched", "closed"];

/** Per-row dispatch control: pick an engineer, assign/reassign. */
function AssignControl({
  t,
  team,
  auditRowId,
}: {
  t: TicketWithState;
  team: TeamMember[];
  auditRowId: string;
}) {
  const [assignee, setAssignee] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (t.state.status === "closed") {
    return (
      <span className="font-mono text-[10px]" style={{ color: "var(--text-on-dark-muted)" }}>
        —
      </span>
    );
  }
  if (team.length === 0) {
    return (
      <span className="font-mono text-[10px]" style={{ color: "var(--text-on-dark-muted)" }}>
        no dispatchable users (viewer/analyst) in this tenant
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 flex-wrap">
      <select
        value={assignee}
        onChange={(e) => setAssignee(e.target.value)}
        className="bg-transparent font-mono text-[11px] px-1.5 py-0.5 cursor-pointer"
        style={{
          color: "var(--text-on-dark-secondary)",
          border: "1px solid var(--border-dark-strong)",
        }}
        aria-label="Assign to engineer"
      >
        <option value="" style={{ color: "black" }}>
          engineer…
        </option>
        {team.map((u) => (
          <option key={u.id} value={u.id} style={{ color: "black" }}>
            {u.name} ({u.role})
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={busy || !assignee}
        onClick={() => {
          setBusy(true);
          setError(null);
          assignTicketAction(t.ticket_ref, auditRowId, assignee).catch(
            (err: unknown) => {
              setError(err instanceof Error ? err.message : "assign failed");
              setBusy(false);
            },
          );
        }}
        className="font-mono text-[10px] px-2 py-0.5 cursor-pointer disabled:opacity-50"
        style={{ border: "1px solid var(--accent)", color: "var(--accent)" }}
      >
        {busy ? "…" : t.state.assigned_user_id ? "reassign" : "assign"}
      </button>
      {error && (
        <span className="font-mono text-[10px]" style={{ color: "var(--danger)" }}>
          {error}
        </span>
      )}
    </span>
  );
}

function AckControl({
  t,
  auditRowId,
}: {
  t: TicketWithState;
  auditRowId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (t.state.status !== "open") return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          ackTicketAction(t.ticket_ref, auditRowId).catch((err: unknown) => {
            setError(err instanceof Error ? err.message : "ack failed");
            setBusy(false);
          });
        }}
        className="font-mono text-[10px] px-2 py-0.5 cursor-pointer disabled:opacity-60"
        style={{
          border: "1px solid var(--border-dark-strong)",
          color: "var(--text-on-dark-muted)",
        }}
      >
        {busy ? "…" : "ack"}
      </button>
      {error && (
        <span className="font-mono text-[10px]" style={{ color: "var(--danger)" }}>
          {error}
        </span>
      )}
    </span>
  );
}

function StatusGroup({
  status,
  tickets,
  team,
  auditRowId,
}: {
  status: TicketStatus;
  tickets: TicketWithState[];
  team: TeamMember[];
  auditRowId: string;
}) {
  return (
    <section>
      <h2 className="op-label mb-2 flex items-center gap-2">
        <span style={{ color: ticketStatusColor(status) }}>{status}</span>—{" "}
        {tickets.length} ticket{tickets.length === 1 ? "" : "s"}
      </h2>
      <div className="op-card overflow-x-auto">
        <table className="op-table w-full border-collapse">
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Priority</th>
              <th>Type</th>
              <th>Team</th>
              <th>ONTs</th>
              <th>SLA</th>
              <th>Rev at risk /yr</th>
              <th>Assigned to</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => {
              const breached = t.days_to_sla < 0;
              return (
                <tr
                  key={t.ticket_ref}
                  style={
                    breached && t.state.status !== "closed"
                      ? { backgroundColor: "rgba(239, 68, 68, 0.08)" }
                      : undefined
                  }
                >
                  <td className="font-mono">
                    <Link
                      href={`/field/ticket/${encodeURIComponent(t.ticket_ref)}`}
                      style={{ color: "var(--accent-hover)" }}
                    >
                      {t.ticket_ref}
                    </Link>
                  </td>
                  <td
                    className="font-mono font-semibold"
                    style={{ color: severityColor(t.ticket.priority) }}
                  >
                    {t.ticket.priority}
                  </td>
                  <td>{t.ticket.fault_type}</td>
                  <td>{t.ticket.team}</td>
                  <td className="font-mono">{t.ticket.affected_ont_count}</td>
                  <td
                    className="font-mono"
                    style={{
                      color: breached
                        ? "var(--status-offline)"
                        : "var(--text-on-dark-secondary)",
                    }}
                    title={`due ${new Date(t.sla_due).toLocaleDateString("en-GB")}`}
                  >
                    {breached
                      ? `${-t.days_to_sla}d OVERDUE`
                      : `in ${t.days_to_sla}d`}
                  </td>
                  <td className="font-mono">
                    <span className="inline-flex items-center gap-2">
                      {fmtMoney(t.ticket.estimated_revenue_at_risk_annual)}
                      <AssumptionBadge assumptions={t.ticket.assumptions} />
                    </span>
                  </td>
                  <td className="font-mono text-xs">
                    {t.state.assigned_user_name ?? "—"}
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-2 flex-wrap">
                      <AckControl t={t} auditRowId={auditRowId} />
                      <AssignControl t={t} team={team} auditRowId={auditRowId} />
                      <ShareTicketActions
                        t={t}
                        auditRowId={auditRowId}
                        // Direct wa.me chat when the assignee has a phone on
                        // file; otherwise the sender picks the recipient.
                        phone={
                          team.find((u) => u.id === t.state.assigned_user_id)
                            ?.phone ?? null
                        }
                      />
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

function SupervisorBoard() {
  const { data, unavailable, meta, loading, error } =
    useProjection<SupervisorProjection>("supervisor");

  const groups = useMemo(() => {
    const by = new Map<TicketStatus, TicketWithState[]>();
    for (const t of data?.queue ?? []) {
      const list = by.get(t.state.status) ?? [];
      list.push(t);
      by.set(t.state.status, list);
    }
    for (const list of by.values()) {
      list.sort((a, b) => a.ticket.priority.localeCompare(b.ticket.priority));
    }
    return STATUS_ORDER.filter((s) => by.has(s)).map(
      (s) => [s, by.get(s) as TicketWithState[]] as const,
    );
  }, [data]);

  const breaches =
    data?.queue.filter((t) => t.days_to_sla < 0 && t.state.status !== "closed")
      .length ?? 0;

  return (
    <AppShell title="Dispatch Board" meta={meta}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading dispatch board…
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
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <StatCard label="tickets" value={data.queue.length} />
            <StatCard
              label="awaiting dispatch"
              value={
                data.queue.filter(
                  (t) => t.state.status === "open" || t.state.status === "acked",
                ).length
              }
              color="var(--status-warn)"
            />
            <StatCard
              label="dispatched"
              value={data.queue.filter((t) => t.state.status === "dispatched").length}
              color="var(--status-unknown)"
            />
            <StatCard
              label="sla breaches"
              value={breaches}
              color={breaches > 0 ? "var(--status-offline)" : "var(--status-online)"}
            />
            <StatCard
              label="p1 / p2"
              value={
                data.queue.filter(
                  (t) => t.ticket.priority === "P1" || t.ticket.priority === "P2",
                ).length
              }
              color="var(--status-warn)"
            />
          </div>

          {data.queue.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
              No tickets generated from this audit.
            </p>
          ) : (
            groups.map(([status, tickets]) => (
              <StatusGroup
                key={status}
                status={status}
                tickets={tickets}
                team={data.team}
                auditRowId={data.provenance.id}
              />
            ))
          )}

          {/* Dispatchable team */}
          <section>
            <h2 className="op-label mb-2">
              team — {data.team.length} dispatchable user
              {data.team.length === 1 ? "" : "s"} (role viewer/analyst)
            </h2>
            <div className="flex flex-wrap gap-2">
              {data.team.map((u) => (
                <span
                  key={u.id}
                  className="op-card px-3 py-2 font-mono text-xs"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  {u.name} · {u.role} · {u.persona}
                  {u.phone ? ` · ${u.phone}` : ""}
                </span>
              ))}
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}

export default function SupervisorPage() {
  return (
    <RoleGuard minRole="manager">
      <SupervisorBoard />
    </RoleGuard>
  );
}
