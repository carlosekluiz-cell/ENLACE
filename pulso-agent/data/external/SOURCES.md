# External Real-World Datasets — Sources & Provenance

Collected 2026-07-02 to validate Pulso parsers and fault-detection logic against real
PON/FTTH telemetry ahead of the Community Fibre (Adtran SDX) pilot.
Rule of thumb: everything below is believed to be REAL device/lab data unless explicitly
marked SYNTHETIC. Items that could not be downloaded without registration are listed with
their access requirements instead.

---

## 1. PRIMARY TARGET — Fraunhofer HHI "OLT-OTDR Dataset" (Sica et al., JOCN 2026)

- **Paper:** M. Sica, S. K. Patri, P. Safari, V. C. Rai, J. John, B. Shariati, J. K. Fischer,
  R. E. Freund, "Detection, identification, and localization of faults in PONs using joint
  OLT and OTDR telemetry data," J. Opt. Commun. Netw. 18(9), D44–D55 (2026).
  DOI: https://doi.org/10.1364/JOCN.587134 (paper itself is paywalled; abstract confirms
  "An experimental dataset is collected in this study, and it is made publicly available").
  Affiliations: Fraunhofer HHI + ADTRAN Networks SE (co-authored with Adtran — directly
  relevant to the SDX pilot).
