"use client";

// /noc — NOC incident board: open incidents by severity, per-PON health
// cards, always-visible source badge + import report.

import { useMemo, useState } from "react";
import { RoleGuard } from "@/lib/auth";
import { useAuditFeed } from "@/lib/useAuditFeed";
import { fmtDate, fmtDbm, rxColor, severityColor } from "@/lib/format";
import { OFFLINE_STATUSES, type OntData } from "@/lib/types";
import AppShell from "@/components/AppShell";
import ImportReportBanner from "@/components/ImportReportBanner";
import StatCard from "@/components/StatCard";

function PortHealthCards({ onts }: { onts: OntData[] }) {
  const ports = useMemo(() => {
    const byPort = new Map<string, OntData[]>();
    for (const ont of onts) {
      const list = byPort.get(ont.pon_port) ?? [];
      list.push(ont);
      byPort.set(ont.pon_port, list);
    }
    return [...byPort.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [onts]);

  return (
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
      {ports.map(([port, list]) => {
        const online = list.filter((o) => !OFFLINE_STATUSES.includes(o.status) && o.status !== "Unknown").length;
        const offline = list.filter((o) => OFFLINE_STATUSES.includes(o.status)).length;
        const unknown = list.filter((o) => o.status === "Unknown").length;
        const rxValues = list
          .map((o) => o.rx_power_dbm)
          .filter((v): v is number => v !== null);
        const avgRx =
          rxValues.length > 0
            ? rxValues.reduce((a, b) => a + b, 0) / rxValues.length
            : null;
        return (
          <div key={port} className="op-card p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm" style={{ color: "var(--text-on-dark)" }}>
                {port}
              </span>
              <span className="op-label">{list.length} onts</span>
            </div>
            <div className="flex gap-4 font-mono text-xs">
              <span style={{ color: "var(--status-online)" }}>{online} up</span>
              <span style={{ color: offline > 0 ? "var(--status-offline)" : "var(--text-on-dark-muted)" }}>
                {offline} down
              </span>
              <span style={{ color: unknown > 0 ? "var(--status-unknown)" : "var(--text-on-dark-muted)" }}>
                {unknown} unknown
              </span>
              <span className="ml-auto" style={{ color: rxColor(avgRx) }}>
                {avgRx !== null ? fmtDbm(avgRx) : "rx —"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NocBoard() {
  const { feed, loading, error } = useAuditFeed();
  const [acked, setAcked] = useState<Set<string>>(new Set());

  if (loading) {
    return (
      <AppShell title="NOC Board" feed={null}>
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading audit feed…
        </p>
      </AppShell>
    );
  }
  if (error || !feed) {
    return (
      <AppShell title="NOC Board" feed={null}>
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error ?? "no data"}
        </p>
      </AppShell>
    );
  }

  const { summary } = feed.audit;
  const faults = [...feed.audit.faults].sort((a, b) =>
    a.severity === b.severity ? 0 : a.severity === "critical" ? -1 : 1,
  );

  return (
    <AppShell title="NOC Board" feed={feed}>
      <ImportReportBanner report={feed.audit.import_report} />

      {/* Fleet summary */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard
          label="health score"
          value={summary.health_score}
          color={
            summary.health_score >= 80
              ? "var(--status-online)"
              : summary.health_score >= 50
                ? "var(--status-warn)"
                : "var(--status-offline)"
          }
          sub={`${summary.total_onts} ONTs / ${summary.analysis_period_days}d window`}
        />
        <StatCard label="online" value={summary.online} color="var(--status-online)" />
        <StatCard label="offline" value={summary.offline} color="var(--status-offline)" />
        <StatCard
          label="unknown"
          value={summary.unknown}
          color="var(--status-unknown)"
          sub="status not determinable — not an outage"
        />
        <StatCard label="avg rx" value={fmtDbm(summary.avg_rx_dbm)} color={rxColor(summary.avg_rx_dbm)} />
        <StatCard label="worst rx" value={fmtDbm(summary.worst_rx_dbm)} color={rxColor(summary.worst_rx_dbm)} />
      </div>

      {/* Open incidents */}
      <section>
        <h2 className="op-label mb-2">
          open incidents — {faults.length} from fault detector
        </h2>
        {faults.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
            No fault events in this analysis window.
          </p>
        ) : (
          <div className="grid lg:grid-cols-2 gap-3">
            {faults.map((fault) => {
              const id = `${fault.pon_port}:${fault.timestamp}`;
              const isAcked = acked.has(id);
              const gasps = fault.affected_onts.filter((o) => o.had_dying_gasp).length;
              return (
                <div
                  key={id}
                  className="op-card p-4"
                  style={{
                    borderLeft: `3px solid ${severityColor(fault.severity)}`,
                    opacity: isAcked ? 0.55 : 1,
                  }}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                      className="font-mono text-xs uppercase tracking-wider"
                      style={{ color: severityColor(fault.severity) }}
                    >
                      {fault.severity} · {fault.fault_type}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setAcked((prev) => {
                          const next = new Set(prev);
                          if (next.has(id)) next.delete(id);
                          else next.add(id);
                          return next;
                        })
                      }
                      className="font-mono text-[10px] px-2 py-0.5 cursor-pointer"
                      style={{
                        border: "1px solid var(--border-dark-strong)",
                        color: isAcked ? "var(--status-online)" : "var(--text-on-dark-muted)",
                      }}
                      title="Acknowledgement is session-local — not persisted yet"
                    >
                      {isAcked ? "ACKED (local)" : "ACK"}
                    </button>
                  </div>
                  <p className="font-mono text-sm mb-1" style={{ color: "var(--text-on-dark)" }}>
                    {fault.pon_port}
                    {fault.olt_id && ` @ ${fault.olt_id}`}
                  </p>
                  <p className="text-xs mb-2" style={{ color: "var(--text-on-dark-secondary)" }}>
                    {fault.affected_onts.length} ONTs affected · {gasps} sent dying gasp ·
                    detected {fmtDate(fault.timestamp)}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {fault.affected_onts.map((ont) => (
                      <span
                        key={ont.serial_number}
                        className="font-mono text-[10px] px-1.5 py-0.5"
                        style={{
                          border: "1px solid var(--border-dark)",
                          color: "var(--text-on-dark-muted)",
                        }}
                        title={
                          ont.had_dying_gasp
                            ? "dying gasp received → power failure evidence"
                            : "no dying gasp → possible fibre break"
                        }
                      >
                        {ont.serial_number}
                        {ont.had_dying_gasp ? " ⚡" : ""}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Per-PON health */}
      <section>
        <h2 className="op-label mb-2">per-PON health</h2>
        <PortHealthCards onts={feed.audit.onts} />
      </section>
    </AppShell>
  );
}

export default function NocPage() {
  return (
    <RoleGuard minRole="analyst">
      <NocBoard />
    </RoleGuard>
  );
}
