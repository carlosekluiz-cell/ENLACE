// ── Executive audit report (PDF, server-side) ──
//
// Built with pdfkit (pure JS, built-in Standard-14 fonts — no native deps,
// no headless browser: self-hosted portability). Renders the PERSISTED
// AuditResult verbatim-derived — the app reads, the agent computes.
//
// Honesty invariants are hard requirements here (ONTOLOGY.md §5):
//   - no estimated number prints without an "estimate" label and its
//     declared assumptions;
//   - absence of data prints as "not measured" / "—", never as zero or
//     "healthy" (frontier coverage notes always print, even with 0 findings);
//   - Unknown is its own status, reconciled: total = online+offline+unknown;
//   - the report ends with a mandatory "Data honesty" page.
//
// Brand: indigo accent #6366f1, dark cover, Courier for numbers.

import PDFDocument from "pdfkit";
import type { AuditProvenance, TicketWithState } from "@/lib/opsTypes";
import type { AuditResult } from "@/lib/types";

export interface ReportInput {
  tenantName: string;
  /** Labeled tenant-setting assumption lines (tenantSettings.ts). */
  tenantAssumptionLines: string[];
  provenance: AuditProvenance;
  result: AuditResult;
  /** Agent tickets joined with the persisted ticket_state overlay. */
  tickets: TicketWithState[];
  generatedBy: string;
  generatedAt: string;
}

// ── Palette (globals.css) ──
const INDIGO = "#6366f1";
const INDIGO_DEEP = "#4f46e5";
const DARK = "#0f172a";
const DARK_SUBTLE = "#1e293b";
const INK = "#111827";
const MUTED = "#6b7280";
const FAINT = "#9ca3af";
const RULE = "#e5e7eb";
const GREEN = "#15803d";
const AMBER = "#b45309";
const RED = "#dc2626";
const VIOLET = "#7c3aed";

const PAGE = { width: 595.28, height: 841.89 };
const MARGIN = 48;
const CONTENT_W = PAGE.width - MARGIN * 2;
const BOTTOM = PAGE.height - 64;

const SANS = "Helvetica";
const SANS_BOLD = "Helvetica-Bold";
const SANS_OBLIQUE = "Helvetica-Oblique";
const MONO = "Courier";
const MONO_BOLD = "Courier-Bold";

type Doc = InstanceType<typeof PDFDocument>;

function fmtNum(v: number, dp = 0): string {
  return v.toLocaleString("en-GB", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      }) + " UTC";
}

/** Missing is missing: null/undefined renders as an em-dash, never 0. */
function dash(v: number | null | undefined, fmt: (n: number) => string): string {
  return v === null || v === undefined ? "—" : fmt(v);
}

function sourceBadge(source: AuditProvenance["source"]): { label: string; color: string } {
  switch (source) {
    case "live":
      return { label: "LIVE — Elasticsearch feed", color: GREEN };
    case "audit":
      return { label: "AUDIT — uploaded CSV, real agent output", color: INDIGO };
    case "demo":
      return { label: "DEMO — bundled sample, real agent output", color: VIOLET };
  }
}

// ── Flow helpers ──

function ensureSpace(doc: Doc, needed: number): void {
  if (doc.y + needed > BOTTOM) doc.addPage();
}

function sectionTitle(doc: Doc, text: string): void {
  ensureSpace(doc, 60);
  doc.moveDown(0.8);
  const y = doc.y;
  doc.rect(MARGIN, y + 1, 3, 14).fill(INDIGO);
  doc
    .font(SANS_BOLD)
    .fontSize(13)
    .fillColor(INK)
    .text(text, MARGIN + 10, y, { width: CONTENT_W - 10 });
  doc.moveDown(0.35);
  doc.x = MARGIN;
}

function subTitle(doc: Doc, text: string): void {
  ensureSpace(doc, 40);
  doc.moveDown(0.5);
  doc.font(SANS_BOLD).fontSize(10.5).fillColor(INK).text(text, MARGIN, doc.y, {
    width: CONTENT_W,
  });
  doc.moveDown(0.2);
}

function para(doc: Doc, text: string, opts?: { color?: string; italic?: boolean; size?: number }): void {
  ensureSpace(doc, 30);
  doc
    .font(opts?.italic ? SANS_OBLIQUE : SANS)
    .fontSize(opts?.size ?? 9.5)
    .fillColor(opts?.color ?? INK)
    .text(text, MARGIN, doc.y, { width: CONTENT_W, lineGap: 1.5 });
  doc.moveDown(0.3);
}

/** Amber-tinted labeled note — used for assumption / coverage callouts. */
function noteBox(doc: Doc, label: string, lines: string[]): void {
  const bodyText = lines.join("\n");
  doc.font(SANS).fontSize(8.5);
  const bodyH = doc.heightOfString(bodyText, { width: CONTENT_W - 20, lineGap: 1.5 });
  const boxH = bodyH + 26;
  ensureSpace(doc, boxH + 10);
  const y = doc.y;
  doc.rect(MARGIN, y, CONTENT_W, boxH).fillOpacity(0.06).fill(AMBER).fillOpacity(1);
  doc.rect(MARGIN, y, 3, boxH).fill(AMBER);
  doc
    .font(SANS_BOLD)
    .fontSize(7.5)
    .fillColor(AMBER)
    .text(label.toUpperCase(), MARGIN + 10, y + 6, { width: CONTENT_W - 20 });
  doc
    .font(SANS)
    .fontSize(8.5)
    .fillColor(INK)
    .text(bodyText, MARGIN + 10, y + 17, { width: CONTENT_W - 20, lineGap: 1.5 });
  doc.y = y + boxH + 8;
  doc.x = MARGIN;
}

