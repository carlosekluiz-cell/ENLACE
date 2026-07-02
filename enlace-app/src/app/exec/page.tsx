"use client";

// /exec — executive KPI dashboard on the server-side exec projection.
// Every money figure is an ESTIMATE and is badged as such with the agent's
// declared assumptions (carried through the projection, never stripped);
// KPIs the pipeline does not measure yet (uptime, truck-rolls avoided) are
// "not measured", never zero; the health trend is an HONEST empty state
// until multi-audit trending exists.

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RoleGuard } from "@/lib/auth";
import { fmtDbm, fmtMoney, rxColor, severityColor } from "@/lib/format";
import type { ExecProjection } from "@/lib/opsTypes";
import { useProjection } from "@/lib/useOps";
import AppShell from "@/components/AppShell";
import AssumptionBadge from "@/components/AssumptionBadge";
import ImportReportBanner from "@/components/ImportReportBanner";
import NoAuditState from "@/components/NoAuditState";
import StatCard from "@/components/StatCard";

function capacityColor(pct: number): string {
  if (pct >= 90) return "var(--status-offline)";
  if (pct >= 80) return "var(--status-warn)";
  return "var(--accent)";
}

function ExecDashboard() {
  const { data, unavailable, meta, loading, error } =
    useProjection<ExecProjection>("exec");

  const capacityData = useMemo(
    () =>
      [...(data?.capacity ?? [])]
        .sort((a, b) => b.utilisation_pct - a.utilisation_pct)
        .map((c) => ({
          port: c.port,
          pct: Math.round(c.utilisation_pct * 10) / 10,
          detail: `${c.active_onts}/${c.max_ports} on ${c.splitter_type}${c.splitter_assumed ? " (assumed)" : ""}`,
          monthsToFull: c.months_to_full,
        })),
    [data],
  );

  const anySplitterAssumed = data?.capacity.some((c) => c.splitter_assumed) ?? false;

  return (
    <AppShell title="Executive KPIs" meta={meta}>
      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading KPIs…
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

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard
              label="health score"
              value={data.summary.health_score}
              color={
                data.summary.health_score >= 80
                  ? "var(--status-online)"
                  : data.summary.health_score >= 50
                    ? "var(--status-warn)"
                    : "var(--status-offline)"
              }
              sub={`${data.summary.analysis_period_days}-day window`}
            />
            <StatCard label="online" value={data.summary.online} color="var(--status-online)" />
            <StatCard label="offline" value={data.summary.offline} color="var(--status-offline)" />
            <StatCard
              label="unknown"
              value={data.summary.unknown}
              color="var(--status-unknown)"
              sub="not an outage"
            />
            <StatCard
              label="rev at risk /yr"
              value={fmtMoney(data.revenue_at_risk.estimated_total_annual)}
              color="var(--status-warn)"
              badge={<AssumptionBadge assumptions={data.revenue_at_risk.assumptions} />}
              sub={`${data.revenue_at_risk.label} across ${data.revenue_at_risk.ticket_count} ticket${data.revenue_at_risk.ticket_count === 1 ? "" : "s"}`}
            />
            <StatCard
              label="avg rx"
              value={fmtDbm(data.summary.avg_rx_dbm)}
              color={rxColor(data.summary.avg_rx_dbm)}
            />
          </div>

          {/* Ticket lifecycle rollup (persisted state) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-2xl">
            <StatCard label="tickets open" value={data.ticket_counts.by_status.open} color="var(--status-warn)" />
            <StatCard label="acked" value={data.ticket_counts.by_status.acked} color="var(--accent)" />
            <StatCard label="dispatched" value={data.ticket_counts.by_status.dispatched} color="var(--status-unknown)" />
            <StatCard label="closed" value={data.ticket_counts.by_status.closed} color="var(--status-online)" />
          </div>

          {/* KPIs the pipeline does not measure yet — shown honestly */}
          <div className="grid grid-cols-2 gap-3 max-w-xl">
            <StatCard
              label="uptime"
              value="—"
              sub="not measured — needs continuous polling, not a CSV audit"
            />
            <StatCard
              label="truck-rolls avoided"
              value="—"
              sub="not measured — needs closed-ticket history"
            />
          </div>

          {/* Health trend — honest empty state */}
          <section>
            <h2 className="op-label mb-2">health-score trend</h2>
            <div className="op-card p-4">
              <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
                {data.trend.reason}
              </p>
            </div>
          </section>

          {/* Capacity hotspots */}
          <section>
            <div className="flex items-center gap-2 mb-2">
              <h2 className="op-label">capacity hotspots — pon utilisation %</h2>
              {anySplitterAssumed && (
                <AssumptionBadge
                  assumptions={[
                    "Splitter ratios were not configured; the agent assumed the ratio shown per port (splitter_assumed=true).",
                  ]}
                />
              )}
            </div>
            <div className="op-card p-4" style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={capacityData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="var(--border-dark)" vertical={false} />
                  <XAxis
                    dataKey="port"
                    tick={{ fill: "var(--text-on-dark-muted)", fontSize: 11, fontFamily: "monospace" }}
                    axisLine={{ stroke: "var(--border-dark-strong)" }}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "var(--text-on-dark-muted)", fontSize: 11, fontFamily: "monospace" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    contentStyle={{
                      backgroundColor: "var(--bg-dark-subtle)",
                      border: "1px solid var(--border-dark-strong)",
                      fontFamily: "monospace",
                      fontSize: 12,
                    }}
                    formatter={(value, _name, item) => [
                      `${value}% — ${(item?.payload as { detail: string }).detail}`,
                      "utilisation",
                    ]}
                  />
                  <Bar dataKey="pct" isAnimationActive={false}>
                    {capacityData.map((entry) => (
                      <Cell key={entry.port} fill={capacityColor(entry.pct)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Churn cohort */}
          <section>
            <h2 className="op-label mb-2">
              churn-risk cohort — {data.churn_risk.length} degrading ONTs
            </h2>
            {data.churn_risk.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
                No ONTs met the degradation criteria in this window.
              </p>
            ) : (
              <div className="op-card overflow-x-auto">
                <table className="op-table w-full border-collapse">
                  <thead>
                    <tr>
                      <th>ONT</th>
                      <th>Impact</th>
                      <th>Current rx</th>
                      <th>Degrading</th>
                      <th>Rate /day</th>
                      <th>90d churn prob</th>
                      <th>Rev at risk /yr</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.churn_risk.map((risk) => (
                      <tr key={risk.ont_serial}>
                        <td className="font-mono">{risk.ont_serial}</td>
                        <td
                          className="font-mono"
                          style={{ color: severityColor(risk.impact) }}
                        >
                          {risk.impact}
                        </td>
                        <td className="font-mono" style={{ color: rxColor(risk.current_rx_dbm) }}>
                          {fmtDbm(risk.current_rx_dbm)}
                        </td>
                        <td className="font-mono">{risk.days_degrading}d</td>
                        <td className="font-mono">{risk.degradation_rate.toFixed(2)} dB</td>
                        <td className="font-mono">
                          <span className="inline-flex items-center gap-2">
                            {(risk.estimated_churn_probability_90day * 100).toFixed(0)}%
                            <AssumptionBadge
                              assumptions={[
                                `Churn model: baseline ${risk.assumptions.baseline_probability * 100}%, subtle ${risk.assumptions.subtle_probability * 100}%, noticeable ${risk.assumptions.noticeable_probability * 100}%, severe ${risk.assumptions.severe_probability * 100}%, +${risk.assumptions.micro_dropout_bonus * 100}% micro-dropout bonus`,
                                `Assumed monthly ARPU: ${risk.assumptions.monthly_arpu}`,
                              ]}
                            />
                          </span>
                        </td>
                        <td className="font-mono">{fmtMoney(risk.estimated_annual_revenue_at_risk)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}

export default function ExecPage() {
  return (
    <RoleGuard minRole="manager">
      <ExecDashboard />
    </RoleGuard>
  );
}
