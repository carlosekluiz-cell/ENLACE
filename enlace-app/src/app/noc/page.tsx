"use client";

// /noc — NOC incident board on the SERVER-SIDE NOC PROJECTION of the
// persisted audit (never client-shipped JSON): open incidents, actionable
// tickets with persisted ack, the frontier sections (pre-FEC degradation,
// laser end-of-life, rogue-ONT hypotheses — coverage notes always shown),
// per-PON health, and the always-visible source badge + import report.

import { useMemo, useState } from "react";
import Link from "next/link";
import { RoleGuard } from "@/lib/auth";
import { fmtDate, fmtDbm, rxColor, severityColor } from "@/lib/format";
import { OFFLINE_STATUSES, type FaultEvent, type OntData } from "@/lib/types";
import type { NocProjection, TicketWithState } from "@/lib/opsTypes";
import { ackTicketAction, useProjection } from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import ImportReportBanner from "@/components/ImportReportBanner";
import NoAuditState from "@/components/NoAuditState";
import StatCard from "@/components/StatCard";
import TicketStatusPill from "@/components/TicketStatusPill";

/** Persisted ack control — writes ticket_state through the server. */
function AckButton({
  ticket,
  auditRowId,
}: {
  ticket: TicketWithState;
  auditRowId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (ticket.state.status !== "open") {
    return (
      <span
        className="font-mono text-[10px]"
        style={{ color: "var(--status-online)" }}
        title={
          ticket.state.acked_at
            ? `acknowledged by ${ticket.state.acked_by_name ?? ticket.state.acked_by} at ${fmtDate(ticket.state.acked_at)}`
            : undefined
        }
      >
        ACKED
        {ticket.state.acked_by_name ? ` — ${ticket.state.acked_by_name}` : ""}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          ackTicketAction(ticket.ticket_ref, auditRowId).catch((err: unknown) => {
            setError(err instanceof Error ? err.message : "ack failed");
            setBusy(false);
          });
        }}
        className="font-mono text-[10px] px-2 py-0.5 cursor-pointer disabled:opacity-60"
        style={{
          border: "1px solid var(--border-dark-strong)",
          color: "var(--text-on-dark-muted)",
        }}
        title="Acknowledge — persisted to ticket_state, visible to every colleague"
      >
        {busy ? "ACKING…" : "ACK"}
      </button>
      {error && (
        <span className="font-mono text-[10px]" style={{ color: "var(--danger)" }}>
          {error}
        </span>
      )}
    </span>
  );
}