// ── Table ──

interface Col {
  header: string;
  width: number;
  align?: "left" | "right";
  mono?: boolean;
}

interface Cell {
  text: string;
  color?: string;
}

function drawTableHeader(doc: Doc, cols: Col[]): void {
  const y = doc.y;
  let x = MARGIN;
  doc.font(SANS_BOLD).fontSize(7.5).fillColor(MUTED);
  for (const col of cols) {
    doc.text(col.header.toUpperCase(), x, y, {
      width: col.width - 6,
      align: col.align ?? "left",
    });
    x += col.width;
  }
  const yAfter = y + 12;
  doc
    .moveTo(MARGIN, yAfter)
    .lineTo(MARGIN + cols.reduce((s, c) => s + c.width, 0), yAfter)
    .lineWidth(0.8)
    .strokeColor(INDIGO)
    .stroke();
  doc.y = yAfter + 4;
}

function table(doc: Doc, cols: Col[], rows: Cell[][]): void {
  ensureSpace(doc, 50);
  drawTableHeader(doc, cols);
  const totalW = cols.reduce((s, c) => s + c.width, 0);

  for (const row of rows) {
    // Measure row height (max cell height).
    let rowH = 0;
    row.forEach((cell, i) => {
      const col = cols[i];
      doc.font(col.mono ? MONO : SANS).fontSize(8.5);
      const h = doc.heightOfString(cell.text, { width: col.width - 6, lineGap: 1 });
      rowH = Math.max(rowH, h);
    });
    if (doc.y + rowH + 6 > BOTTOM) {
      doc.addPage();
      drawTableHeader(doc, cols);
    }
    const y = doc.y;
    let x = MARGIN;
    row.forEach((cell, i) => {
      const col = cols[i];
      doc
        .font(col.mono ? MONO : SANS)
        .fontSize(8.5)
        .fillColor(cell.color ?? INK)
        .text(cell.text, x, y, {
          width: col.width - 6,
          align: col.align ?? "left",
          lineGap: 1,
        });
      x += col.width;
    });
    const yAfter = y + rowH + 4;
    doc
      .moveTo(MARGIN, yAfter)
      .lineTo(MARGIN + totalW, yAfter)
      .lineWidth(0.4)
      .strokeColor(RULE)
      .stroke();
    doc.y = yAfter + 3;
  }
  doc.x = MARGIN;
  doc.moveDown(0.3);
}

function kvGrid(doc: Doc, pairs: Array<[string, string, string?]>): void {
  const rows: Cell[][] = pairs.map(([k, v, color]) => [
    { text: k, color: MUTED },
    { text: v, color: color ?? INK },
  ]);
  table(
    doc,
    [
      { header: "", width: 190 },
      { header: "", width: CONTENT_W - 190, mono: true },
    ],
    rows,
  );
}

function healthColor(score: number): string {
  return score >= 80 ? GREEN : score >= 50 ? AMBER : RED;
}

function priorityColor(p: string): string {
  const s = p.toLowerCase();
  if (s === "p1" || s.includes("critical")) return RED;
  if (s === "p2" || s.includes("warn")) return AMBER;
  return INK;
}

// ── Pages ──

