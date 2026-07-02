# Proposal claims inventory — 2026-07-02

Every distinct claim in the customer-facing proposal artifacts (10-page PDF proposal,
deliverables 00–07, public site), inventoried for the proposal-vs-deliverable gap lock-in.
One row per claim: what was promised, where, and what proves it shippable.
Assessment of current status happens in the gap lock-in pass, not here.

Perfect. I now have all the source materials. Let me build the comprehensive claim inventory.

| ID | Claim | Source | Type | What would prove it deliverable |
|---|---|---|---|---|
| P1 | Reads telemetry from OLTs in a read-only manner (SNMP GET, CLI show/display, NETCONF get, RouterOS read, passive RADIUS) | enlace-pilot-proposal.html; 06-pilot-plan-and-data-request.md; page.tsx | scope-limit | Code review of all query operations; no SET/WRITE/CONFIGURE/REBOOT commands in agent codebase |
| P2 | Never sends a write command to your equipment | enlace-pilot-proposal.html | scope-limit | Audit of agent binary; engineers can verify via code walkthrough |
| P3 | Credentials stay local and never leave the network | enlace-pilot-proposal.html; 06-pilot-plan-and-data-request.md | scope-limit | Network traffic analysis; credentials remain in /etc/enlace/ |
| P4 | Only aggregated findings leave the network, never raw customer data | enlace-pilot-proposal.html; page.tsx | scope-limit | Network capture showing only structured JSON findings transmitted |
| P5 | Single ~6-8 MB binary (~6.3 MB reported) | enlace-pilot-proposal.html; page.tsx; 05-technical-differentiation.md | metric | Binary distribution shows exactly 6.3 MB or reported range |
| P6 | Runs at <1% CPU usage | enlace-pilot-proposal.html; page.tsx | metric | System monitoring during live deployment shows CPU <1% |
| P7 | Uses ~50 MB RAM per 1,000 ONTs | 05-technical-differentiation.md | metric | Memory profiling under 1,000 ONT load |
| P8 | Polling configurable as fast as 60-second intervals | enlace-pilot-proposal.html; page.tsx | capability | Agent runs successfully at 60s interval; terminal output shows "60s Poll interval" |
| P9 | Collects over 7 protocols: SNMP v2c/v3, SSH CLI, NETCONF, gRPC streaming, RouterOS API, RADIUS, TR-069/GenieACS | enlace-pilot-proposal.html | capability | Code shows parsers for all 7 protocols; successful polling from test equipment |
| P10 | Normalises 12+ OLT vendors: Adtran SDX, Huawei, Nokia, ZTE, FiberHome, Datacom, Intelbras, Parks, BDCOM, VSOL, CDATA, Ubiquiti + generic SNMP | enlace-pilot-proposal.html; page.tsx | capability | Vendor list matches; each vendor has a parser module; test output shows auto-detection working |
| P11 | Per-ONT normalization includes: serial, PON port, Rx/Tx optical power, status, distance, uptime, last-down cause, Ethernet link speed, plus temperature, voltage, laser bias where available | enlace-pilot-proposal.html | capability | Example audit output (examples/page.tsx) shows all fields populated; dashboard displays all metrics |
| P12 | Detects fibre cuts (mass dropouts on PON branch with no dying gasp signature) | enlace-pilot-proposal.html; features/page.tsx; examples/page.tsx | capability | Example report shows "Fibre cut" finding with affected ONT list |
| P13 | Classifies power vs fibre (dying-gasp signatures distinguish power outage from physical break) | enlace-pilot-proposal.html | capability | Example output shows "Mixed power / fibre area event" finding |
| P14 | Identifies reflectance culprit ONT (return-loss anomaly that knocks neighbours offline) | enlace-pilot-proposal.html | capability | Detection module exists; confidence score 0.3–0.9 as suspect recurs |
| P15 | Detects signal degradation with time-to-failure forecast | enlace-pilot-proposal.html; features/page.tsx | capability | Linear regression on Rx history produces days-to-failure; example shows "-0.3 dBm/week → failure in ~23 days" |
| P16 | Classifies optical budget loss and attributes to probable cause (connector, splice, macro-bend, splitter over-loss, insufficient power) | enlace-pilot-proposal.html | capability | Optical budget table shows margin thresholds and cause attribution |
| P17 | Detects SFP ageing via port-wide synchronized decline (all ONTs on port drifting together) | enlace-pilot-proposal.html | capability | Detection identifies per-port Rx trend, weeks-to-failure, outlier-vs-siblings flag |
| P18 | Detects weather faults: nighttime condensation, periodic rain ingress, thermal expansion (no weather station needed) | enlace-pilot-proposal.html | capability | Requires ≥3 ONTs within 100m on a port; output pattern, affected ONTs, distance range, correlation strength |
| P19 | Detects flapping ONTs with cascade risk scoring | enlace-pilot-proposal.html | capability | Severity tiers: Sporadic 2–5/h, Moderate 5–15/h, Severe >15/h; cascade risk by port load |
| P20 | Detects ghost connections (provisioned, online, no real traffic) | enlace-pilot-proposal.html; examples/page.tsx | capability | Example audit shows "Ghost connection" finding; criteria: uptime >90%, healthy Rx, no Ethernet activity/flat variance |
| P21 | Predicts churn risk with 90-day probability and revenue at risk | enlace-pilot-proposal.html; page.tsx | capability | Example shows "Churn risk (3 customers)" finding; combines signal trend + micro-dropouts + low usage |
| P22 | Capacity planning: infers splitter size, measures fill rate, projects months-to-full at 95% threshold | enlace-pilot-proposal.html; features/page.tsx | capability | Example shows "ONTs: 112/128 (87.5%)" with "Full in ~4 months" projection |
| P23 | Generates prioritised tickets with P1–P4 tiering and team routing | enlace-pilot-proposal.html | capability | Example routing table: P1 → field (1 day), P2 → build/management (5 days), P3 → passive (14 days) |
| P24 | Produces impact scoring that weights by customer count and time-of-day | enlace-pilot-proposal.html | capability | High-impact work floats to top automatically |
| P25 | Help-desk health view (colour-coded per OLT in plain language) | enlace-pilot-proposal.html | capability | Example output shows "green/amber/red" card per OLT; no SNMP tables needed |
| P26 | Outputs to: Elasticsearch, Slack/PagerDuty, custom webhooks, WhatsApp Business API | enlace-pilot-proposal.html; 04-beyond-monitoring-vision.md; page.tsx | capability | Integration code exists; alerts successfully route to each destination |
| P27 | Optional dry-run mode that just prints, showing exactly what would be sent | enlace-pilot-proposal.html | capability | Agent --dry-run flag executes, prints JSON findings without sending |
| P28 | Internal validation found: 1 fibre cut, 1 area power event, 1 ghost connection, 3 at-risk customers, 1 flapping ONT on 52 ONTs/7 days | enlace-pilot-proposal.html | metric | Internal validation report shows those exact 5 findings; 7-day window on representative data |
| P29 | Health score of 52 from internal validation | enlace-pilot-proposal.html | metric | Example output shows numeric health score; audits ~1,000 ONTs in ~10 milliseconds |
| P30 | 17 detection modules running at the edge | 01-pilot-proposal.md; 05-technical-differentiation.md | metric | Code inspection shows 17 distinct detection functions; 157 tests pass |
| P31 | 180+ automated tests validating detection logic | enlace-pilot-proposal.html; 05-technical-differentiation.md | metric | Test suite passes locally and in CI |
| P32 | Fault classification accuracy ~98% on network-design schemas (synthetic 400-ONT dataset, blind test 10/10) | 05-technical-differentiation.md | metric | Synthetic dataset test results; caveat: not live customer data validation |
| P33 | No runtime dependencies (single static binary, zero dependencies) | 05-technical-differentiation.md | capability | Binary analysis shows no linked .so files; runs on fresh VM |
| P34 | Runs as unprivileged user | 06-pilot-plan-and-data-request.md | capability | systemd service shows User=enlace; no CAP_NET_ADMIN required |
| P35 | Local buffer survives connectivity loss; retries with backoff | enlace-pilot-proposal.html | capability | Offline scenarios tested; buffer resumes on reconnect |
| P36 | Installation: one command under 10 seconds | page.tsx | capability | `curl -sSL get.enlace.network | sudo bash` completes in <10s |
| P37 | Configuration: one TOML file with OLT list and polling interval | page.tsx | capability | /etc/enlace/agent.toml example shows minimal config; systemd unit file created |
| P38 | Supports Adtran SDX 6320 via gRPC (OpenOLT) | page.tsx; 05-technical-differentiation.md | capability | Parser module exists; Community Fibre uses Adtran XGS-PON |
| P39 | Includes 15,482 lines of code (Rust) | about/page.tsx | metric | Repository shows code audit results |
| P40 | Built entirely in Rust for memory safety and performance | about/page.tsx; 05-technical-differentiation.md | capability | Repository shows 100% Rust source (excluding tests/examples) |
| P41 | Pilot Step 1: offline audit of ~1 month ONT telemetry from one problem area, returns findings within 24 hours | 06-pilot-plan-and-data-request.md; enlace-pilot-proposal.html | process | CSV import pipeline exists; audit runs in <1 hour; report generated within 24h SLA |
| P42 | Pilot Step 2: review findings against customer's operational numbers (truck-roll cost, churn, ARPU, alarm volume) | 06-pilot-plan-and-data-request.md | process | Discovery questionnaire completed; review meeting held; value calculated in customer's units |
| P43 | Pilot Step 3: optional live read-only deployment to one OLT, expands at customer's pace | 06-pilot-plan-and-data-request.md | process | Agent deployed to customer infrastructure; monitoring confirmed live |
| P44 | Pilot is free for duration | enlace-pilot-proposal.html; 06-pilot-plan-and-data-request.md | process | No invoice; billing disabled for pilot phase |
| P45 | Preferential pricing reserved for launch partners | enlace-pilot-proposal.html; page.tsx | process | Pricing terms offered in contract |
| P46 | Operator performance benchmarks: truck rolls down 30–50%, MTTR down ~40%, alarm noise down 60–70% | 01-pilot-proposal.md; 04-beyond-monitoring-vision.md; 06-pilot-plan-and-data-request.md | metric | Literature references; caveats: "operators running proactive assurance report" — not Enlace-specific guarantees, tested against customer reality |
| P47 | Supports GPON with 128 ONTs per PON port | features/page.tsx | capability | Example shows "103/128 for GPON" as alert threshold |
| P48 | Supports bandwidth utilisation tracking with 70% sustained 15-min alert threshold | features/page.tsx | capability | Capacity module includes Gbps tracking; example shows "1.82/2.49 Gbps" (73.1%) |
| P49 | Supports splitter occupancy tracking with alert at last 2 available ports | features/page.tsx | capability | Capacity module infers 1:32 splitter size; alerts when 30/32 occupied |
| P50 | Supports ONT growth trend projection (months to full capacity) | features/page.tsx | capability | Example shows "+4 ONTs/month → Full in ~4 months" |
| P51 | Auto-detects OLT vendor from SNMP sysObjectID | features/page.tsx | capability | Startup log shows "sysObjectID: 1.3.6.1.4.1.2011.2.6.6.1 → Huawei MA5800-X17" |
| P52 | Loads correct parser per vendor automatically | features/page.tsx | capability | Startup shows "Loading parser: huawei::ma5800" |
| P53 | Unified schema across vendors (same metrics, alerts regardless of vendor) | features/page.tsx | capability | Multi-vendor deployment shows consistent output format |
| P54 | No per-device licensing model | page.tsx | capability | Pricing is per deployment, not per ONT/subscriber |
| P55 | Telemetry data export support: CSV, NETCONF/Mosaic PM export formats | 06-pilot-plan-and-data-request.md | capability | Import parsers exist for CSV and NETCONF; "Adtran SDX 6320 parser is built" |
| P56 | Discovers per-OLT: number of PON ports and total ONTs | features/page.tsx | capability | Startup shows "Discovered 16 PON ports, 847 ONTs" |
| P57 | Per-ONT diagnostics include: serial, model, firmware, Rx/Tx, distance, temperature, traffic in/out, uptime, signal trend, CRC errors, FEC errors | features/page.tsx | capability | Diagnostics terminal output shows all 12 fields per ONT per poll |
| P58 | Supports NETCONF on Adtran SDX (note: SDX does not use SNMP) | 05-technical-differentiation.md | capability | NETCONF parser module built for Adtran |
| P59 | Injects Adtran telemetry via NETCONF / RESTCONF or CSV/PM export | 05-technical-differentiation.md | capability | Parser exists; SDX-specific integration tested |
| P60 | Vendor-agnostic across 12+ OLT vendors as estate diversifies (acquisition-ready: unify both networks day one) | features/page.tsx | capability | Multi-vendor deployment demonstrates unified view |
| P61 | Signal degradation severity thresholds: Watch −0.015 dBm/day, Warning −0.035 dBm/day, Critical −0.07 dBm/day or Rx < −27 dBm | enlace-pilot-proposal.html | metric | Signal prediction module uses these exact thresholds; test output shows applied thresholds |
| P62 | Time-to-failure output includes days + confidence (R² of linear regression) | enlace-pilot-proposal.html | metric | Example shows "~23 days" forecast with implied fit quality |
| P63 | Reflectance confidence ranges 0.3–0.9 as suspect recurs | enlace-pilot-proposal.html | metric | Multiple events show increasing confidence |
| P64 | Fault localisation outputs estimated distance from OLT + human-readable span (last-online → first-offline node) | enlace-pilot-proposal.html | metric | Example shows "break at 800–850 m on port 0/1/4" |
| P65 | Mass-offline trigger: ≥ configurable N offline within 60-second window | enlace-pilot-proposal.html | metric | Configurable threshold in agent.toml; severity scales with affected count |
| P66 | Weather fault detection requires ≥3 ONTs within 100m on a port | enlace-pilot-proposal.html | metric | Output: pattern, affected ONTs, distance range, correlation strength |
| P67 | Flapping severity tiers: Sporadic 2–5/h, Moderate 5–15/h, Severe >15/h | enlace-pilot-proposal.html | metric | Severity assessment applied per detection |
| P68 | Capacity alerts: Watch 50–75%, Warning 75–90%, Critical >90% | enlace-pilot-proposal.html | metric | Alert thresholds configured; example shows 87.5% → WARNING |
| P69 | Capacity output includes: splitter type, utilisation %, new connections/month, months-to-full | enlace-pilot-proposal.html | metric | Example shows "1:32 splitter, 30/32 ports, +4 ONTs/month → 4 months" |
| P70 | Ghost connection criteria: uptime >90%, healthy Rx, no Ethernet activity or flat variance, sorted by days online | enlace-pilot-proposal.html | metric | Detection logic filters by uptime and activity; output ranked by revenue leak |
| P71 | Churn risk output: probability, days degrading, revenue at risk | enlace-pilot-proposal.html | metric | Example finding includes churn probability and revenue impact |
| P72 | Impact scoring weights by customer count AND time-of-day (daytime business hours > 3 a.m.) | enlace-pilot-proposal.html | metric | Ticket priority reflects time-aware impact |
| P73 | P1 findings (Reflectance source ONT) routed to Customer/field team with 1-day SLA | enlace-pilot-proposal.html | metric | Ticket template shows P1 = 1 day SLA |
| P74 | P2 findings (Capacity critical, Churn risk cohort) routed to Passive (build)/Management with 5-day SLA | enlace-pilot-proposal.html | metric | Ticket template shows P2 = 5 day SLA |
| P75 | P3 findings (Weather/water ingress, Ghost connections) routed to Passive (splice)/Management with 14-day SLA | enlace-pilot-proposal.html | metric | Ticket template shows P3 = 14 day SLA |
| P76 | Offers "free pilot for launch partners" with "preferential pricing reserved for launch partners when we move to paid" | enlace-pilot-proposal.html; page.tsx | process | Offer confirmed in proposal; pricing terms in contract |
| P77 | Expects data export can be ~1 month of ONT telemetry from one problem area; 50+ ONTs over 30 days "plenty"; more is better | 06-pilot-plan-and-data-request.md | process | Accepts CSV with cadence 5-min ideal, 15–60 min acceptable |
| P78 | Data cadence: whatever OLT exports (5-min polling ideal, 15–60 min acceptable) | 06-pilot-plan-and-data-request.md | metric | Agent handles variable cadence; example shows 4.2s poll time for 847 ONTs |
| P79 | Acceptable to anonymise telemetry serials/addresses (only signal patterns needed) | 06-pilot-plan-and-data-request.md | process | Audit engine works on normalized data; no customer PII required |
| P80 | Indicative pilot timeline: Day 0 kick-off + discovery, Days 0–3 data export, +1 day findings report, Weeks 1–2 review, Weeks 2+ optional live deployment | 06-pilot-plan-and-data-request.md | metric | Project schedule meets timeline |
| P81 | Success metric: headline metric agreed upfront (avoidable truck rolls, MTTR, churn from quality, first-call resolution, alarm noise) | 06-pilot-plan-and-data-request.md | process | Metric selected during discovery questionnaire; measured against baseline |
| P82 | Operators running proactive assurance report truck rolls down 30–50% and MTTR down ~40% | 06-pilot-plan-and-data-request.md | metric | Industry benchmark (conservative estimate); pilot tests against customer's own reality |
| P83 | Closed-loop assurance targets TM Forum L3–L4 autonomy (predictive, conditional, closed-loop, humans in loop for exceptions) | 04-beyond-monitoring-vision.md | metric | Architecture aligns with TM Forum Autonomous Networks standard |
| P84 | Auto-ticket generation: P1–P4 tiering, escalation, team routing into existing tooling (PagerDuty, Opsgenie, ServiceNow, Jira) | 04-beyond-monitoring-vision.md | capability | Integration code exists for standard ticketing APIs |
| P85 | WhatsApp Business API alerts to field team with ticket ID, device, fault type, severity, and map pin to fault site | 04-beyond-monitoring-vision.md | capability | WhatsApp integration module; map pin location from per-ONT address |
| P86 | Per-ONT fault narrowed to known subscriber address for immediate dispatch (no extra hardware needed) | 04-beyond-monitoring-vision.md | capability | Service address lookup from ONT serial; dispatch system integration |
| P87 | Proactive planned-maintenance ticketing for slow degradation (Loop B) before customer calls | 04-beyond-monitoring-vision.md | capability | Slow-degradation module opens P3/P4 tickets before threshold breach |
| P88 | Auto-resolution when telemetry confirms recovery (closing Loop A — acute fault) | 04-beyond-monitoring-vision.md | capability | Ticket auto-close on signal restoration; confirmed via telemetry re-poll |
| P89 | "Ready now" claim: automated incident creation, WhatsApp alerts, per-ONT → service address, proactive maintenance, auto-resolution, read-only throughout (all proven patterns) | 04-beyond-monitoring-vision.md | process | Feature verification; all listed capabilities in production | 
| P90 | "Roadmap" claim: OTDR-distance → exact street pin (needs OTDR/RFTS + as-built GIS); calibrated "weeks-to-failure" forecasting (matures with data) | 04-beyond-monitoring-vision.md | process | Caveats disclosed; dependencies stated explicitly |
| P91 | Multi-year, multi-£m carrier OSS (Netcracker, Blue Planet, Ericsson) are the alternative to Enlace | 05-technical-differentiation.md | scope-limit | Competitive positioning vs. heavy integrations |
| P92 | Calix Cloud per-subscriber billing model (vs. Enlace free pilot + no per-endpoint licensing) | page.tsx | capability | Comparison table shows Calix per-subscriber pricing |
| P93 | Calix Cloud Calix-only hardware lock-in (vs. Enlace 12+ vendors) | page.tsx | capability | Comparison table shows Calix single vendor |
| P94 | Enlace installation time 5 minutes vs. Calix weeks | page.tsx | metric | Curl script + systemd setup = ~5 min; comparison claim |
| P95 | Enlace credentials never leave network (Calix credentials sent to cloud) | page.tsx | capability | Network traffic analysis shows Enlace keeps credentials local |
| P96 | Enlace uses open standards (SNMP/NETCONF) vs. Calix closed | page.tsx | scope-limit | Protocol list shows standard-based APIs |
| P97 | Enlace is "complementary to Adtran's Mosaic/Clarity, not competing" (fills gaps vendor cloud leaves) | 05-technical-differentiation.md | process | Positioning statement; integration with Mosaic data exports confirmed |
| P98 | Enlace self-hosted option (telemetry stays on your infrastructure) vs. Calix cloud vendor lock | 05-technical-differentiation.md | capability | On-premises deployment supported; no cloud-only requirement |
| P99 | Enlace handles acquisitions: unify both networks on day one with vendor-agnostic parsing | features/page.tsx | capability | Multi-vendor normalization enables rapid post-acquisition integration |
| P100 | No per-connected-device or per-subscriber licensing (vs. Calix per-device) | page.tsx; 05-technical-differentiation.md | scope-limit | Pricing model is per deployment, not per endpoint |

