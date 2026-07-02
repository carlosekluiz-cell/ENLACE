// ── Server-side auth enforcement ──
//
// Verifies the session JWT on every non-public request:
//   - /api/*   → 401 JSON when unauthenticated (routes re-check roles +
//                DB revocation via requireSession/requireRole).
//   - pages    → redirect to / (login) when unauthenticated; redirect to
//                the persona home when below the route's role floor
//                (map in src/lib/routeAccess.ts — one place).
//
// Runs on the Node runtime so the dev-fallback secret file is readable.
// Revocation (DB) is deliberately NOT checked here — middleware stays
// DB-free; requireSession does the denylist check inside routes.

import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/jwt";
import { isPublicPath, roleFloorFor } from "@/lib/routeAccess";
import { personaById, roleAtLeast } from "@/lib/roles";

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (isPublicPath(pathname)) return NextResponse.next();

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  const claims = token ? await verifySessionToken(token) : null;

  if (pathname.startsWith("/api/")) {
    if (!claims) {
      return NextResponse.json(
        { error: "authentication required" },
        { status: 401 },
      );
    }
    return NextResponse.next();
  }

  if (!claims) {
    // Deep links (e.g. a WhatsApp-dispatched ticket URL) must survive the
    // auth flow: send the intended path+query along as `next=` so the login
    // page can land the user back on it. Same-origin relative path only —
    // the login page re-validates before redirecting.
    const login = req.nextUrl.clone();
    login.pathname = "/";
    login.search = "";
    const next = pathname + req.nextUrl.search;
    if (next !== "/" && next.startsWith("/") && !next.startsWith("//")) {
      login.searchParams.set("next", next);
    }
    return NextResponse.redirect(login);
  }

  const floor = roleFloorFor(pathname);
  if (floor && !roleAtLeast(claims.role, floor)) {
    const home = req.nextUrl.clone();
    home.pathname = personaById(claims.persona)?.home ?? "/";
    home.search = "";
    return NextResponse.redirect(home);
  }

  return NextResponse.next();
}

export const config = {
  runtime: "nodejs",
  // Everything except Next internals and static assets (files with an
  // extension). All /api/* routes match.
  matcher: ["/((?!_next/|favicon\\.ico|.*\\.[\\w]+$).*)"],
};