function coverPage(doc: Doc, input: ReportInput): void {
  const { result, provenance } = input;
  doc.rect(0, 0, PAGE.width, PAGE.height).fill(DARK);
  doc.rect(0, 0, PAGE.width, 6).fill(INDIGO);

  // Wordmark
  doc.font(SANS_BOLD).fontSize(26).fillColor("#f8fafc").text("enlace", MARGIN, 84);
  doc
    .font(MONO_BOLD)
    .fontSize(11)
    .fillColor(INDIGO)
    .text("OPS", MARGIN + 96, 96);

  doc
    .font(SANS_BOLD)
    .fontSize(30)
    .fillColor("#f8fafc")
    .text("Network Audit Report", MARGIN, 170, { width: CONTENT_W });
  doc
    .font(SANS)
    .fontSize(15)
    .fillColor("#cbd5e1")
    .text(input.tenantName, MARGIN, 212);

  // Source badge
  const badge = sourceBadge(provenance.source);
  doc.font(MONO_BOLD).fontSize(9);
  const bw = doc.widthOfString(badge.label) + 20;
  doc.roundedRect(MARGIN, 250, bw, 20, 3).lineWidth(1).strokeColor(badge.color).stroke();
  doc.fillColor(badge.color).text(badge.label, MARGIN + 10, 256);

  // Meta block
  const meta: Array<[string, string]> = [
    ["audit date", fmtDate(provenance.created_at)],
    ["audit id", provenance.audit_id],
    ["agent version", provenance.agent_version ?? "not recorded"],
    ["uploaded by", provenance.uploader_name ?? "—"],
    [
      "analysis window",
      `${result.summary.analysis_period_days} days · ${fmtNum(result.summary.total_readings)} readings`,
    ],
  ];
  let y = 300;
  for (const [k, v] of meta) {
    doc.font(SANS).fontSize(8).fillColor("#64748b").text(k.toUpperCase(), MARGIN, y);
    doc.font(MONO).fontSize(9.5).fillColor("#e2e8f0").text(v, MARGIN + 130, y - 1, {
      width: CONTENT_W - 130,
    });
    y += 22;
  }

  // Health score — BIG
  const score = result.summary.health_score;
  const panelY = 470;
  doc.rect(MARGIN, panelY, CONTENT_W, 180).fill(DARK_SUBTLE);
  doc.rect(MARGIN, panelY, CONTENT_W, 2).fill(INDIGO_DEEP);
  doc
    .font(SANS_BOLD)
    .fontSize(9)
    .fillColor("#94a3b8")
    .text("FLEET HEALTH SCORE", MARGIN + 28, panelY + 26);
  doc
    .font(MONO_BOLD)
    .fontSize(96)
    .fillColor(healthColor(score))
    .text(String(score), MARGIN + 24, panelY + 44);
  const scoreW = doc.widthOfString(String(score));
  doc
    .font(MONO)
    .fontSize(20)
    .fillColor("#64748b")
    .text("/ 100", MARGIN + 32 + scoreW, panelY + 116);
  doc
    .font(SANS)
    .fontSize(9)
    .fillColor("#94a3b8")
    .text(
      `${fmtNum(result.summary.total_onts)} ONTs — ${fmtNum(result.summary.online)} online · ${fmtNum(result.summary.offline)} offline · ${fmtNum(result.summary.unknown)} unknown (unknown is not an outage)`,
      MARGIN + 28,
      panelY + 152,
      { width: CONTENT_W - 56 },
    );

  doc
    .font(SANS)
    .fontSize(8)
    .fillColor("#64748b")
    .text(
      `Generated ${fmtDate(input.generatedAt)} by ${input.generatedBy}. Every figure labeled "estimate" in this report derives from declared assumptions, not measurements — see the Data honesty page.`,
      MARGIN,
      PAGE.height - 90,
      { width: CONTENT_W, lineGap: 2 },
    );
}

function summaryPage(doc: Doc, input: ReportInput): void {
  const { result, tickets } = input;
  const s = result.summary;

  sectionTitle(doc, "1 · Executive summary");
  para(
    doc,
    `This audit analysed ${fmtNum(s.total_onts)} ONTs over ${s.analysis_period_days} day(s) (${fmtNum(s.total_readings)} readings). The fleet health score is ${s.health_score}/100.`,
  );

  subTitle(doc, "ONT status");
  table(
    doc,
    [
      { header: "Status", width: 160 },
      { header: "ONTs", width: 100, align: "right", mono: true },
      { header: "Note", width: CONTENT_W - 260 },
    ],
    [
      [{ text: "Online" }, { text: fmtNum(s.online), color: GREEN }, { text: "includes low-signal and dying (still up)" }],
      [{ text: "Offline" }, { text: fmtNum(s.offline), color: RED }, { text: "offline / power-fail / fibre-cut" }],
      [
        { text: "Unknown" },
        { text: fmtNum(s.unknown), color: VIOLET },
        { text: "status not determinable — NOT an outage, never counted as offline" },
      ],
      [{ text: "Total", color: MUTED }, { text: fmtNum(s.total_onts) }, { text: "total = online + offline + unknown (reconciles by construction)" }],
    ],
  );
  kvGrid(doc, [
    ["Average rx power", `${s.avg_rx_dbm.toFixed(1)} dBm`],
    ["Worst rx power", `${s.worst_rx_dbm.toFixed(1)} dBm`],
  ]);

  subTitle(doc, "Findings by detection module");
  const findingRows: Array<[string, number, string]> = [
    ["Faults (port/OLT level)", result.faults.length, "§2"],
    ["Ghost customers", result.ghosts.length, "§3"],
    ["Churn-risk ONTs", result.churn_risk.length, "§4"],
    ["Capacity entries", result.capacity.length, "§5"],
    ["Flapping ONTs", result.flapping.length, "—"],
    ["Weather correlations (suspected)", result.weather_correlation.length, "—"],
    ["Reflectance events", result.reflectance.length, "—"],
    ["SFP health entries", result.sfp_health.length, "—"],
    ["Pre-FEC findings", result.fec_health.findings.length, "§6.1 (see coverage note)"],
    ["Laser end-of-life predictions", result.laser_health.predictions.length, "§6.2 (see coverage counters)"],
    ["Rogue-ONT hypotheses", result.rogue.length, "§6.3 (hypotheses, not verdicts)"],
  ];
  table(
    doc,
    [
      { header: "Module", width: 250 },
      { header: "Count", width: 80, align: "right", mono: true },
      { header: "Section", width: CONTENT_W - 330 },
    ],
    findingRows.map(([m, n, sec]) => [
      { text: m },
      { text: fmtNum(n), color: n > 0 ? INK : MUTED },
      { text: sec, color: MUTED },
    ]),
  );

  subTitle(doc, "Tickets");
  const byPriority = new Map<string, number>();
  const byStatus = new Map<string, number>();
  for (const t of tickets) {
    byPriority.set(t.ticket.priority, (byPriority.get(t.ticket.priority) ?? 0) + 1);
    byStatus.set(t.state.status, (byStatus.get(t.state.status) ?? 0) + 1);
  }
  const prioLine =
    tickets.length === 0
      ? "none generated for this audit"
      : [...byPriority.entries()]
          .sort((a, b) => a[0].localeCompare(b[0]))
          .map(([p, n]) => `${p}: ${n}`)
          .join("   ");
  const statusLine =
    tickets.length === 0
      ? "—"
      : ["open", "acked", "dispatched", "closed"]
          .map((st) => `${st}: ${byStatus.get(st) ?? 0}`)
          .join("   ");
  kvGrid(doc, [
    ["Tickets generated", fmtNum(tickets.length)],
    ["By priority", prioLine],
    ["By lifecycle status", statusLine],
  ]);

  const ir = result.import_report;
  para(
    doc,
    ir
      ? `Data intake: CSV import — ${fmtNum(ir.rows_ok)} rows parsed, ${fmtNum(ir.rows_skipped)} skipped. Full import honesty counters on the final page.`
      : "Data intake: not CSV-fed (no import report) — stated, not hidden. See the Data honesty page.",
    { color: MUTED, size: 8.5 },
  );
}

