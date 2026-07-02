// ── Password hashing ──
//
// Primary: argon2id via the native `argon2` package (verified to build and
// load on this box — the fallback below did NOT need to land as primary).
// Fallback: node:crypto scrypt, used only if the native module fails to
// load at runtime (e.g. a deploy target without prebuilt binaries).
//
// Hash formats are self-describing, so a DB seeded under one scheme
// verifies under either: "$argon2id$…" vs "scrypt$N$r$p$salt$hash".

import {
  randomBytes,
  scrypt as scryptCb,
  timingSafeEqual,
  type ScryptOptions,
} from "node:crypto";

function scrypt(
  password: string,
  salt: Buffer,
  keylen: number,
  opts: ScryptOptions,
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scryptCb(password, salt, keylen, opts, (err, key) =>
      err ? reject(err) : resolve(key),
    );
  });
}

type Argon2Module = {
  argon2id: number;
  hash(pw: string, opts: { type: number }): Promise<string>;
  verify(hash: string, pw: string): Promise<boolean>;
};

let argon2: Argon2Module | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  argon2 = require("argon2") as Argon2Module;
} catch {
  console.warn(
    "[enlace-auth] native argon2 failed to load — falling back to node:crypto scrypt for password hashing",
  );
}

const SCRYPT_N = 1 << 15;
const SCRYPT_R = 8;
const SCRYPT_P = 1;

async function scryptHash(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await scrypt(password, salt, 32, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
    maxmem: 128 * SCRYPT_N * SCRYPT_R * 2,
  });
  return `scrypt$${SCRYPT_N}$${SCRYPT_R}$${SCRYPT_P}$${salt.toString("base64")}$${key.toString("base64")}`;
}

async function scryptVerify(stored: string, password: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const [, nStr, rStr, pStr, saltB64, hashB64] = parts;
  const N = Number(nStr);
  const r = Number(rStr);
  const p = Number(pStr);
  if (!Number.isFinite(N) || !Number.isFinite(r) || !Number.isFinite(p)) return false;
  const salt = Buffer.from(saltB64, "base64");
  const expected = Buffer.from(hashB64, "base64");
  const actual = await scrypt(password, salt, expected.length, {
    N,
    r,
    p,
    maxmem: 128 * N * r * 2,
  });
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

export async function hashPassword(password: string): Promise<string> {
  if (argon2) return argon2.hash(password, { type: argon2.argon2id });
  return scryptHash(password);
}

export async function verifyPassword(
  stored: string,
  password: string,
): Promise<boolean> {
  try {
    if (stored.startsWith("$argon2")) {
      if (!argon2) return false;
      return await argon2.verify(stored, password);
    }
    if (stored.startsWith("scrypt$")) return await scryptVerify(stored, password);
    return false;
  } catch {
    return false;
  }
}
