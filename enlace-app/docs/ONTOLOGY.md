# Enlace Operations — Ontology & Architecture

The reverse-ontology of an ISP (the working model: a London altnet like
Community Fibre) operating the Enlace telemetry platform. Everything in the
app maps back to these entities, and every number on screen traces to either
the pulso-agent audit output or the live Elasticsearch feed. **Nothing is
fabricated. Missing data is shown as missing.**

---

## 1. Entities

### Physical plant (containment hierarchy)

```
Network
 └── OLT                      (e.g. an Adtran SDX 6320 in an exchange)
      └── PON port            (e.g. CTP-0/3 — one SFP, one fibre out)
           └── Splitter       (1:32 typical; ratio often ASSUMED, flagged)
                └── ONT       (customer premises unit, serial-keyed)
                     └── Customer  (billing identity; NOT in telemetry —
                                    joined later from the ISP's CRM)
```

- **Network** — the operator's whole footprint. App-level aggregate only.
- **OLT** — head-end chassis. Identified by `olt_id`. Health rolls up from
  its PON ports (`diagnostics.overall_health`, `sfp_health`).
- **PON port** — the shared medium. Unit of blast radius: a fibre cut or SFP
  failure here takes out every downstream ONT. Keys: `pon_port` strings like
  `CTP-0/3`. Carries capacity state (`active_onts / max_ports`,
  `utilisation_pct`, `months_to_full`).
- **Splitter** — passive optical split between port and ONTs. The agent often
  cannot see it; when the ratio is assumed the data says so
  (`splitter_assumed: true`) and the UI must render the assumption badge.
- **ONT** — the atom of telemetry. Serial number, status
  (`Online | LowSignal | Dying | Offline | PowerFail | FiberCut | Unknown`),
  rx/tx power, distance, uptime, eth speed. `Unknown` is a first-class state:
  the vendor vocabulary wasn't recognized or status was missing. It is *not*
  an outage and is never lumped with Offline (`total = online + offline +
  unknown` reconciles by construction).
- **Customer** — one-to-one with ONT in practice. Telemetry has no PII;
  revenue figures attached to ONTs are **ARPU assumptions**, echoed in
  `assumptions` fields, never billing truth.

### Operational objects

- **Incident** (`IncidentUpdate` from the fault detector) — lifecycle object.
  `action: open | resolve`, stable `incident_id`
  (`"{olt}:{port}:{opened_at}"`), `scope: port | olt`, `opened_at`,
  `resolved_at?`, plus the flattened `FaultEvent` (severity, fault_type
  `FibreCut | PowerOutage | Mixed`, affected ONTs with dying-gasp evidence).
  Opened by the detector, pushed over webhooks, resolved when ONTs return.
  The NOC board is a projection of open incidents.
- **Finding** — one row from any of the 11 detection modules in an audit:
  faults, ghosts, capacity, flapping, weather_correlation, reflectance,
  optical_budget, sfp_health, churn_risk, diagnostics alerts, impact.
  A Finding carries *evidence* (measured) and, where money enters,
  *assumptions* (declared). Findings feed Tickets.
- **Ticket** — actionable work generated from findings. `ticket_id`,
  `priority (P1..P4)`, `team` (routing target: Field Ops / NOC / Management…),
  `sla_days` → due date = `generated_at + sla_days`, `evidence[]`,
  `recommended_action`, `estimated_revenue_at_risk_annual` + `estimated_roi`
  (both estimates, with the `assumptions[]` that produced them), and a geo
  link **once customer records are joined** — telemetry alone has no
  coordinates, and the app says so rather than inventing a pin.
- **MaintenanceWindow** — trend-driven planned work: SFP health gives
  `estimated_weeks_to_failure`, capacity gives `months_to_full`. The
  "days-to-act" horizon converts a trend into a scheduled window before it
  becomes an Incident. (Derived object; not yet emitted by the agent.)
- **ImportReport** (`ImportReportSummary`) — the data-honesty object attached
  to every CSV-fed audit: `rows_ok`, `rows_skipped` (+ sanitized samples),
  `cells_unparsed`, `unknown_statuses` (+ the actual unrecognized values),
  `snapshot_mode` (timestamps were defaulted), sniffed `delimiter`. Surfaced
  on **every** audit view — you always know how much of the file was actually
  understood.

