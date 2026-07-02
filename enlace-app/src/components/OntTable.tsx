"use client";

// ONT fleet table: filterable by status (Unknown is a first-class filter),
// searchable by serial/port, rx-power severity coloring, and "—" for
// missing values — never a fabricated zero.

import { useMemo, useState } from "react";
import type { OntData } from "@/lib/types";
import { dash, fmtDbm, rxColor } from "@/lib/format";
import { statusColor } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

const STATUS_FILTERS = [
  "All",
  "Online",
  "LowSignal",
  "Dying",
  "Offline",
  "PowerFail",
  "FiberCut",
  "Unknown",
] as const;

export default function OntTable({ onts }: { onts: OntData[] }) {
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]>("All");
  const [query, setQuery] = useState("");

  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const ont of onts) c.set(ont.status, (c.get(ont.status) ?? 0) + 1);
    return c;
  }, [onts]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return onts.filter((ont) => {
      if (status !== "All" && ont.status !== status) return false;
      if (
        q &&
        !ont.serial_number.toLowerCase().includes(q) &&
        !ont.pon_port.toLowerCase().includes(q)
      )
        return false;
      return true;
    });
  }, [onts, status, query]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((s) => {
          const count = s === "All" ? onts.length : (counts.get(s) ?? 0);
          const active = status === s;
          const color = s === "All" ? "var(--text-on-dark-secondary)" : statusColor(s);
          return (
            <button
              key={s}
              type="button"
              onClick={() => setStatus(s)}
              className="px-2.5 py-1 font-mono text-[11px] cursor-pointer"
              style={{
                color: active ? "var(--bg-dark)" : color,
                backgroundColor: active ? color : "transparent",
                border: `1px solid ${color}`,
                opacity: count === 0 && !active ? 0.4 : 1,
              }}
            >
              {s} {count}
            </button>
          );
        })}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search serial or port…"
          className="enlace-input-dark md:max-w-60 ml-auto"
          style={{ height: 30 }}
        />
      </div>

      <div className="op-card overflow-x-auto">
        <table className="op-table w-full border-collapse">
          <thead>
            <tr>
              <th>Serial</th>
              <th>PON port</th>
              <th>Status</th>
              <th>Rx power</th>
              <th>Tx power</th>
              <th>Distance</th>
              <th>Eth speed</th>
              <th>Last down cause</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((ont) => (
              <tr key={`${ont.pon_port}-${ont.serial_number}`}>
                <td className="font-mono">{ont.serial_number}</td>
                <td className="font-mono">{ont.pon_port}</td>
                <td>
                  <StatusPill status={ont.status} />
                </td>
                <td className="font-mono" style={{ color: rxColor(ont.rx_power_dbm) }}>
                  {fmtDbm(ont.rx_power_dbm)}
                </td>
                <td className="font-mono">{fmtDbm(ont.tx_power_dbm)}</td>
                <td className="font-mono">{ont.distance_meters} m</td>
                <td className="font-mono">
                  {dash(ont.eth_speed_mbps, (v) => `${v} Mbps`)}
                </td>
                <td className="font-mono">{dash(ont.last_down_cause, (v) => v)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} style={{ color: "var(--text-on-dark-muted)" }}>
                  No ONTs match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
