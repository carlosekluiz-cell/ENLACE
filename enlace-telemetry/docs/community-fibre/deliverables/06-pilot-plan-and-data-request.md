# The Free Pilot: Plan & Data Request
*Enlace · Pulso Technologies Limited*

---

## The offer

A **free pilot** for a small number of UK launch partners, with preferential pricing at launch.
No cost, no obligation, and **nothing touches your network** until you've seen value on your own data.

---

## How it works — three low-risk steps

**Step 1 — Offline audit (this week, zero footprint).**
You export **~one month of ONT / optical telemetry** (CSV, or NETCONF / Mosaic PM export) from **one area
where you've had recurring issues**. We analyse it and, within a day, send back what Enlace found: fibre
faults, at-risk customers, capacity hot-spots, rogue/reflecting ONTs, and degradations trending toward
failure — each scored, located, and ticket-ready. No install, no account, nothing connects to your network.

**Step 2 — Review together.**
We walk through the findings against your operation, using the discovery questionnaire to put *your* numbers
(truck-roll cost, churn, ARPU, alarm volume) against the results — so the value is in your figures, not
industry averages.

**Step 3 — Live read-only deployment (only if you want it).**
Deploy the agent against a live OLT, **strictly read-only**, feeding alerts/tickets into your existing tooling
(and optionally WhatsApp). Expand at your pace.

---

## What we need from you for Step 1

A telemetry export covering one area, ideally including per-ONT, time-series:

| Field | Example | Needed? |
|---|---|---|
| Timestamp | `2026-06-01T00:05:00Z` | Required |
| ONT serial / ID | `ALCLB3A1C2D3` | Required |
| PON port | `0/1/4` | Required |
| Rx power (dBm) | `-22.1` | Required |
| Tx power (dBm) | `2.3` | Strongly preferred |
| Status | `Online` / `Offline` | Required |
| Distance (m) | `812` | Preferred (enables fault location) |
| Eth speed (Mbps) | `1000` | Optional (ghost detection) |
| Last-down cause | `LOS` / `dying-gasp` | Optional |

- **Cadence:** whatever your OLT exports — 5-minute polling is ideal; 15–60 min still works.
- **Volume:** ~50+ ONTs over ~30 days is plenty to demonstrate value; more is better.
- **Format:** CSV is simplest. We already have an Adtran SDX 6320 parser; we can adapt to your export shape.
- **Anonymisation:** fine to anonymise serials/addresses — we only need the signal patterns.

---

## Read-only by design — verifiable by your engineers

Enlace is built so your team can sign it off without seeing source:

- **Read-only methods only:** SNMP GET, CLI `show`/`display`, NETCONF `get`, RouterOS read, passive RADIUS.
  **Never** set/write/configure/reboot.
- **Credentials stay local** — only aggregated metrics leave the device; in the pilot's Step 1, nothing leaves
  your network at all.
- **Single ~8 MB binary**, no runtime dependencies, runs as an unprivileged user.
- **Self-hosted option** — telemetry can stay entirely on your infrastructure.

---

## Indicative timeline

| When | What |
|---|---|
| Day 0 | Kick-off call + discovery questionnaire |
| Day 0–3 | You export ~1 month of telemetry from one problem area |
| +1 day | We return the analysed findings |
| Week 1–2 | Review session; agree whether to go live read-only |
| Week 2+ | Optional live read-only deployment, alerts into your tooling |

---

## What success looks like

We'll agree one headline metric to move with you — typically **avoidable truck rolls**, **MTTR**, **churn from
quality**, **first-call resolution**, or **alarm noise**. Operators running proactive assurance report truck
rolls down 30–50% and MTTR down ~40%; the pilot tests that against your reality, conservatively.

---

*Ready when you are — **hello@enlace.network**.
Pulso Technologies Limited, registered in England & Wales, company no. 17151141.*
</content>