function faultsSection(doc: Doc, result: AuditResult): void {
  sectionTitle(doc, "2 · Faults");
  if (result.faults.length === 0) {
    para(doc, "No port- or OLT-level fault events were detected in this window.", { color: MUTED });
    return;
  }
  table(
    doc,
    [
      { header: "OLT / PON port", width: 130, mono: true },
      { header: "Type", width: 80 },
      { header: "Severity", width: 70 },
      { header: "Affected ONTs", width: 90, align: "right", mono: true },
      { header: "Dying gasps", width: 80, align: "right", mono: true },
      { header: "Detection", width: CONTENT_W - 450, align: "right", mono: true },
    ],
    result.faults.map((f) => [
      { text: `${f.olt_id}\n${f.pon_port}` },
      { text: f.fault_type },
      { text: f.severity, color: priorityColor(f.severity) },
      { text: fmtNum(f.affected_onts.length) },
      { text: fmtNum(f.affected_onts.filter((o) => o.had_dying_gasp).length) },
      { text: `${f.detection_latency_seconds}s` },
    ]),
  );
  para(
    doc,
    "Dying-gasp counts are measured evidence (the ONT's own power-fail message), used to separate power outages from fibre cuts.",
    { color: MUTED, size: 8.5, italic: true },
  );
}

function ghostsSection(doc: Doc, result: AuditResult): void {
  sectionTitle(doc, "3 · Ghost customers");
  para(
    doc,
    "ONTs that are optically online but have carried no Ethernet link for an extended period — connected, possibly unbilled.",
  );
  if (result.ghosts.length === 0) {
    para(doc, "No ghost customers were detected in this audit.", { color: MUTED });
    return;
  }
  table(
    doc,
    [
      { header: "ONT serial", width: 110, mono: true },
      { header: "Port", width: 70, mono: true },
      { header: "Rx (dBm)", width: 65, align: "right", mono: true },
      { header: "Days online", width: 70, align: "right", mono: true },
      { header: "Distance", width: 70, align: "right", mono: true },
      { header: "Est. revenue/mo (ESTIMATE)", width: CONTENT_W - 385, align: "right", mono: true },
    ],
    result.ghosts.map((g) => [
      { text: g.ont_serial },
      { text: g.port },
      { text: g.rx_power_dbm.toFixed(1) },
      { text: fmtNum(g.days_online) },
      { text: dash(g.distance_m, (d) => `${fmtNum(d)} m`) },
      { text: `${fmtNum(g.estimated_monthly_revenue, 2)} (est.)`, color: AMBER },
    ]),
  );
  noteBox(doc, "Estimate — assumption declared", [
    "The revenue figure per ghost is the configured ARPU assumption, not billing truth. It answers \"what might this connection be worth monthly IF it were a paying customer\".",
  ]);
}

function churnSection(doc: Doc, result: AuditResult): void {
  sectionTitle(doc, "4 · Churn risk");
  para(
    doc,
    "ONTs with degrading optical signal, scored against an assumed churn-probability model. Probabilities and revenue-at-risk figures are ESTIMATES.",
  );
  if (result.churn_risk.length === 0) {
    para(doc, "No ONTs met the degradation criteria in this window.", { color: MUTED });
    return;
  }
  table(
    doc,
    [
      { header: "ONT serial", width: 105, mono: true },
      { header: "Impact", width: 65 },
      { header: "Rx (dBm)", width: 60, align: "right", mono: true },
      { header: "Degrading", width: 62, align: "right", mono: true },
      { header: "Rate/day", width: 62, align: "right", mono: true },
      { header: "90d churn (EST.)", width: 75, align: "right", mono: true },
      { header: "Rev at risk/yr (EST.)", width: CONTENT_W - 429, align: "right", mono: true },
    ],
    result.churn_risk.map((c) => [
      { text: c.ont_serial },
      { text: c.impact, color: priorityColor(c.impact) },
      { text: c.current_rx_dbm.toFixed(1) },
      { text: `${c.days_degrading}d` },
      { text: `${c.degradation_rate.toFixed(2)} dB` },
      { text: `${(c.estimated_churn_probability_90day * 100).toFixed(0)}% (est.)`, color: AMBER },
      { text: `${fmtNum(c.estimated_annual_revenue_at_risk, 2)} (est.)`, color: AMBER },
    ]),
  );
  const a = result.churn_risk[0].assumptions;
  noteBox(doc, "Estimate — assumed churn model (declared by the agent)", [
    `Churn probabilities: baseline ${a.baseline_probability * 100}%, subtle ${a.subtle_probability * 100}%, noticeable ${a.noticeable_probability * 100}%, severe ${a.severe_probability * 100}%, +${a.micro_dropout_bonus * 100}% micro-dropout bonus.`,
    `Assumed monthly ARPU: ${a.monthly_arpu}. These are assumptions, not measurements.`,
  ]);
}

