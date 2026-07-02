# Pulso Agent — Research & Strategy Document
## Compiled March 15, 2026

---

## 1. MARKET OPPORTUNITY

### Brazilian ISP Ecosystem
- 128,091 licensed ISPs (Anatel), ~11,800 active
- 54,429,216 broadband subscribers across 5,570 municipalities
- 75.3% FTTH, R$50 billion/year market
- 93.3% have fewer than 5,000 subscribers
- Market consolidating: Vero, Brasil TecPar, Alares making massive acquisitions
- Starlink: 656,413 subscribers in 5,433 municipalities — fastest growing

### Global ISP Market
- 100,000+ small/medium ISPs worldwide using MikroTik + Chinese OLTs
- Key markets: Indonesia (800+), India (30,000+), Nigeria (200+), Philippines (1,500+), Mexico (2,000+), Turkey, Eastern Europe, Sub-Saharan Africa
- MikroTik is dominant router in developing countries (150+ countries)
- Chinese OLTs (Huawei, ZTE, FiberHome) dominate globally

### Competitive Landscape — NOBODY Does This
- **Calix** ($3B, USA): Closest concept but vendor-locked to Calix hardware only, $30K+/year, US-only
- **Preseem** (Canada): QoE for WISPs only, no GPON, $0.50/sub/month
- **SmartOLT** (Romania): OLT management only, no intelligence, no MikroTik, no predictions
- **Support Robotics** / **RouteThis** (UK/Canada): WiFi diagnostics only
- **No company globally** combines: vendor-agnostic OLT monitoring + MikroTik + RADIUS + WiFi + market intelligence + predictive analytics

---

## 2. TECHNICAL ARCHITECTURE

### Protocols Used (ALL open standards, zero licensing)
- **SNMP v2c/v3** (RFC 3416-3418): Universal, works on every OLT
- **SSH** (RFC 4253): CLI scraping for data not in SNMP
- **NETCONF/YANG** (RFC 6241): Datacom DmOS, Huawei MA5800, ZTE C600+
- **MikroTik RouterOS API**: Binary protocol, TCP 8728, fully documented
- **RADIUS** (RFC 2866): Accounting packets for session tracking
- **TR-069/CWMP**: Via GenieACS (open source) for CPE/WiFi management
- **REST API**: Ubiquiti UISP at /nms/api/v2.1/

### OLT Vendor Coverage (100% of Brazilian market)
| Vendor | Enterprise OID | SNMP | SSH | NETCONF | Market Share |
|--------|---------------|------|-----|---------|-------------|
| Huawei | .2011 | Full | VRP | Yes (MA5800) | ~40% |
| ZTE | .3902 | Full | Cisco-like | Yes (C600+) | ~30% |
| FiberHome | .5875 | Full | Directory | No | ~15% |
| Intelbras | .5875/.13464 | Full | Both | No | Very common |
| Datacom | .3709 | Full | Junos-like | Yes | Growing |
| Parks | .6771 | Enterprise | Yes | No | Common |
| BDCOM | .3320 | Partial | Cisco-like | No | Budget |
| VSOL | Custom | Off by default | Yes | No | Budget |
| CDATA | .34592 | Full (LibreNMS) | Huawei-like | No | Budget |
| Ubiquiti | .41112 | Basic | Limited | No | Niche |

### Rust Ecosystem
- **SNMP**: rasn-snmp (pure Rust ASN.1/BER), snmp_mp, snmp_usm for v3
- **SSH**: russh (async, Tokio-based, maintained by Microsoft/Eugeny)
- **NETCONF**: Build on russh + quick-xml (no mature crate exists)
- **gRPC**: tonic (for future Pulso Cloud communication)
- **HTTP**: reqwest (for cloud telemetry upload + Ubiquiti REST API)
- **SQLite**: rusqlite with bundled feature (offline buffer)

