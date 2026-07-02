"use client";

// /admin/settings — tenant assumption constants (admin only).
//
// These constants (ARPU, truck-roll cost, currency) parameterize the
// estimate math — they are assumptions by definition, and the page says so
// with each field. Saving is an admin act → audit_log. The seam is stated:
// persisted audits keep the assumptions the agent declared when they ran.

import { useEffect, useState } from "react";
import { RoleGuard } from "@/lib/auth";
import type { TenantSettingsResponse } from "@/lib/adminTypes";
import AdminTabs from "@/components/AdminTabs";
import AppShell from "@/components/AppShell";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => null)) as (T & { error?: string }) | null;
  if (!res.ok) throw new Error(body?.error ?? `request failed (${res.status})`);
  return body as T;
}

const FIELDS: Array<{
  key: "arpu_gbp_month" | "truck_roll_cost_gbp" | "currency";
  label: string;
  meaning: string;
  numeric: boolean;
}> = [
  {
    key: "arpu_gbp_month",
    label: "Assumed monthly ARPU",
    meaning:
      "Used for revenue-at-risk estimates (ghosts, churn, tickets). An assumption, never billing truth.",
    numeric: true,
  },
  {
    key: "truck_roll_cost_gbp",
    label: "Assumed truck-roll cost",
    meaning: "Used for fix-cost and ROI estimates on tickets.",
    numeric: true,
  },
  {
    key: "currency",
    label: "Currency (ISO 4217)",
    meaning: "Display currency for the constants above (e.g. GBP, BRL).",
    numeric: false,
  },
];

function SettingsAdmin() {
  const [data, setData] = useState<TenantSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    fetch("/api/admin/settings")
      .then((res) => jsonOrThrow<TenantSettingsResponse>(res))
      .then((body) => {
        if (cancelled) return;
        setData(body);
        setForm({
          arpu_gbp_month: body.assumptions.arpu_gbp_month?.toString() ?? "",
          truck_roll_cost_gbp: body.assumptions.truck_roll_cost_gbp?.toString() ?? "",
          currency: body.assumptions.currency ?? "",
        });
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoading(false);
          setError(err instanceof Error ? err.message : "failed to load settings");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const save = async () => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const patch: Record<string, unknown> = {};
      for (const f of FIELDS) {
        const raw = (form[f.key] ?? "").trim();
        if (raw === "") continue; // leave unset values unset — no silent defaults
        patch[f.key] = f.numeric ? Number(raw) : raw;
      }
      const res = await fetch("/api/admin/settings", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(patch),
      });
      const body = await jsonOrThrow<TenantSettingsResponse>(res);
      setData(body);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to save settings");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell title="Admin — Tenant settings" meta={null}>
      <AdminTabs />

      {loading && (
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          loading settings…
        </p>
      )}
      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      {data && (
        <>
          <section>
            <h2 className="op-label mb-2">
              assumption constants — {data.tenant.name}
            </h2>
            <div className="op-card p-4 flex flex-col gap-4 max-w-2xl">
              <p className="text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                {data.applies_to}
              </p>
              {FIELDS.map((f) => {
                const current = data.assumptions[f.key];
                return (
                  <div key={f.key} className="flex flex-col gap-1">
                    <label className="op-label" htmlFor={`setting-${f.key}`}>
                      {f.label}
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        id={`setting-${f.key}`}
                        value={form[f.key] ?? ""}
                        inputMode={f.numeric ? "decimal" : "text"}
                        placeholder="not set"
                        onChange={(e) =>
                          setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
                        }
                        className="bg-transparent font-mono text-sm px-2 py-1.5 w-40"
                        style={{
                          color: "var(--text-on-dark)",
                          border: "1px solid var(--border-dark)",
                        }}
                      />
                      <span
                        className="font-mono text-[11px]"
                        style={{ color: "var(--text-on-dark-muted)" }}
                      >
                        current:{" "}
                        {current === null || current === undefined ? "not set" : String(current)}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                      {f.meaning}
                    </p>
                  </div>
                );
              })}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void save()}
                  className="font-mono text-xs px-4 py-2 cursor-pointer disabled:opacity-40"
                  style={{ backgroundColor: "var(--accent)", color: "#fff" }}
                >
                  save settings
                </button>
                {saved && (
                  <span className="font-mono text-xs" style={{ color: "var(--status-online)" }}>
                    saved — logged to the activity trail
                  </span>
                )}
              </div>
            </div>
          </section>

          <p className="text-xs max-w-2xl" style={{ color: "var(--text-on-dark-muted)" }}>
            Honesty note: figures inside already-persisted audits carry the assumptions
            the agent declared when each audit ran — changing these constants never
            rewrites past estimates. The exec view and PDF reports surface these values
            explicitly labeled as tenant settings.
          </p>
        </>
      )}
    </AppShell>
  );
}

export default function AdminSettingsPage() {
  return (
    <RoleGuard minRole="admin">
      <SettingsAdmin />
    </RoleGuard>
  );
}
