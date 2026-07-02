# Enlace — Positioning, Story & Technical Differentiation

*The narrative spine for the Community Fibre meeting. Three parts: (1) why this is more than monitoring, (2) why the Rust architecture is genuinely different, (3) the origin story. All figures are sourced; honest caveats are kept in so we survive technical scrutiny.*

---

## Part 1 — This is not monitoring. It's closed-loop intelligence.

Monitoring tells you something **has broken** and pages a human. That's where almost the entire market stops — alarms, dashboards, thresholds. Enlace is built to close the loop:

> **Observe → Analyse → Locate → Decide → Act → Confirm**

This is the industry's own language for the next step: **closed-loop assurance** (TM Forum *Autonomous Networks*, ETSI *Zero-touch* / ZSM, intent-based assurance). On TM Forum's autonomy curve (L0 manual → L5 full), classic monitoring is **L1 (assisted)**. Enlace targets **L3–L4 for the PON/access domain** — predictive, conditional, closed-loop, human-in-the-loop only for exceptions. We should use that vocabulary; it's exactly how Adtran, Nokia and Ericsson frame their own roadmaps, so it positions us as peers, not outsiders.

### The two loops, concretely

**Loop A — acute fault (seconds to minutes):**
```
Telemetry detects LOS / mass-offline on a PON port
  → classify: trunk cut (all ONTs down) vs branch vs single drop
  → locate: distance-to-break + PON port + splitter  (or ONT = a known service address)
  → open a tiered ticket (P1 outage straight away) in the NOC's tooling
  → notify the field/NOC team on WhatsApp with a map pin to the fault
  → when telemetry confirms signal restored, auto-resolve the ticket
```

**Loop B — slow degradation (days to weeks) — the higher-value one:**
```
Rx power on 3 ONTs trends down 0.04 dB/day at ~800m on port 0/1/4
  → weather/optical-budget modules flag "moisture ingress in a splice enclosure"
  → open a LOW-priority planned-maintenance ticket BEFORE any customer notices
  → schedule a single planned visit; fix it once; zero customer impact, zero churn
```

Loop B is the story that lands: **the customer never calls, because the fault was fixed before it reached them.**

### Is the loop real, or roadmap? (be precise)

We researched the feasibility of every component. Promise only what's proven:

**Safe to promise in a pilot (production-proven patterns):**
- Automated incident creation into ticketing/on-call — Slack and PagerDuty (Events-format) natively, Opsgenie / Jira SM / ServiceNow via the generic webhook — with **P1–P4 severity tiering** and SLA-based routing.
- **One-tap WhatsApp dispatch** from the ops app: the supervisor shares a ready-made message — ticket ID, device, fault type, severity and a map link — straight into the technician's WhatsApp chat. *(WhatsApp Business API push — pre-approved Utility templates with a location header — is a roadmap integration.)*
- **Map-pin dispatch for the per-ONT case** — a fault narrowed to a specific ONT *is* a known subscriber address; no OTDR required.
- **Proactive planned-maintenance ticketing** for slow Rx degradation (Loop B).
- **Auto-resolution** when telemetry confirms recovery.

