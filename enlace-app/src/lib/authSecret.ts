// ── JWT signing secret ──
//
// Production: set ENLACE_AUTH_SECRET (any high-entropy string).
// Dev fallback: a random secret generated once into ./data/auth-secret.dev
// (same gitignored dir as the app DB) so sessions survive restarts. The
// fallback warns LOUDLY — it must never be how a real deploy runs.

import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";

const DEV_SECRET_FILE = "./data/auth-secret.dev";

let cached: Uint8Array | null = null;

export function getAuthSecret(): Uint8Array {
  if (cached) return cached;

  const fromEnv = process.env.ENLACE_AUTH_SECRET;
  if (fromEnv && fromEnv.length > 0) {
    cached = new TextEncoder().encode(fromEnv);
    return cached;
  }

  const file = path.resolve(DEV_SECRET_FILE);
  let hex: string;
  if (fs.existsSync(file)) {
    hex = fs.readFileSync(file, "utf8").trim();
  } else {
    hex = randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, hex + "\n", { mode: 0o600 });
  }
  console.warn(
    "╔════════════════════════════════════════════════════════════════════╗\n" +
      "║ [enlace-auth] ENLACE_AUTH_SECRET is NOT set.                       ║\n" +
      `║ Using a generated dev secret from ${DEV_SECRET_FILE}.        ║\n` +
      "║ This is fine for local demos only — set ENLACE_AUTH_SECRET in any  ║\n" +
      "║ real deployment.                                                   ║\n" +
      "╚════════════════════════════════════════════════════════════════════╝",
  );
  cached = new TextEncoder().encode(hex);
  return cached;
}
