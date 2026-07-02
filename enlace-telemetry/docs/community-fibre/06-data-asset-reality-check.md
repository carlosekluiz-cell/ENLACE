# Data Asset — Honest Reality Check (INTERNAL)

*A blind, skeptical assessment of the UK open-data asset before we build a teaser or pitch it. Three independent research agents + verification against the actual ingested files. Goal: don't overclaim to a customer who knows their own network.*

---

## What we actually hold (verified on the box, 2026-06-26)

`pulso-uk/data/` — all loaded and row-counted:

| Dataset | Scale (verified) | Granularity |
|---|---|---|
| OS Open UPRN | **41,593,226 premises** | premises point (UPRN + coords); no address/operator |
| OS Code-Point Open | ~1.7m postcodes | postcode centroid |
| Ofcom CN2025 fixed coverage | UK-wide | **postcode = gigabit-capable %**, OA, LA, constituency |
| Ofcom CN2025 full-fibre take-up | by LA | **local-authority only** |
| ONS NSPL Nov 2025 | UK postcodes | postcode → OA/LSOA/MSOA/LA + lat-long |
| Census 2021 TS001/TS041 | EW | Output Area population & households |
| OS Built Up Areas | GB | urban-footprint polygons |

**Real London cut (genuine, from the take-up file):** full-fibre take-up as % of FF coverage —
Kensington & Chelsea 17%, Islington 20%, Camden 22%, Enfield 23%, Haringey 27%, Westminster 28%,
Hackney 32%; **London avg 38.3%** across 33 boroughs. This is defensible: "available but not converting."

---

## Verdict 1 — Is it novel? **No. Things like it exist.**

- **Point Topic** sells postcode-level coverage + competitor footprint + take-up + tariffs to operators
  (CSV/JSON/shapefile), **£2k–£80k**; used by operators covering ~90% of the UK market. The closest direct competitor.
- **thinkbroadband** — postcode FTTP/altnet coverage feeds + availability API.
- **VCTI Broadband IQ** / **Wireless 20/20** — US SaaS "where to build" fusing coverage+competition+demographics.
- **McKinsey / BCG** — bespoke geospatial fibre-rollout studies (six–seven figure engagements).
- Analyst firms (Analysys Mason, Enders, Omdia, Assembly) — national/operator level, **not** geospatial premises.

**The data and even the postcode-level product are crowded.** A UK-native, UPRN-granular, take-up-lag-framed
**self-serve** tool is a thinner niche — but that's packaging/granularity/UX/price, **not a new category.**
→ **Never pitch "nobody does this."** Name Point Topic; differentiate on granularity, price, and the telemetry fusion below.

## Verdict 2 — What would it take? **Teaser = weeks. Product = ~a year.**

- **Credible London teaser (open data only):** 3–6 weeks (small team) / 6–10 weeks (one strong engineer).
- **Robust national, refreshed, operator-grade platform:** ~9–15 months — *this* is where "about a year" is fair (slightly optimistic once you count refresh maintenance).
- Open data is **free and joins cleanly on UPRN**; PostGIS at 41M points is routine. The cost is engineering + refresh maintenance.
- → "This took a year" is true of the **product**, not the demo. Pitch: "productising to operator grade is ~a year — here's the teaser in weeks."

## Verdict 3 — Can it tell CF "where to do better in London"? **At borough level, yes. Operator-specific, no.**

The hard limits (confirmed against our files):
- Postcode-level Ofcom open data is **gigabit-capable %** (includes Virgin coax) — **not full-fibre, not per-operator.**
- Full-fibre availability **and take-up are local-authority level only** — no postcode-level take-up.
- Coverage is **modelled/predicted** premises-passed, a **lagged snapshot** (Jul 2025).
- OS UPRN is **points only** — no address, occupier, operator, churn, or pricing.
- **We cannot show CF's own homes-passed, or a named competitor's exact footprint, from open data.**

### Defensible vs overreach (the sales guardrail)

| ✅ CAN say to CF | ❌ MUST NOT say |
|---|---|
| Rank London **boroughs** by FF availability vs take-up (conversion gaps) | "The **postcodes** where FTTP is available but take-up is low" (take-up is LA-only) |
| Map **gigabit-capable** coverage gaps at postcode level; count premises via UPRN | "Map **full-fibre** coverage at postcode level" |
| Overlay Census demographics to prioritise high-demand low-take-up areas | "Predict each household's likelihood to buy / churn" |
| Flag likely **overbuild zones** where gigabit availability is saturated | "Show where **a named competitor** built / their homes-passed" |
| "Modelled/predicted snapshot (Jul 2025), for prioritisation" | "Measured, current connectable coverage" |
| Use BDUK UPRN data for no-gigabit-plan / subsidy gaps (EW) | "Show **your** under-penetrated streets" (no per-operator layer) |

---

## The strategic conclusion (where the moat actually is)

The open-data market intelligence is a **door-opener, not the product** — Point Topic already sells that layer.
**Nobody fuses open-data market triage with the operator's OWN homes-passed data + live read-only telemetry.**
That fusion — open data says *which boroughs*, CF's footprint + telemetry says *which streets and which splices* —
is the genuinely novel, defensible, ~year-plus asset, and it's the natural up-sell from the telemetry pilot.

**Play:** lead with the borough conversion-gap teaser (real, in weeks), be explicit it's triage-level, and position
the street-level/operator-specific version as the fusion that requires CF's own data — which is exactly what the
pilot brings in. Honest, and it sells itself into the telemetry engagement.

*Caveat for the author: before publishing any London teaser, open the actual postcode file and confirm whether it
carries an FTTP column or only gigabit-capable (our inspection found gigabit-capable, no per-postcode FTTP), and
confirm the BDUK extract's reference date.*
</content>
