"use client";

// /admin/activity — the accountability view (admin only).
//
// Renders the tenant's audit_log newest first: logins, uploads, ticket
// lifecycle, user admin, settings changes, report generations. Filterable
// by action.

import { useEffect, useState } from "react";
import { RoleGuard } from "@/lib/auth";
import type { ActivityResponse } from "@/lib/adminTypes";
import { fmtDate } from "@/lib/format";
import AdminTabs from "@/components/AdminTabs";
import AppShell from "@/components/AppShell";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => null)) as (T & { error?: string }) | null;
  if (!res.ok) throw new Error(body?.error ?? `request failed (${res.status})`);
  return body as T;
}

function ActivityAdmin() {
  const [data, setData] = useState<ActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState("");

  useEffect(() => {
    let cancelled = false;
    const url = action
      ? `/api/admin/activity?action=${encodeURIComponent(action)}`
      : "/api/admin/activity";
    fetch(url)
      .then((res) => jsonOrThrow<ActivityResponse>(res))
      .then((body) => {
        if (!cancelled) {
          setData(body);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoading(false);
          setError(err instanceof Error ? err.message : "failed to load activity");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [action]);

  return (
    <AppShell title="Admin — Activity" meta={null}>
      <AdminTabs />

      <div className="flex items-center gap-3 flex-wrap">
        <label className="flex items-center gap-2">
          <span className="op-label">action</span>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value)}
            className="bg-transparent font-mono text-xs px-2 py-1.5 cursor-pointer"
            style={{ color: "var(--text-on-dark)", border: "1px solid var(--border-dark)" }}
          >
            <option value="">all actions</option>
            {(data?.actions ?? []).map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        {data && (
          <span className="font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
            {data.total} entr{data.total === 1 ? "y" : "ies"}, newest first
          </span>
        )}
      </div>

      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading activity…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      {data && data.entries.length === 0 && !loading && (
        <p className="text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          No log entries{action ? ` for action "${action}"` : ""}.
        </p>
      )}

      {data && data.entries.length > 0 && (
        <div className="op-card overflow-x-auto">
          <table className="op-table w-full border-collapse">
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Action</th>
                <th>Subject</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e) => (
                <tr key={e.id}>
                  <td className="font-mono whitespace-nowrap">{fmtDate(e.at)}</td>
                  <td>
                    {e.user_name ?? (
                      <span style={{ color: "var(--text-on-dark-muted)" }}>system</span>
                    )}
                    {e.user_email && (
                      <span
                        className="font-mono text-[10px] block"
                        style={{ color: "var(--text-on-dark-muted)" }}
                      >
                        {e.user_email}
                      </span>
                    )}
                  </td>
                  <td className="font-mono" style={{ color: "var(--accent-hover)" }}>
                    {e.action}
                  </td>
                  <td className="font-mono" style={{ color: "var(--text-on-dark-secondary)" }}>
                    {e.subject ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}

export default function AdminActivityPage() {
  return (
    <RoleGuard minRole="admin">
      <ActivityAdmin />
    </RoleGuard>
  );
}
