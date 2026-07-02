// ── Wave C shared types: /admin area + tenant settings ──
//
// Client-safe (no server imports). Server helpers live in
// src/lib/tenantSettings.ts and the /api/admin/* routes.
//
// Honesty note: the tenant assumption constants below parameterize
// `estimated_*` figures. They are assumptions by definition — surfaced with
// their meaning, never presented as measurements. A missing constant is
// null ("not set"), never a silent default (ONTOLOGY.md §5 #5).

import type { Role } from "@/lib/roles";

// ── Tenant assumption settings (tenants.settings JSON → .assumptions) ──

export interface TenantAssumptions {
  /** Assumed average revenue per user, per month — feeds revenue-at-risk estimates. */
  arpu_gbp_month: number | null;
  /** Assumed cost of one truck roll — feeds fix-cost / ROI estimates. */
  truck_roll_cost_gbp: number | null;
  /** Display currency for the constants above (ISO 4217, e.g. "GBP"). */
  currency: string | null;
  /** Free-text provenance note stored alongside the constants. */
  note?: string;
}

export interface TenantSettingsResponse {
  tenant: { id: string; name: string };
  assumptions: TenantAssumptions;
  /**
   * The seam, stated: the agent computes estimates at audit time with the
   * assumptions it declares in the result. Changing these settings applies
   * to FUTURE estimate math; persisted audits are never retro-recomputed.
   */
  applies_to: string;
}

// ── /api/admin/users ──

export interface AdminUserEntry {
  id: string;
  email: string;
  name: string;
  role: Role;
  persona: string;
  disabled: boolean;
  created_at: string;
}

export interface AdminUsersResponse {
  users: AdminUserEntry[];
}

/** users row → wire shape. Pure mapper; the password hash NEVER leaves the server. */
export function toAdminUserEntry(u: {
  id: string;
  email: string;
  name: string;
  role: string;
  persona: string;
  disabled: number;
  createdAt: string;
}): AdminUserEntry {
  return {
    id: u.id,
    email: u.email,
    name: u.name,
    role: u.role as Role,
    persona: u.persona,
    disabled: u.disabled !== 0,
    created_at: u.createdAt,
  };
}

/** POST create / password reset: the temp password is returned ONCE, never stored. */
export interface AdminUserMutationResponse {
  user: AdminUserEntry;
  temp_password?: string;
}

// ── /api/admin/activity (the accountability view) ──

export interface ActivityEntry {
  id: number;
  user_id: string | null;
  /** Resolved display name; null when the action had no actor or the user is gone. */
  user_name: string | null;
  user_email: string | null;
  action: string;
  subject: string | null;
  at: string;
}

export interface ActivityResponse {
  entries: ActivityEntry[];
  /** Distinct actions present in the log — feeds the filter dropdown. */
  actions: string[];
  total: number;
}
