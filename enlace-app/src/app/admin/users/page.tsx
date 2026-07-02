"use client";

// /admin/users — tenant user administration (admin only).
//
// List, invite/create (temp password shown ONCE — it is never stored in
// clear), disable/enable, reset password, role change. Every mutation goes
// through /api/admin/users* which writes audit_log (see /admin/activity).

import { useEffect, useState } from "react";
import { RoleGuard, useAuth } from "@/lib/auth";
import type {
  AdminUserEntry,
  AdminUserMutationResponse,
  AdminUsersResponse,
} from "@/lib/adminTypes";
import { fmtDate } from "@/lib/format";
import { PERSONAS, ROLES, type Role } from "@/lib/roles";
import AdminTabs from "@/components/AdminTabs";
import AppShell from "@/components/AppShell";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => null)) as (T & { error?: string }) | null;
  if (!res.ok) throw new Error(body?.error ?? `request failed (${res.status})`);
  return body as T;
}

interface Secret {
  email: string;
  password: string;
  kind: "created" | "reset";
}

function UsersAdmin() {
  const { session } = useAuth();
  const [users, setUsers] = useState<AdminUserEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [busy, setBusy] = useState(false);

  // Invite form
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [persona, setPersona] = useState(PERSONAS[1].id); // field_engineer default
  const [secret, setSecret] = useState<Secret | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/admin/users")
      .then((res) => jsonOrThrow<AdminUsersResponse>(res))
      .then((body) => {
        if (!cancelled) {
          setUsers(body.users);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoading(false);
          setError(err instanceof Error ? err.message : "failed to load users");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const mutate = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "request failed");
    } finally {
      setBusy(false);
    }
  };

  const createUser = () =>
    mutate(async () => {
      const res = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, name, role, persona }),
      });
      const body = await jsonOrThrow<AdminUserMutationResponse>(res);
      if (body.temp_password) {
        setSecret({ email: body.user.email, password: body.temp_password, kind: "created" });
      }
      setEmail("");
      setName("");
    });

  const patchUser = (id: string, patch: Record<string, unknown>) =>
    mutate(async () => {
      const res = await fetch(`/api/admin/users/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(patch),
      });
      const body = await jsonOrThrow<AdminUserMutationResponse>(res);
      if (body.temp_password) {
        setSecret({ email: body.user.email, password: body.temp_password, kind: "reset" });
      }
    });

  return (
    <AppShell title="Admin — Users" meta={null}>
      <AdminTabs />

      {error && (
        <p className="font-mono text-sm" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}

      {secret && (
        <div
          className="op-card p-4 flex items-start justify-between gap-4"
          style={{ borderLeft: "3px solid var(--accent)" }}
        >
          <div>
            <p className="text-sm" style={{ color: "var(--text-on-dark)" }}>
              Temporary password for <span className="font-mono">{secret.email}</span>
              {secret.kind === "created" ? " (new account)" : " (password reset)"}:
            </p>
            <p className="font-mono text-lg my-1" style={{ color: "var(--accent-hover)" }}>
              {secret.password}
            </p>
            <p className="text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
              Shown once — only the hash is stored. Share it over a trusted channel.
            </p>
          </div>
          <button
            type="button"
            className="font-mono text-xs cursor-pointer px-2 py-1"
            style={{ color: "var(--text-on-dark-muted)", border: "1px solid var(--border-dark)" }}
            onClick={() => setSecret(null)}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Invite / create */}
      <section>
        <h2 className="op-label mb-2">invite user</h2>
        <div className="op-card p-4 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="op-label">email</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@operator.example"
              className="bg-transparent font-mono text-sm px-2 py-1.5 w-64"
              style={{ color: "var(--text-on-dark)", border: "1px solid var(--border-dark)" }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="op-label">name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              className="bg-transparent font-mono text-sm px-2 py-1.5 w-48"
              style={{ color: "var(--text-on-dark)", border: "1px solid var(--border-dark)" }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="op-label">role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="bg-transparent font-mono text-sm px-2 py-1.5 cursor-pointer"
              style={{ color: "var(--text-on-dark)", border: "1px solid var(--border-dark)" }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="op-label">persona (lens, not capability)</span>
            <select
              value={persona}
              onChange={(e) => setPersona(e.target.value as (typeof PERSONAS)[number]["id"])}
              className="bg-transparent font-mono text-sm px-2 py-1.5 cursor-pointer"
              style={{ color: "var(--text-on-dark)", border: "1px solid var(--border-dark)" }}
            >
              {PERSONAS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !email || !name}
            onClick={() => void createUser()}
            className="font-mono text-xs px-4 py-2 cursor-pointer disabled:opacity-40"
            style={{ backgroundColor: "var(--accent)", color: "#fff" }}
          >
            create — temp password shown once
          </button>
        </div>
      </section>

      {/* User table */}
      <section>
        <h2 className="op-label mb-2">
          tenant users {loading ? "" : `(${users.length})`}
        </h2>
        {loading ? (
          <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
            loading users…
          </p>
        ) : (
          <div className="op-card overflow-x-auto">
            <table className="op-table w-full border-collapse">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Persona</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = session?.sub === u.id;
                  return (
                    <tr key={u.id} style={u.disabled ? { opacity: 0.55 } : undefined}>
                      <td>
                        {u.name}
                        {isSelf && (
                          <span
                            className="font-mono text-[10px] ml-2"
                            style={{ color: "var(--accent)" }}
                          >
                            you
                          </span>
                        )}
                      </td>
                      <td className="font-mono">{u.email}</td>
                      <td>
                        <select
                          value={u.role}
                          disabled={busy || isSelf}
                          onChange={(e) => void patchUser(u.id, { role: e.target.value })}
                          className="bg-transparent font-mono text-xs px-1 py-0.5 cursor-pointer disabled:cursor-default"
                          style={{
                            color: "var(--text-on-dark)",
                            border: "1px solid var(--border-dark)",
                          }}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="font-mono">{u.persona}</td>
                      <td className="font-mono">{fmtDate(u.created_at)}</td>
                      <td
                        className="font-mono"
                        style={{
                          color: u.disabled ? "var(--danger)" : "var(--status-online)",
                        }}
                      >
                        {u.disabled ? "disabled" : "active"}
                      </td>
                      <td>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={busy || isSelf}
                            onClick={() => void patchUser(u.id, { disabled: !u.disabled })}
                            className="font-mono text-[11px] px-2 py-1 cursor-pointer disabled:opacity-40"
                            style={{
                              color: u.disabled
                                ? "var(--status-online)"
                                : "var(--danger)",
                              border: "1px solid var(--border-dark)",
                            }}
                          >
                            {u.disabled ? "enable" : "disable"}
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void patchUser(u.id, { reset_password: true })}
                            className="font-mono text-[11px] px-2 py-1 cursor-pointer disabled:opacity-40"
                            style={{
                              color: "var(--text-on-dark-secondary)",
                              border: "1px solid var(--border-dark)",
                            }}
                          >
                            reset password
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs mt-2" style={{ color: "var(--text-on-dark-muted)" }}>
          Disabling a user revokes their active sessions immediately. You cannot disable
          your own account or drop your own admin role. Every action here is recorded in
          the activity log.
        </p>
      </section>
    </AppShell>
  );
}

export default function AdminUsersPage() {
  return (
    <RoleGuard minRole="admin">
      <UsersAdmin />
    </RoleGuard>
  );
}