**Position as Phase 2 / roadmap (state the dependency, don't overpromise):**
- **OTDR-distance → exact street pin.** Deployed at carrier scale (Windstream / VIAVI / 3-GIS) but needs an RFTS/OTDR feed **and** accurate as-built GIS route geometry + slack data — optical distance mismatches geographic distance by ~15–20%. Without good OSP GIS, we deliver a fibre-metre distance + probable map segment, not a precise pin.
- **Quantified "weeks-to-failure" forecasting.** Credible *today* as a trend-and-threshold alert ("Rx declining, projected below LOS threshold in ~N days"); a calibrated time-to-failure model is a maturation item.

**Two honesty flags for the room:**
1. WhatsApp Utility templates need Meta approval (minutes–24h) and must be designed up front.
2. "Higher→lower severity routing" as casually phrased is non-standard; industry escalation is **time/acknowledgement-based up an ordered on-call chain**. We can downgrade severity by re-firing a lower event, but describe the loop in the standard "escalate-up-on-no-ack" terms to stay credible.

---

## Part 2 — Why Rust is a real advantage, not a buzzword

The competitive norm is heavyweight Java/JVM NMS platforms, Python pipelines, and hardware probes installed in the network. Enlace is a single **8.7 MB static binary** (musl, stripped), **under 50 MB RAM per 1,000 ONTs** (26 MB measured on a 1,000-ONT audit, which completes in 0.12 s), async I/O (Tokio), local SQLite buffer for offline resilience. Here's the defensible case — and where to tread carefully, because CF's engineers will push back.

### Claim 1 — No garbage collection → predictable tail latency

Telemetry ingest is a high-churn workload (millions of small objects created and discarded per second) — exactly what punishes GC runtimes, because the collector must periodically pause to walk live memory.

- **Discord's flagship example:** their Go service spiked in latency/CPU **every ~2 minutes** because Go's GC scanned a huge cache on a forced cycle. Rewritten in Rust, **average latency fell to microseconds, worst-case to milliseconds**, with no spikes — beating a hand-tuned Go version on latency, CPU *and* memory. ([discord.com/blog](https://discord.com/blog/why-discord-is-switching-from-go-to-rust))
- This is structural: the entire modern low-pause-GC effort (ZGC, Shenandoah) exists to fight stop-the-world tail latency.

For an engine whose job is to catch a transient optical fault *the moment it happens*, predictable tail latency **is the product.**

### Claim 2 — Tens of MB, not GB → run it at the edge, beside the OLT

- Published comparisons: idle Spring Boot ~256–280 MB vs an Axum/Tokio service **<5–12 MB**; Discord saw **~10×** memory reduction; AWS (Tenable) cited **95% memory / 75% CPU** reduction rewriting a component in Rust.
- Our ~50 MB / 1,000-ONT figure is consistent with this class. **Consequence:** the agent runs inside a small VM or beside the OLT in the NOC — no provisioned monitoring cluster.

### Claim 3 — "Billions of points per day" — shown, not asserted

Always show the arithmetic. Take ~25 metrics/ONT (Rx/Tx power, temperature, bias current, voltage, FEC/CRC counters, traffic):

- **1 agent, 1,000 ONTs, 60s interval** = 1,000 × 25 × 1,440 = **36 million points/day** — on the ~50 MB / <2%-core footprint.
- **National fleet, 5,000,000 ONTs** = **180 billion points/day**, sharded across ~100 lightweight agents (~50k ONTs each) — **≈2.1 million points/second** aggregate.
- Is 2M points/s realistic for Rust? Yes, with margin: Datadog's Rust **Vector** sustains millions of events/sec (largest user >500 TB/day); Cloudflare's Rust **Pingora** serves **>1 trillion requests/day** at ~⅓ the CPU/memory of its predecessor.

**Honest framing:** billions/day is a **fleet-aggregate** reached by many small agents — *not* one process on one core. Say it that way every time.

### Claim 4 — Memory safety → fewer bugs, smaller attack surface (it runs read-only inside their network)

- ~**70% of CVEs** at Microsoft and Google Chromium are memory-safety defects; **67% of 2021 zero-days** were too (Project Zero). CISA/NSA recommend memory-safe languages and name Rust.
- An agent parsing untrusted telemetry from a dozen vendor formats, sitting **read-only** in a third party's production network, is exactly where eliminating that bug class matters. Plus: single binary, zero runtime deps, sub-100ms startup — a security-conscious operator can actually reason about it.

### Honest caveats (say these *before* an engineer does — it builds trust)

- **Modern GCs are good.** A tuned ZGC can hit sub-ms pauses. Our claim is *structural predictability + footprint*, not "GC always means giant pauses" — and ZGC buys low pauses with CPU/memory headroom, which is the budget we're keeping tiny at the edge.
- **Headline wins are rewrites,** partly second-system hindsight, not pure language magic. Attribute gains to "GC-free + low overhead + clean design," not "the compiler."
- **JVM memory numbers are partly config** (default heap reservation). The order-of-magnitude gap is real; the exact "280 vs 12 MB" is benchmark-specific.
- **Memory-safe ≠ bug-free.** Logic errors, panics, `unsafe`/FFI bugs still happen. It removes the worst ~70% class, not 100% of risk.
- **Rust's cost is upstream:** steeper learning curve, smaller talent pool. That's a team-cost trade-off, not a runtime one — worth conceding to a technical buyer.

*(Full claims-with-citations table lives in `03-differentiation-appendix.md`.)*

---

## Part 3 — The origin story (≈150 words, accurate, usable verbatim)

> Enlace began in Brazil, one of the world's most fragmented broadband markets: more than 20,000 regional ISPs — over 18,800 of them licensed with Anatel — now serve the majority of the country's ~54 million fixed-broadband lines, having overtaken the big incumbents. Yet most run their networks on spreadsheets and disconnected systems, with little real analytics. We started by building market intelligence from open data — Anatel's telecom datasets, IBGE demographics, public registries — to map where networks were, and where they weren't. That work pulled us into optical and RF propagation modelling, predicting coverage and performance. But the models kept hitting the same wall: there was no reliable live data from the networks themselves. The real gap wasn't intelligence or prediction — it was telemetry. So we built the engine that closes it, turning networks that ran blind into networks operators can actually see.

**Notes on accuracy:**
- Use **"more than 20,000 regional ISPs (~18,800 Anatel-licensed)"** — **not** the old "13,000" figure, which is outdated/low. Brazil's regional ISPs now hold ~60% of fixed broadband (Ookla), having overtaken Claro/Vivo/Oi.
- **The UK parallel writes itself:** the same open-data method is replicable here — **Ofcom Connected Nations + ONS + Companies House** are the UK analogues of Anatel/IBGE/PGFN. (Today, though, lead with telemetry + market intelligence; keep the UK propagation model as future, per direction.)
- Don't claim we invented the category — Kentik and observability incumbents exist. The honest claim is that this gap is **acute and unserved for the under-tooled operator segment**, which the Brazil data supports.
</content>
