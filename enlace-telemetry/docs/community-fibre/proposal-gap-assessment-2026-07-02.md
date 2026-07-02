# Proposal-vs-deliverable gap assessment — Enlace telemetry pilot (P1–P100)

All verification done against working tree at HEAD (eb9c59c). Agent: 519/519 tests green in 5.07s. No files modified.

## Verdict table

| ID | Verdict | Evidence / Action |
|---|---|---|
| P1 | **SHIPPABLE** | Only `GetRequest`/`GetBulkRequest` PDUs built (src/snmp/mod.rs:747–760); NETCONF only `<get>`/`<get-config>`/`<create-subscription>` (src/netconf/session.rs:407–449); RouterOS `/print` only (src/mikrotik/mod.rs); RADIUS passive listener (src/radius/mod.rs). No SET/edit-config/reboot anywhere in src/ |
| P2 | **SHIPPABLE** | Zero write paths found across all 15 device-facing protocol/vendor modules; SSH CLI path is disabled and read-only ("display ont …") anyway |
| P3 | **SHIPPABLE** | Credentials only in local config + HTTP auth headers (src/output/elastic.rs:180–188); `TelemetryPayload` (src/transport/mod.rs:15–41) has no credential fields |
| P4 | **REWORD** | Per-ONT serials + raw metrics ARE in outbound Elasticsearch docs (elastic.rs:244–260, 327–401). See reword list |
| P5 | **FIX (docs)** | Measured: 8,546,232 B = **8.5 MB** (stripped, opt-level=z, LTO). "6.3 MB" stale; site page.tsx:73/102/352, 01-pilot-proposal.md:36, 05-tech-diff.md:53, 06-pilot-plan.md:63 |
| P6 | **HUMAN/PILOT** | Needs live devices; plausible (1,000-ONT audit uses 0.12 s CPU total). Measure at pilot |
| P7 | **SHIPPABLE** (audit path, measured) | 1,000 ONTs / 30k readings: peak RSS **26 MB** — claim of ~50 MB is a safe upper bound; live daemon RAM confirmed in pilot |
| P8 | **SHIPPABLE** | `default_poll_interval` = 60 s, configurable (src/config/mod.rs:405) |
| P9 | **REWORD** | Real: SNMP v2c/v3 (USM), NETCONF, RouterOS API, RADIUS, TR-069/GenieACS = **5**. SSH CLI: parser complete but gated off "not yet validated against real firmware" (vendors/huawei.rs:208). gRPC: proto/openolt.proto compiled by build.rs with tonic, but generated client **never referenced in src/** — dormant |
| P10 | **SHIPPABLE** | 13 vendors (vendors/mod.rs:27–39, 232–264): the 12 named + generic SNMP |
| P11 | **SHIPPABLE** | `OntData` (vendors/mod.rs:102–170) has every claimed field + FEC/BIP + DDM (temp/voltage/bias) |
| P12 | **SHIPPABLE** | fault/detector.rs:34–35 mass-dropout w/ dying-gasp discrimination |
| P13 | **SHIPPABLE** | `classify()` v2 ratio-based: POWER_GASP_RATIO_MIN=0.6, FIBRE_GASP_RATIO_MAX=0.1 (detector.rs:629–680); verified live: sample audit emits `fault_type: Mixed` with per-ONT `had_dying_gasp` |
| P14 | **SHIPPABLE** | reflectance.rs:222–226 |
| P15 | **SHIPPABLE** | predictions/mod.rs:139–166: rate/day, days_to_failure, R² |
| P16 | **SHIPPABLE** | optical_budget.rs:117–128: ExcessConnectorLoss, MacroBend, SpliceDegradation, SplitterOverloss, InsufficientOltPower — exactly the 5 claimed |
| P17 | **SHIPPABLE** | sfp_health.rs: rx_trend_per_week, estimated_weeks_to_failure, is_outlier_vs_siblings |
| P18 | **SHIPPABLE** | weather.rs:49–56: NighttimeCondensation, PeriodicRainIngress, ThermalExpansion |
| P19 | **SHIPPABLE** | flapping.rs:45–69 + cascade risk; tiers match claim |
| P20 | **SHIPPABLE** | ghost.rs: MIN_UPTIME_RATIO=0.90, MIN_HEALTHY_RX_DBM=−25.0, octet/eth-link evidence |
| P21 | **SHIPPABLE** | churn.rs:76–79: `estimated_churn_probability_90day`, `estimated_annual_revenue_at_risk` (+ explicit assumptions block — over-delivers) |
| P22 | **SHIPPABLE** | capacity.rs: splitter inference, utilisation, months_to_full (note: critical trips at >90%, claim says 95% — align wording) |
| P23 | **SHIPPABLE** | tickets.rs: P1–P4, SLA 1/5/14/30 d, team routing; + full lifecycle in enlace-app (schema.ts:97–121) |
| P24 | **SHIPPABLE** | impact.rs:152–156: affected × active_ratio × time_multiplier (2.0/1.5/1.0/0.5) |
| P25 | **SHIPPABLE** | diagnostics/mod.rs:33–44 Green/Yellow/Red per OLT + app NOC projection |
| P26 | **REWORD** | Elastic + Slack + PagerDuty + generic webhook real (output/webhook.rs:207–295); **no WhatsApp Business API anywhere** — app has wa.me deep links only |
| P27 | **SHIPPABLE** | `--dry-run` (main.rs:261), confirmed in `--help` |
| P28 | **FIX (regenerate example)** | Labelled honestly ("internal validation… not customer data") BUT current engine on the shipped 52-ONT sample now yields: health **64**, **2 Mixed faults**, **0 ghosts**, **0 flapping**, 3 churn, 1 ticket — not the claimed 1 cut/1 power/1 ghost/1 flapping/health 52. Example narrative is stale vs the v2 engine |
| P29 | **FIX (docs)** | Health 52→**64** now. "1,000 ONTs in ~10 ms": measured **0.12 s end-to-end** (30k readings, incl. process start + CSV parse); 52-ONT/7-day = 10 ms; HTTP round-trip 24 ms |
| P30 | **SHIPPABLE** | Exactly **17 modules** verified: 12 detection (capacity, churn, fec_health, flapping, ghost, impact, optical_budget, reflectance, rogue, sfp_health, tickets, weather) + fault detector/locator/topology + predictions laser_health/stats |
| P31 | **SHIPPABLE** (update number) | Measured **519 tests, 0 failed**. "180+" is true but badly stale — say 500+ |
| P32 | **SHIPPABLE** | Caveat explicit, 05-tech-diff.md:93–96: "Neither is live-telemetry validation on your network — that's exactly what the pilot produces." Keep verbatim |
| P33 | **REWORD or FIX** | Binary is **dynamically linked (glibc)**, not static (`file` output). Either add musl release target or reword to "single self-contained binary, no runtime packages to install" |
| P34 | **SHIPPABLE** | install.sh:151: `User=pulso-agent`, `NoNewPrivileges=true`, `ProtectSystem=strict` |
| P35 | **SHIPPABLE** | SQLite retry buffer + exponential backoff (elastic.rs:607–620; test at :1086) |
| P36 | **FIX (infra)** | install.sh is good (prebuilt download, hardened unit, refuses to start on placeholder creds; no compile step; ~10 s plausible on broadband). **But `get.enlace.network` and `releases.enlace.network` have no DNS** (verified; github.com resolves from this box) — the advertised command fails today. Also enlace-telemetry/agent/install.sh still points at stale `releases.pulsonetwork.com.br` (also no DNS) and runs as root |
| P37 | **SHIPPABLE** | One TOML (examples/community_fibre.toml; src/config/mod.rs) — but fix line 2 comment saying "Adtran (gRPC)" |
| P38 | **REWORD** | Adtran SDX is **NETCONF/YANG over SSH primary, SNMP fallback** (vendors/adtran.rs:402–614, collect() :1288–1320); gRPC config parsed but never called |
| P39 | **FIX (docs)** | Measured: **39,513 lines** Rust in src (23,491 code + 16,022 inline test), 62 files. "15,482" stale |
| P40 | **SHIPPABLE** | src/ is 100% Rust |
| P41 | **SHIPPABLE** | Verified live: `--audit-csv` runs (0.01 s on real sample); HTTP POST /audit multipart → 200 + `{audit_id, result}` in 24 ms; 401 without bearer. 24 h SLA trivially met on our side |
| P42 | **HUMAN/PILOT** | Discovery questionnaire + ROI framework exist; needs customer numbers |
| P43 | **HUMAN/PILOT** | Agent ready, read-only proven (P1–P2); needs customer infra |
| P44 | **HUMAN/PILOT** | Stated in docs; no billing exists, trivially true |
| P45 | **HUMAN/PILOT** | Contract-time term; docs consistent |
| P46 | **SHIPPABLE** | Attributed correctly: "Operators running proactive assurance report… We won't quote those as your numbers" (01-pilot-proposal.md:43–45; 04-vision.md:84–88) |
| P47 | **SHIPPABLE** | `topology.splitter_ratios` accepts arbitrary per-port ratios incl. 128 (config/mod.rs:334–338; test :1005–1016); inference-only defaults to 1:32 |
| P48 | **REWORD (or medium FIX)** | **No bandwidth/Gbps utilisation tracking or 70%-sustained-15-min alert in code** — capacity is ONT-count based. Per-ONT octets exist, so port Gbps is buildable, but not for pilot |
| P49 | **FIX (small)** | No "last 2 ports" rule; alerts are %-based (>90% critical). One-line rule `free_ports <= 2 → alert` in capacity.rs:168–176, or reword |
| P50 | **SHIPPABLE** | months_to_full + new_connections_per_month (capacity.rs:28–38) |
| P51 | **SHIPPABLE** | sysObjectID → vendor, 11 enterprise OID prefixes (vendors/mod.rs:266–298) |
| P52 | **SHIPPABLE** | Auto parser selection (vendors/mod.rs:232–264) |
| P53 | **SHIPPABLE** | All 13 vendors emit identical `OntData` |
| P54 | **SHIPPABLE** | Stated consistently; no licensing code exists — trivially true |
| P55 | **SHIPPABLE** | csv_import with column aliases, 5+ timestamp formats, semicolon/UK-Excel test fixtures; NETCONF live path for Adtran |
| P56 | **SHIPPABLE** | `PonPortData`: port_id, onts_registered/online/offline (vendors/mod.rs:79–88) |
| P57 | **SHIPPABLE** | diagnostics/mod.rs:64–97: all 12 claimed fields |
| P58 | **SHIPPABLE** | Real NETCONF: SSH subsystem port 830, hello exchange, RFC 6241 framing, subtree filters (netconf/session.rs) |
| P59 | **SHIPPABLE** (minor reword) | NETCONF + CSV real; drop "RESTCONF" from the sentence (not implemented) |
| P60 | **SHIPPABLE** | Concurrent multi-vendor collectors w/ per-OLT timeouts (main.rs:454–469, 566–586) |
| P61 | **REWORD (align numbers)** | Code: Watch **−0.05**, Warning **−0.10**, Critical **−0.20 dBm/day** (predictions/mod.rs:34–35) — proposal says −0.015/−0.035/−0.07. Rx<−27 dBm matches. Code values are the tested truth; update the proposal |
| P62 | **SHIPPABLE** | days_to_failure + R² (MIN_R_SQUARED=0.6) |
| P63 | **SHIPPABLE** | 1 event→0.3, 2→0.6, 3+→0.9 (reflectance.rs:222–226) |
| P64 | **SHIPPABLE** | locator.rs:14–30, 237–239: estimated/min/max distance + last-online→first-offline span |
| P65 | **SHIPPABLE** | `min_offline_onts` + `time_window_seconds` configurable (config/mod.rs:293–298; default 120 s — say "configurable, default 120 s" not "60-second") |
| P66 | **SHIPPABLE** | MIN_GROUP_SIZE=3, DISTANCE_GROUP_TOLERANCE=100 m — exact match |
| P67 | **SHIPPABLE** | FLAP_RATE 2.0/5.0/15.0 per hour — exact match |
| P68 | **REWORD (minor)** | Watch is ">50% **and** full within 6 months" (capacity.rs:168–176), not a plain 50–75% band; Warning >75% / Critical >90% match |
| P69 | **SHIPPABLE** | All four output fields present |
| P70 | **SHIPPABLE** | Criteria match; code uses octet deltas + eth link, not "flat Rx variance" (deliberately — GPON broadcasts constantly). Update rationale text |
| P71 | **SHIPPABLE** | Verified in live audit output: probability 0.35, days_degrading 7, £377.58/yr at risk, explicit assumptions |
| P72 | **SHIPPABLE** | time_multiplier in impact.rs:152–156 |
| P73 | **SHIPPABLE** | Reflectance conf≥0.8 → P1, sla_days=1 (tickets.rs:216–217) |
| P74 | **SHIPPABLE** | Capacity Warning/Churn → P2, 5 d (tickets.rs:219, 366) |
| P75 | **SHIPPABLE** | Weather/ghost → P3, 14 d (tickets.rs:221) |
| P76 | **HUMAN/PILOT** | Docs consistent; contract-time |
| P77 | **SHIPPABLE** | Stated in 06-pilot-plan; CSV pipeline proven on 52-ONT/7-day sample |
| P78 | **SHIPPABLE** | Timestamp-driven import is cadence-agnostic — verified: 6-hour-cadence synthetic (30k rows) and ~5-min sample both audit cleanly |
| P79 | **SHIPPABLE** | Verified: audit ran on opaque synthetic serials; no PII fields required by importer |
| P80 | **HUMAN/PILOT** | Our side is seconds, not days; timeline depends on customer export |
| P81 | **HUMAN/PILOT** | Discovery artifact ready |
| P82 | **SHIPPABLE** | Same attribution as P46, quoted |
| P83 | **SHIPPABLE** | Phrased as "Enlace **targets** L3–L4" (04-vision.md:17–19) — aspiration, not achievement. Keep |
| P84 | **REWORD** | PagerDuty (Events-format) + Slack native; Opsgenie/ServiceNow/Jira only via generic webhook — no product-specific clients |
| P85 | **REWORD** | App ships **share-to-WhatsApp deep links (wa.me)** with prefilled ticket/device/fault/severity + location link; code self-documents "It is not the WhatsApp Business API; nothing is sent server-side" (ShareTicketActions.tsx:3–9) |
| P86 | **REWORD** | Location derivation (coords/distance range) exists in app; street address requires customer-provided ONT↔address mapping |
| P87 | **SHIPPABLE** | Watch/Warning tiers fire pre-critical (predictions/mod.rs) and degradation findings generate P2/P3 tickets (tickets.rs); "planned-maintenance before the customer calls" is backed |
| P88 | **FIX** | Agent emits recovery/resolve (fault/detector.rs); **app has no listener to auto-close tickets** — lifecycle is human ack→dispatch→close. Small build: app webhook endpoint consuming agent resolve events; else reword to "resolution signals ready; auto-close lands in live phase" |
| P89 | **REWORD** | Of 6 "ready now" items: incident creation ✓, proactive maintenance ✓, read-only ✓; WhatsApp = deep-link not API; address = needs customer mapping; auto-resolution = agent-side only. Must be restated honestly |
| P90 | **SHIPPABLE** | Dependencies disclosed verbatim (OTDR/RFTS + as-built GIS; forecast "matures with your data") |
| P91 | **SHIPPABLE** | Defensible industry characterization |
| P92 | **SHIPPABLE** | Calix per-subscriber pricing is public knowledge |
| P93 | **SHIPPABLE** | Calix assurance is Calix-native — accurate |
| P94 | **REWORD** | "Calix: weeks to install" (site page.tsx:879) is **unsourced** — soften or cite |
| P95 | **REWORD** | "Calix: credentials leave network" (page.tsx:880) **unsourced/inference** — soften to "management and data live in the vendor cloud" |
| P96 | **SHIPPABLE** | SNMP/NETCONF/RADIUS/TR-069 all open standards |
| P97 | **SHIPPABLE** | "Complementary, not competing" positioning + real CSV/Mosaic-export ingestion path |
| P98 | **SHIPPABLE** | Agent cloud-optional; app uses local SQLite; nothing cloud-mandatory |
| P99 | **SHIPPABLE** | Concurrent multi-vendor collectors (same as P60) |
| P100 | **SHIPPABLE** | No per-endpoint licensing anywhere; docs consistent |

**Tally: 68 SHIPPABLE · 8 FIX · 14 REWORD · 10 HUMAN/PILOT**

## (a) Measured metrics — old claim → measured today

| Metric | Claimed | Measured now |
|---|---|---|
| Binary size | 6.3 MB / "6–8 MB" | **8,546,232 B = 8.5 MB** (stripped, LTO, opt-z; dynamic glibc) |
| Tests | "180+" (one doc says 157) | **519 passed, 0 failed** (5.07 s) |
| Lines of Rust | 15,482 | **39,513** in src/ (23,491 code + 16,022 inline test; 62 files) |
| Detection modules | 17 | **17** — still true (12 detection + 3 fault + 2 predictions) |
| Audit speed | "~1,000 ONTs in ~10 ms" | 52 ONTs/1,528 rows: **10 ms** process total; 1,000 ONTs/30k rows: **0.12 s** end-to-end; HTTP /audit round-trip **24 ms** |
| RAM | ~50 MB / 1,000 ONTs | **26 MB peak RSS** for 1,000-ONT audit (claim is a safe ceiling; live daemon TBD) |
| Health score (sample) | 52 | **64** (and 2 Mixed faults / 0 ghosts / 0 flapping / 3 churn / 1 ticket) |
| CPU <1% | unmeasured | Not measurable without live devices — pilot item |

## (b) FIX list, by effort

1. **DNS/hosting for install (P36)** — create `get.enlace.network` (script) + `releases.enlace.network` (binary); neither resolves today, so the advertised one-liner fails. Also purge stale `releases.pulsonetwork.com.br` from enlace-telemetry/agent/install.sh (and its root-user unit).
2. **Stale numbers sweep (P5/P29/P31/P39)** — replace 6.3 MB→8.5 MB, 180+→500+ (519), 15,482→~39,500 (or 23,500 excl. tests), 10 ms→"52 ONTs in 10 ms; 1,000 ONTs in ~0.1 s" at: site page.tsx:73/102/352, about/page.tsx:114, 01-pilot-proposal.md:26/36, 05-tech-diff.md:53/81, 06-pilot-plan.md:63, proposal.html:424.
3. **Regenerate the example audit (P28/P29)** — rerun the shipped sample through the current engine and update the examples page/proposal narrative (health 64, Mixed classification, no ghost/flapping on this sample) — or adjust the sample data to genuinely exhibit those findings.
4. **`free_ports <= 2` splitter alert (P49)** — one-line rule in capacity.rs alert logic.
5. **Fix examples/community_fibre.toml line-2 comment** — says "Adtran (gRPC)"; it's NETCONF.
6. **App auto-close listener (P88)** — endpoint consuming agent resolve events to close matching tickets; agent side already emits.
7. **musl static build (P33)** — optional; otherwise reword.
8. **Port-level bandwidth tracking (P48)** — medium build (aggregate ONT octets per port, 15-min sustained 70% alert); recommend reword for pilot, build for v2.

## (c) REWORD list — proposed replacement text

- **P4**: "Credentials never leave your network. Telemetry sent outward is structured per-ONT findings and optical metrics — never traffic contents or subscriber PII — and with self-hosted Elasticsearch nothing leaves your infrastructure at all."
- **P9**: "Collects over five protocols today — SNMP v2c/v3, NETCONF, RouterOS API, passive RADIUS, and TR-069 (GenieACS) — with SSH CLI and gRPC streaming in validation."
- **P26/P84**: "Outputs to Elasticsearch, Slack and PagerDuty natively, plus custom webhooks that drop into Opsgenie, ServiceNow or Jira; one-tap WhatsApp dispatch from the ops app."
- **P33**: "A single self-contained binary — nothing else to install, no agents, no runtimes."
- **P38/P58/P59**: "Adtran SDX 6320 via NETCONF/YANG (the SDX's native management interface), with SNMP fallback and CSV/Mosaic PM-export import." (Drop "gRPC (OpenOLT)" and "RESTCONF".)
- **P61**: Update thresholds to code truth: Watch −0.05, Warning −0.10, Critical −0.20 dBm/day, or Rx < −27 dBm.
- **P65**: "≥ configurable N offline within a configurable window (default 120 s)."
- **P68**: "Watch: >50% and filling within 6 months; Warning >75%; Critical >90%."
- **P70**: replace "flat Rx variance" rationale with "no real traffic on the Ethernet side (octet counters flat / link never up)".
- **P85**: "One-tap WhatsApp dispatch: the supervisor shares a ready-made message — ticket ID, device, fault type, severity and a map link — straight into the technician's WhatsApp chat. (WhatsApp Business API push is a roadmap integration.)"
- **P86**: "Faults are narrowed to the serving ONT and its location; where you provide your ONT-to-address mapping, that becomes the subscriber's street address on the ticket."
- **P89**: "Ready now: automated incident creation with P1–P4 routing, one-tap WhatsApp dispatch, fault-to-location on every ticket, proactive maintenance tickets, and read-only operation throughout. Landing during the pilot: automatic ticket close-out on confirmed recovery, and street-address mapping once you share your ONT-address data."
- **P94**: "Traditional vendor-cloud assurance: production rollouts measured in weeks" (or cite a source, or drop the row).
- **P95**: "Enlace: credentials never leave your network. Vendor-cloud platforms: management and telemetry live in the vendor's cloud."

## (d) Over-delivery — free wins for proposal v2

- **FEC health analytics** (detection/fec_health.rs): pre-FEC degradation trending with dispersion-vs-attenuation diagnosis and honest coverage notes ("absence of a finding is not evidence of health" — already in live output).
- **Rogue ONT detection** (detection/rogue.rs): passive multi-victim upstream-corruption scoring — a marquee PON capability not claimed anywhere.
- **Laser health / EOL prediction** (predictions/laser_health.rs): bias-current drift with temperature detrending, ageing vs actively-failing classification.
- **Ghost detection v2**: octet-counter evidence with reset-aware deltas — stronger than the claimed variance heuristic.
- **Explicit assumptions in every £-figure**: churn/ticket outputs carry ARPU, truck-roll-cost and probability assumptions inline — auditable ROI.
- **HTTP audit platform**: bearer-auth POST /audit (200 in 24 ms), CORS/body-limit/TTL tunables — the proposal only promises an emailed report.
- **Ops app beyond claims**: multi-tenant JWT auth, 5-persona RBAC projections, PDF reports with a mandatory Data Honesty page, full provenance/audit-log, admin console.
- **Fault localisation detail**: min/max distance bounds + ambiguity flag, not just a point estimate.
- **Hardened install**: systemd `ProtectSystem=strict`, watchdog, refuses to start with placeholder credentials.

**Sharpest risks if unfixed**: P36 (advertised install command has no DNS behind it), P28/P29 (demo narrative no longer matches the engine a prospect could run themselves via the upload page), and P85/P89 (WhatsApp "Business API" wording — the code itself is more honest than the proposal).