---

## Summary

**100 distinct claims inventoried** across:
- **Scope-limit promises:** 6 claims (read-only operations, credentials, data security, licensing model, open standards)
- **Capability claims:** 54 claims (detection modules, output formats, vendor support, integration, diagnostics, automation)
- **Metric/performance claims:** 28 claims (binary size, CPU/RAM, timing, accuracy, thresholds, SLA tiers, benchmarks)
- **Process claims:** 12 claims (pilot steps, timeline, discovery, success metrics, feature status)

**Key deliverable dependencies:**
- **Detection modules (P12–P24, P27–P32):** Require code review + example report showing each finding type
- **Vendor support (P9–P11, P38, P47–P60):** Require successful polling from each vendor OLT; example shows vendor auto-detection
- **Performance metrics (P5–P8, P29, P39, P61–P72):** Require system profiling and live deployment data
- **Output integrations (P26, P84–P85):** Require successful sends to Slack/Elasticsearch/WhatsApp with webhook verification
- **Read-only verification (P1–P4):** Requires code audit + network traffic capture during live ops
- **Pilot process (P41–P45, P77–P82):** Requires successful completion of offline Step 1 + customer review meeting

**High-priority verifications before shipping:**
1. All 17 detection modules functioning on representative test data (example audit shows 5 finding types; full suite needs coverage proof)
2. Output integration tests passing for Elasticsearch, Slack, PagerDuty, WhatsApp
3. Read-only operation verified by security audit (no SNMP SET/CONFIGURE/REBOOT commands in agent binary)
4. Vendor auto-detection working for all 12+ OLT types
5. Live performance baseline: CPU <1%, RAM for stated ONT counts, poll latency <60s for configurable cadence