function capacitySection(doc: Doc, result: AuditResult): void {
  sectionTitle(doc, "5 · Capacity");
  if (result.capacity.length === 0) {
    para(doc, "No capacity data in this audit.", { color: MUTED });
    return;
  }
  table(
    doc,
    [
      { header: "Port", width: 75, mono: true },
      { header: "OLT", width: 90, mono: true },
      { header: "ONTs / max", width: 75, align: "right", mono: true },
      { header: "Utilisation", width: 70, align: "right", mono: true },
      { header: "Splitter", width: 90, mono: true },
      { header: "Months to full", width: CONTENT_W - 400, align: "right", mono: true },
    ],
    [...result.capacity]
      .sort((a, b) => b.utilisation_pct - a.utilisation_pct)
      .map((c) => [
        { text: c.port },
        { text: c.olt_id },
        { text: `${c.active_onts}/${c.max_ports}` },
        {
          text: `${c.utilisation_pct.toFixed(1)}%`,
          color: c.utilisation_pct >= 90 ? RED : c.utilisation_pct >= 80 ? AMBER : INK,
        },
        { text: c.splitter_assumed ? `${c.splitter_type} (assumed)` : c.splitter_type },
        { text: dash(c.months_to_full, (m) => `${fmtNum(m)} mo`) },
      ]),
  );
  if (result.capacity.some((c) => c.splitter_assumed)) {
    noteBox(doc, "Assumption declared", [
      "Splitter ratios marked \"(assumed)\" were not configured — the agent assumed the ratio shown; utilisation on those ports inherits that assumption.",
    ]);
  }
  para(doc, "\"—\" under months-to-full means no growth trend was measurable — not measured, not zero.", {
    color: MUTED,
    size: 8.5,
    italic: true,
  });
}

function frontierSection(doc: Doc, result: AuditResult): void {
  sectionTitle(doc, "6 · Frontier detections");
  para(
    doc,
    "Early-warning modules. Coverage is stated explicitly: absence of a finding is not evidence of health when only part of the estate was assessable.",
  );

  // 6.1 Pre-FEC
  subTitle(doc, "6.1 · Pre-FEC degradation");
  const fec = result.fec_health;
  noteBox(doc, "Coverage", [fec.coverage_note]);
  if (fec.findings.length === 0) {
    para(
      doc,
      `No pre-FEC findings among the ${fmtNum(fec.onts_with_fec_data)} of ${fmtNum(fec.total_onts)} ONTs with FEC data. ONTs without FEC counters were not assessed — not measured, not healthy.`,
      { color: MUTED },
    );
  } else {
    table(
      doc,
      [
        { header: "ONT serial", width: 105, mono: true },
        { header: "Port", width: 65, mono: true },
        { header: "Corrected/h", width: 70, align: "right", mono: true },
        { header: "Uncorrected", width: 70, align: "right", mono: true },
        { header: "Hypothesis", width: 110 },
        { header: "Confidence", width: CONTENT_W - 420 },
      ],
      fec.findings.map((f) => [
        { text: f.serial_number },
        { text: f.pon_port },
        { text: fmtNum(f.corrected_rate_per_hour, 1) },
        { text: fmtNum(f.uncorrected_total) },
        { text: f.hypothesis },
        { text: f.confidence },
      ]),
    );
  }

  // 6.2 Laser health
  subTitle(doc, "6.2 · Laser end-of-life (bias-current drift)");
  const lh = result.laser_health;
  const cov = lh.coverage;
  kvGrid(doc, [
    ["ONTs total", fmtNum(cov.onts_total)],
    ["ONTs with bias data", fmtNum(cov.onts_with_bias)],
    ["ONTs analyzed", fmtNum(cov.onts_analyzed)],
    ["Gated out (insufficient data)", `${fmtNum(cov.onts_gated_out)} — "not assessable yet", not healthy`],
    ["Temperature-detrended", fmtNum(cov.onts_temperature_detrended)],
    ["Flagged", fmtNum(cov.onts_flagged)],
  ]);
  if (lh.predictions.length === 0) {
    para(
      doc,
      cov.onts_with_bias === 0
        ? "No ONTs reported laser bias current in this dataset — laser ageing was NOT assessed. This is absence of data, not an all-clear."
        : "No laser end-of-life predictions among the analyzed ONTs.",
      { color: MUTED },
    );
  } else {
    table(
      doc,
      [
        { header: "ONT serial", width: 100, mono: true },
        { header: "Drift %/mo", width: 65, align: "right", mono: true },
        { header: "Urgency", width: 90 },
        { header: "ETA to EOL (HEURISTIC)", width: 130, mono: true },
        { header: "R²", width: CONTENT_W - 385, align: "right", mono: true },
      ],
      lh.predictions.map((p) => [
        { text: p.serial_number },
        { text: p.drift_pct_per_month.toFixed(2) },
        { text: p.urgency, color: p.urgency === "ActivelyFailing" ? RED : AMBER },
        {
          text: `${p.eta_days_to_eol_earliest}–${p.eta_days_to_eol_latest ?? "open-ended"} days (heuristic)`,
          color: AMBER,
        },
        { text: p.confidence.toFixed(2) },
      ]),
    );
    noteBox(doc, "Heuristic ETA — not a promise", [
      "ETA ranges use a +50%-over-baseline end-of-life HEURISTIC on the drift confidence band. They are planning ranges, not failure dates.",
    ]);
  }

  // 6.3 Rogue
  subTitle(doc, "6.3 · Rogue-ONT hypotheses");
  para(
    doc,
    "Passive multi-victim upstream-integrity analysis. Every finding here is a HYPOTHESIS with a confirmation step — never a verdict against a specific ONT.",
    { italic: true, size: 8.5, color: MUTED },
  );
  if (result.rogue.length === 0) {
    para(doc, "No rogue-ONT hypotheses were raised for this window.", { color: MUTED });
  } else {
    for (const r of result.rogue) {
      ensureSpace(doc, 70);
      para(
        doc,
        `${r.olt} ${r.pon_port} — ${r.victim_count} victim ONTs, confidence ${r.confidence} (hypothesis, not verdict)`,
      );
      para(doc, `Evidence: ${r.evidence.join("; ")}`, { color: MUTED, size: 8.5 });
      para(
        doc,
        `Candidates (ranked, unconfirmed): ${r.candidates.map((c) => `${c.serial_number} (${c.score.toFixed(2)})`).join(", ")}`,
        { color: MUTED, size: 8.5 },
      );
      para(doc, `Confirmation step: ${r.recommended_action}`, { size: 8.5 });
    }
  }
}