### Why Rust
- Single static binary (~8 MB), zero dependencies
- 5-10 MB RAM for 10,000 SNMP endpoints (Python: 500+ MB)
- No garbage collector = predictable latency for polling
- Cross-compilation: x86_64, ARM64 (Raspberry Pi), MIPS
- Virtually unknown in telecom — competitive moat
- Performance: millions of data points/minute on single server

---

## 3. ADDITIONAL INTEGRATIONS (Open Data)

### Already Achievable Without ISP Connection
- **Ookla Open Data**: Global speedtest tiles on AWS S3, CC BY-NC-SA 4.0
- **M-Lab NDT**: Largest open internet measurement dataset, CC0 license
- **RIPE Atlas**: 12,000+ probes, free API, latency/traceroute data
- **PeeringDB**: Free REST API, peering policies, IXP memberships
- **IX.br Looking Glass**: BGP routing tables for all Brazilian IXPs
- **RouteViews**: BGP archive data, CC BY 4.0
- **Hurricane Electric BGP Toolkit**: ASN analysis, prefix reports

### From the Agent (Requires ISP Installation)
- **MikroTik API**: PPPoE sessions, BGP, traffic, CPU/memory
- **RADIUS accounting**: Session lifecycle, churn patterns
- **TR-069/GenieACS**: WiFi diagnostics, channel optimization
- **SNMP on OLTs**: ONT signal, status, PON utilization

---

## 4. CUSTOMER SERVICE & PREDICTIVE REPAIR

### Customer Health Card (for non-technical support staff)
- Instant per-customer view: ONT signal, PPPoE status, WiFi health
- Color-coded: 🟢 Green (OK), 🟡 Yellow (attention), 🔴 Red (problem)
- One-click actions: optimize WiFi, reboot ONT, escalate to technician
- **70% of support calls resolved by receptionist without truck roll**

### Predictive Analytics
1. **Signal degradation**: Linear regression on ONT rx_power over time
   - Predicts failure threshold (-28 dBm) crossing date
   - Generates maintenance schedule before customer notices
2. **Capacity forecasting**: PON port utilization trend analysis
   - Predicts saturation date at current growth rate
   - Recommends expansion timing and cost
3. **Churn prediction**: RADIUS session duration trends + market data
   - Flags customers with declining usage
   - Cross-references with Starlink/competitor activity

### Financial Impact (5,000-subscriber ISP)
- Truck roll reduction: R$21,000/month saved
- Preventive vs reactive maintenance: R$8-12K/month saved
- Churn reduction (20-30%): R$7-10.5K/month saved
- João (technician) freed for installations: +R$960/month growing revenue
- **Total savings: R$36-43K/month vs Pulso subscription of R$2-5K/month**

---

## 5. M&A DUE DILIGENCE AUTOMATION

### Automated (from Pulso's 37+ sources)
- Regulatory: Anatel licenses, PGFN debt, CEIS/CNEP sanctions
- Market: Subscriber count, growth, HHI, competitive position
- Quality: RQUAL scores, Ookla benchmarks, consumer complaints
- Ownership: Receita Federal graph (783,003 links)
- Financial: BNDES loans, CAGED employment
- Network: ASN, BGP, peering (PeeringDB, IX.br)

### Agent-Enhanced (requires installation on target)
- ONT signal distribution across entire customer base
- PON port utilization and capacity headroom
- MikroTik health, BGP diversity, bandwidth utilization
- Real vs reported subscriber comparison (PPPoE vs Anatel STEL)
- CAPEX forecast: ONT replacements, OLT expansion, fiber repairs

---

## 6. OPEN-SOURCE STRATEGY

### What to Open-Source (Apache 2.0)
- The Pulso Agent binary + all source code
- Vendor YAML device profiles (community-contributable)
- SNMP simulator data files for testing
- Installation scripts and documentation

### What Stays Proprietary
- Intelligence engine (data fusion, predictions, scoring algorithms)
- Data pipelines (42 pipelines, 37+ government sources)
- Database schema (69 tables, cross-reference logic)
- RF propagation engine (Rust, biome-specific corrections)
- Cloud backend, frontend, API layer
- Market intelligence modules