- **Dataset:** "OLT-OTDR Dataset" on the Fraunhofer HHI network data portal.
  - URL: https://networkdata.hhi.fraunhofer.de/
  - License: Creative Commons Attribution 4.0 (CC BY 4.0) — stated in the portal's consent
    checkbox (license agreement links to https://creativecommons.org/licenses/by/4.0/legalcode).
  - **ACCESS REQUIREMENT (not downloaded):** the portal gates downloads behind a Gravity
    Forms request form requiring name, e-mail address, and affiliation, plus consent to the
    CC BY 4.0 license and the site privacy policy; the download link is presumably e-mailed.
    Per collection rules (no registration/forms), this was NOT submitted. A human should
    fill the form at https://networkdata.hhi.fraunhofer.de/ (select "OLT-OTDR Dataset").
  - Fraunhofer publica record for the paper: https://publica.fraunhofer.de/handle/publica/517652
  - Corresponding author: massimiliano.sica@hhi.fraunhofer.de
- **Useful for:** end-to-end validation of fault detection + localization (fault/detector.rs,
  fault/locator.rs) against real experimental OLT monitoring data + OTDR traces, including
  the exact fault classes the JOCN paper reports (~90% ID accuracy, sub-meter localization).
- Checked and ruled out as hosts: Zenodo (API search), IEEE DataPort, Fraunhofer Fordatis,
  arXiv (no preprint), GitHub. The HHI portal is the only distribution point as of 2026-07-02.

## 2. Known-but-gated: IEEE DataPort OTDR datasets (Abdelli et al.)

All require a (free) IEEE account to download — NOT downloaded, recorded only.
Note: these are laboratory testbed traces where faults were emulated with connectors/VOAs
(real measurements of emulated faults); treat as lab-real, not field data.

- "An OTDR event dataset" — https://ieee-dataport.org/documents/otdr-event-dataset
- "An OTDR dataset for optical fiber monitoring" —
  https://ieee-dataport.org/documents/otdr-dataset-optical-fiber-monitoring
- "Dataset for Optical fiber faults" —
  https://ieee-dataport.org/documents/dataset-optical-fiber-faults
- **Useful for:** secondary OTDR-trace classification benchmarks; lower priority than the
  HHI OLT-OTDR dataset because Pulso's near-term parsers consume OLT telemetry, not raw
  OTDR traces.

---

## 3. PT-Predictor (MDPI Sensors 2023) — identified, data PRIVATE

- **Paper:** H. Zhao, Y. Fang, W. Zhang, X. Feng, et al. (Shanghai Jiao Tong University +
  **China Mobile Zhejiang Innovation Research Co., Ltd.** + ShanghaiTech), "Time-Series
  Representation Learning in Topology Prediction for Passive Optical Network of Telecom
  Operators," Sensors 2023, 23(6), 3345. DOI: 10.3390/s23063345.
  Open-access full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC10056920/ and
  https://www.mdpi.com/1424-8220/23/6/3345
- This is the "PT-Predictor" paper (GCE-Scorer + MaxMeanVoter/TransVoter) predicting the
  secondary-splitter membership of ONUs from optical-power time series.
- **Dataset (NOT public):** 65,043 unchecked + 3,084 verified ONUs from China Mobile
  Zhejiang; ONU optical power sampled **every 10 minutes** over 2–29 weeks across 7 OLTs.
- **Data Availability Statement (verbatim):** "The data presented in this study are
  available on request from the corresponding author. The data are not publicly available
  due to privacy."
- No GitHub/Zenodo/code release anywhere in the paper. **Restriction: private; request to
  corresponding author only.** Recorded 2026-07-02; nothing downloaded.

## 4. Known-but-gated: "PON Physical Twin" GPON testbed dataset (Univ. de la República / IMT Atlantique)

- **Repo:** https://github.com/linglesloggia/PONData — "Dynamic PON Configuration Dataset";
  ECOC 2025 paper "PON Physical Twin: Enabling Third-party Research on FTTH Optimization
  with Open Datasets" (L. Inglés, L. Anet Neto, C. Rattaro, M. Morvan, A. Castro, L. Nuaymi).
- REAL lab testbed: OLT + 16 ONUs + traffic generator + SDN controller; 2.43 GB CSV;
  24-hour runs sampled at 12-minute intervals; 88 metrics per direction.
- **Caveat:** published metrics are traffic/QoS KPIs (latency, frame-loss ratio, BER,
  throughput, packet size) — per-ONU *optical power* fields are not confirmed from the README.
- **License:** ODC-BY-NC 1.0 (non-commercial — would need review before any commercial use
  in Pulso anyway).
- **ACCESS REQUIREMENT (not downloaded):** ZIPs are gated behind an IMT request form:
  https://partage.imt.fr/index.php/apps/forms/s/LrGgmXkFEnmqyNFZdRnx7jF5 — form submission
  required, so skipped per collection rules.

## 5. Known-but-gated / unverified: Kaggle "OptiCom Signal Quality Dataset"

- URL: https://www.kaggle.com/datasets/tinnyrobot/opticom-signal-quality-dataset
- Requires a Kaggle account to download (NOT downloaded). Provenance could not be verified
  without login; name/uploader pattern suggests **likely SYNTHETIC** — verify before use.

## 6. Known-but-gated, SYNTHETIC: IEEE DataPort "Reliability Data for Laser Lifetime Prediction" (Abdelli et al.)

- URL: https://ieee-dataport.org/documents/reliability-data-laser-lifetime-prediction
- Explicitly **synthetic** data for InGaAsP MQW-DFB lasers (Ith, optical power, wavelength,
  slope efficiency, voltage, junction temperature → MTTF). Requires an IEEE DataPort
  *subscription* (stricter than the free-account OTDR sets in §2). Recorded only because it
  is adjacent to laser-bias/EOL prediction; DO NOT treat as real telemetry.

## 7. Exists in literature only (no data release): INEA (Poland) GPON deployment statistics

- A flexible-rate PON paper (ca. 2016) uses a real dataset of ~20,000 ONUs' received
  optical power from **INEA's** commercial GPON deployment; only aggregate figures were
  published, no raw data release found anywhere.
  - https://www.researchgate.net/figure/Statistics-of-a-dataset-of-the-GPON-deployments-of-INEA-aONU-received-optical-power_fig1_310824451
  - https://www.researchgate.net/figure/Statistics-of-a-dataset-of-20-000-ONUs-of-the-GPON-deployments-of-INEA-on-a-per-OLT-port_fig5_310824451

## 8. Negative-search log (2026-07-02, second pass)

Searched with no freely-downloadable REAL ONU/ONT optical-power dataset found:
- **Zenodo API** (`zenodo.org/api/records`): queries "gpon dataset", "onu rx power",
  "PON telemetry", "FTTH monitoring", "optical transceiver monitoring", "SFP DDM",
  "xgs-pon", "splitter port identification", "PON physical twin", "dying gasp",
  "optical distribution network" → only irrelevant or publication-only records.
- **IEEE DataPort** search pages ("GPON", "passive optical network") → nothing PON/ONU
  beyond §2/§6.
- **Harvard Dataverse** API, **Hugging Face** datasets API ("gpon", "onu", "optical
  power", "ftth"), **PapersWithCode**/**Mendeley Data** APIs (blocked or empty),
  **Figshare** API (403 from this network; web search shows no relevant items).
- **GitHub** repo search (smartolt/olt/onu/gpon/pon monitoring, xgspon, ont optical):
  tooling only, no committed real telemetry exports. `aletelecom/GPON-Network-Visualization`
  notebooks generate their "optical power" data with scipy `skewnorm/norm.rvs` — SYNTHETIC.
  Sourcegraph public code search: no `.csv` files with ONU optical-power headers.
- **Kaggle** via web search: only §5 candidate; ISP traffic captures (not optical).

---

# DOWNLOADED COLLECTIONS (per-file provenance in each directory's NOTES.md)

## 9. snmp-dumps/ — real GPON/EPON OLT SNMP walks (3.8 MB, 37 files)

Community-captured walks from real devices, mostly LibreNMS `tests/snmpsim/*.snmprec`
(GPL-3.0, verified byte-for-byte against upstream raw.githubusercontent.com URLs) plus
forum-thread raw excerpts (license unclear — treat as quotable reference, not
redistributable). Downloaded 2026-07-02. Highlights:

- **zte/**: ZXA10 C320 full walks; ZTE C300/C320 forum excerpts (`raw*0.002-30` scaling).
- **huawei/**: SmartAX MA5600T-family walks; MA5680T `hwGponOntOpticalDdmRxPower` walk
  (~50 ONTs, 0.01 dBm scaling, invalid marker 0x7FFFFFFF); MA5683T DDM `.51` table.
- **fiberhome/**: AN5516-01/-04/-06 walks (chassis-level; no per-ONU optics publicly).
- **nokia/**: 7360 ISAM R6.5 — PON optics exposed as strings ("-0.34 dBm", "No Power").
- **datacom/**: DmOS DM4610/4611/4616 (XGS-PON)/4618.
- **parks/**: PK-700 (SFP DDM 0.1 dBm, INT32_MIN invalid marker).
- **vsol/**: V1600D EPON OLT. **bdcom/**: GP3600-16B + FS.com OEM clone (enterprise
  52642) + nag.wiki walks cross-checked against CLI proving 0.1 dBm scaling.
- **cdata/**: CData OLT (17409/34592 dual-enterprise quirk). **ubiquiti/**: UFiber
  EdgeOS 4.4.2 + UISP Fiber XGS (0.01 dBm, ASCII-serial table indexes).
- `librenms_expected_*.json` files provide per-OID decoded ground truth (what LibreNMS
  itself decodes each walk into) — usable as oracle values for vendors/*.rs unit tests.
- **Useful for:** validating OID trees, scaling factors, and invalid-value sentinels in
  src/vendors/{zte,huawei,fiberhome,nokia,datacom,parks,vsol,bdcom,cdata,ubiquiti}.rs.
- Not found publicly: FiberHome per-ONU optics, Nokia per-ONT optics (.637.61.1.35.10.x),
  ZTE C650 full walk — need real device captures (consistent with the pilot audit).

## 10. broadband-forum-yang/ — bbf-xpon YANG modules (792 KB, 45 modules + LICENSE)

- Source: https://github.com/BroadbandForum/yang (master). License: BSD-3-Clause.
- All `bbf-xpon*`, `bbf-xponani*`, `bbf-xponvani*`, `bbf-xpongemtcont*`,
  `bbf-hardware-transceivers(-xpon)`, `bbf-hardware-types`, alarm-types modules.
- **Useful for:** schema-truth for the Adtran SDX NETCONF path (SDX exposes bbf-xpon);
  validating XPaths/leaf names/units used by the NETCONF transport and SDX parser.
- Note: these are spec schemas, not device data.

## 11. adtran-samples/ — bbf-xpon NETCONF payloads + Adtran-authored code (724 KB)

- **obbaa-examples/** (39 XML, Apache-2.0, github.com/BroadbandForum/obbaa): genuine
  bbf-xpon OLT/ONU NETCONF provisioning flows (1:1 and N:1), `<get>` state request,
  telemetry subscription payloads.
- **obbaa-yang-library/** (3 XML, BSD-3): real-format `<rpc-reply>` ietf-yang-library
  capability lists for a standard bbf-xpon OLT (29 modules) and ONU.
- **voltha-adtran-adapter/** (9 files, Apache-2.0, © Adtran Inc.,
  github.com/opencord/voltha-adtran-adapter): Adtran's own NETCONF client/codec code
  revealing real Adtran OLT namespaces: `http://www.adtran.com/ns/yang`, `gpon-olt-hw`,
  `adtran-physical-entities`.
- **GAP (recorded, not obtainable):** no public real SDX 6320/6330 NETCONF `<get>` reply
  captures or Mosaic CSV exports with documented headers; Adtran support-community docs
  are login-gated. Must come from the CF pilot device itself.

## 12. ddm-dumps/ — real SFF-8472 DDM dumps (668 KB)

- **hack-gpon/** (MIT, github.com/hack-gpon/hack-gpon.github.io): per-device A0h/A2h
  EEPROM tables with real byte values and DDM alarm/warning thresholds for GPON ONT
  sticks (Huawei MA5671A, Zyxel PMG3000-D20B, FS.com, Fibermall, Sercomm FGS202 with
  live TX/RX dBm) + Adtran SDX 611/611Q/621i ONT pages.
- **github-issues/** (user content, license unclear): verbatim `ethtool -m` outputs —
  Zyxel PMG3000-D20B GPON stick, 10GBase-SR, 1000BASE-LX, FS BiDi 1000BASE-BX10.
- **gists/**: full FS.com SFP-10GLR-31 dump with complete threshold block.
- **debian-bts/**: Debian bug #960702 — corrupted DDM values from the mlx4 EEPROM-read
  kernel bug: real-world NEGATIVE test case for plausibility/garbage-rejection checks.
- **Useful for:** SFF-8472 plausibility ranges in diagnostics + transceiver decode tests.

---

Total on disk: ~5.9 MB (well under the 2 GB budget). Nothing was git-committed.