function ticketsSection(doc: Doc, tickets: TicketWithState[]): void {
  sectionTitle(doc, "7 · Tickets & SLA");
  if (tickets.length === 0) {
    para(doc, "No tickets were generated from this audit.", { color: MUTED });
    return;
  }
  para(
    doc,
    "Lifecycle status and assignment come from the persisted ticket_state overlay (who acknowledged / dispatched / closed, and when) — the agent's ticket data itself is never modified.",
    { color: MUTED, size: 8.5 },
  );
  table(
    doc,
    [
      { header: "Ticket", width: 95, mono: true },
      { header: "Priority", width: 50 },
      { header: "Team", width: 80 },
      { header: "SLA due", width: 85, mono: true },
      { header: "Status", width: 70 },
      { header: "ONTs", width: 40, align: "right", mono: true },
      { header: "Rev at risk/yr (EST.)", width: CONTENT_W - 420, align: "right", mono: true },
    ],
    tickets.map((t) => [
      { text: t.ticket_ref },
      { text: t.ticket.priority, color: priorityColor(t.ticket.priority) },
      { text: t.ticket.team },
      { text: fmtDate(t.sla_due).replace(" UTC", "") },
      {
        text:
          t.state.status +
          (t.state.assigned_user_name ? `\n→ ${t.state.assigned_user_name}` : ""),
        color: t.state.status === "closed" ? GREEN : t.state.status === "open" ? AMBER : INK,
      },
      { text: fmtNum(t.ticket.affected_ont_count) },
      { text: `${fmtNum(t.ticket.estimated_revenue_at_risk_annual, 2)} (est.)`, color: AMBER },
    ]),
  );

  for (const t of tickets) {
    ensureSpace(doc, 80);
    subTitle(doc, `${t.ticket_ref} — ${t.ticket.fault_type}`);
    para(doc, `Recommended action: ${t.ticket.recommended_action}`, { size: 8.5 });
    para(doc, `Evidence: ${t.ticket.evidence.join(" · ")}`, { color: MUTED, size: 8.5 });
    para(
      doc,
      `Estimates — revenue at risk ${fmtNum(t.ticket.estimated_revenue_at_risk_annual, 2)}/yr, fix cost ${fmtNum(t.ticket.fix_cost_estimate, 2)}, ROI ${t.ticket.estimated_roi.toFixed(2)}x — all estimates from the declared assumptions below.`,
      { color: AMBER, size: 8.5 },
    );
    noteBox(doc, "Assumptions declared for this ticket", t.ticket.assumptions);
  }
}

