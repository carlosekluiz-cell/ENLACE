// ── Session JWT (jose, HS256) ──
//
// Claim shape is deliberately identical to python/api's tokens
// (ARCHITECTURE-TENANCY.md §2.3) so the issuer can be swapped later without
// touching a single guard: { sub, name, tenant_id, role, persona, jti }.
// jti is recorded in the sessions table; logout revokes (denylist).

import { SignJWT, jwtVerify } from "jose";
import { getAuthSecret } from "@/lib/authSecret";
import { ROLES, type PersonaId, type Role } from "@/lib/roles";

export const SESSION_COOKIE = "enlace_session";
/** 12 h, per the architecture doc. */
export const SESSION_TTL_SECONDS = 12 * 60 * 60;

export interface SessionClaims {
  sub: string;
  name: string;
  tenant_id: string;
  role: Role;
  persona: PersonaId;
  jti: string;
}

export async function signSessionToken(claims: SessionClaims): Promise<string> {
  const { sub, jti, ...rest } = claims;
  return new SignJWT({ ...rest })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(sub)
    .setJti(jti)
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .sign(getAuthSecret());
}

/** Verify signature + expiry and validate claim shape. Null on any failure. */
export async function verifySessionToken(
  token: string,
): Promise<SessionClaims | null> {
  try {
    const { payload } = await jwtVerify(token, getAuthSecret(), {
      algorithms: ["HS256"],
    });
    const { sub, jti } = payload;
    const name = payload.name;
    const tenantId = payload.tenant_id;
    const role = payload.role;
    const persona = payload.persona;
    if (
      typeof sub !== "string" ||
      typeof jti !== "string" ||
      typeof name !== "string" ||
      typeof tenantId !== "string" ||
      typeof role !== "string" ||
      !(ROLES as readonly string[]).includes(role) ||
      typeof persona !== "string"
    ) {
      return null;
    }
    return {
      sub,
      jti,
      name,
      tenant_id: tenantId,
      role: role as Role,
      persona: persona as PersonaId,
    };
  } catch {
    return null;
  }
}
