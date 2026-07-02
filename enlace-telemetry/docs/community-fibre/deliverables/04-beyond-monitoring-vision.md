# Beyond Monitoring: Closed-Loop Network Intelligence
*Enlace · Pulso Technologies Limited*

---

## Monitoring tells you it broke. Enlace closes the loop.

Most network tooling stops at the alarm: something fails, a dashboard turns red, a human gets paged.
That's **reactive** — the customer often calls before the alert lands, and a chunk of those calls end
in a truck roll with no fault found.

Enlace is built to close the loop:

> **Observe → Analyse → Locate → Decide → Act → Confirm**

This is the industry's own direction of travel — *closed-loop assurance* (TM Forum Autonomous Networks),
*zero-touch operations* (ETSI ZSM), *intent-based assurance*. On TM Forum's autonomy scale (L0 manual →
L5 full), classic monitoring is **L1**. Enlace targets **L3–L4 for the PON/access domain**: predictive,
conditional, closed-loop, with humans in the loop only for exceptions.

---

## The two loops

### Loop A — acute fault (seconds to minutes)
```
Telemetry detects loss-of-signal / mass-offline on a PON port
  → classify: trunk cut (all ONTs down) vs branch vs single drop
  → locate: distance-to-break + PON port + splitter, or the specific ONT = a known service address
  → open a tiered ticket (P1 outage immediately) in your existing tooling
  → notify the field/NOC team on WhatsApp with a map pin to the fault
  → when telemetry confirms the signal is restored, auto-resolve the ticket
```

### Loop B — slow degradation (days to weeks) — the high-value one
```
Rx power on 3 ONTs trends down ~0.04 dB/day at ~800 m on the same port
  → the optical-budget / weather modules flag "moisture ingress in a splice enclosure"
  → open a LOW-priority planned-maintenance ticket BEFORE any customer notices
  → schedule one planned visit; fix it once; zero customer impact, zero churn
```

**Loop B is the story that matters: the customer never calls, because the fault was fixed before it
reached them.** That is the difference between monitoring and intelligence.

---

## How the loop reaches a person

- **Auto-ticketing & escalation.** Enlace pushes incidents into the tooling you already run —
  PagerDuty, Opsgenie, ServiceNow, Jira Service Management — with **P1–P4 severity** and time-based
  escalation to the right on-call. This is a standard, production-proven integration pattern.
- **WhatsApp alerts with a location pin.** Everyone's on WhatsApp. Via the WhatsApp Business / Cloud API,
  Enlace sends the field team an alert — ticket ID, device, fault type, severity — **with a map pin to the
  fault site**. They reply in the same thread; arrival and updates flow back.
- **Map-pin dispatch today, for the per-ONT case.** A fault narrowed to a specific ONT *is* a known
  subscriber address — dispatchable immediately, no extra hardware.

---

## What we can deliver in the pilot vs what's roadmap

We'd rather under-promise. Here's the honest split.

**Ready now (proven patterns):**
- Automated incident creation with P1–P4 tiering and escalation into your ticketing/on-call tool.
- Automated WhatsApp alerts to the NOC/field team, including a map-pin location.
- Per-ONT fault → known service address for immediate dispatch.
- Proactive planned-maintenance ticketing for slow degradation (Loop B).
- Auto-resolution when telemetry confirms recovery.
- Read-only throughout — credentials never leave your network.

**Roadmap (we'll be clear about the dependency):**
- *OTDR-distance → exact street pin.* Deployed at carrier scale elsewhere, but it needs an OTDR/RFTS feed
  **and** accurate as-built GIS route geometry. Without that, we give a fibre-metre distance and a probable
  map segment, not a precise pin.
- *Calibrated "weeks-to-failure" forecasting.* Today this is a trend-and-threshold projection ("Rx declining,
  projected below the loss threshold in ~N days"); a fully calibrated model matures with your data.

---

## Why "closed loop" matters commercially

Operators running closed-loop assurance report material gains: **truck rolls down 30–50%**, **mean-time-to-repair
down ~40%**, **alarm noise down 60–70%**. A single rogue ONT can take down an entire PON tree of 32–128
subscribers; connector contamination is the single most common physical fault. Catching these early — and acting
automatically — is where the opex and churn savings live. The pilot is designed to put *your* numbers against
those ranges.
</content>
