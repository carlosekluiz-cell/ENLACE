"use client";

// ── Enlace marketing-site i18n — lightweight client-side translations ──
// Same pattern as enlace-app/src/lib/i18n.tsx: inline dictionaries,
// localStorage persistence, useSyncExternalStore. English is the default and
// the fallback; pt-BR is a full, hand-written Brazilian-Portuguese translation
// (telecom register, not machine-translated). Missing pt-BR keys fall back to
// English so nothing ever renders blank.
//
// t(key, params?) supports {token} interpolation, e.g.
//   t("report.cover.fec", { a: 12, b: 52 })

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  localStorageGet,
  localStorageSet,
  subscribeLocalStorage,
} from "@/lib/clientStore";

export type Locale = "en" | "pt-BR";

const en: Record<string, string> = {
  // ── Nav ──
  "nav.features": "Features",
  "nav.examples": "Examples",
  "nav.intelligence": "UK Intelligence",
  "nav.contact": "Contact",
  "nav.requestPilot": "Request a pilot",
  "nav.openMenu": "Open menu",
  "nav.closeMenu": "Close menu",
  "nav.language": "Language",

  // ── Footer ──
  "footer.product": "Product",
  "footer.resources": "Resources",
  "footer.company": "Company",
  "footer.features": "Features",
  "footer.examples": "Examples",
  "footer.requestPilot": "Request a pilot",
  "footer.contact": "Contact",
  "footer.about": "About",
  "footer.copyright": "© 2026 Pulso Technologies. All rights reserved.",
  "footer.tagline": "Read-only telemetry · multi-vendor · your data stays yours",
  "footer.legal":
    "Pulso Technologies Limited · Registered in England & Wales · company no. 17151141",

  // ── Common CTAs ──
  "common.requestPilot": "Request a pilot",
  "common.seeExample": "See an example",
  "common.learnMore": "Learn more ↓",

  // ── Home: hero ──
  "home.hero.title1": "Your network is talking.",
  "home.hero.title2": "Now you can listen.",
  "home.hero.lead":
    "Enlace reads the telemetry your OLTs already produce — read-only — and turns it into early warnings: fibre faults, degrading signal, ghost connections, churn risk. 12+ OLT vendors. 60-second intervals. One 8.7 MB static binary.",
  "home.hero.sub":
    "Enlace is the first product from Pulso Technologies, a UK telecom-technology startup. We're pre-launch — onboarding a small number of fibre operators as validation partners.",
  "home.metric.binarySize": "Binary size",
  "home.metric.oltVendors": "OLT vendors",
  "home.metric.pollInterval": "Poll interval",
  "home.metric.audit": "1,000-ONT audit",
  "home.metric.protocols": "Protocols",
  "home.metric.credentials": "Credentials sent",
  "home.hero.figuresNote": "Figures from internal validation.",

  // ── Home: problem ──
  "home.problem.eyebrow": "THE PROBLEM",
  "home.problem.title1": "Your NOC is reactive.",
  "home.problem.title2": "Your customers know before you do.",
  "home.problem.before": "Before",
  "home.problem.after": "After",
  "home.problem.before.1": "Customer calls with complaint",
  "home.problem.before.2": "Technician dispatched blind",
  "home.problem.before.3": "Signal degrading undetected for weeks",
  "home.problem.before.4": "No per-ONT visibility",
  "home.problem.before.5": "Truck roll: £80–150 each",
  "home.problem.before.6": "15–25% are 'no fault found'",
  "home.problem.after.1": "Per-ONT monitoring every 60 seconds",
  "home.problem.after.2": "Tech gets diagnosis before customer calls",
  "home.problem.after.3": "Continuous failure prediction",
  "home.problem.after.4": "Dashboard with signal, distance, trend",
  "home.problem.after.5": "70% of calls resolved by help desk",
  "home.problem.after.6": "Churn risk scored before the customer calls",

  // ── Home: how it works ──
  "home.how.eyebrow": "HOW IT WORKS",
  "home.how.title1": "One binary. Five minutes.",
  "home.how.title2": "From blind to predictive.",
  "home.how.install.title": "Install",
  "home.how.install.desc": "One command. Under 10 seconds.",
  "home.how.configure.title": "Configure",
  "home.how.configure.desc":
    "One TOML file. Add your OLTs, set the interval, done.",
  "home.how.collect.title": "Collect",
  "home.how.collect.desc":
    "The agent connects to each OLT using the right protocol and pulls per-ONT data.",
  "home.how.connect.title": "Connect",
  "home.how.connect.desc":
    "Data flows to Elasticsearch, Slack, and webhooks. Plug into what you already use.",

  // ── Home: features ──
  "home.features.eyebrow": "CAPABILITIES",
  "home.features.title1": "17 intelligence modules.",
  "home.features.title2":
    "Six highlighted here. Each one replaces a manual process.",
  "home.feat.fault.title": "Fault Detection",
  "home.feat.fault.desc":
    "Fibre cut vs power outage. Multi-ONT correlation on the same PON port. Instant classification.",
  "home.feat.fault.metric": "Per-cycle detection",
  "home.feat.signal.title": "Signal Prediction",
  "home.feat.signal.desc":
    "Linear regression on dBm history. Continuous failure forecast per ONT.",
  "home.feat.signal.metric": "Continuous forecast",
  "home.feat.churn.title": "Churn Scoring",
  "home.feat.churn.desc":
    "Degrading signal + micro-dropouts = estimated 90-day churn probability and revenue at risk — with every assumption stated inline.",
  "home.feat.churn.metric": "Assumptions stated",
  "home.feat.capacity.title": "Capacity Planning",
  "home.feat.capacity.desc":
    "PON port utilisation tracking. Watch above 50% when filling within 6 months; warning above 75%, critical above 90%.",
  "home.feat.capacity.metric": "Months-to-full forecast",
  "home.feat.vendor.title": "Multi-Vendor",
  "home.feat.vendor.desc":
    "Huawei, ZTE, FiberHome, Adtran, Nokia, Datacom + more. One dashboard.",
  "home.feat.vendor.metric": "12+ vendors",
  "home.feat.diag.title": "Real-time Diagnostics",
  "home.feat.diag.desc":
    "Per-ONT signal level, distance, status, temperature. Customer health card for the help desk.",
  "home.feat.diag.metric": "60s intervals",

  // ── Home: vendor support ──
  "home.vendors.eyebrow": "VENDOR SUPPORT",
  "home.vendors.title1": "12+ OLT vendors.",
  "home.vendors.title2": "Every protocol. One agent.",
  "home.vendors.col.vendor": "Vendor",
  "home.vendors.col.models": "Models",
  "home.vendors.col.protocols": "Protocols",
  "home.vendors.partial": "Partial support",
  "home.vendors.alsoCollected": "Also collected",
  "home.vendors.proto.adtran": "NETCONF/YANG + SNMP + CSV import",
  "home.vendors.proto.mikrotik": "RouterOS API (PPPoE, BGP, traffic)",
  "home.vendors.proto.radius": "UDP 1813 (sessions, bytes, duration)",
  "home.vendors.proto.tr069": "GenieACS API (WiFi, SNR, devices)",
  "home.vendors.footnote":
    "Validated collection paths today: SNMP v2c/v3, NETCONF, RouterOS API, passive RADIUS, and TR-069 (GenieACS). SSH CLI and gRPC streaming are implemented but still in validation against real firmware.",

  // ── Home: trust ──
  "home.trust.eyebrow": "TRUST",
  "home.trust.title1": "Read-only & verifiable.",
  "home.trust.title2": "No lock-in by design.",
  "home.trust.1": "Read-only — the agent never writes to your kit",
  "home.trust.2": "Your credentials stay on your network",
  "home.trust.3":
    "Vendor-agnostic via open standards (SNMP/NETCONF) — no single-vendor lock-in",
  "home.trust.4": "Your data stays yours",
  "home.trust.5":
    "We'll walk your engineers through exactly what the agent does — read-only — so they can verify it without us handing over source",

  // ── Home: vs Calix ──
  "home.calix.eyebrow": "COMPARISON",
  "home.calix.title1": "Calix Cloud charges per subscriber.",
  "home.calix.title2": "And only works with Calix hardware.",
  "home.calix.col.feature": "Feature",
  "home.calix.row.vendors.f": "OLT vendors",
  "home.calix.row.vendors.c": "Calix only",
  "home.calix.row.vendors.e": "12+ vendors",
  "home.calix.row.telemetry.f": "Per-ONT telemetry",
  "home.calix.row.telemetry.c": "Yes",
  "home.calix.row.telemetry.e": "Yes",
  "home.calix.row.predictive.f": "Predictive maintenance",
  "home.calix.row.predictive.c": "Yes",
  "home.calix.row.predictive.e": "Yes",
  "home.calix.row.readonly.f": "Read-only / no lock-in",
  "home.calix.row.readonly.c": "Closed",
  "home.calix.row.readonly.e": "Yes — open standards",
  "home.calix.row.lockin.f": "Vendor lock-in",
  "home.calix.row.lockin.c": "Total",
  "home.calix.row.lockin.e": "None",
  "home.calix.row.pricing.f": "Pricing model",
  "home.calix.row.pricing.c": "Per subscriber",
  "home.calix.row.pricing.e": "Free pilot at launch",
  "home.calix.row.install.f": "Install",
  "home.calix.row.install.c": "Cloud onboarding project",
  "home.calix.row.install.e": "One command, minutes",
  "home.calix.row.creds.f": "Credentials & management",
  "home.calix.row.creds.c": "Live in the vendor cloud",
  "home.calix.row.creds.e": "Stay on your network",

  // ── Home: pilot ──
  "home.pilot.eyebrow": "LAUNCH PARTNERS",
  "home.pilot.title": "Free pilot for launch partners",
  "home.pilot.lead":
    "We're onboarding a small number of fibre operators to validate Enlace on real networks — free during the pilot, with preferential pricing at launch.",

  // ── Home: closing CTA ──
  "home.cta.title1": "Your network has the data.",
  "home.cta.title2": "Stop flying blind.",
  "home.cta.lead":
    "See an example of what Enlace finds, then request a pilot to run it against your own network.",

  // ── Features page ──
  "features.eyebrow": "Platform Capabilities",
  "features.hero.title1": "Everything Enlace does for your network.",
  "features.hero.title2": "17 modules. One agent. Zero guesswork.",
  "features.hero.lead":
    "The agent ships 17 analysis modules — fault detection and localisation, signal and laser end-of-life prediction, pre-FEC health, churn scoring, ghost and rogue-ONT detection, optical budget, reflectance, weather correlation, flapping, capacity, SFP health, impact scoring and ticket generation. The five highlighted below are the ones you'll use daily. No add-ons, no upsells — every module ships with every install.",

  "features.fault.eyebrow": "FAULT DETECTION",
  "features.fault.title":
    "Fibre cut vs power outage — classified every poll cycle.",
  "features.fault.desc":
    "The agent monitors every ONT on every PON port each poll cycle. When ONTs go offline, it correlates the pattern to classify the fault type — no human analysis needed.",
  "features.fault.1":
    "Multiple ONTs offline on same PON port = fibre cut (CRITICAL)",
  "features.fault.2": "Single ONT offline, neighbours up = CPE failure (MINOR)",
  "features.fault.3":
    "ONTs across different ports, same area = power outage (MAJOR)",
  "features.fault.4":
    "Dying-gasp evidence per ONT separates power loss from fibre damage",
  "features.fault.5":
    "Rx power dropping below -27 dBm = signal degradation (WARNING)",

  "features.signal.eyebrow": "SIGNAL PREDICTION",
  "features.signal.title": "Know which ONTs will fail before they do.",
  "features.signal.desc":
    "The agent stores Rx power history per ONT and runs linear regression on the signal trend. It extrapolates the current degradation rate to a failure threshold, producing a continuous days-to-failure forecast.",
  "features.signal.1":
    "Polls Rx power (dBm) every cycle, stores per-ONT time series",
  "features.signal.2":
    "Linear regression calculates slope (dBm/day) with R² confidence gating",
  "features.signal.3":
    "Watch at -0.05, warning at -0.10, critical at -0.20 dBm/day — or any ONT below -27 dBm",
  "features.signal.4":
    "Cause estimate based on degradation pattern (connector, bend, splice)",

  "features.capacity.eyebrow": "CAPACITY PLANNING",
  "features.capacity.title": "Know when your PON ports will saturate.",
  "features.capacity.desc":
    "The agent tracks ONT count, bandwidth utilisation, and splitter occupancy across every PON port. You get alerts before you run out of capacity — not after a failed installation.",
  "features.capacity.1":
    "ONTs per PON port — watch above 50% when filling within 6 months, warning above 75%, critical above 90%",
  "features.capacity.2":
    "Splitter occupancy per port — configured or inferred ratios, 1:2 to 1:128",
  "features.capacity.3":
    "Growth trend projection — months until full capacity",
  "features.capacity.4":
    "Per-ONT traffic counters collected today; port-level Gbps alerting is on the roadmap",

  "features.vendor.eyebrow": "MULTI-VENDOR",
  "features.vendor.title": "12+ OLT vendors. One unified view.",
  "features.vendor.desc":
    "Most ISPs run equipment from multiple vendors. Enlace normalises the data from all of them into a single schema — same metrics, same alerts, regardless of whether the OLT is Huawei, ZTE, or BDCOM.",
  "features.vendor.1": "Auto-detects vendor from SNMP sysObjectID",
  "features.vendor.2": "Loads correct parser per vendor automatically",
  "features.vendor.3":
    "No vendor lock-in — mix Huawei and ZTE in the same network",
  "features.vendor.4": "Acquisition-ready: unify both networks on day one",

  "features.diag.eyebrow": "REAL-TIME DIAGNOSTICS",
  "features.diag.title": "Per-ONT health cards for the help desk.",
  "features.diag.desc":
    "When a subscriber calls, your support agent needs answers in seconds. Enlace provides a complete health card for every ONT — no SSH into the OLT, no CLI commands, no guessing.",
  "features.diag.1":
    "Serial number, model, firmware, Rx/Tx power, distance",
  "features.diag.2": "Temperature, traffic in/out, uptime, signal trend",
  "features.diag.3": "12 data points per ONT per poll cycle",
  "features.diag.4": "Normalised schema regardless of OLT vendor",

  "features.cta.title": "See it in action.",
  "features.cta.lead":
    "See an example report — signal scores, fault detection, ghost connections, and churn risk — then request a pilot to run Enlace against your own network.",

  // ── About page ──
  "about.eyebrow": "About",
  "about.hero.title1": "Engineered for ISPs.",
  "about.hero.title2": "Built in Rust.",
  "about.hero.lead":
    "Pulso Technologies builds telemetry intelligence for fibre operators. Enlace is our first product — a telemetry agent that gives ISPs the per-ONT visibility they've never had.",
  "about.mission.title":
    "We believe every ISP deserves the same network intelligence that Tier 1 carriers have.",
  "about.mission.body":
    "The data is already in your OLTs. We just help you use it.",
  "about.tech.eyebrow": "Under the hood",
  "about.tech.rust.title": "Built with Rust",
  "about.tech.rust.body": "For performance and reliability. 500+ tests (528 passing).",
  "about.tech.lines.body": "Lines of Rust (~39,500 including tests).",
  "about.tech.readonly.title": "Read-only & verifiable",
  "about.tech.readonly.body":
    "Never writes to your kit. We'll walk your engineers through exactly what it does.",
  "about.contact.eyebrow": "Get in touch",
  "about.contact.emailLabel": "Email",
  "about.legal":
    "Pulso Technologies Limited. Registered in England & Wales, company no. 17151141.",

  // ── Examples page ──
  "examples.eyebrow": "Example output",
  "examples.hero.title": "What an Enlace audit produces",
  "examples.hero.lead":
    "Enlace reads the telemetry your OLTs already produce and turns it into a plain-language report: a fleet health score, the faults worth acting on, and a per-ONT table you can sort and filter. Below is a representative example.",
  "examples.banner.label": "Example output",
  "examples.banner.text":
    "— generated from Enlace's internal validation on representative data. Not customer data.",
  "examples.report.eyebrow": "The report",
  "examples.report.title": "Fleet health, findings, and every ONT",
  "examples.report.lead":
    "Click a finding to filter the ONT table. 52 ONTs across four PON branches, analysed over a 7-day window — this is the verbatim JSON the current engine produced from our validation sample, including its own coverage notes.",
  "examples.report.figuresNote":
    "Figures from internal validation on representative data.",
  "examples.found.eyebrow": "What it found",
  "examples.found.title": "Six findings — including what it refused to claim",
  "examples.find.1.title": "Two branch outages, classified by evidence",
  "examples.find.1.detail":
    "Five ONTs on CTP-0/4 and four on CTP-0/2 dropped inside the detection window. On CTP-0/4, two sent a dying gasp and three went silent — mixed evidence, so the engine says “Mixed” instead of guessing power vs fibre. Per-ONT gasp evidence is attached to each fault.",
  "examples.find.2.title": "Churn risk: 3 customers, assumptions stated",
  "examples.find.2.detail":
    "Three subscribers at −25 to −29 dBm with degrading signal — an estimated 35% 90-day churn probability and ~£378/yr revenue at risk each. Every figure carries its assumptions inline (ARPU £89.90, probability model), so the ROI is auditable, not asserted.",
  "examples.find.3.title": "One proactive ticket, ready to dispatch",
  "examples.find.3.detail":
    "The three churn risks were rolled into a single P2 ticket with a 5-day SLA: evidence lines per ONT, a recommended action, £1,133/yr at risk vs a £450 estimated fix — a 2.5× ROI with the cost assumptions printed on the ticket.",
  "examples.find.4.title": "Shared-plant downtrend on CTP-0/1",
  "examples.find.4.detail":
    "The whole PON branch is trending down at −0.74 dB/week — roughly 13 weeks to threshold at the current rate. A fleet-wide trend points at shared plant (splitter, feeder, OLT SFP), not any single customer's kit.",
  "examples.find.5.title": "Three links running on marginal optical budget",
  "examples.find.5.detail":
    "Loss-model analysis of all 52 links found three with ~8 dB more loss than their distance and splitter ratio explain — probable excess connector loss, flagged with the expected-vs-measured maths.",
  "examples.find.6.title": "What it refused to claim",
  "examples.find.6.detail":
    "This sample has no FEC or laser-bias columns, so the report states “0 of 52 ONTs covered” for those analyses instead of implying health. No ghosts, no flapping, no rogue ONTs were flagged — absence of a finding is reported as absence of evidence, never as a pass.",
  "examples.cta.title": "Want this for your network?",
  "examples.cta.lead":
    "We're onboarding a small number of fibre operators as validation partners. Enlace runs read-only against the OLTs you already have.",

  // ── Report explorer / HealthScore / FindingsSidebar / OntTable ──
  "report.findings": "Findings",
  "report.clearFilter": "Clear filter",
  "report.noFindings": "No findings",
  "report.cat.faults": "Fault Events",
  "report.cat.churn": "Churn Risk",
  "report.cat.ghosts": "Ghost Customers",
  "report.cat.capacity": "PON Capacity",
  "report.cat.sfp": "PON-wide Trend",
  "report.cat.rogue": "Rogue ONT Suspects",
  "report.cat.tickets": "Tickets Raised",
  "report.cat.flapping": "Flapping ONTs",
  "report.cat.weather": "Weather Correlation",
  "report.cat.reflectance": "Reflectance",
  "report.cat.optical": "Optical Budget",
  "report.sub.severe": "{n} severe (assumed model)",
  "report.sub.monitoring": "monitoring",
  "report.sub.ghosts": "revenue leakage detected",
  "report.sub.capacity.alerting": "{n} ports alerting",
  "report.sub.capacity.alerting.one": "{n} port alerting",
  "report.sub.capacity.tracked": "{n} ports tracked · peak {peak}%",
  "report.sub.sfp": "shared-plant degradation",
  "report.sub.rogue": "needs vendor confirmation",
  "report.sub.flapping": "unstable connections",
  "report.sub.weather": "environment-linked faults",
  "report.sub.reflectance": "connector issues",
  "report.sub.optical": "of {n} links assessed",

  "report.health.title": "Fleet Health Score",
  "report.health.healthy": "HEALTHY",
  "report.health.attention": "NEEDS ATTENTION",
  "report.health.critical": "CRITICAL",
  "report.stat.faults": "Faults",
  "report.stat.degrading": "Degrading",
  "report.stat.ghosts": "Ghost ONTs",
  "report.stat.capacity": "PON 80%+",
  "report.stat.healthy": "Healthy",
  "report.stat.avgRx": "Avg Rx dBm",

  "report.cover.title": "Analysis coverage — stated, not assumed",
  "report.cover.fec": "Pre-FEC health — {a}/{b} ONTs covered",
  "report.cover.laser":
    "Laser end-of-life — {a}/{b} ONTs reporting bias current",
  "report.cover.laser.none":
    "No bias-current telemetry in this dataset, so no laser predictions were made — absence of a finding is not evidence of health.",
  "report.cover.laser.some":
    "{analyzed} analysed, {flagged} flagged, {detrended} temperature-detrended.",
  "report.cover.rogue": "Rogue ONT scan — {n} ports flagged",
  "report.cover.rogue.one": "Rogue ONT scan — {n} port flagged",
  "report.cover.rogue.intro":
    "Passive multi-victim upstream-corruption scoring ran across all PON ports. ",
  "report.cover.rogue.none": "No rogue-suspect events in this window.",
  "report.cover.rogue.some": "Candidates require vendor-native confirmation.",

  "table.search": "Search by serial...",
  "table.col.serial": "Serial",
  "table.col.pon": "PON Port",
  "table.col.rx": "Rx dBm",
  "table.col.status": "Status",
  "table.col.issue": "Issue",
  "table.noMatch": "No ONTs match the current filter",
  "table.prev": "Previous",
  "table.next": "Next",
  "table.page": "Page {page} of {total}",
  "table.status.offlineLos": "OFFLINE (LOS)",
  "table.status.lowSignal": "LOW SIGNAL",
  "table.issue.rogue": "Rogue suspect",
  "table.issue.fault": "Fault affected",
  "table.issue.ghost": "Ghost customer",
  "table.issue.degrading": "Degrading ({days}d, ~{pct}% est. churn)",
  "table.issue.flapping": "Flapping",
  "table.issue.reflectance": "Reflectance issue",
  "table.issue.optical": "Low optical margin",
  "table.issue.lowSignal": "Low signal",
};

