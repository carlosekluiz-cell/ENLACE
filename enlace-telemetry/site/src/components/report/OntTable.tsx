"use client";

import { useState, useMemo } from "react";
import type { AuditResult, OntData } from "@/lib/audit-types";

interface OntTableProps {
  result: AuditResult;
  filter: string | null;
}

interface OntRow {
  serial: string;
  ponPort: string;
  rxDbm: number | null;
  status: string;
  issue: string | null;
  issueSeverity: "critical" | "warning" | "info" | null;
  filterKey: string | null;
}

type SortKey = "serial" | "ponPort" | "rxDbm" | "status" | "issue";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 50;

function rxColor(rx: number | null): string {
  if (rx === null) return "var(--text-on-dark-muted)";
  if (rx > -25) return "#22c55e";
  if (rx >= -28) return "#f59e0b";
  return "#ef4444";
}

function statusDot(status: string): string {
  const s = status.toUpperCase();
  if (s === "ONLINE" || s === "ACTIVE") return "#22c55e";
  if (s === "OFFLINE" || s === "DOWN" || s === "INACTIVE") return "#ef4444";
  return "#f59e0b";
}

function statusLabel(status: string): string {
  const s = status.toUpperCase();
  if (s === "ONLINE" || s === "ACTIVE") return "ONLINE";
  if (s === "OFFLINE" || s === "DOWN" || s === "INACTIVE") return "OFFLINE";
  return s;
}

function rowBgColor(severity: "critical" | "warning" | "info" | null): string {
  if (severity === "critical") return "rgba(239, 68, 68, 0.08)";
  if (severity === "warning") return "rgba(245, 158, 11, 0.06)";
  return "transparent";
}

