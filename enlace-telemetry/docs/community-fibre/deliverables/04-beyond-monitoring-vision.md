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
  → one-tap WhatsApp dispatch to the field team — ticket, device, fault, severity, map link
  → when telemetry confirms the signal is restored, auto-close the ticket
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

- **Auto-ticketing & escalation.** Enlace outputs to Elasticsearch, Slack and PagerDuty natively, plus
  custom webhooks that drop into Opsgenie, ServiceNow or Jira Service Management — with **P1–P4 severity**
  and SLA-based routing to the right team.
- **One-tap WhatsApp dispatch.** Everyone's on WhatsApp. The supervisor shares a ready-made message —
  ticket ID, device, fault type, severity and a map link — **straight into the technician's WhatsApp
  chat.** *(WhatsApp Business API push is a roadmap integration.)*
- **Fault-to-location today, for the per-ONT case.** A fault is narrowed to the serving ONT and its
  location (distance range and map link); where you provide your ONT-to-address mapping, that becomes
  the subscriber's street address on the ticket — dispatchable immediately, no extra hardware.

---

## What we can deliver in the pilot vs what's roadmap

We'd rather under-promise. Here's the honest split.

**Ready now (built and tested):**
- Automated incident creation with P1–P4 tiering, SLA routing, and Slack/PagerDuty/webhook delivery.
- One-tap WhatsApp dispatch from the ops app — ticket, device, fault type, severity, map link.
- Fault-to-location on every ticket (serving ONT, distance range, map link).
- Proactive planned-maintenance ticketing for slow degradation (Loop B).
- Automatic ticket close-out on confirmed recovery.
- Read-only operation throughout — credentials never leave your network.

**Landing during the pilot:**
- Street-address mapping on tickets, once you share your ONT-to-address data.
- WhatsApp Business API push (today dispatch is one-tap share from the supervisor's screen).

**Roadmap (we'll be clear about the dependency):**
- *OTDR-distance → exact street pin.* Deployed at carrier scale elsewhere, but it needs an OTDR/RFTS feed
  **and** accurate as-built GIS route geometry. Without that, we give a fibre-metre distance and a probable
  map segment, not a precise pin.
- *Calibrated "weeks-to-failure" forecasting.* Today this is a trend-and-threshold projection ("Rx declining,
  projected below the loss threshold in ~N days"); a fully calibrated model matures with your data.
- *Infrastructure sensing beyond telecom (research-stage).* At fleet scale the same read-only telemetry
  doubles as a passive infrastructure sensor — recurring co-outage patterns can map low-voltage grid
  domains that no distribution operator currently observes. Pre-registered validation tests already ship
  in the agent; no verdict on real data yet, and we won't claim one until there is.

---

## Why "closed loop" matters commercially

Operators running closed-loop assurance report material gains: **truck rolls down 30–50%**, **mean-time-to-repair
down ~40%**, **alarm noise down 60–70%**. A single rogue ONT can take down an entire PON tree of 32–128
subscribers; connector contamination is the single most common physical fault. Catching these early — and acting
automatically — is where the opex and churn savings live. The pilot is designed to put *your* numbers against
those ranges.
</content>
