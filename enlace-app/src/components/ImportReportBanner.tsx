"use client";

// Honesty rule 3: the CSV import report is surfaced on every audit view.
// You always know how much of the source file the agent actually understood.

import type { ImportReportSummary } from "@/lib/types";

export default function ImportReportBanner({
  report,
}: {
  report: ImportReportSummary | undefined;
}) {
  if (!report) {
    return (
      <div
        className="px-4 py-2 font-mono text-[11px]"
        style={{
          backgroundColor: "var(--bg-dark-surface)",
          border: "1px solid var(--border-dark)",
          color: "var(--text-on-dark-muted)",
        }}
      >
        No import report — this audit was not fed from a CSV import.
      </div>
    );
  }

  const hasIssues =
    report.rows_skipped > 0 ||
    report.cells_unparsed > 0 ||
    report.unknown_statuses > 0 ||
    report.snapshot_mode;

  return (
    <div
      className="px-4 py-2"
      style={{
        backgroundColor: "var(--bg-dark-surface)",
        border: `1px solid ${hasIssues ? "var(--status-warn)" : "var(--border-dark-strong)"}`,
      }}
    >
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px]"
        style={{ color: "var(--text-on-dark-secondary)" }}
      >
        <span className="op-label">import report</span>
        <span>{report.rows_ok.toLocaleString()} rows ok</span>
        <span style={{ color: report.rows_skipped > 0 ? "var(--status-warn)" : undefined }}>
          {report.rows_skipped} skipped
        </span>
        <span style={{ color: report.cells_unparsed > 0 ? "var(--status-warn)" : undefined }}>
          {report.cells_unparsed} cells unparsed
        </span>
        <span style={{ color: report.unknown_statuses > 0 ? "var(--status-unknown)" : undefined }}>
          {report.unknown_statuses} unknown statuses
        </span>
        {report.snapshot_mode && (
          <span style={{ color: "var(--status-warn)" }}>
            snapshot mode — timestamps defaulted to import time
          </span>
        )}
        <span style={{ color: "var(--text-on-dark-muted)" }}>
          delimiter “{report.delimiter}”
        </span>
      </div>
      {report.unknown_status_values.length > 0 && (
        <p className="font-mono text-[11px] mt-1" style={{ color: "var(--status-unknown)" }}>
          unrecognized status values: {report.unknown_status_values.join(", ")}
        </p>
      )}
      {report.skip_samples.length > 0 && (
        <p className="font-mono text-[11px] mt-1" style={{ color: "var(--text-on-dark-muted)" }}>
          skip samples: {report.skip_samples.join(" · ")}
        </p>
      )}
    </div>
  );
}
