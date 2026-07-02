# Pulso Agent — Pilot Readiness Audit (2026-07-02)

> **STATUS UPDATE (2026-07-02, same day):** a remediation campaign addressed all 32
> findings; full test suite 408 passed / 0 failed. See "Remediation status" at the end
> of this document for the per-finding outcome, corrections to two audit claims, and
> the short list of items that still require a human or real hardware.

Five parallel deep audits of `pulso-agent` (~20k lines Rust) ahead of the Community Fibre
(UK, Adtran SDX) pilot and subsequent Brazil pilots, plus market/frontier research.
Every code finding below was verified by reading the source; file:line references included.

**Overall verdict:** well-structured, well-tested demo code — but tested exclusively
against its own synthetic fixtures. The layers where a real pilot will break (real YANG
paths, real CSV headers, real SNMP responses, real CLI output, chronic-offline ONT
populations, sensor noise) are exactly the layers no test exercises. Not production-ready
without the blockers below, but the fixes are mostly well-scoped.

---

## Theme 1 — Day-one alert storm (kills the pilot in the first hour)

1. **Fault detector alarms on *currently offline*, not *newly offline*.**
   `src/fault/detector.rs:79-98,151-158` + `src/main.rs:62-96`. `previous_state` is written
   every cycle but never read; `time_window_seconds` never used. Every real network has
   3–10% chronically offline ONTs (vacant homes, powered-off routers) → any port with ≥5
   emits a critical "fibre cut" webhook **every poll cycle, forever**.
   Fix: transition detection + active-incident map keyed by port; emit once on open, once on resolve.

2. **Every offline ONT is a Red alert every cycle in diagnostics.**
   `src/diagnostics/mod.rs:144-174`. No dedup/hysteresis/baseline. Fix: alert on transitions with debounce.

3. **No cross-port correlation.** `src/fault/detector.rs:72-75`. A feeder cut taking down 16
   ports emits 16 independent events per cycle instead of one incident. Deterministic
   topology suppression ("N of M ONTs under splitter S down ⇒ one incident") is a graph walk, not ML.

4. **Webhooks hardcode "Trunk fibre cut" for every fault type and CRITICAL for every severity.**
   `src/output/webhook.rs:100-106,134-138`. A power outage pages the NOC as a fibre cut —
   the exact failure mode the product exists to prevent. No PagerDuty `dedup_key` → duplicate
   incidents every cycle; no resolve events; serial dispatch inside the poll loop (a down
   endpoint costs ~33s per webhook per event).

## Theme 2 — Never validated against real gear (silent zero-data / wrong-data)

5. **Adtran NETCONF subtree filters likely match nothing on real SDX firmware.**
   `src/vendors/adtran.rs:29-70`. Filters request top-level `<xpon>` with
   `urn:bbf:yang:bbf-xpon-onu-state`; current TR-385 uses `bbf-xpon-onu-states` (plural),
   different container name, and channel-termination as an interface augmentation. A
   mismatched subtree filter returns empty `<data/>` — parsed as **success with 0 ONTs**.
   Nothing treats "0 ONTs from an OLT serving thousands" as suspicious. Single most likely
   day-one failure. Fix: fetch `ietf-yang-library` on connect, support both module revisions,
   treat empty-reply-on-nonempty-OLT as error.

6. **Dying-gasp pipeline is dead code.** `src/vendors/adtran.rs:163-183,250-255`.
   `create_subscription`/`parse_dying_gasp` never called outside tests → PowerFail vs
   FiberCut differentiation (the headline feature) can never occur in production. On the
   other 10 vendors `last_down_cause` is never populated at all (`fault/detector.rs:82-84`),
   so power outages classify as fibre cuts everywhere. Also `FaultType::PowerOutage` is
   unreachable (detector.rs:112-113 requires `hard_offline.is_empty()` inside a branch
   requiring it non-empty).