---

## 2. Personas — who sees what, who does what

| Persona | Role | Home | Top jobs |
|---|---|---|---|
| **NOC operator** | analyst | `/noc` | Watch the live incident board; triage opens by severity/scope; acknowledge; drill into per-OLT/port health; check ONT table for a caller's serial |
| **Field engineer** | viewer | `/field` | See my ticket queue on a phone; open a ticket for evidence + recommended action; navigate to site (map link when geo exists); close out |
| **Supervisor** | manager | `/supervisor` | Watch queue health per team; catch SLA breaches before they age; re-prioritize and dispatch crews |
| **Network manager** | manager | `/exec` | Health-score trend; capacity planning (`months_to_full` hotspots); churn-risk cohort; decide maintenance windows |
| **Director** | admin | `/exec` | Exec KPIs: fleet health score, online/offline/**unknown** split, revenue-at-risk **labeled as estimate**, truck-rolls avoided & uptime (only when measured — otherwise shown as "not measured") |

## 3. Role hierarchy

`viewer < analyst < manager < admin` — a route or nav item declares
`minRole`; a user's role must rank at or above it.

- field engineer → **viewer** (own queue, read + close-out)
- NOC operator → **analyst** (fleet visibility, triage)
- supervisor → **manager** (cross-team queues, dispatch)
- network manager → **manager** (planning views)
- director → **admin** (everything, incl. future admin/config)

Auth today is a demo persona-picker session (localStorage). The structure is
JWT-ready: `Session { sub, name, persona, role }` matches the claims shape of
`python/api` JWTs — see TODO in `src/lib/auth.tsx`.

## 4. Data flow

```
             ┌────────────────────── pulso-agent (Rust) ──────────────────────┐
 OLTs ──SNMP/│ CLI/CSV → detection modules → AuditResult                      │
 TR-069/CSV  │           fault detector    → IncidentUpdate (open/resolve)    │
             └───┬──────────────────────┬──────────────────────┬──────────────┘
                 │                      │                      │
                 ▼                      ▼                      ▼
        Elasticsearch          Webhooks (PagerDuty,     Audit HTTP API
     enlace-ont-{date}          Slack, generic)         POST /audit (multipart)
     enlace-faults-*                                    GET  /audit/:id
                 │                                      Bearer PULSO_AUDIT_TOKEN
                 │                                      binds 127.0.0.1
                 ▼                                             │
        ┌────────────────────── enlace-app (Next.js) ──────────▼─────────┐
        │ server routes: /api/noc/*  (ES proxy)     /api/audit[/:id]     │
        │                (token + ES creds injected server-side ONLY)    │
        │ data layer: LiveAdapter ⇄ DemoAdapter (bundled REAL agent run) │
        │ views: /noc  /noc/onts  /field  /supervisor  /exec             │
        └────────────────────────────────────────────────────────────────┘
```

The browser never holds the audit token or ES credentials; it only talks to
Next server routes.

## 5. Honesty rules (product invariants)

1. **`estimated_*` fields always render with an assumption badge.** The badge
   exposes the underlying `assumptions[]` (ARPU £/mo, truck-roll cost, churn
   probability model). No estimate ever appears styled as a measurement.
2. **`Unknown` is its own status and its own color** (violet in the UI).
   Never merged with Offline, never counted as an outage, always shown in the
   online/offline/unknown triple so totals reconcile.
3. **`import_report` is surfaced on every audit view** — rows skipped, cells
   unparsed, unrecognized status values, snapshot-mode timestamp defaulting.
4. **Live vs. audit vs. demo provenance is always on screen.** If
   Elasticsearch is not connected, the UI says "live feed not connected —
   showing audit data"; it never fakes liveness. Demo data is a bundled,
   unedited run of the real agent and is labeled as such.
5. **Missing is missing.** Null rx power renders as "—", absent geo renders
   as "no location data", unmeasured KPIs (uptime, truck-rolls avoided)
   render as "not measured", not as zero.
