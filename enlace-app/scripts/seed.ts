// ── Seed: demo tenant + one user per persona ──
//
// Run with: npm run db:seed   (idempotent — upserts by stable ids)
//
// Demo credentials are a pilot-demo feature, documented in .env.example and
// README.md. Source of truth: src/lib/demoCredentials.ts.

import { db, tables } from "../src/db";
import { DEMO_TENANT, DEMO_USERS } from "../src/lib/demoCredentials";
import { hashPassword } from "../src/lib/password";

async function main() {
  const now = new Date().toISOString();

  db.insert(tables.tenants)
    .values({
      id: DEMO_TENANT.id,
      name: DEMO_TENANT.name,
      slug: DEMO_TENANT.slug,
      settings: JSON.stringify(DEMO_TENANT.settings),
    })
    .onConflictDoUpdate({
      target: tables.tenants.id,
      set: {
        name: DEMO_TENANT.name,
        slug: DEMO_TENANT.slug,
        settings: JSON.stringify(DEMO_TENANT.settings),
      },
    })
    .run();
  console.log(`tenant  ${DEMO_TENANT.id} (${DEMO_TENANT.name})`);

  for (const u of DEMO_USERS) {
    const passwordHash = await hashPassword(u.password);
    db.insert(tables.users)
      .values({
        id: `u-demo-${u.persona.replace(/_/g, "-")}`,
        tenantId: DEMO_TENANT.id,
        email: u.email,
        name: u.name,
        passwordHash,
        role: u.role,
        persona: u.persona,
        createdAt: now,
        disabled: 0,
      })
      .onConflictDoUpdate({
        target: tables.users.id,
        set: {
          email: u.email,
          name: u.name,
          passwordHash,
          role: u.role,
          persona: u.persona,
          disabled: 0,
        },
      })
      .run();
    console.log(
      `user    ${u.email.padEnd(38)} ${u.password.padEnd(24)} role=${u.role.padEnd(7)} persona=${u.persona}`,
    );
  }

  console.log("\nseed complete — demo credentials above (also in README.md).");
}

main().catch((err) => {
  console.error("seed failed:", err);
  process.exit(1);
});