export default function OntTable({ result, filter }: OntTableProps) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("rxDbm");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  // Build lookup sets for issues
  const rows = useMemo(() => {
    const ghostSerials = new Set(result.ghosts.map((g) => g.ont_serial));
    const churnSerials = new Map(
      result.churn_risk.map((c) => [c.ont_serial, c])
    );
    const flappingSerials = new Set(
      result.flapping
        .map((f) => f.ont_serial)
        .filter((s): s is string => !!s)
    );
    const reflectanceSerials = new Set(
      result.reflectance
        .map((r) => r.ont_serial)
        .filter((s): s is string => !!s)
    );
    const opticalBudgetSerials = new Set(
      result.optical_budget
        .map((o) => o.ont_serial)
        .filter((s): s is string => !!s)
    );

    // Fault-affected serials
    const faultSerials = new Set<string>();
    for (const f of result.faults) {
      if (f.affected_onts) {
        for (const s of f.affected_onts) faultSerials.add(s);
      }
    }

    // Diagnostic alerts by serial
    const alertsBySerial = new Map<string, string>();
    if (result.diagnostics?.alerts) {
      for (const a of result.diagnostics.alerts) {
        if (
          !alertsBySerial.has(a.serial_number) ||
          a.severity === "critical"
        ) {
          alertsBySerial.set(a.serial_number, a.alert_type);
        }
      }
    }

    return result.onts.map((ont: OntData): OntRow => {
      const s = ont.serial_number;
      let issue: string | null = null;
      let issueSeverity: "critical" | "warning" | "info" | null = null;
      let filterKey: string | null = null;

      // Priority: fault > ghost > churn > flapping > reflectance > optical_budget > diagnostic alert
      if (faultSerials.has(s)) {
        issue = "Fault affected";
        issueSeverity = "critical";
        filterKey = "faults";
      } else if (ghostSerials.has(s)) {
        issue = "Ghost customer";
        issueSeverity = "warning";
        filterKey = "ghosts";
      } else if (churnSerials.has(s)) {
        const cr = churnSerials.get(s)!;
        issue = `Degrading (${cr.days_degrading}d, ${(cr.churn_probability_90day * 100).toFixed(0)}% churn risk)`;
        issueSeverity = cr.churn_probability_90day > 0.5 ? "critical" : "warning";
        filterKey = "churn_risk";
      } else if (flappingSerials.has(s)) {
        issue = "Flapping";
        issueSeverity = "warning";
        filterKey = "flapping";
      } else if (reflectanceSerials.has(s)) {
        issue = "Reflectance issue";
        issueSeverity = "warning";
        filterKey = "reflectance";
      } else if (opticalBudgetSerials.has(s)) {
        issue = "Low optical margin";
        issueSeverity = "warning";
        filterKey = "optical_budget";
      } else if (alertsBySerial.has(s)) {
        issue = alertsBySerial.get(s)!;
        issueSeverity = "info";
        filterKey = null;
      }

      // Check status-based issues
      const st = ont.status.toUpperCase();
      if (
        !issue &&
        ont.rx_power_dbm !== null &&
        ont.rx_power_dbm < -28 &&
        (st === "ONLINE" || st === "ACTIVE")
      ) {
        issue = "Low signal";
        issueSeverity = "warning";
      }

      return {
        serial: s,
        ponPort: ont.pon_port,
        rxDbm: ont.rx_power_dbm,
        status: ont.status,
        issue,
        issueSeverity,
        filterKey,
      };
    });
  }, [result]);

  // Filter + search
  const filtered = useMemo(() => {
    let list = rows;

    if (filter) {
      // Special handling for capacity and weather_correlation (port-based, not serial-based)
      if (filter === "capacity") {
        const capPorts = new Set(result.capacity.map((c) => c.port));
        list = list.filter((r) => capPorts.has(r.ponPort));
      } else if (filter === "weather_correlation") {
        const wxPorts = new Set(
          result.weather_correlation
            .map((w) => w.port)
            .filter((p): p is string => !!p)
        );
        list = list.filter((r) => wxPorts.has(r.ponPort));
      } else {
        list = list.filter((r) => r.filterKey === filter);
      }
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((r) => r.serial.toLowerCase().includes(q));
    }

    return list;
  }, [rows, filter, search, result.capacity, result.weather_correlation]);

  // Sort
  const sorted = useMemo(() => {
    const arr = [...filtered];
    const severityOrder = { critical: 0, warning: 1, info: 2 };

    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "serial":
          cmp = a.serial.localeCompare(b.serial);
          break;
        case "ponPort":
          cmp = a.ponPort.localeCompare(b.ponPort);
          break;
        case "rxDbm": {
          const aVal = a.rxDbm ?? -999;
          const bVal = b.rxDbm ?? -999;
          cmp = aVal - bVal;
          break;
        }
        case "status":
          cmp = a.status.localeCompare(b.status);
          break;
        case "issue": {
          const aS = a.issueSeverity
            ? severityOrder[a.issueSeverity]
            : 3;
          const bS = b.issueSeverity
            ? severityOrder[b.issueSeverity]
            : 3;
          cmp = aS - bS;
          break;
        }
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return arr;
  }, [filtered, sortKey, sortDir]);

  // Paginate
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " \u25B2" : " \u25BC";
  };

  return (
    <div className="flex-1 min-w-0">
      {/* Search + info */}
      <div className="flex items-center gap-3 mb-3">
        <input
          type="text"
          placeholder="Search by serial..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="enlace-input-dark font-mono text-sm"
          style={{ maxWidth: 280 }}
        />
        <span
          className="font-mono text-xs"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          {sorted.length} ONTs
        </span>
      </div>

      {/* Table */}
      <div
        className="overflow-x-auto"
        style={{
          border: "1px solid var(--border-dark-strong)",
        }}
      >
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr
              style={{
                backgroundColor: "var(--bg-dark-subtle)",
                borderBottom: "1px solid var(--border-dark-strong)",
              }}
            >
              {(
                [
                  { key: "serial" as SortKey, label: "Serial" },
                  { key: "ponPort" as SortKey, label: "PON Port" },
                  { key: "rxDbm" as SortKey, label: "Rx dBm" },
                  { key: "status" as SortKey, label: "Status" },
                  { key: "issue" as SortKey, label: "Issue" },
                ] as const
              ).map((col) => (
                <th
                  key={col.key}
                  className="text-left px-3 py-2.5 font-mono text-xs uppercase tracking-widest cursor-pointer select-none"
                  style={{ color: "var(--text-on-dark-muted)" }}
                  onClick={() => toggleSort(col.key)}
                >
                  {col.label}
                  {sortIndicator(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr
                key={row.serial + i}
                style={{
                  backgroundColor: rowBgColor(row.issueSeverity),
                  borderBottom: "1px solid var(--border-dark)",
                }}
              >
                <td
                  className="px-3 py-2 font-mono text-sm"
                  style={{ color: "var(--text-on-dark)" }}
                >
                  {row.serial}
                </td>
                <td
                  className="px-3 py-2 font-mono text-sm"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  {row.ponPort}
                </td>
                <td
                  className="px-3 py-2 font-mono text-sm font-semibold"
                  style={{ color: rxColor(row.rxDbm) }}
                >
                  {row.rxDbm !== null ? row.rxDbm.toFixed(1) : "--"}
                </td>
                <td className="px-3 py-2">
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block w-2 h-2"
                      style={{
                        backgroundColor: statusDot(row.status),
                        borderRadius: "50%",
                      }}
                    />
                    <span
                      className="font-mono text-xs uppercase"
                      style={{ color: statusDot(row.status) }}
                    >
                      {statusLabel(row.status)}
                    </span>
                  </span>
                </td>
                <td
                  className="px-3 py-2 font-mono text-xs"
                  style={{
                    color: row.issueSeverity === "critical"
                      ? "#ef4444"
                      : row.issueSeverity === "warning"
                        ? "#f59e0b"
                        : "var(--text-on-dark-muted)",
                  }}
                >
                  {row.issue || "--"}
                </td>
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-8 text-center font-mono text-sm"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  No ONTs match the current filter
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <button
            className="enlace-btn-ghost font-mono text-xs"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            style={{ opacity: page === 0 ? 0.4 : 1, height: 32, paddingLeft: 12, paddingRight: 12 }}
          >
            Previous
          </button>
          <span
            className="font-mono text-xs"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            Page {page + 1} of {totalPages}
          </span>
          <button
            className="enlace-btn-ghost font-mono text-xs"
            disabled={page >= totalPages - 1}
            onClick={() => setPage(page + 1)}
            style={{ opacity: page >= totalPages - 1 ? 0.4 : 1, height: 32, paddingLeft: 12, paddingRight: 12 }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
