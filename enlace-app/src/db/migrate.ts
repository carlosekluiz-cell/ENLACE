// ── Idempotent DDL for the app DB ──
//
// Applied on every open (CREATE TABLE IF NOT EXISTS), so the app and the
// seed script self-migrate. Mirror of src/db/schema.ts — keep in sync.

import type DatabaseType from "better-sqlite3";

const DDL = `
CREATE TABLE IF NOT EXISTS tenants (
  id       TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  slug     TEXT NOT NULL UNIQUE,
  settings TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  tenant_id     TEXT NOT NULL REFERENCES tenants(id),
  email         TEXT NOT NULL,
  name          TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('viewer','analyst','manager','admin')),
  persona       TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  disabled      INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS users_tenant_email_uq ON users (tenant_id, email);

CREATE TABLE IF NOT EXISTS sessions (
  jti        TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  tenant_id  TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);

CREATE TABLE IF NOT EXISTS audits (
  id               TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL REFERENCES tenants(id),
  audit_id         TEXT NOT NULL,
  source           TEXT NOT NULL CHECK (source IN ('live','audit','demo')),
  uploader_user_id TEXT,
  agent_version    TEXT,
  created_at       TEXT NOT NULL,
  result_json      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS audits_tenant_audit_uq ON audits (tenant_id, audit_id);

CREATE TABLE IF NOT EXISTS ticket_state (
  id               TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL REFERENCES tenants(id),
  audit_id         TEXT NOT NULL,
  ticket_ref       TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('open','acked','dispatched','closed')),
  assigned_user_id TEXT,
  acked_by         TEXT,
  acked_at         TEXT,
  closed_by        TEXT,
  closed_at        TEXT,
  close_note       TEXT,
  updated_at       TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ticket_state_tenant_audit_ref_uq
  ON ticket_state (tenant_id, audit_id, ticket_ref);

CREATE TABLE IF NOT EXISTS audit_log (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  user_id   TEXT,
  action    TEXT NOT NULL,
  subject   TEXT,
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_log_tenant_idx ON audit_log (tenant_id);
`;

export function migrate(sqlite: DatabaseType.Database): void {
  sqlite.exec(DDL);
}
