# DQT research roadmap — Dual-Field Quasi-Static Tomography

**Status: LOCKED (2026-07-03).** Built, tested, shipping in every audit.
Internal research track — never customer-facing until a pre-registered test
produces a verdict on real data.

## What this is

The agent's telemetry doubles as a passive quasi-static environmental
sensor: endpoint PSUs sample the low-voltage grid (dying-gasp co-timing),
and buried fiber samples the soil thermo-mechanical state (diurnal phase
lag, FEC waterfall gain). Four pre-registered falsification tests ship in
`src/detection/dqt.rs` and run on every audit at zero marginal cost:

| Test | Hypothesis | Support / kill criteria (pre-registered) |
|---|---|---|
| T1 grid | Recurring co-failure sets = LV transformer domains | median max-Jaccard ≥ / < 0.5 over ≥5 multi-ONT power events |
| T2 thermal | Multi-hour diurnal lag = buried-medium filtering | ≥20% responders with \|folded lag\| ≥ 2 h vs ≥95% at zero lag |
| T3 FEC gain | Corrected-FEC rate rides the erfc waterfall vs rx | median \|slope\| ≥ 0.3 decades/dB, negative sign ≥ 60% |
| T4 wavelength | Upstream/downstream loss asymmetry = water vs strain | needs OLT-side upstream rx field (not in schema yet) |

Hard honesty rules (enforced in code): never generates tickets, never
touches the health score, `experimental: true` on every report, absence of
data is `InsufficientData` (never support), Nyquist ceiling stated in every
output (~mHz at polling cadence — hours-to-seasons dynamics only; this is
not an acoustic or seismic sensor).

## Scoreboard

| Date | Dataset | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| 2026-07-03 | CF 52-ONT / 7-day sample | InsufficientData (0 power events) | InsufficientData (no temperature columns) | InsufficientData (0 eligible ONTs) | Not measured (no upstream rx) |

Nothing supported, nothing refuted yet — the machinery is validated on
synthetic ground truth (13/13 module tests: planted communities recovered,
planted 3 h burial lag recovered ±0.5 h, planted waterfall slope recovered
±0.35), but real data so far cannot feed any test. Update this table on
every new real dataset.

## What unlocks each verdict

1. **Pilot dataset #1 (expected first verdict: T3).** A month+ of telemetry
   from hundreds of ONTs gives enough rx wander for the FEC-gain
   regression. If the export includes DDM columns, T2 fires the same day.
2. **DDM columns in pilot exports (unlocks T2).** Already requested in the
   pilot data-request doc, justified by laser-health/SFP analysis — DQT
   rides along at no extra ask.
3. **A storm during any live deployment (unlocks T1).** Cannot be
   scheduled; the test arms itself. ≥5 multi-ONT power events in a window.
4. **Code item (unlocks T4): map the OLT-side upstream rx into the CSV
   importer / reading schema.** Present in NETCONF collection and in
   Mission Control exports with olt-rx columns; also requested in the
   data-request doc under optical-budget justification. Precipitation
   correlation additionally needs a weather feed (T4 classifier can run
   without it; the odds-ratio kill test cannot).

## Decision gates

- **T1 validates against a known substation/postcode mapping** → open a
  separate product conversation (DNO / LV-grid visibility). That is a new
  market, not a telecom feature; do not fold it into the assurance pitch.
- **T2 or T3 supported on two independent datasets** → write it up
  (whitepaper appendix), consider an "environmental telemetry" appendix in
  the vision doc with measured numbers only.
- **Any test refuted on two independent, well-fed datasets** → record it
  here, strip the corresponding vision-doc sentence, keep the module (a
  clean refutation is a publishable negative result and proof of the
  honesty pipeline working).

## Customer-facing boundary (do not cross)

The only permitted external mention until a real verdict exists is the
single research-stage sentence in the beyond-monitoring vision doc. No
pilot proposal, pricing, or sales claim may reference DQT capabilities.
