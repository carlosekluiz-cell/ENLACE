# Enlace × Community Fibre
### Pilot proposal — proactive PON telemetry intelligence
*Pulso Technologies Limited · enlace.network · company no. 17151141*

---

## Why now

The UK full-fibre build-out is essentially done — 78–81% FTTP coverage, the capital that funded a decade
of digging has dried up, and the altnet sector lost £1.5bn in 2024. The industry has pivoted from *passing
homes* to *operating them profitably*. Community Fibre is one of the few operators already across that line —
profitable, ~32% take-up (nearly double the sector average), resuming build from strength, and now wholesaling
to VodafoneThree. The opportunity is to **protect a premium reputation and a profitable book.** *(Full market
context: `02-uk-fttp-market-dossier.md`.)*

## The problem we solve

Most NOCs are reactive: the customer calls first, and a chunk of those calls end in a truck roll with no fault
found. The data to prevent this already exists — your OLTs produce per-ONT optical telemetry every few minutes —
but almost none of it is used proactively. Splices absorb moisture for weeks before a customer notices; a single
rogue ONT can take down a whole PON tree of 32–128 subscribers; SFPs degrade predictably before they fail.

## What Enlace does

Enlace reads the telemetry your OLTs already produce and **closes the loop**: detect → analyse → locate →
ticket → notify → confirm. It runs **17 detection modules** — fibre-cut classification, fault location,
rogue-ONT/reflectance, churn prediction, ghost customers, splitter capacity, weather-correlated degradation,
SFP health, optical budget — and turns each finding into a scored, located, ticket-ready action. For slow
degradations it opens a **planned-maintenance ticket before the customer is ever affected.** *(Detail:
`04-beyond-monitoring-vision.md`.)*

## Why Enlace, specifically

A **lightweight, read-only, vendor-agnostic software agent that applies predictive analytics at the PON optical
layer** — without the per-device lock-in of vendor NMS, the CAPEX of OTDR hardware, or the integration weight of
carrier OSS. A single ~8 MB Rust binary, ~50 MB RAM per 1,000 ONTs, self-hosted so telemetry stays on your
infrastructure. It **complements** Adtran's Mosaic/Clarity rather than competing with it — covering the
cross-vendor, no-per-device-licence, data-sovereignty gaps a single-vendor cloud leaves. *(Detail:
`05-technical-differentiation.md`.)*

## The value

Operators running proactive assurance report **truck rolls down 30–50%**, **MTTR down ~40%**, **alarm noise
down 60–70%**. We won't quote those as your numbers — the pilot puts *your* truck-roll cost, churn, ARPU and
alarm volume against those ranges, conservatively. *(Inputs gathered via `03-discovery-questionnaire.md`.)*

## The pilot — free, three low-risk steps

1. **Offline audit:** you export ~1 month of ONT telemetry from one problem area; within a day we return what
   Enlace found. Nothing touches your network.
2. **Review together** against your own operational numbers.
3. **Optional live read-only deployment** into your existing tooling, at your pace.

Free for launch partners, preferential pricing at launch. *(Full plan + data spec: `06-pilot-plan-and-data-request.md`.)*

## Read-only by design

Read-only methods only (SNMP GET, CLI show/display, NETCONF get, passive RADIUS) — never set/write/reboot.
Credentials stay local; in Step 1 nothing leaves your network. Your engineers can sign it off without seeing
source.

## Where we came from

> Enlace began in Brazil, one of the world's most fragmented broadband markets: more than 20,000 regional ISPs
> serve the majority of the country's ~54 million fixed-broadband lines, yet most run their networks on
> spreadsheets with little real analytics. We started by building market intelligence from open data, which
> pulled us into propagation modelling — and the models kept hitting the same wall: there was no reliable live
> data from the networks themselves. The real gap wasn't intelligence or prediction — it was telemetry. So we
> built the engine that closes it, turning networks that ran blind into networks operators can actually see.

The same open-data method ports directly to the UK (Ofcom, ONS, OS, BDUK).

## The ask

A 15-minute call, the discovery questionnaire, and one month of telemetry from an area that's been giving you
grief. **hello@enlace.network.**

---
*Pulso Technologies Limited, registered in England & Wales, company no. 17151141, 128 City Road, London EC1V 2NX.*
</content>
