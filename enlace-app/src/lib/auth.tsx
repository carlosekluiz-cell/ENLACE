"use client";

// ── Session-backed auth (client side) ──
//
// The session lives in an httpOnly cookie issued by /api/auth/login; the
// client can't read the JWT, so it asks GET /api/auth/session for the
// verified claims. The answer is held in a module-level external store read
// through useSyncExternalStore (the app convention — no setState-in-effect).
//
// Server-side enforcement is middleware.ts + requireSession/requireRole in
// routes; RoleGuard below is UX only (redirects, ACCESS DENIED panel), not
// load-bearing.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { personaById, roleAtLeast, type Persona, type Role } from "@/lib/roles";

/** Mirror of the JWT claims (minus jti/exp) — see lib/jwt.ts SessionClaims. */
export interface Session {
  /** Subject — user id from the users table. */
  sub: string;
  name: string;
  tenantId: string;
  persona: Persona["id"];
  role: Role;
}

interface SessionWire {
  session: {
    sub: string;
    name: string;
    tenant_id: string;
    role: Role;
    persona: Persona["id"];
  };
}

// ── External store ──

interface AuthState {
  /** False until /api/auth/session has answered once (avoids redirect flicker). */
  ready: boolean;
  session: Session | null;
}

const SERVER_STATE: AuthState = { ready: false, session: null };

let state: AuthState = SERVER_STATE;
const listeners = new Set<() => void>();

function setState(next: AuthState): void {
  state = next;
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function fromWire(body: SessionWire): Session {
  const s = body.session;
  return {
    sub: s.sub,
    name: s.name,
    tenantId: s.tenant_id,
    role: s.role,
    persona: s.persona,
  };
}

let initialFetch: Promise<void> | null = null;

function ensureSessionFetched(): void {
  initialFetch ??= (async () => {
    try {
      const res = await fetch("/api/auth/session", { cache: "no-store" });
      if (res.ok) {
        setState({ ready: true, session: fromWire((await res.json()) as SessionWire) });
      } else {
        setState({ ready: true, session: null });
      }
    } catch {
      setState({ ready: true, session: null });
    }
  })();
}

// ── Provider / hook ──

interface AuthContextValue {
  session: Session | null;
  /** False until the server has been consulted once. */
  ready: boolean;
  /**
   * Real login: POST /api/auth/login. Resolves to the user's persona on
   * success; throws Error with a display message on failure.
   */
  login: (email: string, password: string) => Promise<Persona>;
  /** Revokes the session server-side (jti denylist) and clears the cookie. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore(
    subscribe,
    () => state,
    () => SERVER_STATE,
  );

  useEffect(() => {
    ensureSessionFetched();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      throw new Error(body?.error ?? `login failed (${res.status})`);
    }
    const session = fromWire((await res.json()) as SessionWire);
    setState({ ready: true, session });
    const persona = personaById(session.persona);
    if (!persona) throw new Error(`unknown persona "${session.persona}"`);
    return persona;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setState({ ready: true, session: null });
    }
  }, []);

  const value = useMemo(
    () => ({ session: snapshot.session, ready: snapshot.ready, login, logout }),
    [snapshot, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/**
 * Gates children on a minimum role. Redirects to / when logged out.
 * UX layer only — middleware.ts enforces the same floors server-side.
 */
export function RoleGuard({
  minRole,
  children,
}: {
  minRole: Role;
  children: ReactNode;
}) {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !session) router.replace("/");
  }, [ready, session, router]);

  if (!ready || !session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="font-mono text-sm" style={{ color: "var(--text-on-dark-muted)" }}>
          checking session…
        </p>
      </div>
    );
  }

  if (!roleAtLeast(session.role, minRole)) {
    return (
      <div className="flex items-center justify-center min-h-screen px-6">
        <div
          className="max-w-md p-6 text-center"
          style={{
            backgroundColor: "var(--bg-dark-surface)",
            border: "1px solid var(--border-dark-strong)",
          }}
        >
          <p className="font-mono text-sm font-semibold mb-2" style={{ color: "var(--danger)" }}>
            ACCESS DENIED
          </p>
          <p className="text-sm" style={{ color: "var(--text-on-dark-secondary)" }}>
            This view requires role <span className="font-mono">{minRole}</span> or above.
            Your session ({session.name}) has role{" "}
            <span className="font-mono">{session.role}</span>.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
