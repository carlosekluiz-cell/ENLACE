# Community Fibre — Intelligence Brief

*Prepared for the Enlace pilot meeting. Every material claim is sourced. Items we could not confirm are flagged **UNVERIFIED** — confirm them in the room, do not assert them.*

---

## 1. Who they are (and why the timing is right)

Community Fibre is **London's largest dedicated full-fibre (FTTP) altnet**, founded 2013, present in **31 of 32 boroughs**.

| Metric | Latest figure | Source |
|---|---|---|
| Premises passed | **~1.4m London homes** (+185k businesses nearby) | ISPreview, May 2026 |
| Customers connected | **~450,000** (Jan 2026), up ~23–26% YoY | Advanced Television, Jan 2026 |
| **Take-up / penetration** | **~32%** — sector-leading (altnet average is ~18%) | Advanced Television, Jan 2026 |
| Revenue (FY25) | **£113m (+48% YoY)** | Comms Business |
| Adjusted EBITDA (FY25) | **~£50m** (+~530%); **cash-positive** | TelcoTitans; ISPreview |
| Build status | **Resumed build May 2026**, targeting **2m+ premises** by 2028–29 | ISPreview, May 2026 |
| Speeds | Up to **5 Gbps** residential (launched Apr 2025) | ISPreview |
| Ownership | **Warburg Pincus, DTCP, Amber Infrastructure, RPMI Railpen**; >£1.3bn funding | Capacity; Computer Weekly |
| Reputation | **Trustpilot 4.7/5**, 75k+ reviews — best-rated major UK ISP | Trustpilot |

> **Correction for our older notes:** DigitalBridge is **not** an investor. Use Warburg Pincus / DTCP / Amber / Railpen.

**Why this matters for the pitch:** Community Fibre is the clearest altnet "winner" archetype — dense London footprint, sector-leading take-up, freshly profitable, and **resuming build**. They have run out of the easy growth ("pass more homes") and are now in the phase that telemetry serves directly: **operate what you've built efficiently, and don't lose the customers you have.**

---

## 2. The market context that *is* the pitch

The UK full-fibre land-grab is essentially over and the money has flipped from *building* to *operating*:

- **78–81% of UK premises now have FTTP**; 87% gigabit-capable (Ofcom Connected Nations 2025).
- The largest altnets posted **combined losses of £1.5bn in 2024**; financing costs averaged **121% of revenue**; new debt financing collapsed (Enders / AlixPartners / BDO).
- **Consolidation is now fact, not forecast:** Netomnia+Brsk merged (2024); **nexfibre is acquiring Netomnia (~£2bn, Feb 2026)** — the largest altnet deal ever; real exits (Lightspeed, F&W, G.Network).
- Viability needs **~40% take-up**; the sector average is **~18%**. ARPU (£25–35) sits **below the ~£45 breakeven** Point Topic estimates.
- The industry's own language has flipped: INCA — *"building value, not just fibre"*; BDO — *"build, build, build → sell, sell, sell"*; Intelligens — *"2026 will be make-or-break."*

**One-liner for the room:** *"The industry has run out of road on 'build more' and is being forced, by its own balance sheets, onto 'run what you've built, better.' That's the exact two levers we move: lower opex per connected premise, and lower churn through faster fault resolution."*

Community Fibre is unusually well-placed in this shakeout (profitable, ~32% take-up), so the frame is **"protect a premium reputation and a profitable book,"** not "fix a broken network."

---

## 3. Decoding "Mission Control"

**There is no public Community Fibre product, platform, or system called "Mission Control."** Targeted searches returned only generic industry usage (NOC-as-mission-control metaphors) and an unrelated N-able MSP product.

**Most plausible reading:** internal shorthand for their **network/service operations centre or an internal ops dashboard.** The closest *documented* real systems they run are:
- **Zinier** — field-service management (scheduling, dispatch, workforce) — they publicly modernised field ops with it.
- **Cognizant** — built them a new API platform.
- **A10 Networks** (CGNAT), **NetSapiens** (voice) — adjacent infra.