### Why This Works
- Agent without cloud = generic SNMP tool (already exists in dozens of alternatives)
- Agent WITH cloud = world's first ISP intelligence platform
- Open-source builds trust, enables community contributions, maximizes adoption
- Data network effect: more agents = better benchmarking = more value = more agents
- Proven model: Grafana ($250M+ revenue), Datadog ($26B market cap), Elastic ($1B+)

---

## 7. ESG & IMPACT

### Social Impact
- 16,375 schools without internet (1,029,482 students) — identifiable by Pulso
- R$2.8 billion FUST fund for school connectivity
- 451 municipalities with monopoly — expansion opportunities
- SDG 4 (Education), SDG 9 (Infrastructure), SDG 10 (Reduced Inequality)

### EU/ESG Regulatory Connection
- CSRD (Corporate Sustainability Reporting Directive): Large operators in scope
- Supply chain reporting requirements will cascade to ISP partners
- Pulso can automate ESG metrics: energy/subscriber, digital inclusion, school connectivity
- Relevant for international expansion and impact investor fundraising

---

## 8. PROOF OF CONCEPT — No ISP Access Needed

### Option A: SNMP Simulator (instant, free)
- snmpsim (Python, BSD license) replays recorded SNMP walks
- One ISP runs `snmpwalk` (2 minutes), emails text file
- Agent demonstrated against simulated multi-vendor OLTs

### Option B: Used OLT (R$1,500-3,000)
- ZTE C320 or FiberHome AN5516 on MercadoLivre
- Real hardware proof with actual optical power readings
- Complete demo: agent → Pulso dashboard with market intelligence overlay

### All OLT documentation publicly available
- Huawei MIBs: LibreNMS GitHub repo + gponsolution.com
- ZTE MIBs: zte_c320_monitoring GitHub repo
- FiberHome: snmp-fiberhome GitHub repo (MIT license)
- Datacom: LibreNMS native support
- Parks: Zabbix templates on GitHub
- CDATA: LibreNMS FD-OLT-MIB

---

## 9. TIMELINE

### Month 1-2: Build Agent
- SNMP poller (Huawei/ZTE/FiberHome) + MikroTik API client
- Local SQLite buffer + HTTPS cloud transport
- Test against snmpsim simulators

### Month 3: Expand Coverage
- Add remaining vendors (Datacom, Parks, BDCOM, VSOL, CDATA)
- Generic SNMP fallback for unknown OLTs
- Diagnostics engine + basic predictions

### Month 4-5: Beta
- 10-20 ISPs via Raul's network / ABRINT
- Free during beta, collect feedback
- Refine customer health cards based on support staff usage

### Month 6: Launch
- Open-source agent on GitHub
- Free tier + paid intelligence tiers on pulsonetwork.com.br
- Announce: Hacker News, r/rust, Brasil Peering Forum, Under-Linux

### Month 7-12: Scale
- Target 500-1,000 agents deployed
- Add benchmarking (ISP vs industry average)
- Add M&A dossiê automation
- Futurecom 2026 presentation

---

## 10. REVENUE MODEL

### Pricing Tiers
- **Free**: Agent + basic monitoring + 24h data retention
- **Starter** (R$99/mês): Raio-X + basic intelligence
- **Provedor** (R$1,500/mês): Agent intelligence + competitive data + PDF reports
- **Profissional** (R$5,000/mês): Full API + M&A + all modules + predictions
- **Enterprise** (sob consulta): SSO/SAML, SLA 99.9%, custom integrations

### Conservative Projections
- 20% agent penetration (2,360 ISPs) × 5% conversion = 118 paying
- Average R$1,500/month = R$2.1M ARR Year 1
- With sales-assisted 10% conversion: R$5-10M ARR Year 2-3
- International expansion (Year 2+): 100K+ addressable ISPs globally
