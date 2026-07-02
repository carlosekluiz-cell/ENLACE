# enlace-app — Enlace Operations

Multi-persona ISP operations app on the Enlace telemetry pipeline (NOC,
field, supervisor and executive views). See `docs/ARCHITECTURE-TENANCY.md`
for the tenancy/auth design and `docs/ONTOLOGY.md` for the honesty
invariants.

## Quick start

```bash
npm install
npm run db:seed     # creates ./data/enlace-app.db + demo tenant/users
npm run dev
```

Optional env (see `.env.example`): `PULSO_AUDIT_SERVER` / `PULSO_AUDIT_TOKEN`
for CSV audits through the agent, `ELASTIC_URL` for the live NOC feed,
`ENLACE_APP_DB` for the DB path, `ENLACE_AUTH_SECRET` for JWT signing
(required in real deployments; dev generates one into `./data/`).

## Auth

In-house JWT issuer (`jose`, HS256) inside the Next app: `POST
/api/auth/login` sets an httpOnly `enlace_session` cookie (12 h);
`middleware.ts` enforces authentication and per-route role floors
server-side; `POST /api/auth/logout` revokes the token's jti in the
`sessions` table. Passwords are argon2id hashes. Claims
`{sub, name, tenant_id, role, persona, jti}` are shape-compatible with
`python/api` tokens so the issuer can be swapped later.

## Demo accounts (pilot demo — discoverability is a feature)

Seeded by `npm run db:seed` into tenant **demo-operator**. One account per
persona, matching `src/lib/roles.ts`:

| Persona | Email | Password | Role | Home |
|---|---|---|---|---|
| Director | `director@demo.enlace.network` | `demo-director` | admin | `/exec` |
| Network Manager | `network-manager@demo.enlace.network` | `demo-network-manager` | manager | `/exec` |
| Supervisor | `supervisor@demo.enlace.network` | `demo-supervisor` | manager | `/supervisor` |
| NOC Operator | `noc-operator@demo.enlace.network` | `demo-noc-operator` | analyst | `/noc` |
| Field Engineer | `field-engineer@demo.enlace.network` | `demo-field-engineer` | viewer | `/field` |

The login page lists these as one-click fill; they still go through real
login. Source of truth: `src/lib/demoCredentials.ts` (keep `.env.example`
and this table in sync).

## PDF reports

`GET /api/reports/audit/[id].pdf` (manager+, tenant-scoped, logged to
`audit_log` as `report.generate`) renders an executive audit report
server-side with pdfkit (pure JS, built-in fonts — no native deps, no
headless browser): dark cover with source badge + health score, executive
summary (ONT status triple with `total = online + offline + unknown`
reconciliation, findings by module, ticket counts), findings sections
(faults, ghosts, churn, capacity, and the frontier modules with coverage
notes, "heuristic ETA" and "hypothesis, not verdict" framing), a tickets/SLA
table from the `ticket_state` overlay, a mandatory **Data honesty** page
(import report counters, coverage notes, every assumption line, and the
"estimates are estimates" statement), plus an ONT inventory appendix.
Honesty invariants are hard requirements: no estimated figure prints
without its label and assumptions; missing data prints as "not measured" or
"—", never as zero. Download button: `/exec` header ("Download report
(PDF)") for the current audit.

## Admin area (`/admin`, role `admin` only)

- **/admin/users** — list tenant users, invite/create (server-generated
  temp password returned **once**, only the hash is stored), disable/enable
  (disable also revokes the user's active sessions), reset password, role
  change. Self-lockout is blocked (you cannot disable yourself or drop your
  own admin role). API: `GET/POST /api/admin/users`,
  `PATCH /api/admin/users/[id]`. Password hashes never leave the server.
- **/admin/settings** — tenant assumption constants stored in
  `tenants.settings` JSON (`assumptions.arpu_gbp_month`,
  `assumptions.truck_roll_cost_gbp`, `assumptions.currency`). These feed
  the estimate math and are surfaced, labeled, in the exec projection
  (`tenant_assumptions`) and on the PDF honesty page. The seam is stated
  honestly: the agent computes estimates at audit time with the assumptions
  it declares in the result — settings changes apply to future estimate
  math and never retro-recompute persisted audits. API:
  `GET/PUT /api/admin/settings`.
- **/admin/activity** — the accountability view: tenant `audit_log` newest
  first, filterable by action, with resolved actor names. API:
  `GET /api/admin/activity?action=&limit=`.

Every admin mutation writes `audit_log`
(`admin.user.create|disable|enable|reset_password|role`,
`admin.settings.update`), alongside the existing `auth.login`,
`ticket.*` and `report.generate` entries. Route floor: `/admin` requires
role `admin` (`src/lib/routeAccess.ts`, enforced in middleware).

## App DB

SQLite (better-sqlite3 + drizzle), path `ENLACE_APP_DB` (default
`./data/enlace-app.db`, gitignored). Every table is tenant-keyed:
`tenants`, `users`, `sessions`, `audits` (agent `AuditResult` stored
**verbatim** with provenance: source/uploader/agent_version),
`ticket_state`, `audit_log`. Schema: `src/db/schema.ts`; idempotent DDL:
`src/db/migrate.ts` (applied on open).
