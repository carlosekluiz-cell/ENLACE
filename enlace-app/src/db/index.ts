// ── App DB singleton (better-sqlite3 + drizzle) ──
//
// File path from ENLACE_APP_DB (default ./data/enlace-app.db, gitignored).
// Cached on globalThis so Next dev-server HMR doesn't leak connections.
// The idempotent DDL in migrate.ts runs on first open.

import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";
import { drizzle, type BetterSQLite3Database } from "drizzle-orm/better-sqlite3";
import { migrate } from "./migrate";
import * as schema from "./schema";

export type AppDb = BetterSQLite3Database<typeof schema>;

const DEFAULT_DB_PATH = "./data/enlace-app.db";

function openDb(): AppDb {
  const file = path.resolve(process.env.ENLACE_APP_DB ?? DEFAULT_DB_PATH);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const sqlite = new Database(file);
  sqlite.pragma("journal_mode = WAL");
  sqlite.pragma("foreign_keys = ON");
  migrate(sqlite);
  return drizzle(sqlite, { schema });
}

const globalForDb = globalThis as unknown as { __enlaceAppDb?: AppDb };

export const db: AppDb = (globalForDb.__enlaceAppDb ??= openDb());

export * as tables from "./schema";
