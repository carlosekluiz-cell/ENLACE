# Network Operations Discovery — Community Fibre

*A short questionnaire to send (or walk through) with whoever owns network operations. Purpose: understand how their day actually runs, and capture the handful of numbers that let us build a bottom-up ROI in **their** figures rather than our industry averages. Keep it conversational — they can skip anything commercially sensitive and give ranges.*

> **Framing line when you send it:** *"Before we run the free pilot, a few questions so we tailor what we look for to your actual pain — and so any results we show you are grounded in how Community Fibre really operates, not generic benchmarks."*

---

## Section 1 — A day in the NOC

1. Walk us through a typical day for your network operations / NOC team. What are the first things they check each morning?
2. How many people sit in network operations vs field engineering? Roughly what's the on-call setup out of hours?
3. What does **"Mission Control"** mean inside Community Fibre — is it your NOC, a specific dashboard, a platform? What does an operator actually see on it today?
4. When something goes wrong, how does the team usually find out — an alarm, a monitoring dashboard, a customer call, a wholesale partner (VodafoneThree), or social media?

## Section 2 — Visibility & monitoring today

5. What tooling do you use for network/PON monitoring today? (e.g. Adtran Mosaic / Mosaic One, a general NMS, in-house, Elasticsearch/Kibana, OTDR/fibre monitoring.)
6. You mentioned AI systems rolling out through 2026 — is that **Adtran Mosaic One / Clarity**? What do you expect it to give you, and where do you think it'll fall short?
7. How much of your monitoring is **reactive** (you find out when it's already broken) vs **predictive** (you get a warning before customers are affected)? Roughly what % of issues do you catch *before* the first customer call?
8. Can you see **per-ONT optical signal** (Rx/Tx power) trends over time today, or only current status / alarms?
9. How many distinct OLT/equipment vendors are in your estate? Is it all Adtran, or is that changing as you grow?
10. Where does your telemetry/alarm data live — vendor cloud, your own infrastructure, or both? How do you feel about telemetry leaving your network vs staying on-prem?

## Section 3 — Faults & field dispatch *(the ROI inputs)*

> *These five numbers let us model the pilot's value. Ranges/estimates are fine.*

11. Roughly how many **engineer visits / truck rolls** per month, per 1,000 connected subscribers?
12. What's your rough **fully-loaded cost per engineer visit** (labour, travel, vehicle, parts)?
13. What share of dispatches are **"no fault found"** or end in a repeat/second visit?
14. What are your **top recurring physical fault modes**? (e.g. rogue/reflecting ONT taking down a whole PON tree, moisture ingress in splice enclosures, dirty connectors, macro-bends, ageing SFPs, fibre cuts.)
15. When a fault hits, how do you **locate it physically today**, and how long does it typically take to get a technician to the right spot? (mean time to repair?)

## Section 4 — Customers & churn

16. What's your annual **churn rate**, and how much of it do you attribute to service quality / reliability vs price/competition?
17. What's your blended **ARPU** and rough **cost to acquire** a subscriber? *(So we can put a £ value on each prevented churn.)*
18. What do your most common **support-call themes** look like, and what's a rough cost per call/ticket?
19. With the **VodafoneThree wholesale** relationship, do undiagnosed faults now carry SLA penalties or reputational exposure? How does that change your priorities?

## Section 5 — Alarms, tickets & automation

20. Roughly how many **alarms/day** does the NOC see, and what share are actionable vs noise? Is alarm fatigue a real problem?
21. How are tickets created and routed today — manual, or auto-generated from monitoring? What ticketing/on-call tooling do you use (ServiceNow, Jira, PagerDuty, Opsgenie, in-house)?
22. How does your field team get dispatched — and **would automated alerts to the team on WhatsApp, with a map pin to the fault location, be useful or unwelcome**?
23. If telemetry could open a **planned-maintenance** ticket for a splice that's *going* to fail in a few weeks — before any customer is affected — where would that sit on your priority list?

## Section 6 — Success & the pilot

24. If a pilot worked, what would make you say "yes, this is worth keeping"? What's the one metric you'd most want to move (truck rolls, MTTR, churn, first-call resolution, alarm noise)?
25. For the free pilot, could you export ~a month of ONT/optical telemetry (CSV or via NETCONF/Mosaic) from **one area where you've had recurring issues**? That's all we need to show you what Enlace finds in your real data.

---

### Internal note (not for the customer)

The questions that unlock the ROI model are **11, 12, 13, 16, 17, 20, 21**. With those we compute:
*"You spend ~£X/yr on avoidable dispatches and lose ~£Y/yr to quality-driven churn; Enlace conservatively removes 30–50% of avoidable truck rolls and ~40% of MTTR."*
All multipliers are cited in `03-differentiation-appendix.md` §C — never quote a benefit % without anchoring it to their input number.
</content>
