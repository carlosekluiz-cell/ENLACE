// ── Demo tenant + credentials ──
//
// This is a pilot demo: discoverability of these accounts is a feature, not
// a leak. The seed script (scripts/seed.ts) creates them; the login page
// offers them as one-click fill. They are ALSO documented in .env.example
// and README.md — keep all three in sync.
//
// Safe to import from client code: contains no secrets beyond the demo
// passwords, which are public by design.

import { PERSONAS, type Persona, type PersonaId } from "./roles";

export const DEMO_TENANT = {
  id: "demo-operator",
  name: "Demo Operator",
  slug: "demo-operator",
  /**
   * Tenant-level assumption constants. These parameterize `estimated_*`
   * figures and must always surface as assumptions, never measurements.
   */
  settings: {
    assumptions: {
      arpu_gbp_month: 25,
      truck_roll_cost_gbp: 150,
      currency: "GBP",
      note: "demo assumption constants — admin-editable tenant settings, echoed into estimates",
    },
  },
} as const;

export interface DemoUser {
  persona: PersonaId;
  label: string;
  role: Persona["role"];
  home: string;
  email: string;
  password: string;
  name: string;
  /**
   * Optional engineer phone — enables direct wa.me dispatch from the
   * supervisor board. Placeholder from the Ofcom drama range (not a real
   * number); demo-only.
   */
  phone: string | null;
}

function kebab(id: PersonaId): string {
  return id.replace(/_/g, "-");
}

/** One demo account per persona, matching src/lib/roles.ts exactly. */
export const DEMO_USERS: DemoUser[] = PERSONAS.map((p) => ({
  persona: p.id,
  label: p.label,
  role: p.role,
  home: p.home,
  email: `${kebab(p.id)}@demo.enlace.network`,
  password: `demo-${kebab(p.id)}`,
  name: p.label,
  phone: p.id === "field_engineer" ? "+44 7700 900123" : null,
}));
