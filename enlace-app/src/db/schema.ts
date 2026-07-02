// ── App DB schema (drizzle / SQLite) ──
//
// Every table is tenant-keyed from day one (ARCHITECTURE-TENANCY.md §1.2):
// single-tenant deploys are the degenerate case N=1, not a different schema.
// The `audits.result_json` column stores the agent's AuditResult VERBATIM —
// the app reads, the agent computes (honesty invariant, ONTOLOGY.md §5).
//
// DDL lives in src/db/migrate.ts (idempotent CREATE TABLE IF NOT EXISTS,
// applied on first open). Keep the two in sync.

import {
  index,
  integer,
  sqliteTable,
  text,
  uniqueIndex,
} from "drizzle-orm/sqlite-core";
import { ROLES } from "../lib/roles";

export const tenants = sqliteTable("tenants", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  slug: text("slug").notNull().unique(),
  /**
   * JSON blob of tenant-level assumption constants (ARPU, truck-roll cost…).
   * These parameterize `estimated_*` figures and are echoed into results —
   * never presented as measurements (honesty invariant #1).
   */
  settings: text("settings").notNull().default("{}"),
});

export const users = sqliteTable(
  "users",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id")
      .notNull()
      .references(() => tenants.id),
    email: text("email").notNull(),
    name: text("name").notNull(),
    passwordHash: text("password_hash").notNull(),
    /** The ONLY authorization input (roles.ts lattice). */
    role: text("role", { enum: ROLES }).notNull(),
    /** Lens: home route + default framing. Never grants capability. */
    persona: text("persona").notNull(),
    createdAt: text("created_at").notNull(),
    disabled: integer("disabled").notNull().default(0),
  },
  (t) => [uniqueIndex("users_tenant_email_uq").on(t.tenantId, t.email)],
);

/** One row per issued JWT; logout sets revoked_at (jti denylist). */
export const sessions = sqliteTable(
  "sessions",
  {
    jti: text("jti").primaryKey(),
    userId: text("user_id")
      .notNull()
      .references(() => users.id),
    tenantId: text("tenant_id").notNull(),
    createdAt: text("created_at").notNull(),
    expiresAt: text("expires_at").notNull(),
    revokedAt: text("revoked_at"),
  },
  (t) => [index("sessions_user_idx").on(t.userId)],
);

/**
 * Persisted audit results. `result_json` is the agent AuditResult stored
 * verbatim (never reshaped; assumptions[] and import_report always travel
 * with it). Provenance (source / uploader / agent_version) is a DB record,
 * not a UI guess.
 */
export const audits = sqliteTable(
  "audits",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id")
      .notNull()
      .references(() => tenants.id),
    /** Agent-assigned audit id (UUID from POST /audit). */
    auditId: text("audit_id").notNull(),
    source: text("source", { enum: ["live", "audit", "demo"] }).notNull(),
    uploaderUserId: text("uploader_user_id"),
    agentVersion: text("agent_version"),
    createdAt: text("created_at").notNull(),
    resultJson: text("result_json").notNull(),
  },
  (t) => [uniqueIndex("audits_tenant_audit_uq").on(t.tenantId, t.auditId)],
);

export const ticketState = sqliteTable(
  "ticket_state",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id")
      .notNull()
      .references(() => tenants.id),
    auditId: text("audit_id").notNull(),
    ticketRef: text("ticket_ref").notNull(),
    status: text("status", {
      enum: ["open", "acked", "dispatched", "closed"],
    }).notNull(),
    assignedUserId: text("assigned_user_id"),
    ackedBy: text("acked_by"),
    ackedAt: text("acked_at"),
    closedBy: text("closed_by"),
    closedAt: text("closed_at"),
    closeNote: text("close_note"),
    updatedAt: text("updated_at").notNull(),
  },
  (t) => [
    uniqueIndex("ticket_state_tenant_audit_ref_uq").on(
      t.tenantId,
      t.auditId,
      t.ticketRef,
    ),
  ],
);

export const auditLog = sqliteTable(
  "audit_log",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id"),
    action: text("action").notNull(),
    subject: text("subject"),
    at: text("at").notNull(),
  },
  (t) => [index("audit_log_tenant_idx").on(t.tenantId)],
);
