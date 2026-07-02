"use client";

// ── Demo session auth ──
// Persona-picker session persisted in localStorage (read through
// useSyncExternalStore so SSR/hydration stay consistent). The Session shape
// mirrors JWT claims so swapping in real auth is a transport change, not a
// data-model change.
//
// TODO(auth): wire python/api JWT — POST /auth/login → { access_token };
// decode claims { sub, name, role } into Session, store the token in an
// httpOnly cookie via a Next server route, and have RoleGuard read the
// session from /api/me instead of localStorage.

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
import {
  localStorageGet,
  localStorageSet,
  subscribeLocalStorage,
} from "@/lib/clientStore";
import { personaById, roleAtLeast, type Persona, type Role } from "@/lib/roles";

export interface Session {
  /** Subject — demo: persona id. JWT-ready. */
  sub: string;
  name: string;
  persona: Persona["id"];
  role: Role;
  loggedInAt: string;
}

const STORAGE_KEY = "enlace.session";
/** Pre-hydration marker: the server cannot see localStorage. */
const SERVER_SENTINEL = "__server__";

interface AuthContextValue {
  session: Session | null;
  /** False until the client store has been consulted (avoids redirect flicker). */
  ready: boolean;
  login: (personaId: Persona["id"], name: string) => Persona | undefined;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const raw = useSyncExternalStore(
    subscribeLocalStorage,
    () => localStorageGet(STORAGE_KEY),
    () => SERVER_SENTINEL,
  );

  const ready = raw !== SERVER_SENTINEL;

  const session = useMemo<Session | null>(() => {
    if (!ready || !raw) return null;
    try {
      const parsed = JSON.parse(raw) as Session;
      return personaById(parsed.persona) ? parsed : null;
    } catch {
      return null; // corrupt session — treat as logged out
    }
  }, [raw, ready]);

  const login = useCallback((personaId: Persona["id"], name: string) => {
    const persona = personaById(personaId);
    if (!persona) return undefined;
    const next: Session = {
      sub: persona.id,
      name: name.trim() || persona.label,
      persona: persona.id,
      role: persona.role,
      loggedInAt: new Date().toISOString(),
    };
    localStorageSet(STORAGE_KEY, JSON.stringify(next));
    return persona;
  }, []);

  const logout = useCallback(() => {
    localStorageSet(STORAGE_KEY, null);
  }, []);

  const value = useMemo(
    () => ({ session, ready, login, logout }),
    [session, ready, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Gates children on a minimum role. Redirects to / when logged out. */
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
