# Differentiation Appendix — Citations & Defensible Numbers

*Technical backup for the meeting. Hand-pick from these; every figure is attributed. Convention: `[HARD]` = regulator / operator financials / peer-reviewed / standards body. `[EST]` = vendor or analyst estimate without disclosed methodology — frame as "operators report…".*

---

## A. Rust architecture — claims with evidence

| Claim | Evidence | Source |
|---|---|---|
| GC runtimes inject periodic latency spikes; Rust has none | Discord Go→Rust: spikes every ~2 min from GC cache scan; Rust → avg µs, worst-case ms, no spikes, beat hand-tuned Go on latency+CPU+memory | discord.com/blog/why-discord-is-switching-from-go-to-rust |
| Stop-the-world GC is a known tail-latency hazard | ZGC/Shenandoah exist specifically to fight p99/p999 breaches under high allocation | azul.com; morling.dev (ZGC tail latency) |
| Rust services run in tens of MB vs hundreds of MB–GB for JVM | Spring Boot ~256–280 MB vs Axum/Tokio <5–12 MB; Discord ~10×; AWS/Tenable 95% mem / 75% CPU cut | Discord; theregister.com (AWS re:Invent 2021) |
| Rust async sustains millions of events/sec | Datadog Vector: millions ev/s, largest user >500 TB/day; Cloudflare Pingora >1T req/day at ~⅓ CPU/mem | github.com/vectordotdev/vector; blog.cloudflare.com/pingora |
| Memory safety removes the largest bug class | ~70% of CVEs at Microsoft & Chromium; 67% of 2021 zero-days; CISA/NSA name Rust | msrc.microsoft.com; cisa.gov |
| Tiny, fast-start, minimal-attack-surface binary | AWS Firecracker: ~50k LOC Rust vs ~1.4M LOC C in QEMU; <125 ms boot; <5 MiB overhead | aws.amazon.com/blogs/opensource/firecracker |
| GC-free code is more energy/cost-efficient (edge TCO) | Pereira et al. (Sci. Comp. Prog. 2021): Rust 2nd most efficient of 27 langs (~2× Java); AWS advocates Rust for sustainability | haslab.github.io/SAFER/scp21.pdf; rcrwireless.com |

**The arithmetic for "billions/day"** (always show it): 25 metrics/ONT × ONTs × polls/day.
- 1,000 ONTs @ 60s = **36M points/day** (one tiny agent).
- 5M ONTs @ 60s = **180B points/day** ≈ **2.1M points/sec** across ~100 agents.

---

## B. Competitive landscape — one table

| Tier | Examples | Deploy | Locked? | Predictive? | vs Enlace |
|---|---|---|---|---|---|
| Vendor NMS/assurance | Adtran **Mosaic/Clarity**, Nokia Altiplano, Calix Cloud, Huawei iMaster | Cloud + on-prem; SaaS | Tied to own OLT/ONT; per-device licensed | Yes (newer AI claims) | We're agnostic, read-only, self-hosted, no per-device fee |
| Hardware fibre test | EXFO (RTU/Nova), VIAVI ONMSi | **CAPEX hardware** — RTUs, optical switches, per-drop reflectors | Physical-layer agnostic, proprietary HW | Reactive; ML add-on | We're software-only, zero added optics |
| General NMS | SolarWinds, Zabbix, LibreNMS, PRTG, Grafana+Elastic | Software (often JVM/SQL-heavy) | Agnostic | Reactive thresholds; no PON model | We have a purpose-built PON optical model + prediction |
| Carrier OSS | Netcracker, Blue Planet, Ericsson | Carrier-grade integrations | Agnostic | Yes | Multi-year/multi-£m; we're a drop-in agent |
| **Near neighbours** | **NetSense NMS** | Software, read-only, agnostic | No | **No ML** ← gap | We add prediction |
| | **PBN Global** | Heavier platform | Provisions too | Yes (ML) | We're read-only + lightweight |

**No single competitor sits at the intersection: lightweight + read-only + vendor-agnostic + predictive at the PON optical layer.** That intersection is the wedge — *not* "nothing exists."

---

## C. Defensible economics — numbers we can quote

| Metric | Conservative figure | Basis |
|---|---|---|
| Cost per truck roll (fully loaded) | **£75–150 / ~$200** | AEX methodology; Bain "$100 to roll vs $5 to call" `[EST+HARD]` |
| UK regulated engineer-visit charge | **£99–295** | Openreach Time Related Charges `[HARD-ish]` (inter-operator price, not internal cost) |
| Avoidable / no-fault-found dispatches | **~20%** (range 20–30%) | TechSee; Bain `[EST+HARD]` |
| UK broadband churn/switching | **~10%/yr historically, ~18% in 2024** (post One-Touch-Switch) | Ofcom / Which? `[HARD]` |
| UK broadband ARPU | **~£30/mo (~£360/yr)** mid-market | Openreach FTTP £16.86 wholesale; BT Consumer ~£42; altnet £25–35 `[HARD]` |
| Customer acquisition cost | **~£240/subscriber** | CityFibre connection bonus; Enders `[HARD]` |
| Customer lifetime | **~5 years** | Simon-Kucher 5.5y `[EST/HARD]` |
| Customers hit by a fault/yr | **~85%** | Which? Jan 2025 `[HARD]` |
| Truck-roll reduction from proactive assurance | **30–50%** (conservative end of 34–85%) | Calix operators: CTC −34%, Jade −40%, IHR up to −85% `[HARD, vendor-published]` |
| MTTR reduction from closed-loop | **~40%** | China Mobile TM Forum PoC `[HARD]` |
| Alarm-noise reduction from correlation | **60–70%** | Frontiers (peer-reviewed) >62%; Vodafone >70% `[HARD]` |
| Cost per NOC/support ticket | **~$15.56 avg** | MetricNet `[HARD]` |
| #1 physical fault cause | **Connector contamination** — 80% of operators affected | NTT-AT via EXFO `[HARD]` |
| Rogue-ONT blast radius | **whole PON tree: 32–128 subscribers** | ISE Magazine `[HARD]` |

**Genuine data gaps (acknowledge, don't fabricate):** no published "truck rolls per 1,000 subs/yr" benchmark; no methodology-backed UK *internal* cost-per-truck-roll; most telecom truck-roll-reduction figures are vendor-published with selection bias. → This is precisely what the discovery questionnaire (doc 04) asks CF to supply, turning generic ranges into *their* numbers.

---

## D. The 17 detection modules (what's actually built)

For the technical buyer who asks "what does it actually detect?" — all implemented and unit-tested (157 tests, 10/10 on the blind 400-ONT / 802k-row test):

**Fault:** mass-offline detector (fibre-cut vs power-outage classification), fault locator (distance-to-break), PON topology inference.
**Diagnostics & prediction:** per-ONT signal grading, ethernet-negotiation/restart/temperature/voltage/bias-current checks, 30-day linear-regression degradation forecast with R² confidence.
**Advanced:** reflectance "rogue ONT" identifier, churn predictor (telemetry→90-day churn %), fault-impact scorer (time-of-day weighted), ghost-customer detector, splitter-capacity forecaster, weather-correlation (condensation/rain-ingress/thermal), flapping detector, SFP health, optical-budget analyser.
**Output:** auto-ticket generator (P1–P4, team routing, ROI per ticket), Elasticsearch bulk, webhook (Slack/PagerDuty/generic).

**Caveat for honesty:** the 10/10 blind test was on **synthetic** data; CF calibration (98% design match) was on **network-design/estate-discovery**, not telemetry-audit accuracy. The pilot is what produces real-data validation — say that plainly.
</content>
