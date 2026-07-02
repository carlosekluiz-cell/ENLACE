// ── Route access map (single source of truth) ──
//
// Used by middleware.ts for server-side enforcement. Role is the ONLY
// authorization input; persona never grants capability (ONTOLOGY.md §3,
// ARCHITECTURE-TENANCY.md §2.1).

import type { Role } from "@/lib/roles";

/** Paths reachable without a session (login page + auth endpoints). */
export const PUBLIC_PATHS: readonly string[] = [
  "/",
  "/api/auth/login",
  "/api/auth/session",
  "/api/auth/logout",
];

/** Minimum role per app-page route prefix. Admin ranks above all floors. */
export const ROUTE_ROLE_FLOORS: ReadonlyArray<{
  prefix: string;
  minRole: Role;
}> = [
  { prefix: "/noc", minRole: "analyst" },
  { prefix: "/supervisor", minRole: "manager" },
  { prefix: "/exec", minRole: "manager" },
  { prefix: "/field", minRole: "viewer" },
];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.includes(pathname);
}

export function roleFloorFor(pathname: string): Role | null {
  const entry = ROUTE_ROLE_FLOORS.find(
    (r) => pathname === r.prefix || pathname.startsWith(r.prefix + "/"),
  );
  return entry?.minRole ?? null;
}