7. **CSV import will reject or misread real Mission Control / SDX exports.**
   `src/csv_import/adtran.rs`: exact-match snake_case headers only ("Serial Number",
   "RX Power (dBm)" fail, `:116-157`); unknown status → Offline so "IS"/"OOS"/"enabled"
   exports show 100% outage (`:208-213`); one bad timestamp row aborts the whole file
   (`:38-42`); no-timestamp snapshot exports rejected outright; comma-only delimiter (UK/EU
   Excel semicolon exports fail, `:28-32`); `"-22.4 dBm"`, Unicode minus, decimal commas all
   silently → `None` with zero counting (`:196-206`); vendor auto-detect needs `ctp|adtn|pon_port`
   substrings (`csv_import/mod.rs:28-38`). Fix: normalize headers, broaden status vocabulary
   (unknown ≠ offline), skip-and-count bad rows, sniff delimiter, strip units, report
   `rows_skipped`/unparsed-cell counters.

8. **Huawei CLI parser written against invented output.** `src/vendors/huawei.rs:129-191,229-269`.
   Command syntax invalid on most MA5600T/MA5800 firmware; regex expects `ONT-ID State SN`
   but real output is `F/S/P ONT-ID SN Control-flag Run-state…` → **0 ONTs parsed, silently**
   (`unwrap_or_default` :292). No `screen-length 0 temporary`, no pagination, no prompt detection.

9. **PON port fabricated from walk order on ZTE/Datacom/Parks/VSOL/Nokia/CData**
   (`zte.rs:158`, `nokia.rs:78`, etc.) and hardcoded `"cli"` on the Huawei CLI path
   (`huawei.rs:250`) → fault grouping by pon_port is fiction on those vendors: false trunk-cut
   pages and missed real cuts. Only Huawei-SNMP, FiberHome, and Adtran decode real ports.
   Fix: decode per-vendor index encodings; until then disable fault detection for fabricated-port vendors.

10. **Uniform `/100.0` optical scaling copy-pasted across SNMP vendors** (`zte.rs:135`,
    `fiberhome.rs:83`, `cdata.rs:77`, `parks.rs:76`, `vsol.rs:77`…). ZTE firmware families
    widely use `value*0.002−30` or 0.1 dB units; if wrong, LowSignal is a coin flip per
    vendor. ZTE RX/TX OIDs look swapped (`snmp/mod.rs:88-89`). Nokia collects **zero optical
    data** (`nokia.rs:82`). Fix: per-vendor conversion with citations; validate against one
    real `snmpwalk` per vendor (ask pilot ISPs now — cheap).