function honestyPage(doc: Doc, input: ReportInput): void {
  const { result, tickets } = input;
  doc.addPage();
  sectionTitle(doc, "8 · Data honesty");
  para(
    doc,
    "This page is mandatory in every Enlace report. It states how much of the source data was actually understood, what was assumed, and what was not measured.",
  );

  subTitle(doc, "Import report");
  const ir = result.import_report;
  if (!ir) {
    para(
      doc,
      "This audit was not CSV-fed, so there is no import report. That is a statement about provenance, not about data quality.",
      { color: MUTED },
    );
  } else {
    kvGrid(doc, [
      ["Rows parsed OK", fmtNum(ir.rows_ok)],
      ["Rows skipped", fmtNum(ir.rows_skipped), ir.rows_skipped > 0 ? AMBER : INK],
      ["Cells unparsed (kept as null)", fmtNum(ir.cells_unparsed), ir.cells_unparsed > 0 ? AMBER : INK],
      ["Unrecognized status rows", fmtNum(ir.unknown_statuses), ir.unknown_statuses > 0 ? VIOLET : INK],
      [
        "Unrecognized status values",
        ir.unknown_status_values.length > 0 ? ir.unknown_status_values.join(", ") : "none",
      ],
      [
        "Snapshot mode",
        ir.snapshot_mode ? "YES — timestamps were defaulted (file had no timestamp column)" : "no",
        ir.snapshot_mode ? AMBER : INK,
      ],
      ["Delimiter (sniffed)", JSON.stringify(ir.delimiter)],
    ]);
    if (ir.skip_samples.length > 0) {
      noteBox(doc, "Skipped-row samples (sanitized)", ir.skip_samples);
    }
  }

  subTitle(doc, "Coverage notes");
  const cov = result.laser_health.coverage;
  para(doc, `• ${result.fec_health.coverage_note}`, { size: 8.5 });
  para(
    doc,
    `• Laser health: ${fmtNum(cov.onts_with_bias)} of ${fmtNum(cov.onts_total)} ONTs reported bias current; ${fmtNum(cov.onts_analyzed)} analyzed, ${fmtNum(cov.onts_gated_out)} gated out as not assessable yet. ONTs without bias data were NOT assessed — absence of data is not health.`,
    { size: 8.5 },
  );
  para(
    doc,
    "• Rogue analysis is passive and hypothesis-only; candidates are ranked for a vendor-native confirmation step, never named as culprits.",
    { size: 8.5 },
  );
  para(
    doc,
    "• Uptime and truck-rolls-avoided are not measured by a CSV audit and therefore do not appear as numbers anywhere in this report.",
    { size: 8.5 },
  );

  subTitle(doc, "Assumptions in force");
  const lines = new Set<string>();
  for (const t of tickets) for (const a of t.ticket.assumptions) lines.add(a);
  if (result.churn_risk.length > 0) {
    const a = result.churn_risk[0].assumptions;
    lines.add(
      `Churn model (agent-declared): baseline ${a.baseline_probability * 100}%, subtle ${a.subtle_probability * 100}%, noticeable ${a.noticeable_probability * 100}%, severe ${a.severe_probability * 100}%, +${a.micro_dropout_bonus * 100}% micro-dropout bonus; assumed monthly ARPU ${a.monthly_arpu}.`,
    );
  }
  if (result.capacity.some((c) => c.splitter_assumed)) {
    lines.add(
      "Splitter ratios on some ports were assumed, not configured (marked \"(assumed)\" in §5).",
    );
  }
  for (const l of input.tenantAssumptionLines) lines.add(l);
  if (lines.size === 0) {
    para(doc, "No assumption-bearing figures appear in this audit.", { color: MUTED });
  } else {
    for (const l of lines) para(doc, `• ${l}`, { size: 8.5 });
  }
  para(
    doc,
    "Tenant-setting lines above are admin-editable constants that feed FUTURE estimate math; the figures in this report carry the assumptions the agent declared when the audit ran and are never retroactively recomputed.",
    { color: MUTED, size: 8, italic: true },
  );

  doc.moveDown(0.8);
  const stY = doc.y;
  const statement =
    "Estimates are estimates. Every figure labeled \"estimate\" or \"est.\" in this report is derived from the declared assumptions above — it is not a measurement. Where data was not collected, this report says \"not measured\" or \"—\"; absence of data is never rendered as zero, and never as health.";
  doc.font(SANS_BOLD).fontSize(9.5);
  const stH = doc.heightOfString(statement, { width: CONTENT_W - 24, lineGap: 2 }) + 20;
  doc.rect(MARGIN, stY, CONTENT_W, stH).fillOpacity(0.07).fill(INDIGO).fillOpacity(1);
  doc.rect(MARGIN, stY, 3, stH).fill(INDIGO);
  doc
    .fillColor(INK)
    .text(statement, MARGIN + 12, stY + 10, { width: CONTENT_W - 24, lineGap: 2 });
  doc.y = stY + stH + 10;
  doc.x = MARGIN;
}

