# London Full-Fibre Conversion Intelligence
### A teaser — built from open data, computed live
*Pulso Technologies Limited · enlace.network · generated from Ofcom Connected Nations 2025 (data as of 31 Jul 2025)*

---

## The headline

> **1.89 million** premises across London can already receive full fibre — **but haven't taken it.**
> That's the conversion opportunity sitting on networks that are *already built*.

Across the 33 London boroughs:

| | |
|---|---|
| Total premises | **4,048,077** |
| Premises with full fibre available | **3,075,077** |
| Full-fibre take-up (premises-weighted, % of coverage) | **38.4%** |
| **Premises full-fibre-available but not converted** | **1,893,171** |

The build is largely done. The growth is in **converting passed premises** — and the data shows exactly where the gap is deepest.

---

## Where the opportunity is biggest (by absolute unconverted premises)

| Borough | Premises | Full fibre available | Take-up (% of coverage) | **Unconverted FF premises** |
|---|--:|--:|--:|--:|
| Westminster | 165,034 | 86.6% | 28% | **102,907** |
| Camden | 123,412 | 85.7% | 22% | **82,498** |
| Lambeth | 156,960 | 81.7% | 38% | **79,503** |
| Islington | 120,072 | 82.2% | 20% | **78,942** |
| Barnet | 166,945 | 68.7% | 33% | **76,879** |
| Wandsworth | 166,677 | 83.9% | 46% | **75,544** |
| Ealing | 157,363 | 71.6% | 33% | **75,477** |
| Hackney | 129,657 | 83.9% | 32% | **73,996** |
| Brent | 144,456 | 75.5% | 33% | **73,111** |
| Lewisham | 142,260 | 75.9% | 39% | **65,876** |

## Where conversion lags hardest (lowest take-up of available full fibre)

| Borough | Full fibre available | **Take-up (% of coverage)** | Unconverted FF premises |
|---|--:|--:|--:|
| Kensington & Chelsea | 72.5% | **17%** | 58,815 |
| Islington | 82.2% | **20%** | 78,942 |
| Camden | 85.7% | **22%** | 82,498 |
| Enfield | 49.2% | **23%** | 52,077 |
| Haringey | 62.6% | **27%** | 53,431 |
| Westminster | 86.6% | **28%** | 102,907 |

*Central and inner-north London is where full fibre is widely available yet least taken up — the richest conversion ground.*

---

## What this is (and what it honestly isn't)

**What it is:** a live computation over Ofcom Connected Nations 2025 (the official UK regulator dataset),
joined across coverage and full-fibre take-up for all 33 boroughs — a **borough-level triage map** of where
the demand left on the table is greatest. Reproducible from the raw data in minutes.

**What it isn't — and we won't pretend otherwise:** these take-up figures are the **aggregate across all
operators**, not Community Fibre's own. Ofcom open data does not break coverage or take-up down by operator,
and take-up is published at borough level, not postcode. So this tells you *which boroughs* to focus on — not
*which streets*, and not *your specific footprint*.

---

## How the teaser becomes the product

This is one slice, on free public data, in minutes. The operator-grade version fuses three layers:

1. **Open-data triage** (this) — where, across London, the conversion gap is widest.
2. **Community Fibre's own footprint & take-up** — turning borough triage into *your* streets and *your* under-penetrated premises.
3. **Live read-only telemetry** (the Enlace engine) — network health, faults, and churn risk, premises by premises.

No one on the market fuses all three. Point Topic sells the first layer; nobody combines it with live telemetry.
**That fusion — built on the 41.6 million UK premises and regulator data we already hold — is the year-long,
defensible intelligence layer Community Fibre would own.** This teaser is the door; the pilot opens it.

---

*Data: Ofcom Connected Nations 2025 (OGL v3.0). Computed by `pulso-uk/intelligence/build_london_teaser.py`;
full per-borough table in `london_ff_conversion.csv`. Take-up is all-operator aggregate at local-authority level.*
</content>