**How to handle it in the meeting:** Don't assume it's a product. Ask: *"When you say Mission Control — is that your NOC, a dashboard, a specific platform? Walk me through what an operator actually sees on it today."* Their answer tells you exactly where Enlace slots in (it's the telemetry/intelligence **layer that feeds** Mission Control, not a replacement for it).

---

## 4. Decoding "AV systems being rolled out through 2026"

This is the single most important strategic finding. The phrase is almost certainly a transcription of **"AI systems,"** and given CF's vendor, it points squarely at **Adtran**.

- CF has run **Adtran XGS-PON since 2018** (ONT: SDX 621i; OLTs in the SDX 6xxx family). This is confirmed, not a guess.
- In **Oct 2025 Adtran launched Mosaic One Clarity** — explicitly *"a new Mosaic One **module**"* (matches "Adtran are launching a module"), built on Adtran's **"REAL AI"** platform, delivering **predictive maintenance and proactive assurance**, *"already in several customer trials"* (matches "rolled out throughout 2026"). Early result cited: ACE Fiber reporting **up to 75% fewer trouble tickets/month.**
- Alternative reading: **"AV" → "ADVA"** (Adtran's optical-transport line, now "Adtran Networks") — phonetically clean but it's a transport product family, not "a module."

**Verdict:** treat **Adtran Mosaic One Clarity (REAL AI)** as the likely referent. **Confirm it in the room** — *"When you mention the AI systems rolling out in 2026 — is that Adtran's Mosaic One / Clarity?"*

### What this means for our positioning (critical)

**Do NOT pitch against Mosaic/Clarity head-on.** Adtran's own AI assurance is the incumbent on their kit. Our wedge is the gaps Mosaic structurally cannot fill:

| Mosaic One / Clarity | Enlace |
|---|---|
| Adtran-cloud SaaS; data + AI models live in Adtran's cloud | **Self-hosted; telemetry stays on CF's infrastructure** (data sovereignty) |
| Billed **per connected device / per subscriber** | **No per-endpoint licensing** |
| Deepest on Adtran kit; "multi-vendor" is new & cloud-bound | **Vendor-agnostic across 12+ OLT vendors** — one normalised view as their estate diversifies |
| Threshold/AI assurance in the vendor's framing | **Read-only, predictive analytics + fault localisation; complements, doesn't replace** |
| NETCONF/RESTCONF + Kafka, Adtran-native | **Ingests Adtran NETCONF/RESTCONF/CSV today** (the repo already has an SDX 6320 parser) |

**The line to use:** *"We're not here to replace Adtran's assurance — we sit beside it. We're the vendor-neutral, self-hosted layer that keeps your telemetry on your own infrastructure, costs nothing per device, and unifies whatever non-Adtran kit you add next."*

> Technical note: the SDX 6xxx is **NETCONF-first and does not support SNMP**. Our ingest path for them is NETCONF/RESTCONF or CSV/PM export (already built), not classic SNMP polling. Know this so we don't promise an SNMP integration that won't exist on their OLTs.

---

## 5. Who to talk to

| Role | Name | Notes |
|---|---|---|
| CEO | **Graeme Oxby** | Ex-Lebara CEO, ex-Virgin Mobile MD; public-facing |
| Chairman | **Olaf Swantee** | Ex-EE CEO |
| Operations Director | **Paul Lees** | Natural pilot sponsor — owns the ops pain |
| CTO | **Dale Kirkwood** *or* **Sven Huster** — **UNVERIFIED / conflicting** | Confirm on LinkedIn before any named outreach |
| CCO | Peter Rampling | Ex-O2 UK CMO |

**Entry points for a telemetry pilot:** the **technology org (CTO)** and **Operations Director Paul Lees**. Their Zinier/Cognizant/A10 spend proves they **buy ops tooling** — the budget pattern exists.

---

## 6. Pain signals to lean on (gently)

Sentiment is strongly positive (4.7 Trustpilot), so lead with *protection*, not *rescue*. Recurring negative review themes — useful, specific hooks:
- **Outages / drop-outs where engineers "can't find the fault"** → our per-ONT fault localisation.
- **Missed / repeat engineer visits** → "find it once, send the right team once."
- **Dropped callbacks / follow-ups** → lost-confidence churn risk.

**The VodafoneThree wholesale deal raises the stakes:** as of 2025 CF wholesales its network to VodafoneThree (up to 1.3m London homes, products to 2.5 Gbps). A wholesale partner's customers now ride CF's fibre, so undiagnosed PON faults carry **contractual SLA and reputational** risk, not just consumer churn. This is a strong, current reason proactive fault detection matters to them *now*.

---

## 7. Competitive honesty (so we're not caught out)

"Nothing like it exists" is **false and a credibility risk** in front of a technical buyer. The honest landscape:

- **Vendor NMS (Adtran Mosaic, Nokia Altiplano, Calix Cloud, Huawei iMaster):** predictive claims now exist, but per-device-licensed and tied to their own hardware.
- **OTDR/RFTS hardware (EXFO, VIAVI):** CAPEX-heavy — racked test units, optical switches, often a reflector per subscriber drop.
- **General NMS (SolarWinds, Zabbix, LibreNMS, Grafana+Elastic):** SNMP-poll, reactive, no PON optical model; the heavy footprint is Elasticsearch/JVM/SQL Server (note: the Zabbix *server* is C, not Java — don't misstate that).
- **Carrier OSS (Netcracker, Blue Planet, Ericsson):** multi-million, multi-year integrations — different buyer.
- **The two genuine near-neighbours:** **NetSense NMS** (read-only, software-only, multi-vendor — *but no predictive ML*) and **PBN Global** (multi-vendor + ML — *but not read-only; it also provisions, and it's heavier*).

**Our defensible wedge (use this exact framing):** *"The only lightweight, read-only, vendor-agnostic software agent that applies predictive analytics at the PON optical layer — without the per-device lock-in of vendor NMS, the CAPEX of OTDR hardware, or the integration weight of carrier OSS."* If pushed, name NetSense and PBN and explain we beat them on, respectively, **prediction** and **(read-only + lightweight)**.
</content>
</invoke>
