# How Enlace Is Different
### Technical differentiation for Community Fibre's engineers
*Enlace · Pulso Technologies Limited*

*Written for people who will (rightly) push back. Where a claim has a caveat, we state it.*

---

## The one-line claim

> Enlace is a **lightweight, read-only, vendor-agnostic software agent that applies predictive analytics
> at the PON optical layer** — without the per-device lock-in of vendor NMS, the CAPEX of OTDR hardware,
> or the integration weight of carrier OSS.

We don't claim "nothing like it exists." Plenty of good tools exist. None sits at that *intersection.*

---

## Where Enlace sits in the landscape

| Category | Examples | The trade-off |
|---|---|---|
| Vendor NMS / assurance | Adtran Mosaic/Clarity, Nokia Altiplano, Calix Cloud | Strong, but **per-device licensed** and deepest on the vendor's own hardware; data lives in the vendor cloud |
| Hardware fibre test | EXFO, VIAVI ONMSi | Accurate, but **CAPEX** — racked test units, optical switches, often a reflector per drop |
| General NMS | SolarWinds, Zabbix, LibreNMS, Grafana+Elastic | Agnostic, but SNMP-poll, **reactive thresholds, no PON optical model**; heavy footprint |
| Carrier OSS | Netcracker, Blue Planet, Ericsson | Powerful, but **multi-year, multi-£m integrations** |
| Near-neighbours | NetSense, PBN Global | NetSense is read-only/agnostic **but has no predictive ML**; PBN has ML **but isn't read-only and is heavier** |

Enlace's defensible position is the combination: **lightweight + read-only + vendor-agnostic + predictive
at the optical layer**, in a single small binary.

---

## Built beside your existing kit, not against it

Community Fibre runs **Adtran XGS-PON**, and Adtran's own AI assurance (Mosaic One / Clarity) is rolling out.
**Enlace is not a replacement for it.** We're the layer that fills the gaps a single-vendor cloud SaaS
structurally leaves:

| Vendor cloud assurance | Enlace |
|---|---|
| Telemetry + AI models live in the vendor's cloud | **Self-hosted — your telemetry stays on your infrastructure** |
| Billed per connected device / subscriber | **No per-endpoint licensing** |
| Deepest on one vendor's hardware | **Vendor-agnostic across 12+ OLT vendors** as your estate diversifies |

We ingest Adtran telemetry via NETCONF / RESTCONF or CSV/PM export today (the SDX 6320 parser is built).
*(Note: the SDX OLT family is NETCONF-first and does not use SNMP — our integration accounts for that.)*

---

## Why Rust — and the honest limits

Enlace is a single **~8 MB static binary**, **~50 MB RAM per 1,000 ONTs**, **<2% of one core**, async I/O,
with a local buffer for offline resilience.

1. **No garbage collection → predictable latency.** Telemetry ingest creates and discards millions of small
   objects per second — the pattern that triggers GC pauses in JVM/Go runtimes. Rust frees memory
   deterministically, so there are no stop-the-world pauses while a fault goes undetected. *(Caveat: modern
   collectors like ZGC achieve sub-ms pauses — our point is structural predictability **and** a tiny footprint,
   not "GC is always slow.")*
2. **Tens of MB, not GB → runs at the edge.** It fits inside a small VM or beside the OLT in your NOC; no
   monitoring cluster to provision. *(Caveat: JVM idle footprints depend partly on configuration; the
   order-of-magnitude gap is real, the exact numbers are workload-specific.)*
3. **Scale, shown honestly.** At ~25 metrics/ONT, one small agent on 1,000 ONTs at a 60-second cadence is
   **~36 million points/day**. A national-scale fleet (5m ONTs) is **~180 billion points/day** — reached by
   **many small agents (~50k ONTs each), not one process.** Rust pipelines at this class are proven at
   hyperscale (Cloudflare's Rust proxy serves >1 trillion requests/day; Datadog's Rust pipeline moves
   >500 TB/day).
4. **Memory safety → fewer bugs, smaller attack surface.** ~70% of severe CVEs across Microsoft and Chromium
   are memory-safety defects; Rust eliminates that class at compile time. For an agent running **read-only**
   inside your production network, parsing telemetry from a dozen vendor formats, that matters. *(Caveat:
   memory-safe ≠ bug-free — logic errors still happen.)*
5. **Operational simplicity.** One binary, zero runtime dependencies, sub-100ms start. A security-conscious
   team can reason about what it does.

*Trade-off we'll own: Rust has a steeper learning curve and a smaller talent pool than Java/Python — a
team-cost question, not a runtime one.*

---

## What's actually built (17 detection modules, 157 tests)

**Fault:** mass-offline detection (fibre-cut vs power-outage classification), fault location
(distance-to-break), PON topology inference.
**Diagnostics & prediction:** per-ONT signal grading; ethernet-negotiation, restart, temperature, voltage and
bias-current checks; 30-day degradation forecast with confidence.
**Advanced:** rogue-ONT / reflectance identification, churn prediction, time-of-day fault-impact scoring,
ghost-customer detection, splitter-capacity forecasting, weather-correlation (condensation / rain ingress /
thermal), flapping detection, SFP health, optical-budget analysis.
**Output:** auto-ticket generation (P1–P4, team routing, ROI per ticket), Elasticsearch, webhooks (Slack /
PagerDuty / generic).

**Honest note on validation:** detection logic passed a 10/10 blind test on a **synthetic** 400-ONT dataset,
and our design rules matched Community Fibre reference schematics at ~98% on **network-design** accuracy.
Neither is live-telemetry validation on your network — **that's exactly what the pilot produces.**
</content>
