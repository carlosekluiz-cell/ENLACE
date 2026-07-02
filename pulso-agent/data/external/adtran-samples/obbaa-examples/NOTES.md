# NOTES — OB-BAA example NETCONF payloads (bbf-xpon)

- Source repo: https://github.com/BroadbandForum/obbaa (branch master), directory `resources/examples/`
- License: Apache-2.0 (see LICENSE in this directory, copied from repo root)
- Download date: 2026-07-02
- What: the Broadband Forum OB-BAA reference implementation's example NETCONF
  payloads for bbf-xpon OLT/ONU devices. These are NETCONF requests (edit-config /
  get) in the exact bbf-xpon / bbf-xpongemtcont / bbf-xponvani XML encoding a
  standards-compliant XGS-PON OLT (such as the Adtran SDX in BBF-standard mode)
  accepts — useful to validate namespace handling, interface typing
  (`bbf-xpon-if-type`), channel-group/pair/partition/termination structure, v-ani,
  TCONT/GEM structures.
- Not device output: these are orchestration-side payload examples from the OB-BAA
  project, kept because they are genuine standard-conformant bbf-xpon XML.

| Path | What |
|---|---|
| olt-config/PON_1_to_1_Services/*.xml | Full OLT provisioning flow: create OLT, xPON interfaces (channel group/partition/pair/termination, v-ani, olt-v-enet), link table, classifiers, ONU sub-interfaces, GEM/TCONT, 1:1 VLAN forwarding |
| olt-config/PON_N_to_1_Services/*.xml | Same flow for N:1 services |
| olt-config/control-relay-conf-example.xml, vomci-config-example.xml | Control relay / vOMCI function config |
| onu-config/*.xml | ONU device lifecycle incl. 7-get-state-data.xml (NETCONF `<get>` request for ONU state) |
| vomci-end-to-end-config/*.xml | End-to-end vOMCI configs incl. 11-create-telemetry-subscription.xml (telemetry subscription payload) and large standard infra payloads |

Source URL pattern: https://raw.githubusercontent.com/BroadbandForum/obbaa/master/resources/examples/<subpath>