function ontAppendix(doc: Doc, result: AuditResult): void {
  doc.addPage();
  sectionTitle(doc, `Appendix A · ONT inventory (${fmtNum(result.onts.length)})`);
  para(
    doc,
    "Latest snapshot per ONT. \"—\" means the value was not present in the source data (missing is missing, never zero).",
    { color: MUTED, size: 8.5 },
  );
  const MAX = 500;
  table(
    doc,
    [
      { header: "Serial", width: 105, mono: true },
      { header: "Port", width: 65, mono: true },
      { header: "Status", width: 70 },
      { header: "Rx (dBm)", width: 60, align: "right", mono: true },
      { header: "Tx (dBm)", width: 60, align: "right", mono: true },
      { header: "Distance", width: 65, align: "right", mono: true },
      { header: "Eth (Mbps)", width: CONTENT_W - 425, align: "right", mono: true },
    ],
    result.onts.slice(0, MAX).map((o) => [
      { text: o.serial_number },
      { text: o.pon_port },
      {
        text: o.status,
        color:
          o.status === "Online"
            ? GREEN
            : o.status === "Unknown"
              ? VIOLET
              : o.status === "LowSignal" || o.status === "Dying"
                ? AMBER
                : RED,
      },
      { text: dash(o.rx_power_dbm, (v) => v.toFixed(1)) },
      { text: dash(o.tx_power_dbm, (v) => v.toFixed(1)) },
      { text: `${fmtNum(o.distance_meters)} m` },
      { text: dash(o.eth_speed_mbps, (v) => fmtNum(v)) },
    ]),
  );
  if (result.onts.length > MAX) {
    para(doc, `Truncated at ${MAX} of ${fmtNum(result.onts.length)} ONTs for print size.`, {
      color: MUTED,
      size: 8.5,
    });
  }
}

function opticalBudgetAppendix(doc: Doc, result: AuditResult): void {
  if (result.optical_budget.length === 0) return;
  doc.addPage();
  sectionTitle(
    doc,
    `Appendix B · Optical budget (${fmtNum(result.optical_budget.length)} ONTs)`,
  );
  para(
    doc,
    "Measured rx vs. the expected rx from the link-budget model (fibre + connector + splitter losses). Where the splitter ratio was assumed, the expectation inherits that assumption and the row says so.",
    { color: MUTED, size: 8.5 },
  );
  table(
    doc,
    [
      { header: "Serial", width: 100, mono: true },
      { header: "Port", width: 60, mono: true },
      { header: "Rx (dBm)", width: 58, align: "right", mono: true },
      { header: "Expected", width: 58, align: "right", mono: true },
      { header: "Margin (dB)", width: 65, align: "right", mono: true },
      { header: "Excess loss", width: 65, align: "right", mono: true },
      { header: "Status", width: CONTENT_W - 406 },
    ],
    [...result.optical_budget]
      .sort((a, b) => a.margin_db - b.margin_db)
      .map((o) => [
        { text: o.ont_serial },
        { text: o.port },
        { text: o.avg_rx_power_dbm.toFixed(1) },
        { text: `${o.expected_rx_dbm.toFixed(1)}${o.splitter_assumed ? " (assumed split)" : ""}` },
        { text: o.margin_db.toFixed(1), color: o.margin_db < 3 ? RED : o.margin_db < 6 ? AMBER : INK },
        { text: o.excess_loss_db.toFixed(1), color: o.excess_loss_db > o.excess_threshold_db ? AMBER : INK },
        {
          text: o.probable_issue ? `${o.budget_status} — ${o.probable_issue}` : o.budget_status,
          color: o.budget_status.toLowerCase() === "ok" ? MUTED : AMBER,
        },
      ]),
  );
}

// ── Entry point ──

export function buildAuditReport(input: ReportInput): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({
      size: "A4",
      margins: { top: MARGIN, bottom: 56, left: MARGIN, right: MARGIN },
      bufferPages: true,
      info: {
        Title: `Enlace network audit report — ${input.tenantName}`,
        Author: "Enlace Operations",
        Subject: `Audit ${input.provenance.audit_id}`,
      },
    });
    const chunks: Buffer[] = [];
    doc.on("data", (c: Buffer) => chunks.push(c));
    doc.on("end", () => resolve(Buffer.concat(chunks)));
    doc.on("error", reject);

    coverPage(doc, input);
    doc.addPage();
    summaryPage(doc, input);
    faultsSection(doc, input.result);
    ghostsSection(doc, input.result);
    churnSection(doc, input.result);
    capacitySection(doc, input.result);
    frontierSection(doc, input.result);
    ticketsSection(doc, input.tickets);
    honestyPage(doc, input);
    ontAppendix(doc, input.result);
    opticalBudgetAppendix(doc, input.result);

    // Footer on every content page (skip the dark cover).
    const range = doc.bufferedPageRange();
    for (let i = range.start + 1; i < range.start + range.count; i++) {
      doc.switchToPage(i);
      // Writing below the bottom margin would trigger an auto page-break
      // (spawning blank pages) — lift the margin while stamping the footer.
      doc.page.margins.bottom = 0;
      doc
        .font(SANS)
        .fontSize(7)
        .fillColor(FAINT)
        .text(
          `enlace ops — network audit report · ${input.tenantName} · audit ${input.provenance.audit_id}`,
          MARGIN,
          PAGE.height - 40,
          { width: CONTENT_W - 60, lineBreak: false },
        );
      doc.text(`${i + 1} / ${range.count}`, PAGE.width - MARGIN - 50, PAGE.height - 40, {
        width: 50,
        align: "right",
        lineBreak: false,
      });
      doc.page.margins.bottom = 56;
    }

    doc.end();
  });
}
