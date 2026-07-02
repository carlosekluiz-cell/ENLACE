# NOTES — Adtran SDX / Mosaic NETCONF reference material

Collected 2026-07-02 to validate the pulso-agent Adtran SDX (XGS-PON OLT) NETCONF/YANG
parser. Subdirectories each have their own NOTES.md.

## What is here

- `obbaa-examples/` — genuine bbf-xpon NETCONF payloads from BBF OB-BAA (Apache-2.0).
- `obbaa-yang-library/` — real-format `<rpc-reply>` ietf-yang-library module lists
  (YANG capability lists) for a standard bbf-xpon OLT/ONU (BSD-3-Clause, BBF).
- `voltha-adtran-adapter/` — Adtran-authored VOLTHA adapter code (Apache-2.0,
  Copyright 2017-present Adtran, Inc.) showing the exact NETCONF namespaces, XPaths
  and reply structures of real Adtran OLTs (`http://www.adtran.com/ns/yang`,
  gpon-olt-hw, adtran-physical-entities). Code, not device output — but written by
  Adtran against real devices, so the XML element names/paths are authoritative.

## Gated or not publicly available (checked 2026-07-02, no logins used)

- Real SDX 6320/6330 NETCONF `<get>` reply captures: **not found publicly.**
- Adtran Support Community — Mosaic Device Manager / SDX docs index is public but the
  actual documents require a support login:
  https://supportcommunity.adtran.com/t5/Mosaic-Device-Manager/ct-p/MDM_Docs
  https://supportcommunity.adtran.com/t5/Mosaic/ct-p/mosaic-discuss
- Adtran Mosaic Cloud Platform product brief (gated download):
  https://www.adtran.com/en/resources/resources-gated-page/solution-briefs/mosaic-device-manager
  https://portal.adtran.com/web/fileDownload/doc/35050
- Mosaic Device Manager KB (public, but CPE/subscriber-device focused, no OLT CSV
  telemetry headers): https://kb.smartrg.com/DM_KnowledgeBase/
  (Platform Summary: .../Content/User_Manual/BP_PH_Platform_Summary.htm,
  API integration points: .../Content/User_Manual/BP_API_Integration_Points.htm)
- Mosaic One help (public HTML help, no raw telemetry samples):
  https://help.adtran.cloud/m1_csh/Content/Home.htm
- ADTRAN/netconf_client (https://github.com/ADTRAN/netconf_client, Adtran's own
  Python NETCONF client): checked — unit tests are synthetic, no device payloads.
- YangModels/yang vendor tree: no `vendor/adtran` directory exists.
- No public Mosaic CSV telemetry export with documented headers was found; the
  supportcommunity/kb URLs above are the closest documentation sources.
