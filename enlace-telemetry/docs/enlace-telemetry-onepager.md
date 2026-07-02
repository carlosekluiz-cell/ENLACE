# Enlace — see your fibre network before your customers do

**A read-only telemetry agent for PON operators.** By Pulso Technologies Limited (UK).
enlace.network · hello@enlace.network

---

## The problem

Your OLTs already know when a customer's signal is dying, when a PON branch has gone
dark, and when a connection has quietly stopped carrying traffic. That data sits siloed
by vendor, unread. So the NOC stays **reactive**: the customer calls first, the ticket
opens, and an engineer rolls a van — often to find no fault at the premises at all.

Reactive operations cost you twice: in truck rolls (£80–150 each) and in the churn of
customers who lost service before you knew anything was wrong.

## What Enlace does

Enlace is a single, lightweight agent that reads telemetry from the equipment you already
run, normalises it across vendors, and runs continuous detection at the edge:

| Module | What it catches |
|---|---|
| **Fault detection** | Mass-offline events, classified as *fibre cut* vs *power outage* using dying-gasp signals |
| **Signal prediction** | Per-ONT optical degradation, with an estimated time-to-failure |
| **Churn scoring** | Customers on a downward signal/usage trend, before they leave |
| **Ghost detection** | Connections that are "up" but carry no real traffic |
| **Capacity planning** | PON splitter ports trending toward saturation |
| **Live diagnostics** | A colour-coded health view your help desk can read without a network engineer |

Findings come out as prioritised **tickets** and an executive **health score**, ready to
drop into your existing workflow.

## Built to earn trust

- **Read-only.** Enlace never sends a write command to your equipment.
- **Your credentials never leave your network.** Telemetry sent outward is structured per-ONT findings
  and optical metrics — never traffic contents or subscriber PII — and self-hosted output keeps everything
  on your infrastructure.
- **Verifiable.** We'll walk your engineers through exactly what the agent does — read-only, open
  standards (SNMP/NETCONF) — so they can sign it off. No black box behaviour, no lock-in.
- **Vendor-agnostic.** Adtran, Huawei, Nokia, ZTE, FiberHome, Datacom and more — one agent, one data model, no per-vendor tooling.

## Where it stands

- Validated against a benchmark of real-world incident patterns — fibre cuts, splice and
  SFP pre-failure, reflectance, flapping, weather-correlated degradation, capacity exhaustion
  and churn — all detected end-to-end.
- 500+ automated tests (528 passing); audits a 52-ONT week of telemetry in 10 ms and
  1,000 ONTs in ~0.12 s, end to end.
- Designed and tested for UK fibre operators.

## The pilot — free for launch partners

We're inviting a small number of UK operators to validate Enlace on their own networks.

1. **Send us a CSV.** Export an ONT/optical report from one OLT (or upload it at
   enlace.network/upload). No install, nothing touches your network.
2. **We show you what's in it.** Within the hour: the faults, at-risk customers, ghosts and
   capacity hot-spots Enlace found in that window.
3. **Go live if it's useful.** Run the agent against a live OLT for the pilot period —
   **free**, with preferential pricing reserved for launch partners when we move to paid.

> **The ask:** one CSV export, or a 15-minute call. That's it.

---

*Enlace is a product of Pulso Technologies Limited — registered in England & Wales, company
no. 17151141. hello@enlace.network · enlace.network*
