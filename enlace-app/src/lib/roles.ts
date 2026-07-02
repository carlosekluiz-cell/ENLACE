// ── Role hierarchy & personas ──
// viewer < analyst < manager < admin. Routes and nav items declare a
// minRole; a session's role must rank at or above it (see ONTOLOGY.md §3).

export const ROLES = ["viewer", "analyst", "manager", "admin"] as const;
export type Role = (typeof ROLES)[number];

export function roleRank(role: Role): number {
  return ROLES.indexOf(role);
}

export function roleAtLeast(role: Role, min: Role): boolean {
  return roleRank(role) >= roleRank(min);
}

export type PersonaId =
  | "field_engineer"
  | "noc_operator"
  | "supervisor"
  | "network_manager"
  | "director";

export interface Persona {
  id: PersonaId;
  label: string;
  role: Role;
  /** Landing route after login. */
  home: string;
  description: string;
}

export const PERSONAS: Persona[] = [
  {
    id: "noc_operator",
    label: "NOC Operator",
    role: "analyst",
    home: "/noc",
    description: "Incident board, triage, per-OLT health, ONT lookup",
  },
  {
    id: "field_engineer",
    label: "Field Engineer",
    role: "viewer",
    home: "/field",
    description: "My tickets on mobile, evidence, directions, close-out",
  },
  {
    id: "supervisor",
    label: "Supervisor",
    role: "manager",
    home: "/supervisor",
    description: "Queue health per team, SLA breaches, crew dispatch",
  },
  {
    id: "network_manager",
    label: "Network Manager",
    role: "manager",
    home: "/exec",
    description: "Health trends, capacity planning, churn risk",
  },
  {
    id: "director",
    label: "Director",
    role: "admin",
    home: "/exec",
    description: "Exec KPIs: health score, revenue at risk (estimates)",
  },
];

export function personaById(id: string): Persona | undefined {
  return PERSONAS.find((p) => p.id === id);
}
