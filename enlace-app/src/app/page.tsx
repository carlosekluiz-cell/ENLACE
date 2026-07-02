"use client";

// / — login (email + password against /api/auth/login) + role-aware
// redirect. A live session skips straight to its persona home. The five
// demo personas are listed as one-click fill (pilot demo UX): clicking a
// persona fills its seeded credentials — it still goes through real login.

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { DEMO_USERS } from "@/lib/demoCredentials";
import { personaById } from "@/lib/roles";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { session, ready, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && session) {
      router.replace(personaById(session.persona)?.home ?? "/noc");
    }
  }, [ready, session, router]);

  if (!ready || session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          …
        </p>
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const persona = await login(email, password);
      router.push(persona.home);
    } catch (err) {
      setError(err instanceof Error ? err.message : "login failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        <div className="text-center">
          <p className="font-serif text-4xl" style={{ color: "var(--text-on-dark)" }}>
            enlace{" "}
            <span className="font-mono text-sm align-middle" style={{ color: "var(--accent)" }}>
              OPERATIONS
            </span>
          </p>
          <p className="mt-2 text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
            Your network is talking. Sign in to listen.
          </p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label className="op-label block mb-2" htmlFor="email">
              email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@operator.example"
              className="enlace-input-dark"
            />
          </div>
          <div>
            <label className="op-label block mb-2" htmlFor="password">
              password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="enlace-input-dark"
            />
          </div>

          {error && (
            <p className="font-mono text-xs" style={{ color: "var(--danger)" }} role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 font-mono text-sm font-semibold cursor-pointer transition-colors disabled:opacity-60"
            style={{
              backgroundColor: "var(--accent)",
              color: "var(--bg-dark)",
            }}
          >
            {submitting ? "signing in…" : "sign in"}
          </button>
        </form>

        <div>
          <p className="op-label mb-2">demo accounts — click to fill</p>
          <div className="grid sm:grid-cols-2 gap-3">
            {DEMO_USERS.map((u) => {
              const persona = personaById(u.persona);
              return (
                <button
                  key={u.persona}
                  type="button"
                  onClick={() => {
                    setEmail(u.email);
                    setPassword(u.password);
                    setError(null);
                  }}
                  className="op-card text-left p-4 cursor-pointer transition-colors hover:border-[var(--accent)]"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-sm" style={{ color: "var(--text-on-dark)" }}>
                      {u.label}
                    </span>
                    <span className="font-mono text-[10px] uppercase" style={{ color: "var(--accent)" }}>
                      {u.role}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--text-on-dark-muted)" }}>
                    {persona?.description}
                  </p>
                  <p className="mt-2 font-mono text-[10px] truncate" style={{ color: "var(--text-on-dark-muted)" }}>
                    {u.email}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <p
          className="text-center font-mono text-[11px]"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          demo tenant accounts seeded by `npm run db:seed` — sessions are real
          JWTs in an httpOnly cookie (docs/ARCHITECTURE-TENANCY.md §2.4)
        </p>
      </div>
    </div>
  );
}
