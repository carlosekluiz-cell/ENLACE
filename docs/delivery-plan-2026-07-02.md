# Enlace delivery plan — 2026-07-02

Goal: everything in the Community Fibre pilot proposal is shippable (no gaps), the frontier
capabilities are included on top, and the operations app serves every user tier — from the
director to the emergency field engineer who gets the job on WhatsApp. Synthetic/sample data
powers all demos until real CF data arrives; every output stays honestly labelled.

## 1. Where we are (delta: before agents → now)

**Before (this morning's baseline, commit 41a21ef):** 32 pilot-blocking audit findings fixed,
extended ONT data model (FEC/BIP/DDM/octets), SNMPv3 USM, real-device fixtures with decode
oracles, enlace-app persona scaffold (localStorage stub auth), upload auth fixed. 439 tests.

**Now (commit b8d2f1f):** the frontier batch is landed and integrated. 519 tests, 0 failed.

| New capability | Module | Surfaced as |
|---|---|---|
| Pre-FEC degradation trending (dispersion vs attenuation vs error-floor) | detection/fec_health.rs | AuditResult.fec_health + P1/P2 tickets |
| Passive rogue-ONT hypothesis scoring (G.Sup49) | detection/rogue.rs | AuditResult.rogue + P2 ticket w/ confirmation action |
| Laser end-of-life prediction (temp-detrended bias drift) | predictions/laser_health.rs | AuditResult.laser_health + P1/P2/P3 tickets |
| Honest stats layer (median/MAD, EWMA, CUSUM, step-change); splice steps no longer poison trends | predictions/stats.rs | recent_step on SignalPrediction |
| Power-vs-fibre v2 (gasp ratios, onset tightness, cross-OLT area-power, confidence) | fault/detector.rs + main loop | IncidentUpdate.classification in ES/Slack/PagerDuty |
| Real ghost detection from octet deltas (NoTraffic class) | detection/ghost.rs | AuditResult.ghosts (revenue claim now physically sound) |
| Live collection: Adtran NETCONF octets + FEC/BIP 15-min bins; Huawei DDM (+TX OID bug fix) | vendors/, netconf/ | fills the model from real devices, not just CSV |

App side: `enlace-app/docs/ARCHITECTURE-TENANCY.md` (tenancy + RBAC design),
`src/lib/types.ts` mirrors the new audit sections, demo fixture regenerated from the real
agent (health 64, 52 ONTs; laser_health honestly shows 0-bias coverage on the CF sample).
Proposal side: 100-claim inventory at
`enlace-telemetry/docs/community-fibre/proposal-claims-inventory-2026-07-02.md`.

## 2. Build plan — multi-tier user infrastructure (enlace-app)

Per ARCHITECTURE-TENANCY.md. Operator = tenant; single-tenant deploys for pilots, everything
tenant_id-scoped from day one. Personas map to the role lattice: field engineer = viewer
(own-ticket close-out) · NOC = analyst (ack + CSV upload) · supervisor/network manager =
manager (dispatch/reassign) · director = admin (invites, settings).

**Wave A (parallel, disjoint files):**
- A1 Auth: in-house JWT issuer (jose + argon2id, httpOnly cookie), login/logout/session
  routes, `middleware.ts` server-side enforcement, replace localStorage stub. Claims
  `{sub, name, tenant_id, role, persona, jti}` — shape-compatible with python/api for a
  later issuer swap.
- A2 App DB: SQLite + drizzle, tenant-keyed schema: users, sessions/revocations, audits
  (verbatim agent JSON + provenance), tickets_state (ack/close/assign), tenants+settings
  (ARPU assumptions etc.).

**Wave B (after A, parallel):**
- B1 Audit persistence + listing: POST /api/audit persists AuditResult keyed
  (tenant_id, audit_id); agent's 1h TTL store becomes a cache; tenant-scoped GET
  /api/audits replaces the localStorage last-audit-id hack.
- B2 Ticket lifecycle: ack/close-out/assign persisted; state machine
  open → acked → dispatched → closed(confirmed by close-out form); survives refresh;
  role-gated actions.
- B3 Server-side persona projections: NOC (ONT-level faults), field (my tickets),
  supervisor (dispatch board), exec (health rollups) — projections may subset rows but
  never strip assumptions[]/import_report (honesty invariant).

**Wave C (after B, parallel) — the over-deliver layer:**
- C1 WhatsApp dispatch: shareable deep link to /field/ticket/[id] (auth-guarded) +
  `wa.me` share with fault summary, priority, SLA, and location link; works from the
  supervisor dispatch board ("send the job to the engineer's phone").
- C2 Fault location: surface fault/locator.rs output (estimated break distance + span)
  on the ticket; map view (maplibre already installed) when coordinates exist; honest
  empty state when they don't (geo join is post-pilot per the architecture doc).
- C3 PDF reports: per-audit executive report (health score, findings, coverage notes,
  estimate labels) rendered server-side; downloadable from exec/supervisor views.
- C4 /admin: user invites, tenant settings (assumption constants), audit log of actions.

**Definition of done for a credible multi-user pilot** (architecture doc critical path):
two personas with real logins share one audit, acks survive refresh, a ticket dispatched by
WhatsApp opens on a phone at the right ticket with location. All on the CF sample CSV.

## 3. Proposal gap lock-in (after Wave B)

Method: walk all 100 inventoried claims against the working system; each becomes
**shippable** (evidenced by code + demo output), **fixed** (small build to close), or
**reworded** (proposal corrected to what's true — honesty beats marketing). Known watch
items from the inventory: 17-modules/180-tests counts are stale (understated now — update),
WhatsApp Business API claim (P26/P85) must match what C1 actually ships (deep link + wa.me
share vs full Business API), performance metrics (P5–P8) need re-measurement, "ready now"
list in deliverable 04 must match Wave C reality. Then re-render the proposal PDF and
site examples from real agent output, and update outreach docs.

## 4. Sequencing

1. ✅ Frontier batch + integration (commit b8d2f1f)
2. This plan
3. Wave A (agents in parallel) → Wave B → Wave C
4. Gap lock-in + proposal/site/outreach v2
5. End-to-end synthetic-data run-through as the demo script

Environment constraints that bind every step: no outbound network from this box (WebSearch/
WebFetch via harness only; curl SIGKILLed — verify local HTTP with python urllib), no
browser JS testing (node --check + user previews rendering), port 8080 taken.
