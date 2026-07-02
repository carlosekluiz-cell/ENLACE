# Community Fibre — Meeting Playbook

*How to run the room. Pull facts from docs 01–04. Goal of the meeting: not to sell, but to (a) earn the free pilot, (b) get one month of real telemetry from a problem area, (c) leave them thinking "we actually need this."*

---

## The 30-second frame

> *"Most network monitoring tells you something's broken and pages a human — reactively. Enlace is built to close the loop: it reads the telemetry your OLTs already produce, predicts faults before customers feel them, locates them, and turns them into a tiered ticket and a WhatsApp alert with a map pin — automatically. It's a single 8 MB Rust binary, read-only, vendor-agnostic, and it runs beside your kit, not in someone else's cloud. We'd like to prove it on a slice of your real data, free."*

## The arc to walk

1. **Their world first.** Open with discovery (doc 04), not a pitch. Let them define "Mission Control" and confirm the "AI systems" = Adtran Clarity. Listen for pain: outages engineers "can't find," repeat visits, the VodafoneThree SLA exposure.
2. **The market moment.** "The build phase is ending; the whole industry is pivoting to *operate efficiently and don't lose customers* — and you're already one of the few profitable, high-take-up operators. This protects that."
3. **Beyond monitoring.** The two loops (acute fault + slow-degradation pre-emption). Lead with Loop B — *the customer never calls because you fixed it first.*
4. **Why us / why Rust.** Lightweight, read-only, on-prem, no per-device licence. Show the "billions/day" arithmetic. Concede the honest caveats — it builds trust.
5. **The free pilot ask.** One month of CSV/NETCONF telemetry from a problem area → we show them what Enlace finds → then deploy read-only live.

## Positioning vs Adtran (memorise this)

CF runs Adtran XGS-PON and is likely adopting **Mosaic One Clarity (their "AI systems")**. **Do not compete with it.**

> *"We're not replacing Adtran's assurance — we sit beside it. We're the vendor-neutral, self-hosted layer: your telemetry stays on your infrastructure, there's no per-device licence, and we unify whatever non-Adtran kit you add as you grow. Adtran's AI is great on Adtran's boxes and in Adtran's cloud — we cover the gaps that creates."*

Three gaps Mosaic structurally can't fill: **data sovereignty** (self-hosted), **no per-endpoint cost**, **true vendor-agnostic breadth**.

## What we can promise vs what's roadmap

**Promise (proven):** auto-incident creation with P1–P4 + escalation; WhatsApp alerts with a map pin; per-ONT fault → known service address; proactive planned-maintenance tickets; auto-resolve on recovery; read-only, credentials-stay-local, single binary.

**Roadmap (state the dependency):** OTDR-distance → exact street pin (needs RFTS feed + good as-built GIS); calibrated "weeks-to-failure" model (today it's a trend/threshold projection). The propagation/expansion-planning model is deliberately **not** in this pitch — door opens on telemetry + market intelligence only.

## Lines NOT to say

- ❌ "Nothing like this exists." → ✅ "Nothing combines lightweight + read-only + vendor-agnostic + predictive at the PON layer — here's how we differ from the closest, NetSense and PBN."
- ❌ Cite specific knowledge of their internal kit as if we have inside info. (We *infer* Adtran from public 2018 partnership news — ask, don't assert.)
- ❌ Claim the 10/10 blind test or 98% figure as live-customer telemetry validation. It's synthetic / design-accuracy respectively. The pilot is what validates on real data.
- ❌ Quote a benefit % without anchoring it to a number they gave us.
- ❌ Promise SNMP polling on their SDX OLTs — they're NETCONF-first, no SNMP.
- ❌ Mention pricing. It's a free pilot; preferential pricing at launch.

## Numbers to have on the tip of your tongue

- CF: ~1.4m passed, ~450k customers, **~32% take-up (sector-leading vs ~18%)**, £113m revenue, ~£50m EBITDA, cash-positive, resuming build to 2m+.
- Industry: largest altnets lost **£1.5bn in 2024**; viability needs ~40% take-up; nexfibre buying Netomnia (~£2bn).
- Value: truck roll ~£75–150; ~20% avoidable; churn ~10–18%; ARPU ~£30; CAC ~£240; proactive assurance cuts truck rolls **30–50%**, MTTR **~40%**; rogue ONT can down a **whole PON tree (32–128 subs)**; connector contamination is the **#1** physical fault.
- Us: 8 MB binary, ~50 MB/1k ONTs, <2% core, 17 detection modules, 157 tests, 12+ vendors.

## People

- Sponsor target: **Paul Lees (Operations Director)** — owns the pain. Plus **CTO** (confirm Dale Kirkwood vs Sven Huster on LinkedIn first).
- They already buy ops tooling (Zinier, Cognizant, A10) → budget pattern exists.

## The single most important ask

> *"Give us one month of ONT optical telemetry from one area that's been giving you grief. No install, nothing touches your network, credentials never leave it. Within the day we'll show you the faults, at-risk customers, and capacity hot-spots Enlace found in your own data."*

---

## Open items to close before/at the meeting

- [ ] Confirm current **CTO** (Dale Kirkwood vs Sven Huster).
- [ ] Confirm **"Mission Control"** = their NOC/dashboard (ask in room).
- [ ] Confirm **"AI systems"** = Adtran Mosaic One / Clarity (ask in room).
- [ ] Confirm CF's **OLT estate** is Adtran SDX (public signal says yes; verify) and whether it's diversifying.
- [ ] Get the **discovery questionnaire** (doc 04) answered — especially Q11/12/13/16/17/20/21 for the ROI model.
- [ ] Agree the **problem area + export format** (CSV vs NETCONF/Mosaic) for the pilot data.
</content>