11. **SNMP fallback for Adtran uses enterprise OID 18070 (Adtran's PEN is 664)** and all walk
    failures are `.unwrap_or_default()` → fallback "succeeds" with 0 ONTs (`adtran.rs:310-318`);
    5s fallback timeout can never walk a 48-port SDX (`:73`).

## Theme 3 — SNMP/transport correctness

12. **SNMPv3 accepted in config, silently unimplemented — always v2c with community "public".**
    `src/snmp/mod.rs:300-310` vs `src/config/mod.rs:111-142`. CF (security-audited UK
    enterprise) configures v3 → agent spams v2c/"public", gets nothing, logs generic timeouts.
    Fix: implement v3 USM or hard-fail at startup when `version != "v2c"`.

13. **Partial SNMP walks returned as clean success.** `src/snmp/mod.rs:342-348,485-495`.
    One send/recv, no retransmit; timeout mid-walk `break`s and returns partial rows as `Ok`
    → 7,000 missing ONTs read as a mass outage → false fibre-cut page. Will happen week one.
    Fix: 2-3 retransmits per PDU; partial walk = explicit error, never clean data.

14. **No forward-progress guard in walk_table** (`:332-380,525-546`): no check returned OID >
    requested, `parse_varbinds` ignores `error_status`, no iteration cap → infinite loop /
    garbage `Null` rows on buggy firmware (VSOL/CData/older FiberHome/ZTE). Also
    `starts_with` prefix matching without dot boundary bleeds adjacent columns (`:359`), and
    `find_by_suffix`/`find_by_index` (`vendors/snmp_helper.rs:18-22`, `huawei.rs:375-377`)
    match without component boundary — index `8.1` matches `…48.1`/`…108.1` → **metrics
    attributed to the wrong ONT** on any large OLT, poisoning everything downstream.

15. **Sequential polling + 60s all-or-nothing timeout** (`main.rs:350-378`): the biggest OLTs
    are guaranteed to deliver zero data (whole result discarded on timeout); cycle overrun +
    default `MissedTickBehavior::Burst` = thundering herd. Fix: bounded-concurrency polling,
    timeout scaled to ONT count, `MissedTickBehavior::Delay`, jitter.

16. **No sentinel handling anywhere**: Huawei `2147483647`, ZTE `65535`, BDCOM `0x7FFF` for
    "no reading" become e.g. 21,474,836 dBm in signal history and prediction inputs
    (`huawei.rs:80-90` et al., `diagnostics/mod.rs:177-213`). Fix: plausibility window
    (−45..+10 dBm) at conversion; sentinels → `None`.

17. **Offline buffer poison pill + unbounded growth.** `src/transport/mod.rs:130-142,177-198`.
    First undeserializable row aborts every flush forever (schema change after upgrade =
    permanently wedged); no row/byte/age cap (weekend outage on 10k ONTs = gigabytes).
    SQLite: connection per call, no WAL/busy_timeout → SQLITE_BUSY storms vs the RADIUS task.
    Cloud send retries (~97s worst case) run inline in the poll loop.

18. **RADIUS: request authenticator never verified** (spoofable), Gigawords (attrs 52/53)
    ignored → byte counts wrap at 4 GiB, blocking DB writes in the recv loop
    (`src/radius/mod.rs:160-220`). Sessions and signal history never pruned; downsampling
    does a full-table `NOT IN` scan every 60s (`transport/mod.rs:269-315`).

19. **NETCONF robustness**: rpc-error detection is substring-based (misses `<nc:rpc-error>`),
    XML parse errors swallowed (`Err(_) => break` in all four parsers in `netconf/xml.rs`),
    byte-offset `&s[..500]` truncate can panic on multibyte (`session.rs:375-381`), O(n²)
    framing re-scan on every SSH packet (`framing.rs:33-72` — a 50MB reply = thousands of
    full-buffer passes), SSH host keys accepted unconditionally, ONT state DashMap never
    pruned → ghost "online" customers forever (`adtran.rs:185-203,240-283`).

## Theme 4 — Statistics below sensor resolution (fortune-telling)

20. **Prediction thresholds sit below DDM resolution.** WATCH at −0.015 dBm/day
    (`predictions/mod.rs:199-225`), SFP WATCH at −0.01 dBm/**week** (`sfp_health.rs:49`);
    DDM quantizes at ~0.1 dB with ±0.5–1 dB diurnal thermal swing. Predictions run from 3
    points with no minimum elapsed time; R² computed, stored as `confidence`, **never used to
    gate** (`predictions/mod.rs:462`). Real data → mass CRITICAL "failure in ~N days" from
    noise. Fix: ≥7 days window, ≥20 samples, R² ≥ 0.6, predicted drop > 3× resolution,
    same-hour-of-day detrending, confidence bands not point ETAs.

21. **Churn probabilities (2/5/15/35%) and £ economics are invented constants** presented as
    revenue-at-risk (`churn.rs:13-17`, `tickets.rs:143-169`); missing RX defaults to −30 dBm
    → healthy ONT with a polling gap scored Severe (`churn.rs:131-135`);
    `monthly_revenue_at_risk` is actually annual. Ticket IDs restart at ENLACE-0001 every
    cycle (`tickets.rs:139`); every reflectance event is P1 even at 0.3 confidence.

22. **Ghost detector physics is wrong**: GPON downstream is continuous broadcast — RX does not
    vary with traffic (`ghost.rs:59-61`). Stable healthy customers get "revenue leakage"
    tickets. Octet counters exist in `OntData` but are dropped from `OntReading`. Use octet deltas.

23. **Optical budget**: splitter ratio inferred from subscriber count → 1:64 with 20 subs
    modeled as 1:32 = systematic ~3.5 dB error, port-wide false "excess loss"
    (`optical_budget.rs:26-50`); wrong wavelength for direction modeled; OLT-side vs ONT-side
    RX semantics conflated across modules (`predictions/mod.rs:395-403` vs optical_budget);
    no XGS-PON (CF runs XGS on part of the plant). Splitter ratio must come from config/GIS,
    not count. Same flaw in `capacity.rs:94-100`.

24. **Fault locator can send a splice crew past the break.** `(None, Some(false))` first-match
    rule (`locator.rs:206-212`): with undecided (no-ONT) nodes — the norm with incomplete
    topology — a feeder cut at 400m localizes to a span at 1500m. Live topology is loaded
    once, globally, with empty inputs, so "infer" mode is dead in production and one topology
    is shared across all ports (`main.rs:232-233`, `topology.rs:58-79`). Fix: require
    upstream online evidence before the rule fires; report ranges not point estimates;
    per-(OLT,port) topology; cross-check against ONT ranging distances.

25. **Weather module**: thresholds below sensor resolution, UTC-hardcoded day/night (wrong in
    BST and Brazil), the 2-8h episode filter is a no-op (`weather.rs:386` takes `.max()` of
    filtered and unfiltered), no actual weather data despite the name. Impact scorer:
    UTC business hours; "active in last hour" penalizes missing data → big outages scored P4
    (`impact.rs:93-106,148-171`). Flapping: 2 transitions 5 min apart = "Severe" 24/h flapper
    (`flapping.rs:152-167`).

## Theme 5 — Ops / security

26. **systemd watchdog kills the agent every 5 minutes**: `WatchdogSec=300` in
    `pulso-agent.service:13` but no `sd_notify` anywhere in src/ → SIGABRT restart loop from
    hour one, wiping all in-memory detector state. `ExecReload` sends SIGHUP which the agent
    doesn't handle → `systemctl reload` kills it.

27. **install.sh never creates a config** (`install.sh:48-51` — the command loads, doesn't
    write) → first-boot crash loop with `Restart=always`; installer writes a *different,
    weaker* unit (root, no hardening) than the repo's.

28. **Audit HTTP server: no auth, CORS Any, binds 0.0.0.0, 500MB bodies buffered in RAM,
    audits run inline on the async runtime, results held in memory forever**
    (`serve.rs:28,36-49,45,77-81,110-115,137-159`). It serves per-customer ONT serials +
    optical data — a data-protection issue for a UK pilot, not just hygiene. Error responses
    echo anyhow chains incl. temp paths.

29. **Elasticsearch `_bulk` partial failures counted as success** (`elastic.rs:335-353` checks
    only HTTP status; `"errors":true` items silently dropped) and failed batches aren't
    buffered (`main.rs:99-105` just warns) → dashboard silently goes stale exactly when ES is
    under pressure. No index template/ILM. 4xx retried identically; body cloned per retry.

30. **No self-observability in agent mode**: no /healthz, no metrics, `panic="abort"` +
    restart = invisible crash loops. The product *is* observability; the agent must expose
    last-successful-collect per OLT, ONT counts, send failures, buffer depth, plus sd_notify.

31. **Stale domain**: `api.pulsonetwork.com.br` default endpoint (`config/mod.rs:332`),
    also in agent.example.toml/installer/unit/Cargo.toml — everything is enlace.network now.
    Zero config validation (`poll_interval_secs=0` panics; `max_repetitions=0` = silently
    empty walks). Secrets plaintext, world-readable config writes, MikroTik plaintext login
    on 8728, login failures log raw device responses. `--audit-csv` JSON output interleaves
    with tracing logs on stdout (`main.rs:161-181`) — corrupts the platform pipeline; move logs to stderr.

32. **`vendor = "auto"` (shipped in example config) permanently returns the generic collector**
    — `detect_vendor()` exists but is never wired in (`vendors/mod.rs:195-202`) → pilot
    collects zero ONT optical data with no error.

## Test realism

No test consumes real device output; 10 of 11 vendor parsers have zero tests.
`audit_tests.rs` fixtures are handcrafted from the TR-385 spec; `real_seed_tests.rs` reads a
JSON outside the repo (breaks CI) and fabricates clean step-function failures that bypass the
SNMP/parse layer entirely — masking the suffix-matching, sentinel, and scaling bugs.
**Highest-leverage single action: obtain one real NETCONF `<get>` reply and one real CSV
export from an SDX 6320, and one `snmpwalk -On` dump per Brazil vendor, and check them in as
fixtures.** Add a property test that suffix matching never crosses OID component boundaries.

## Not collected but available (Adtran SDX) and needed for diagnosis

Dying-gasp/alarm stream (parser exists, never subscribed); ietf-alarms polling (LOS/LOF causes
via plain `<get>` — easier than notifications); rogue-ONU detection state; BIP-8/FEC
corrected-uncorrected counters (earliest degradation signal — the FEC columns are already in
the CSVs being parsed); OLT-side per-PON-port SFP DDM (distinguish OLT SFP vs plant); ONT
uptime/last-change (flapping has no input on NETCONF path); traffic octets (ghost detection
has no signal); ONT firmware/equipment ID (bad-batch correlation).

---

## Market reality check (research summary)

- **"Mission Control" is not an Adtran product** — likely CF NOC shorthand. CF runs **Mosaic
  Cloud Platform** (SDX 6320 OLTs / SDX 621i ONTs). The "Adtran AI" is **Mosaic One Clarity**
  (launched Oct 2025, trial-stage, one-customer projected metric, cloud-SaaS only, no
  published accuracy). Adtran's real optical-layer strength is **ALM OTDR hardware** + Deep
  PON Assurance. Adtran co-authored the 2026 JOCN paper (Sica et al., Fraunhofer HHI) on
  OLT-telemetry × OTDR fusion with a **public dataset** — researching Pulso's space, not shipping it.
- Nokia: transparent about using classical stats (ARIMA/rolling std); holds a patent on ONT
  light-level anomaly detection (US 12,028,108 — be aware). Calix: best-documented per-ONT
  relative trending (>3 dB weekly) and rogue-ONT quarantine, but Calix-only. Huawei: eOTDR
  and NCE-FAN AI are real but NCE-locked and absent from Brazil/LATAM deployments.
- Brazil today: SmartOLT (ZTE/Huawei only, "prediction" = ±3 dB thresholds), Zabbix+Grafana,
  OZmap for ODN GIS (integration target). **Closest direct competitor: NetSense NMS**
  (claims 1.4M ONUs, 15+ vendors, FEC monitoring, "95% alert-noise reduction") — study it.
- ISP pain points nobody serves: multi-vendor coverage below tier-1 (Fiberhome/Datacom/
  Intelbras/Parks), rogue-ONT hunting, splitter-level localization without hardware,
  alert noise, per-ONT history depth, honest prediction accuracy numbers.

## Frontier build order (feasibility-ranked)

1. **Bias-current drift as laser-death predictor + dying-gasp/geo/grid-feed outage
   classifier** — all data over interfaces already polled; DG-ratio per splitter group +
   spatial clustering + DNO (UK) / distribuidora (BR) outage feeds + weather. Patent-validated
   concept, **no shipping product does it**. Lowest difficulty, highest demo value for CF.
2. **Pre-FEC BER / BIP trend analysis** — degradation signal decades ahead of RX-power
   alarms; per-ONT FEC counters available on Huawei/Nokia/ZTE/Adtran (already in the SDX
   CSVs). Killer diagnostic: FEC↑ + RX stable ⇒ dispersion/reflection; FEC↑ + RX↓ ⇒
   attenuation. White space in access — nobody ships it.
3. **Honest ML stack**: per-ONT median/MAD baselines → EWMA/CUSUM → BOCPD step detection →
   trend-to-threshold ETA with confidence bands → gradient boosting only once truck-roll
   labels exist. Skip deep learning. Sell precision, not recall (Ciena's own LOS forecaster:
   "good precision at low recall").
4. **ODN digital twin**: expected-vs-measured RX residual model (weeks of work) + OZmap/VETRO
   GIS integration ("measured topology disagrees with records here"); PT-Predictor
   (Sensors 2023, 65k real ONUs, 0.846 acc) for splitter-membership inference later.
5. **Passive rogue-ONT scoring** (BIP/FEC storm + drift-of-window clusters + no-dying-gasp
   flaps, per ITU-T G.Sup49) + orchestrated vendor-native detect/bisect with guardrails.
   ISPs name this as unsolved; no multi-vendor product ships it.
6. **NETCONF/TR-385 first-class on SDX** (ask Adtran about gNMI — undocumented); VOLTHA/Kafka
   consumer as integration surface; TR-069 stays the Brazil workhorse, TR-369/USP a forward bet.
7. **SOP-based cut early-warning on backhaul coherent pluggables** (CMIS VDM) — a
   whole-network story no access platform tells. **Never claim fiber sensing on GPON itself
   (physically impossible: IM-DD, no coherent front end).** Never quote reflectance dB
   without an OTDR in the loop (SFF-8472 has no ORL field).
8. **OTDR fusion partnership** (ALM API / field-OTDR uploads + the public Sica/HHI dataset).

## Suggested work order before the CF pilot

1. Alert statefulness (finding 1-4): transition detection, incident dedup, resolve events,
   correct webhook copy. Prerequisite for everything — this is what kills the pilot in hour one.
2. Trivial guaranteed failures: systemd watchdog/SIGHUP (26), installer (27), stale domain
   (31), stdout log corruption (31), `vendor="auto"` (32).
3. "Zero/partial = success" sweep: empty NETCONF replies (5), partial SNMP walks (13),
   ES bulk errors (29), Adtran SNMP fallback (11) — plus /healthz + metrics (30).
4. Real fixtures: one SDX NETCONF capture + one real CSV export → fix YANG paths (5),
   CSV headers/status vocab (7); wire dying-gasp or poll ietf-alarms (6).
5. Auth on the audit server + result TTL (28).
6. Statistical gating on predictions/SFP/churn (20-21); sentinel clamping (16).
7. Before Brazil: SNMP suffix/walk correctness (13-14), per-vendor pon_port decode (9),
   unit verification via real walks (10), Huawei CLI rewrite or disable (8), ZTE/FiberHome
   parity with Adtran.

---

# Remediation status (2026-07-02)

Nine specialized fix passes over the same day, each scoped to disjoint files, verified
per-module and then as a whole: **cargo test 408 passed / 0 failed**, release build clean.
Everything below is in the working tree (not yet committed).

## Corrections to the audit itself (verified against primary sources)

- **Finding 5 had the YANG generations backwards**: `bbf-xpon-onu-state` (singular) is the
  CURRENT TR-385 module; the plural is the extinct Issue-1/OB-BAA era one. The old code's
  filter was wrong under *either* generation (top-level `<xpon>` container exists in no
  published module), so the conclusion stood. The collector now reads the device's
  yang-library on connect and selects/tolerates both generations.
- **Finding 11 understated**: per Adtran's datasheet the SDX 6320/6330 has **no SNMP agent
  at all** (NETCONF/YANG only) — the SNMP "fallback" never applied to the pilot hardware.
  PEN corrected 18070→664 anyway (18070 is BTI Photonic Systems).

## Per-finding outcome

| # | Finding | Status |
|---|---|---|
| 1 | Alarms on currently-offline, not newly-offline | **Fixed** — stateful transition detection, per-(OLT,port) incident lifecycle (open/resolve once), first-cycle baseline, chronic-offline never alarms |
| 2 | Every offline ONT = Red alert every cycle | **Fixed** — transition + 2-cycle debounce, once-per-episode |
| 3 | No cross-port correlation | **Fixed** — same-cycle multi-port opens collapse to one OLT-scope incident |
| 4 | Webhooks hardcode "Trunk fibre cut"/CRITICAL | **Fixed** — copy from real FaultType/severity, PagerDuty dedup_key + resolve events, detached dispatch with 10s timeout |
| 5 | NETCONF filters match nothing on real firmware | **Fixed** (see correction) — yang-library-driven filters, both generations, empty-reply-is-error; real SDX capture still wanted as fixture |
| 6 | Dying-gasp dead code | **Fixed** — ietf-alarms polled every cycle as primary down-cause source (dgi→PowerFail), RFC 5277 subscription as best-effort; PowerOutage classification reachable |
| 7 | CSV rejects real exports | **Fixed** — header aliases, IS/OOS vocab (unknown ≠ offline), delimiter sniffing, skip-and-count ImportReport, snapshot mode, UK number/date formats; realistic fixtures checked in |
| 8 | Huawei CLI parser invented | **Fixed/Disabled** — parser rewritten against real ntc-templates captures; session driver disabled with explicit error until a real transcript validates it (silent zero eliminated) |
| 9 | pon_port fabricated from walk order | **Fixed** — real index decodes (Huawei/ZTE/FiberHome/Datacom/Parks/BDCOM/CData, cited + capture-verified); honest UNKNOWN_PON_PORT elsewhere, excluded from trunk-cut logic |
| 10 | Copy-pasted /100 scaling | **Fixed** — per-vendor scaling verified against real walks (ZTE 0.002x−30, BDCOM 0.1 dB, CData linear 0.1 µW→log, Datacom string-dBm); FiberHome status enum was INVERTED (0=FiberCut,3=Offline) — fixed; Nokia per-ONT optics honestly absent (no public OID path) |
| 11 | Adtran SNMP fallback wrong OID | **Fixed** (see correction) |
| 12 | SNMPv3 silently v2c/"public" | **Fixed** — hard-fail at poller creation + config validation; no community fallback |
| 13 | Partial walks = clean success | **Fixed** — 2 retransmits w/ backoff; PartialWalk is an explicit error |
| 14 | No forward-progress guard; suffix bleed | **Fixed** — progress guard, error_status surfaced, 200k row cap, component-boundary matching (property-tested), huawei local copy removed |
| 15 | Sequential polling, all-or-nothing timeout | **Fixed** — semaphore-bounded concurrency (4), per-OLT scaled timeouts, MissedTickBehavior::Delay, jitter, per-OLT failure isolation |
| 16 | No sentinel handling | **Fixed** — plausible_dbm (−45..+10 dBm) at every vendor conversion + defense-in-depth in detection/predictions |
| 17 | Offline buffer poison pill / unbounded | **Fixed** — dead-letter quarantine, 1M row/512MB/7d caps, WAL + busy_timeout + persistent connection, background flusher off the poll loop |
| 18 | RADIUS spoofable, gigawords, blocking | **Fixed** — RFC 2866 authenticator verified, attrs 52/53, bounded-channel writer task, retention pruning, incremental downsampling |
| 19 | NETCONF robustness | **Fixed** — namespace-aware rpc-error, XML errors surfaced, multibyte-safe truncation, incremental framing (24MB tested), TOFU host keys, ONT-state pruning |
| 20 | Predictions below sensor resolution | **Fixed** — gates: ≥7d, ≥20 samples, ≥5 daily buckets, R²≥0.6, drop >3×0.1 dB LSB; 24h-mean detrending; 95% ETA ranges; honest thresholds (−0.05/−0.10/−0.20) |
| 21 | Invented churn/£ constants | **Fixed** — `estimated_*` naming, assumptions echoed in output, missing RX = no score, annual math matches name, stable ticket IDs, confidence-scaled priority |
| 22 | Ghost physics wrong | **Fixed** — RX-variance inference deleted (GPON downstream is continuous broadcast); NoLink-only + insufficient-data honesty; octet counters still a data-model TODO |
| 23 | Splitter ratio guessed from count | **Fixed** — operator topology via `[topology.splitter_ratios]`; assumed ratios flagged + widened tolerance; 1490/1577 nm wavelengths; XGS-PON params; RX direction semantics reconciled |
| 24 | Locator sends crew past break | **Fixed** — positive downstream evidence required; min/max distance ranges; per-(OLT,port) TopologyRegistry replaces dead global |
| 25 | Weather/impact/flapping dishonesty | **Fixed** — renamed diurnal-pattern correlation, resolution-floored thresholds, working episode filter, utc_offset_hours, missing data not penalized, flapping min-window |
| 26 | Watchdog kills agent every 5 min | **Fixed** — hand-rolled sd_notify (READY/WATCHDOG/STOPPING), Type=notify, SIGHUP survives; verified live |
| 27 | Installer never writes config | **Fixed** — writes config 0640, non-root user, repo's hardened unit, refuses to start on placeholder creds |
| 28 | Audit server open + unbounded | **Fixed** — bearer auth (constant-time), 127.0.0.1 default, CORS off by default, 50MB streamed uploads, spawn_blocking, TTL+cap eviction, sanitized errors, /healthz |
| 29 | ES bulk partial failures dropped | **Fixed** — per-item parsing, 429/503 retry, dead-letter, SQLite requeue + drain, index template + ILM, resolve events indexed |
| 30 | No self-observability | **Fixed** — /healthz + Prometheus /metrics in agent mode (per-OLT last-collect/ont-count/failures, buffer depth, dead letters, incident counters) |
| 31 | Stale domain, no validation, stdout corruption | **Fixed** — enlace.network everywhere (incl. README), config validation at load, logs on stderr, world-readable warning |
| 32 | vendor="auto" dead | **Fixed** — AutoDetectCollector probes sysObjectID/sysDescr, hard-errors on failure; generic fallback removed (fatal); discovery covers all 11 vendors |

## Real-data corpus (new)

`data/external/` (~5.9 MB, SOURCES.md provenance): real snmpwalks for 10 vendors with
LibreNMS per-OID decode oracles (ZTE C320 walk replayed in tests), BBF YANG modules,
real-format Adtran bbf-xpon NETCONF payloads (OB-BAA/VOLTHA), real SFF-8472 DDM dumps.

## Still requires a human or real hardware

1. **Fill the Fraunhofer HHI form** (networkdata.hhi.fraunhofer.de → "OLT-OTDR Dataset",
   CC BY 4.0, 2 min) — the only public end-to-end PON fault-detection validation set;
   co-authored with Adtran.
2. **One real SDX 6320 capture** (NETCONF `<get>` reply + yang-library + Mosaic CSV
   export) from CF — converts the remaining "tolerant-parser" assumptions into fixtures.
3. **One real MA5600T/MA5800 SSH transcript** — re-enables the (rewritten, tested)
   Huawei CLI driver.
4. **Frontend**: enlace-site upload page must send `Authorization: Bearer <token>`; server
   needs PULSO_AUDIT_CORS_ORIGIN + PULSO_AUDIT_BIND set for browser access.
5. Nokia per-ONT optics need the customer-gated APON MIB or TL1/NETCONF; Parks live
   walk still unseen; ZTE 0-based phase-state enum flagged for on-hardware confirmation.
6. OntReading lacks FEC/BIP/octet/temperature fields — csv_import already recognizes the
   headers; adding the fields unblocks pre-FEC BER trending (frontier item 2) and real
   ghost detection.