/** Fault card; when a ticket references the same ONTs, ack is available. */
function FaultCard({
  fault,
  relatedTicket,
  auditRowId,
}: {
  fault: FaultEvent;
  relatedTicket: TicketWithState | undefined;
  auditRowId: string;
}) {
  const gasps = fault.affected_onts.filter((o) => o.had_dying_gasp).length;
  return (
    <div
      className="op-card p-4"
      style={{
        borderLeft: `3px solid ${severityColor(fault.severity)}`,
        opacity: relatedTicket && relatedTicket.state.status !== "open" ? 0.7 : 1,
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span
          className="font-mono text-xs uppercase tracking-wider"
          style={{ color: severityColor(fault.severity) }}
        >
          {fault.severity} · {fault.fault_type}
        </span>
        {relatedTicket ? (
          <AckButton ticket={relatedTicket} auditRowId={auditRowId} />
        ) : (
          <span
            className="font-mono text-[10px]"
            style={{ color: "var(--text-on-dark-muted)" }}
            title="The agent generated no ticket for this fault — nothing to acknowledge"
          >
            no ticket
          </span>
        )}
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
}

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
        const online = list.filter(
          (o) => !OFFLINE_STATUSES.includes(o.status) && o.status !== "Unknown",
        ).length;
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

// ── Frontier sections — the differentiators, rendered honestly ──

function FecHealthSection({ fec }: { fec: NocProjection["fec_health"] }) {
  return (
    <section>
      <h2 className="op-label mb-2">
        pre-FEC degradation — {fec.findings.length} finding
        {fec.findings.length === 1 ? "" : "s"}
      </h2>
      <p className="font-mono text-[11px] mb-2" style={{ color: "var(--text-on-dark-muted)" }}>
        {fec.coverage_note}
      </p>
      {fec.findings.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-3">
          {fec.findings.map((f) => (
            <div
              key={`${f.serial_number}:${f.window_start}`}
              className="op-card p-4"
              style={{ borderLeft: "3px solid var(--status-warn)" }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-sm" style={{ color: "var(--text-on-dark)" }}>
                  {f.serial_number} · {f.pon_port}
                </span>
                <span
                  className="font-mono text-[10px] uppercase tracking-wider"
                  style={{ color: "var(--status-warn)" }}
                  title="Confidence in this hypothesis, as scored by the agent"
                >
                  {f.confidence} confidence
                </span>
              </div>
              <p className="font-mono text-xs mb-1" style={{ color: "var(--text-on-dark-secondary)" }}>
                hypothesis: {f.hypothesis} · {f.corrected_rate_per_hour.toFixed(1)} corrected/h
                ({f.normalization}-normalized
                {f.corrected_per_gbyte !== null
                  ? `, ${f.corrected_per_gbyte.toFixed(1)}/GB`
                  : ""}
                ) · {f.uncorrected_total} uncorrected
              </p>
              <p className="font-mono text-[11px] mb-1" style={{ color: "var(--text-on-dark-muted)" }}>
                rx trend:{" "}
                {f.rx_trend_dbm_per_day !== null
                  ? `${f.rx_trend_dbm_per_day.toFixed(3)} dBm/day`
                  : "insufficient rx samples to quote a trend"}
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-on-dark-secondary)" }}>
                {f.summary}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function LaserHealthSection({ laser }: { laser: NocProjection["laser_health"] }) {
  const c = laser.coverage;
  return (
    <section>
      <h2 className="op-label mb-2">
        laser end-of-life predictions — {laser.predictions.length}
      </h2>
      <p className="font-mono text-[11px] mb-2" style={{ color: "var(--text-on-dark-muted)" }}>
        coverage: {c.onts_with_bias} of {c.onts_total} ONTs exposed bias data ·{" "}
        {c.onts_analyzed} analyzed · {c.onts_gated_out} gated out (insufficient
        data — “not assessable yet”, not healthy) · {c.onts_temperature_detrended}{" "}
        temperature-detrended · {c.onts_flagged} flagged
      </p>
      {c.onts_with_bias === 0 && (
        <p className="text-xs mb-2" style={{ color: "var(--text-on-dark-secondary)" }}>
          No ONT in this audit reported laser bias current, so no prediction was
          possible — absence of a finding here is not evidence of health.
        </p>
      )}
      {laser.predictions.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-3">
          {laser.predictions.map((p) => (
            <div
              key={p.serial_number}
              className="op-card p-4"
              style={{ borderLeft: "3px solid var(--status-warn)" }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-sm" style={{ color: "var(--text-on-dark)" }}>
                  {p.serial_number} · {p.pon_port}
                </span>
                <span className="font-mono text-[10px] uppercase" style={{ color: "var(--status-warn)" }}>
                  {p.urgency}
                </span>
              </div>
              <p className="font-mono text-xs mb-1" style={{ color: "var(--text-on-dark-secondary)" }}>
                bias drift {p.drift_pct_per_month.toFixed(2)}%/mo (95% CI{" "}
                {p.drift_ci95_pct_per_month[0].toFixed(2)}–
                {p.drift_ci95_pct_per_month[1].toFixed(2)}) · median{" "}
                {p.median_bias_ma.toFixed(1)} mA · fit R² {p.confidence.toFixed(2)}
              </p>
              <p className="font-mono text-[11px] mb-1" style={{ color: "var(--text-on-dark-muted)" }}>
                {p.temperature_detrended
                  ? "temperature-detrended"
                  : "24h-mean fallback only — no temperature data, weigh accordingly"}{" "}
                · tx power{" "}
                {p.tx_power_stable === null
                  ? "insufficient data"
                  : p.tx_power_stable
                    ? "stable"
                    : "moving"}
              </p>
              <p className="font-mono text-[11px] mb-1" style={{ color: "var(--status-warn)" }}>
                EOL heuristic ETA: {p.eta_days_to_eol_earliest}d
                {p.eta_days_to_eol_latest !== null
                  ? `–${p.eta_days_to_eol_latest}d`
                  : "+ (slow edge open-ended)"}{" "}
                — a range, not a promise
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-on-dark-secondary)" }}>
                {p.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RogueSection({ rogue }: { rogue: NocProjection["rogue"] }) {
  return (
    <section>
      <h2 className="op-label mb-2">
        rogue-ONT hypotheses — {rogue.length}
      </h2>
      {rogue.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          No multi-victim upstream-integrity patterns in this analysis window.
        </p>
      ) : (
        <div className="grid lg:grid-cols-2 gap-3">
          {rogue.map((r) => (
            <div
              key={`${r.olt}:${r.pon_port}:${r.window_start}`}
              className="op-card p-4"
              style={{ borderLeft: "3px solid var(--status-offline)" }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-sm" style={{ color: "var(--text-on-dark)" }}>
                  {r.pon_port}
                  {r.olt && ` @ ${r.olt}`} · {r.victim_count} victims
                </span>
                <span className="font-mono text-[10px] uppercase" style={{ color: "var(--status-warn)" }}>
                  {r.confidence} confidence
                </span>
              </div>
              <ul className="mb-2">
                {r.evidence.map((line) => (
                  <li
                    key={line}
                    className="font-mono text-[11px] leading-relaxed"
                    style={{ color: "var(--text-on-dark-secondary)" }}
                  >
                    {line}
                  </li>
                ))}
              </ul>
              {r.candidates.length > 0 && (
                <div className="mb-2">
                  <span className="op-label block mb-1">
                    candidates (scored hypotheses — not a verdict)
                  </span>
                  {r.candidates.map((c) => (
                    <p
                      key={c.serial_number}
                      className="font-mono text-[11px]"
                      style={{ color: "var(--text-on-dark-muted)" }}
                    >
                      {c.serial_number} · score {c.score.toFixed(2)} ·{" "}
                      {c.evidence.join("; ")}
                    </p>
                  ))}
                </div>
              )}
              <p className="text-xs leading-relaxed" style={{ color: "var(--status-warn)" }}>
                confirmation step: {r.recommended_action}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function NocBoard() {
  const { data, unavailable, meta, loading, error } =
    useProjection<NocProjection>("noc");

  const faults = useMemo(
    () =>
      [...(data?.faults ?? [])].sort((a, b) =>
        a.severity === b.severity ? 0 : a.severity === "critical" ? -1 : 1,
      ),
    [data],
  );

  // Fault ↔ ticket linkage by shared ONT serials — ack is only offered
  // where a ticket actually exists (never a fake control).
  const ticketForFault = useMemo(() => {
    const map = new Map<FaultEvent, TicketWithState | undefined>();
    for (const fault of faults) {
      const serials = new Set(fault.affected_onts.map((o) => o.serial_number));
      map.set(
        fault,
        data?.tickets.find((t) =>
          t.ticket.affected_ont_serials.some((s) => serials.has(s)),
        ),
      );
    }
    return map;
  }, [faults, data]);

  if (loading) {
    return (
      <AppShell title="NOC Board" meta={null}>
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading NOC projection…
        </p>
      </AppShell>
    );
  }
  if (error) {
    return (
      <AppShell title="NOC Board" meta={null}>
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      </AppShell>
    );
  }
  if (unavailable || !data || !meta) {
    return (
      <AppShell title="NOC Board" meta={null}>
        <NoAuditState reason={unavailable?.reason ?? "no data"} />
      </AppShell>
    );
  }

  const { summary } = data;
  const auditRowId = data.provenance.id;

  return (
    <AppShell title="NOC Board" meta={meta}>
      <ImportReportBanner report={data.import_report ?? undefined} />

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
            {faults.map((fault) => (
              <FaultCard
                key={`${fault.pon_port}:${fault.timestamp}`}
                fault={fault}
                relatedTicket={ticketForFault.get(fault)}
                auditRowId={auditRowId}
              />
            ))}
          </div>
        )}
      </section>

      {/* Actionable tickets (persisted lifecycle) */}
      <section>
        <h2 className="op-label mb-2">
          tickets — {data.tickets.length} from this audit
        </h2>
        {data.tickets.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
            No tickets generated from this audit.
          </p>
        ) : (
          <div className="flex flex-col gap-2 max-w-2xl">
            {data.tickets.map((t) => (
              <div key={t.ticket_ref} className="op-card p-3 flex items-center gap-3">
                <span
                  className="font-mono text-xs font-semibold"
                  style={{ color: severityColor(t.ticket.priority) }}
                >
                  {t.ticket.priority}
                </span>
                <Link
                  href={`/field/ticket/${encodeURIComponent(t.ticket_ref)}`}
                  className="font-mono text-xs"
                  style={{ color: "var(--accent-hover)" }}
                >
                  {t.ticket_ref}
                </Link>
                <span className="text-xs" style={{ color: "var(--text-on-dark-secondary)" }}>
                  {t.ticket.fault_type} · {t.ticket.affected_ont_count} ONTs
                </span>
                <span className="ml-auto inline-flex items-center gap-2">
                  <TicketStatusPill status={t.state.status} />
                  <AckButton ticket={t} auditRowId={auditRowId} />
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Frontier sections — differentiators, honesty-first */}
      <FecHealthSection fec={data.fec_health} />
      <LaserHealthSection laser={data.laser_health} />
      <RogueSection rogue={data.rogue} />

      {/* Per-PON health */}
      <section>
        <h2 className="op-label mb-2">per-PON health</h2>
        <PortHealthCards onts={data.onts} />
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
