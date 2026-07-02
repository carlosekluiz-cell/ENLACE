# The UK Full-Fibre Market: From Building to Operating

### A market dossier for Community Fibre
*Prepared by Pulso Technologies Limited · enlace.network · all figures sourced from public data*

---

## Executive summary

The UK's full-fibre build-out is essentially complete as a land-grab. **78–81% of premises now have FTTP available** and 87% are gigabit-capable. The capital that drove a decade of digging has dried up, the altnet sector lost **£1.5bn in 2024**, and consolidation has moved from forecast to fact. The defining question for every network has shifted from *"how fast can we pass homes?"* to *"how profitably can we run and retain the ones we have?"*

Community Fibre is one of the few operators that has already crossed into that second phase — profitable, with sector-leading take-up, and now resuming build from a position of strength. This dossier sets out the market context, why operational efficiency is the decisive lever in 2026, and the open-data foundation that makes UK fibre intelligence possible.

---

## 1. Coverage: the build is largely done

| Metric | Latest figure | Source |
|---|---|---|
| UK premises with FTTP available | **78%** (Ofcom) / **81.3%** (Point Topic) | Ofcom Connected Nations 2025 (data Jul 2025, pub Nov 2025); Point Topic Q4 2025 |
| Gigabit-capable premises | **87%** (~26m) | Ofcom CN 2025 |
| Gigabit take-up where available | **56%** (up from 49%) | Ofcom CN 2025 |
| Openreach FTTP (ready for service) | **20.68m premises (62%)**; target 25m by end-2026 | ThinkBroadband, Dec 2025 |
| Altnets collectively | **19.7m premises passed (+20% YoY); 3.5m+ live connections** | INCA / Point Topic "State of the Altnets 2026" |

*Note: the altnet 19.7m overlaps heavily with Openreach/nexfibre (overbuild) and is not additive to unique national coverage.*

The UK now averages **2.44 fibre networks per household**, rising toward 2.78 by 2027; 10.9m premises have 2+ FTTP networks. The easy, unpassed premises are gone — what remains is overbuilt, contested ground.

---

## 2. The altnet shakeout is here

The economics caught up with the build:

- The largest altnets posted **combined losses of £1.5bn in 2024** (£1.3bn in 2023), with financing costs averaging **121% of revenue** and accumulated sector debt near £9bn (Enders Analysis; BDO 2025).
- New debt financing **collapsed to ~£170m in early 2025**; ~96% of altnets were weighing M&A in H1 2025 (AlixPartners).
- Consolidation, now real: **Netomnia + Brsk merged** (2024); **nexfibre is acquiring Netomnia** (~£2bn, announced Feb 2026 — the largest altnet deal yet); **CityFibre** bought Lit Fibre and Connexin's infrastructure and raised £2.3bn (Jul 2025). Real exits: Lightspeed, F&W Networks, G.Network.

Enders' Karen Egan: *"It's difficult to see a scenario in which retail altnets generate cash returns, even before interest costs on their debt."*

---

## 3. The maths that now governs survival

- **Viability needs ~40% take-up.** The sector average is **~18%**. First-year take-up runs 9–19%; mature (24+ month) networks reach 30–50% (Eight Advisory).
- **ARPU sits below breakeven.** Altnet ARPU is **£25–35/mo**; Point Topic estimates **~£45** is needed to break even — and has warned altnets "may have to hike prices to survive."
- **Cost per premises passed tripled:** £397 (2022) → £1,061 (2025); net debt per connected home averages **>£4,000** (BDO; AlixPartners).
- **Growth is now a zero-sum switching war.** Openreach lost ~860k lines in the year to March 2025, roughly matched by altnet net adds — amplified by One-Touch Switching, which pushed household switching to ~18% in 2024.

When take-up, ARPU and cost-per-home are all under pressure simultaneously, the only levers left are **operational: opex per connected premise, and churn.** Both are exactly what proactive network telemetry moves.

---

## 4. Community Fibre's position

Community Fibre is the clearest "winner" archetype in this shakeout:

- **~1.4m London premises passed**, 4th-largest UK altnet by coverage and **London's largest dedicated full-fibre provider** (31 of 32 boroughs).
- **~450k customers** (Jan 2026), **~32% take-up — nearly double the sector average** and claimed No.1 among major altnets by penetration.
- **FY25 revenue £113m (+48%), adjusted EBITDA ~£50m, cash-positive**, targeting >£100m annualised EBITDA in 2026.
- **Resumed network build in May 2026**, targeting 2m+ premises; backed by Warburg Pincus, DTCP, Amber Infrastructure and RPMI Railpen (>£1.3bn funding).
- Best-rated major UK ISP on Trustpilot (4.7/5).
- Now **wholesales its network to VodafoneThree** (up to 1.3m London homes) — which raises the stakes on network quality: a partner's customers now ride the same fibre.

Community Fibre has the rare luxury of optimising the *operate* phase from a profitable base. The opportunity is to protect a premium reputation and a profitable book — not to fix a broken network.

---

## 5. The open-data foundation

UK fibre intelligence can be built almost entirely on open, free (OGL) data — the same method Pulso first proved in Brazil on Anatel/IBGE data, ported to UK sources:

| Source | What it provides | Licence |
|---|---|---|
| **Ofcom Connected Nations** | Gigabit-capable coverage at postcode level; full-fibre availability & **take-up** at local-authority level (aggregate of all operators, **not** per-operator) | OGL, free |
| **OS Open UPRN** | Every addressable premises in GB as a point (~40m) | OGL, free |
| **OS Code-Point Open** | All ~1.7m GB postcodes with coordinates | OGL, free |
| **ONS NSPL / Census 2021** | Postcode→geography lookups; population & household counts per Output Area | OGL, free |
| **BDUK / Project Gigabit** | UPRN-level gigabit status + subsidy classification (White/Grey/Black) | OGL, free |
| **ThinkBroadband** | UK availability map as open data | Map open |
| *(Openreach PIA — duct/pole)* | *Restricted to contracted operators* | *gated* |

A UPRN-keyed spine, enriched with Ofcom coverage and BDUK subsidy status, gives a premises-level picture of where fibre is, where it isn't, and where it's already planned — without a single proprietary feed.

---

## 6. Why this is the moment for operational telemetry

The industry's own language has flipped from build to operate:

> INCA: *"building value, not just fibre."* · BDO: *"build, build, build" → "sell, sell, sell."* · Intelligens Consulting: *"2026 will be a make-or-break year."*

The UK has run out of road on "build more," and balance sheets are forcing the sector onto "run what you've built, better." The two levers that decides — **lower opex per connected premise and lower churn through faster, pre-emptive fault resolution** — are precisely what the Enlace telemetry engine is built to move. The market context isn't a backdrop to the pilot; it *is* the case for it.

---

*Sources: Ofcom Connected Nations 2025; Point Topic Q4 2025; INCA/Point Topic State of the Altnets 2026; Enders Analysis (Nov 2025); BDO UK Altnets (2025); AlixPartners (2025); Eight Advisory (Jul 2025); ThinkBroadband (Dec 2025); ISPreview; Advanced Television; Comms Business; Companies House. Figures current to mid-2026; confirm against the latest editions before publication.*
</content>
