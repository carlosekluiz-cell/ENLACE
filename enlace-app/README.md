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

## App DB

SQLite (better-sqlite3 + drizzle), path `ENLACE_APP_DB` (default
`./data/enlace-app.db`, gitignored). Every table is tenant-keyed:
`tenants`, `users`, `sessions`, `audits` (agent `AuditResult` stored
**verbatim** with provenance: source/uploader/agent_version),
`ticket_state`, `audit_log`. Schema: `src/db/schema.ts`; idempotent DDL:
`src/db/migrate.ts` (applied on open).