// ── pt-BR — hand-written Brazilian telecom register ──
const ptBR: Record<string, string> = {
  // Nav
  "nav.features": "Recursos",
  "nav.examples": "Exemplos",
  "nav.intelligence": "Inteligência UK",
  "nav.contact": "Contato",
  "nav.requestPilot": "Solicitar piloto",
  "nav.openMenu": "Abrir menu",
  "nav.closeMenu": "Fechar menu",
  "nav.language": "Idioma",

  // Footer
  "footer.product": "Produto",
  "footer.resources": "Recursos",
  "footer.company": "Empresa",
  "footer.features": "Recursos",
  "footer.examples": "Exemplos",
  "footer.requestPilot": "Solicitar piloto",
  "footer.contact": "Contato",
  "footer.about": "Sobre",
  "footer.copyright": "© 2026 Pulso Technologies. Todos os direitos reservados.",
  "footer.tagline":
    "Telemetria somente leitura · multifabricante · seus dados continuam seus",
  "footer.legal":
    "Pulso Technologies Limited · Registrada na Inglaterra e País de Gales · empresa nº 17151141",

  // Common CTAs
  "common.requestPilot": "Solicitar piloto",
  "common.seeExample": "Ver um exemplo",
  "common.learnMore": "Saiba mais ↓",

  // Home: hero
  "home.hero.title1": "Sua rede está falando.",
  "home.hero.title2": "Agora você pode ouvir.",
  "home.hero.lead":
    "O Enlace lê a telemetria que suas OLTs já produzem — somente leitura — e a transforma em avisos antecipados: falhas de fibra, sinal em degradação, conexões fantasma, risco de churn. Mais de 12 fabricantes de OLT. Intervalos de 60 segundos. Um único binário estático de 8.7 MB.",
  "home.hero.sub":
    "O Enlace é o primeiro produto da Pulso Technologies, uma startup britânica de tecnologia para telecom. Estamos em pré-lançamento — integrando um pequeno número de operadoras de fibra como parceiras de validação.",
  "home.metric.binarySize": "Tamanho do binário",
  "home.metric.oltVendors": "Fabricantes de OLT",
  "home.metric.pollInterval": "Intervalo de coleta",
  "home.metric.audit": "Auditoria de 1.000 ONTs",
  "home.metric.protocols": "Protocolos",
  "home.metric.credentials": "Credenciais enviadas",
  "home.hero.figuresNote": "Números de validação interna.",

  // Home: problem
  "home.problem.eyebrow": "O PROBLEMA",
  "home.problem.title1": "Seu NOC é reativo.",
  "home.problem.title2": "Seus clientes sabem antes de você.",
  "home.problem.before": "Antes",
  "home.problem.after": "Depois",
  "home.problem.before.1": "Cliente liga reclamando",
  "home.problem.before.2": "Técnico despachado às cegas",
  "home.problem.before.3": "Sinal degradando sem detecção por semanas",
  "home.problem.before.4": "Sem visibilidade por ONT",
  "home.problem.before.5": "Visita técnica: £80–150 cada",
  "home.problem.before.6": "15–25% são “sem defeito encontrado”",
  "home.problem.after.1": "Monitoramento por ONT a cada 60 segundos",
  "home.problem.after.2": "Técnico recebe o diagnóstico antes de o cliente ligar",
  "home.problem.after.3": "Previsão contínua de falhas",
  "home.problem.after.4": "Painel com sinal, distância e tendência",
  "home.problem.after.5": "70% dos chamados resolvidos pelo suporte",
  "home.problem.after.6": "Risco de churn pontuado antes de o cliente ligar",

  // Home: how it works
  "home.how.eyebrow": "COMO FUNCIONA",
  "home.how.title1": "Um binário. Cinco minutos.",
  "home.how.title2": "Do cego ao preditivo.",
  "home.how.install.title": "Instalar",
  "home.how.install.desc": "Um comando. Menos de 10 segundos.",
  "home.how.configure.title": "Configurar",
  "home.how.configure.desc":
    "Um arquivo TOML. Adicione suas OLTs, defina o intervalo, pronto.",
  "home.how.collect.title": "Coletar",
  "home.how.collect.desc":
    "O agente conecta a cada OLT com o protocolo certo e extrai os dados por ONT.",
  "home.how.connect.title": "Conectar",
  "home.how.connect.desc":
    "Os dados fluem para Elasticsearch, Slack e webhooks. Integre com o que você já usa.",

  // Home: features
  "home.features.eyebrow": "RECURSOS",
  "home.features.title1": "17 módulos de inteligência.",
  "home.features.title2":
    "Seis destacados aqui. Cada um substitui um processo manual.",
  "home.feat.fault.title": "Detecção de falhas",
  "home.feat.fault.desc":
    "Corte de fibra vs queda de energia. Correlação multi-ONT na mesma porta PON. Classificação instantânea.",
  "home.feat.fault.metric": "Detecção a cada ciclo",
  "home.feat.signal.title": "Previsão de sinal",
  "home.feat.signal.desc":
    "Regressão linear sobre o histórico de dBm. Previsão contínua de falha por ONT.",
  "home.feat.signal.metric": "Previsão contínua",
  "home.feat.churn.title": "Pontuação de churn",
  "home.feat.churn.desc":
    "Sinal em degradação + microquedas = probabilidade estimada de churn em 90 dias e receita em risco — com cada premissa declarada no próprio relatório.",
  "home.feat.churn.metric": "Premissas declaradas",
  "home.feat.capacity.title": "Planejamento de capacidade",
  "home.feat.capacity.desc":
    "Acompanhamento da utilização das portas PON. Atenção acima de 50% quando o preenchimento se der em 6 meses; alerta acima de 75%, crítico acima de 90%.",
  "home.feat.capacity.metric": "Previsão de meses até lotar",
  "home.feat.vendor.title": "Multifabricante",
  "home.feat.vendor.desc":
    "Huawei, ZTE, FiberHome, Adtran, Nokia, Datacom e mais. Um único painel.",
  "home.feat.vendor.metric": "Mais de 12 fabricantes",
  "home.feat.diag.title": "Diagnóstico em tempo real",
  "home.feat.diag.desc":
    "Nível de sinal, distância, status e temperatura por ONT. Ficha de saúde do cliente para o suporte.",
  "home.feat.diag.metric": "Intervalos de 60s",

  // Home: vendor support
  "home.vendors.eyebrow": "SUPORTE A FABRICANTES",
  "home.vendors.title1": "Mais de 12 fabricantes de OLT.",
  "home.vendors.title2": "Todos os protocolos. Um só agente.",
  "home.vendors.col.vendor": "Fabricante",
  "home.vendors.col.models": "Modelos",
  "home.vendors.col.protocols": "Protocolos",
  "home.vendors.partial": "Suporte parcial",
  "home.vendors.alsoCollected": "Também coletado",
  "home.vendors.proto.adtran": "NETCONF/YANG + SNMP + importação CSV",
  "home.vendors.proto.mikrotik": "API RouterOS (PPPoE, BGP, tráfego)",
  "home.vendors.proto.radius": "UDP 1813 (sessões, bytes, duração)",
  "home.vendors.proto.tr069": "API GenieACS (WiFi, SNR, dispositivos)",
  "home.vendors.footnote":
    "Caminhos de coleta validados hoje: SNMP v2c/v3, NETCONF, API RouterOS, RADIUS passivo e TR-069 (GenieACS). CLI SSH e streaming gRPC estão implementados, mas ainda em validação contra firmware real.",

  // Home: trust
  "home.trust.eyebrow": "CONFIANÇA",
  "home.trust.title1": "Somente leitura e verificável.",
  "home.trust.title2": "Sem aprisionamento, por princípio.",
  "home.trust.1": "Somente leitura — o agente nunca escreve nos seus equipamentos",
  "home.trust.2": "Suas credenciais ficam na sua rede",
  "home.trust.3":
    "Independente de fabricante via padrões abertos (SNMP/NETCONF) — sem aprisionamento a um único fornecedor",
  "home.trust.4": "Seus dados continuam seus",
  "home.trust.5":
    "Explicamos aos seus engenheiros exatamente o que o agente faz — somente leitura — para que possam verificar sem que a gente entregue o código-fonte",

  // Home: vs Calix
  "home.calix.eyebrow": "COMPARAÇÃO",
  "home.calix.title1": "O Calix Cloud cobra por assinante.",
  "home.calix.title2": "E só funciona com hardware Calix.",
  "home.calix.col.feature": "Recurso",
  "home.calix.row.vendors.f": "Fabricantes de OLT",
  "home.calix.row.vendors.c": "Somente Calix",
  "home.calix.row.vendors.e": "Mais de 12 fabricantes",
  "home.calix.row.telemetry.f": "Telemetria por ONT",
  "home.calix.row.telemetry.c": "Sim",
  "home.calix.row.telemetry.e": "Sim",
  "home.calix.row.predictive.f": "Manutenção preditiva",
  "home.calix.row.predictive.c": "Sim",
  "home.calix.row.predictive.e": "Sim",
  "home.calix.row.readonly.f": "Somente leitura / sem aprisionamento",
  "home.calix.row.readonly.c": "Fechado",
  "home.calix.row.readonly.e": "Sim — padrões abertos",
  "home.calix.row.lockin.f": "Aprisionamento ao fabricante",
  "home.calix.row.lockin.c": "Total",
  "home.calix.row.lockin.e": "Nenhum",
  "home.calix.row.pricing.f": "Modelo de cobrança",
  "home.calix.row.pricing.c": "Por assinante",
  "home.calix.row.pricing.e": "Piloto gratuito no lançamento",
  "home.calix.row.install.f": "Instalação",
  "home.calix.row.install.c": "Projeto de onboarding na nuvem",
  "home.calix.row.install.e": "Um comando, minutos",
  "home.calix.row.creds.f": "Credenciais e gestão",
  "home.calix.row.creds.c": "Ficam na nuvem do fabricante",
  "home.calix.row.creds.e": "Ficam na sua rede",

  // Home: pilot
  "home.pilot.eyebrow": "PARCEIRAS DE LANÇAMENTO",
  "home.pilot.title": "Piloto gratuito para parceiras de lançamento",
  "home.pilot.lead":
    "Estamos integrando um pequeno número de operadoras de fibra para validar o Enlace em redes reais — gratuito durante o piloto, com preço preferencial no lançamento.",

  // Home: closing CTA
  "home.cta.title1": "Sua rede tem os dados.",
  "home.cta.title2": "Pare de voar às cegas.",
  "home.cta.lead":
    "Veja um exemplo do que o Enlace encontra e depois solicite um piloto para rodá-lo na sua própria rede.",

  // Features page
  "features.eyebrow": "Recursos da plataforma",
  "features.hero.title1": "Tudo o que o Enlace faz pela sua rede.",
  "features.hero.title2": "17 módulos. Um agente. Zero achismo.",
  "features.hero.lead":
    "O agente traz 17 módulos de análise — detecção e localização de falhas, previsão de fim de vida de sinal e laser, saúde pré-FEC, pontuação de churn, detecção de ONTs fantasma e rogue, orçamento óptico, reflectância, correlação com o clima, flapping, capacidade, saúde de SFP, pontuação de impacto e geração de chamados. Os cinco destacados abaixo são os que você usará no dia a dia. Sem módulos avulsos, sem upsell — cada módulo vem em cada instalação.",

  "features.fault.eyebrow": "DETECÇÃO DE FALHAS",
  "features.fault.title":
    "Corte de fibra vs queda de energia — classificado a cada ciclo de coleta.",
  "features.fault.desc":
    "O agente monitora cada ONT em cada porta PON a cada ciclo de coleta. Quando ONTs caem, ele correlaciona o padrão para classificar o tipo de falha — sem análise humana.",
  "features.fault.1":
    "Várias ONTs offline na mesma porta PON = corte de fibra (CRÍTICO)",
  "features.fault.2": "Uma ONT offline, vizinhas no ar = falha de CPE (MENOR)",
  "features.fault.3":
    "ONTs em portas diferentes, mesma região = queda de energia (MAIOR)",
  "features.fault.4":
    "Evidência de dying-gasp por ONT separa queda de energia de dano na fibra",
  "features.fault.5":
    "Potência Rx caindo abaixo de -27 dBm = degradação de sinal (ALERTA)",

  "features.signal.eyebrow": "PREVISÃO DE SINAL",
  "features.signal.title": "Saiba quais ONTs vão falhar antes que falhem.",
  "features.signal.desc":
    "O agente armazena o histórico de potência Rx por ONT e roda regressão linear sobre a tendência do sinal. Ele extrapola a taxa atual de degradação até o limiar de falha, produzindo uma previsão contínua de dias até a falha.",
  "features.signal.1":
    "Coleta a potência Rx (dBm) a cada ciclo e guarda a série temporal por ONT",
  "features.signal.2":
    "A regressão linear calcula a inclinação (dBm/dia) com corte de confiança por R²",
  "features.signal.3":
    "Atenção em -0,05, alerta em -0,10, crítico em -0,20 dBm/dia — ou qualquer ONT abaixo de -27 dBm",
  "features.signal.4":
    "Estimativa de causa com base no padrão de degradação (conector, curvatura, emenda)",

  "features.capacity.eyebrow": "PLANEJAMENTO DE CAPACIDADE",
  "features.capacity.title": "Saiba quando suas portas PON vão saturar.",
  "features.capacity.desc":
    "O agente acompanha a quantidade de ONTs, a utilização de banda e a ocupação dos splitters em cada porta PON. Você recebe alertas antes de faltar capacidade — não depois de uma instalação frustrada.",
  "features.capacity.1":
    "ONTs por porta PON — atenção acima de 50% quando lotar em 6 meses, alerta acima de 75%, crítico acima de 90%",
  "features.capacity.2":
    "Ocupação de splitter por porta — razões configuradas ou inferidas, de 1:2 a 1:128",
  "features.capacity.3":
    "Projeção da tendência de crescimento — meses até a capacidade máxima",
  "features.capacity.4":
    "Contadores de tráfego por ONT já coletados hoje; alertas de Gbps por porta estão no roadmap",

  "features.vendor.eyebrow": "MULTIFABRICANTE",
  "features.vendor.title": "Mais de 12 fabricantes de OLT. Uma visão unificada.",
  "features.vendor.desc":
    "A maioria dos provedores usa equipamentos de vários fabricantes. O Enlace normaliza os dados de todos em um único schema — mesmas métricas, mesmos alertas, seja a OLT Huawei, ZTE ou BDCOM.",
  "features.vendor.1": "Detecta o fabricante automaticamente pelo sysObjectID do SNMP",
  "features.vendor.2": "Carrega o parser correto por fabricante automaticamente",
  "features.vendor.3":
    "Sem aprisionamento — misture Huawei e ZTE na mesma rede",
  "features.vendor.4": "Pronto para aquisições: unifique as duas redes já no primeiro dia",

  "features.diag.eyebrow": "DIAGNÓSTICO EM TEMPO REAL",
  "features.diag.title": "Fichas de saúde por ONT para o suporte.",
  "features.diag.desc":
    "Quando um assinante liga, seu atendente precisa de respostas em segundos. O Enlace entrega uma ficha de saúde completa para cada ONT — sem SSH na OLT, sem comandos de CLI, sem adivinhação.",
  "features.diag.1": "Número de série, modelo, firmware, potência Rx/Tx, distância",
  "features.diag.2": "Temperatura, tráfego de entrada/saída, uptime, tendência de sinal",
  "features.diag.3": "12 pontos de dados por ONT a cada ciclo de coleta",
  "features.diag.4": "Schema normalizado independentemente do fabricante da OLT",

  "features.cta.title": "Veja em ação.",
  "features.cta.lead":
    "Veja um relatório de exemplo — pontuações de sinal, detecção de falhas, conexões fantasma e risco de churn — e depois solicite um piloto para rodar o Enlace na sua própria rede.",

  // About page
  "about.eyebrow": "Sobre",
  "about.hero.title1": "Feito para provedores.",
  "about.hero.title2": "Construído em Rust.",
  "about.hero.lead":
    "A Pulso Technologies constrói inteligência de telemetria para operadoras de fibra. O Enlace é nosso primeiro produto — um agente de telemetria que dá aos provedores a visibilidade por ONT que eles nunca tiveram.",
  "about.mission.title":
    "Acreditamos que todo provedor merece a mesma inteligência de rede que as operadoras Tier 1 têm.",
  "about.mission.body":
    "Os dados já estão nas suas OLTs. Nós só ajudamos você a usá-los.",
  "about.tech.eyebrow": "Por dentro",
  "about.tech.rust.title": "Construído em Rust",
  "about.tech.rust.body":
    "Por desempenho e confiabilidade. Mais de 500 testes (528 passando).",
  "about.tech.lines.body": "Linhas de Rust (~39,500 incluindo testes).",
  "about.tech.readonly.title": "Somente leitura e verificável",
  "about.tech.readonly.body":
    "Nunca escreve nos seus equipamentos. Explicamos aos seus engenheiros exatamente o que ele faz.",
  "about.contact.eyebrow": "Fale conosco",
  "about.contact.emailLabel": "E-mail",
  "about.legal":
    "Pulso Technologies Limited. Registrada na Inglaterra e País de Gales, empresa nº 17151141.",

  // Examples page
  "examples.eyebrow": "Saída de exemplo",
  "examples.hero.title": "O que uma auditoria do Enlace produz",
  "examples.hero.lead":
    "O Enlace lê a telemetria que suas OLTs já produzem e a transforma em um relatório em linguagem clara: uma nota de saúde da frota, as falhas que valem ação e uma tabela por ONT que você pode ordenar e filtrar. Abaixo, um exemplo representativo.",
  "examples.banner.label": "Saída de exemplo",
  "examples.banner.text":
    "— gerada pela validação interna do Enlace sobre dados representativos. Não são dados de clientes.",
  "examples.report.eyebrow": "O relatório",
  "examples.report.title": "Saúde da frota, achados e cada ONT",
  "examples.report.lead":
    "Clique em um achado para filtrar a tabela de ONTs. 52 ONTs em quatro ramais PON, analisadas em uma janela de 7 dias — este é o JSON literal que o motor atual produziu a partir da nossa amostra de validação, incluindo as próprias notas de cobertura.",
  "examples.report.figuresNote":
    "Números de validação interna sobre dados representativos.",
  "examples.found.eyebrow": "O que ele encontrou",
  "examples.found.title":
    "Seis achados — incluindo o que ele se recusou a afirmar",
  "examples.find.1.title": "Duas quedas de ramal, classificadas por evidência",
  "examples.find.1.detail":
    "Cinco ONTs em CTP-0/4 e quatro em CTP-0/2 caíram dentro da janela de detecção. Em CTP-0/4, duas enviaram dying gasp e três ficaram em silêncio — evidência mista, então o motor diz “Mista” em vez de chutar energia vs fibra. A evidência de gasp por ONT fica anexada a cada falha.",
  "examples.find.2.title": "Risco de churn: 3 clientes, premissas declaradas",
  "examples.find.2.detail":
    "Três assinantes de −25 a −29 dBm com sinal em degradação — probabilidade estimada de 35% de churn em 90 dias e ~£378/ano de receita em risco cada. Cada número carrega suas premissas no próprio relatório (ARPU £89.90, modelo de probabilidade), então o ROI é auditável, não afirmado.",
  "examples.find.3.title": "Um chamado proativo, pronto para despachar",
  "examples.find.3.detail":
    "Os três riscos de churn foram reunidos em um único chamado P2 com SLA de 5 dias: linhas de evidência por ONT, uma ação recomendada, £1,133/ano em risco vs £450 de conserto estimado — um ROI de 2.5× com as premissas de custo impressas no chamado.",
  "examples.find.4.title": "Tendência de queda na planta compartilhada em CTP-0/1",
  "examples.find.4.detail":
    "O ramal PON inteiro está em queda a −0.74 dB/semana — cerca de 13 semanas até o limiar no ritmo atual. Uma tendência em toda a frota aponta para a planta compartilhada (splitter, alimentador, SFP da OLT), não para o equipamento de um único cliente.",
  "examples.find.5.title": "Três enlaces operando com orçamento óptico marginal",
  "examples.find.5.detail":
    "A análise por modelo de perdas de todos os 52 enlaces encontrou três com ~8 dB de perda a mais do que a distância e a razão de splitter explicam — provável perda excessiva de conector, sinalizada com a conta de esperado vs medido.",
  "examples.find.6.title": "O que ele se recusou a afirmar",
  "examples.find.6.detail":
    "Esta amostra não tem colunas de FEC ou bias do laser, então o relatório informa “0 de 52 ONTs cobertas” para essas análises em vez de sugerir saúde. Nenhuma ONT fantasma, nenhum flapping, nenhuma ONT rogue foi sinalizada — a ausência de um achado é relatada como ausência de evidência, nunca como aprovação.",
  "examples.cta.title": "Quer isso para a sua rede?",
  "examples.cta.lead":
    "Estamos integrando um pequeno número de operadoras de fibra como parceiras de validação. O Enlace roda somente leitura contra as OLTs que você já tem.",

  // Report explorer / HealthScore / FindingsSidebar / OntTable
  "report.findings": "Achados",
  "report.clearFilter": "Limpar filtro",
  "report.noFindings": "Nenhum achado",
  "report.cat.faults": "Eventos de falha",
  "report.cat.churn": "Risco de churn",
  "report.cat.ghosts": "Clientes fantasma",
  "report.cat.capacity": "Capacidade PON",
  "report.cat.sfp": "Tendência em toda a PON",
  "report.cat.rogue": "Suspeitas de ONT rogue",
  "report.cat.tickets": "Chamados abertos",
  "report.cat.flapping": "ONTs em flapping",
  "report.cat.weather": "Correlação com clima",
  "report.cat.reflectance": "Reflectância",
  "report.cat.optical": "Orçamento óptico",
  "report.sub.severe": "{n} graves (modelo presumido)",
  "report.sub.monitoring": "monitorando",
  "report.sub.ghosts": "vazamento de receita detectado",
  "report.sub.capacity.alerting": "{n} portas em alerta",
  "report.sub.capacity.alerting.one": "{n} porta em alerta",
  "report.sub.capacity.tracked": "{n} portas monitoradas · pico {peak}%",
  "report.sub.sfp": "degradação da planta compartilhada",
  "report.sub.rogue": "precisa de confirmação do fabricante",
  "report.sub.flapping": "conexões instáveis",
  "report.sub.weather": "falhas ligadas ao ambiente",
  "report.sub.reflectance": "problemas de conector",
  "report.sub.optical": "de {n} enlaces avaliados",

  "report.health.title": "Nota de saúde da frota",
  "report.health.healthy": "SAUDÁVEL",
  "report.health.attention": "REQUER ATENÇÃO",
  "report.health.critical": "CRÍTICO",
  "report.stat.faults": "Falhas",
  "report.stat.degrading": "Degradando",
  "report.stat.ghosts": "ONTs fantasma",
  "report.stat.capacity": "PON 80%+",
  "report.stat.healthy": "Saudáveis",
  "report.stat.avgRx": "Rx médio dBm",

  "report.cover.title": "Cobertura da análise — declarada, não presumida",
  "report.cover.fec": "Saúde pré-FEC — {a}/{b} ONTs cobertas",
  "report.cover.laser":
    "Fim de vida do laser — {a}/{b} ONTs reportando corrente de bias",
  "report.cover.laser.none":
    "Sem telemetria de corrente de bias neste conjunto de dados, então nenhuma previsão de laser foi feita — a ausência de um achado não é evidência de saúde.",
  "report.cover.laser.some":
    "{analyzed} analisadas, {flagged} sinalizadas, {detrended} com detrend de temperatura.",
  "report.cover.rogue": "Varredura de ONT rogue — {n} portas sinalizadas",
  "report.cover.rogue.one": "Varredura de ONT rogue — {n} porta sinalizada",
  "report.cover.rogue.intro":
    "A pontuação passiva de corrupção upstream com múltiplas vítimas rodou em todas as portas PON. ",
  "report.cover.rogue.none": "Nenhum evento suspeito de rogue nesta janela.",
  "report.cover.rogue.some":
    "Os candidatos exigem confirmação nativa do fabricante.",

  "table.search": "Buscar por serial...",
  "table.col.serial": "Serial",
  "table.col.pon": "Porta PON",
  "table.col.rx": "Rx dBm",
  "table.col.status": "Status",
  "table.col.issue": "Problema",
  "table.noMatch": "Nenhuma ONT corresponde ao filtro atual",
  "table.prev": "Anterior",
  "table.next": "Próxima",
  "table.page": "Página {page} de {total}",
  "table.status.offlineLos": "OFFLINE (LOS)",
  "table.status.lowSignal": "SINAL BAIXO",
  "table.issue.rogue": "Suspeita rogue",
  "table.issue.fault": "Afetada por falha",
  "table.issue.ghost": "Cliente fantasma",
  "table.issue.degrading": "Degradando ({days}d, ~{pct}% churn est.)",
  "table.issue.flapping": "Flapping",
  "table.issue.reflectance": "Problema de reflectância",
  "table.issue.optical": "Margem óptica baixa",
  "table.issue.lowSignal": "Sinal baixo",
};

const DICTIONARIES: Record<Locale, Record<string, string>> = {
  en,
  "pt-BR": ptBR,
};

const STORAGE_KEY = "enlace.site.locale";

type TParams = Record<string, string | number>;

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, params?: TParams) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function interpolate(str: string, params?: TParams): string {
  if (!params) return str;
  return str.replace(/\{(\w+)\}/g, (m, k) =>
    k in params ? String(params[k]) : m
  );
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // localStorage read through useSyncExternalStore: the server snapshot is
  // null (English), and the client value applies right after hydration.
  const stored = useSyncExternalStore(
    subscribeLocalStorage,
    () => localStorageGet(STORAGE_KEY),
    () => null
  );
  const locale: Locale = stored === "pt-BR" ? "pt-BR" : "en";

  const setLocale = useCallback((l: Locale) => {
    localStorageSet(STORAGE_KEY, l);
  }, []);

  // Keep <html lang> in sync so screen readers and Google see the real locale.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const t = useCallback(
    (key: string, params?: TParams) =>
      interpolate(DICTIONARIES[locale][key] ?? en[key] ?? key, params),
    [locale]
  );

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
