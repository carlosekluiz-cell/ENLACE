import { Pool } from "pg";

// Singleton pool — survives hot reloads in dev and is reused across requests.
const globalForPg = globalThis as unknown as { _enlacePool?: Pool };

export function getPool(): Pool | null {
  if (!process.env.DATABASE_URL) return null;
  if (!globalForPg._enlacePool) {
    globalForPg._enlacePool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 4,
      idleTimeoutMillis: 30_000,
    });
  }
  return globalForPg._enlacePool;
}
