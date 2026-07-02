# SNMP walk dumps — GPON/XGS-PON OLTs (real-world captures)

Collected 2026-07-02 to validate SNMP OID decoding and scaling logic in the Pulso agent.
Total size ~3.8 MB. All files verified non-empty and containing genuine SNMP data
(OID patterns under 1.3.6.1). Nothing here is synthetic unless explicitly marked.
Snapshots (single walk per device), not time series — suitable for parser/OID-mapping and
scaling validation, not for trend/degradation detection tests.

## File formats

- `*.snmprec` — snmpsim record format: `OID|type|value` per line (type codes: 2=Integer32,
  4=OctetString, 4x=hex OctetString, 6=OID, 64=IpAddress, 65=Counter32, 66=Gauge32,
  67=TimeTicks, 70=Counter64). These are REAL walks captured from production devices by the
  LibreNMS community for their test suite (`tests/snmpsim/`). Replayable with `snmpsim` to
  emulate the device against Pulso's SNMP transport.
- `librenms_expected_*.json` — LibreNMS test ground truth paired with the same-named snmprec:
  the sensor values LibreNMS decodes from that walk (`sensors.discovery.sensors[]` with
  `sensor_oid`, `sensor_current`, `sensor_divisor`, `sensor_class`). Use to validate our own
  scaling (e.g. raw -2193 with divisor 100 -> -21.93 dBm).
- `*_excerpt*.txt` / `*_excerpts.txt` — raw snmpwalk lines extracted from forum/wiki/gist/PR
  posts (net-snmp output format `OID = TYPE: value`). NOT contiguous walks; the header comment
  in each file documents device, source URL and coverage.

License note: everything from github.com/librenms/librenms is GPL-3.0 (repo content, no
separate data license). Forum/wiki/gist excerpts: license unclear (publicly posted device
output); treat as internal reference data only, flag before redistributing.

---

## zte/  (ZTE ZXA10 C300/C320/C650)

| file | device | source | license |
|---|---|---|---|
| librenms_zxa10_c320.snmprec | ZXA10 C320 V2.1.0 GPON OLT (real, 8 PON ports "OLT-1..8") | https://raw.githubusercontent.com/librenms/librenms/master/tests/snmpsim/zxa10_c320.snmprec | GPL-3.0 |
| librenms_zxa10.snmprec | ZXA10 C320 (sysDescr/sysObjectID only, os-detection stub) | .../tests/snmpsim/zxa10.snmprec | GPL-3.0 |
| librenms_expected_zxa10_c320.json | ground truth for the above | https://raw.githubusercontent.com/librenms/librenms/master/tests/data/zxa10_c320.json | GPL-3.0 |
| localcomua_zte_c300_c320_thread_excerpts.txt | ZXA10 C300/C320 (GPON) + C220 (EPON), real ISP devices | https://local.com.ua/forum/topic/76498-zte-olt-opros-po-snmp-urovni/ (pages 1-9) | unclear |

Covers: sysDescr/sysObjectID `3902.1082.1001.320.2.1`; card/port tables `3902.1012.3.11/.12/.13`;
optical-diag tables `3902.1082.10.10.2.1.x` (per-PON temp/bias/tx, values like -20, invalid=-1000)
and `3902.1082.10.10.2.4.10/.11` (per-ONU); LibreNMS zxa10.yaml maps `1082.10.10.2.1.6.1.2..5`
and `1082.10.10.2.4.11.1.5..7` to dbm/temperature sensors.
Forum excerpts add GPON ONU RX table `zxGponOntRxPower .1.3.6.1.4.1.3902.1012.3.50.12.1.1.10.<ifidx>.<onu>.1
= INTEGER: 3740` with scaling **dBm = raw*0.002 - 30** (3740 -> -22.52 dBm), plus EPON
`3902.1015.1010.x` ONU tables and chassis temp `3902.1015.2.1.3.2`.
NOT obtained: C6xx (C650) full walk — see "found but inaccessible".

## huawei/  (SmartAX MA5600T / MA5603 / MA5680T / MA5683T / MA5800)

| file | device | source | license |
|---|---|---|---|
| librenms_smartax.snmprec | SmartAX GPON OLT (MA5600T family, sysObjectID 2011.2.123), real walk incl. 480 lines of HUAWEI-XPON-MIB 2011.6.128 | .../tests/snmpsim/smartax.snmprec | GPL-3.0 |
| librenms_smartax-mdu.snmprec | SmartAX MDU (2011.2.185) | .../tests/snmpsim/smartax-mdu.snmprec | GPL-3.0 |
| librenms_expected_smartax.json | ground truth for smartax.snmprec | .../tests/data/smartax.json | GPL-3.0 |
| github_pr9023_ma5680t_ddm_excerpt.txt | MA5680T (real ISP device, H805GPBD boards) | https://github.com/librenms/librenms/pull/9023 (comment by jozefrebjak) | unclear |
| librenms_forum6801_ma5680t_ddm_rxpower.txt | MA5680T, ~50 ONTs full RX-power walk | https://community.librenms.org/t/help-with-dbm-sensors-discovery/6801 | unclear |
| localcomua_ma5683t_thread_excerpts.txt | MA5683T V800R008/R015 (mixed excerpt lines) | https://local.com.ua/forum/topic/89222-huawei-ma5683t-oid-%D0%B8-mib/ (pages 1-7) | unclear |
| gist_jsenin_hwgpon_hexdates_excerpt.txt | Huawei GPON OLT (XPON MIB) | https://gist.github.com/jsenin/0de5475d092c916885acf85671309871 | unclear |

Covers: `hwGponDeviceOntTable 2011.6.128.1.1.2.21/.23` (in snmprec — status, distance, serial);
**`hwGponOntOpticalDdm* 2011.6.128.1.1.2.51.1.1..6`** (temp/voltage/bias/txPower/**rxPower .51.1.4**/oltRx .51.1.6)
in the three excerpt files — units **0.01 dBm** (raw -2193 -> -21.93 dBm), invalid marker
**2147483647 (0x7FFFFFFF)** when ONT offline; ifIndex encoding 4194312192 = frame0/slot1/port0,
+256 per port. Hex-STRING date encoding (07 E4 06 09 ... = 2020-06-09) for
`hwGponDeviceOlt/OntLastUp/DownTime 2011.6.128.1.1.2.21.1.17/.18, .46.1.22, .48.1.8, .52.1.4`
in the gist file. Board/temperature `2011.2.6.7.1.1.2` and serial-number hex quirks
(`...2.43.1.3` returns "HWTC" + binary tail) in the forum excerpts.

## fiberhome/  (AN55xx)

| file | device | source | license |
|---|---|---|---|
| librenms_fiberhome.snmprec | AN5516-01 OLT (real; card sw versions RP0700/WKE2.115.331R1A, temp) | .../tests/snmpsim/fiberhome.snmprec | GPL-3.0 |
| librenms_fiberhome_an5516-01.snmprec | AN5516-01 (os-detection stub, 6 lines) | .../tests/snmpsim/fiberhome_an5516-01.snmprec | GPL-3.0 |
| librenms_fiberhome_an5516-04.snmprec | AN5516-04 stub | .../tests/snmpsim/fiberhome_an5516-04.snmprec | GPL-3.0 |
| librenms_fiberhome_an5516-06.snmprec | AN5516-06 stub | .../tests/snmpsim/fiberhome_an5516-06.snmprec | GPL-3.0 |
| librenms_expected_fiberhome.json | ground truth | .../tests/data/fiberhome.json | GPL-3.0 |

Covers: sysObjectID `5875.800.1001.11/.12`, card table `5875.800.3.9.8.1.1.x`
(cpu/mem 458=45.8%, temp), OLT temp `5875.800.3.9.4.5` (45 = 45 C), ONU online counts
`5875.800.3.60.x`. **GAP: no per-ONU optical DDM walk found publicly**
(`onuRxPower 5875.800.3.9.3.3` / uplink `5875.800.3.9.3.5.1.7`, div 100 per vendor docs) —
these tables are documented but no genuine dump located; capture from a real AN5516 needed.

## nokia/  (7360 ISAM)

| file | device | source | license |
|---|---|---|---|
| librenms_nokia-isam.snmprec | Nokia 7360 ISAM R6.5.02r NFXS-E FANT-H (real, GPON LT boards) | .../tests/snmpsim/nokia-isam.snmprec | GPL-3.0 |
| librenms_expected_nokia-isam.json | ground truth (dbm sensors per PON port) | .../tests/data/nokia-isam.json | GPL-3.0 |

Covers: eqpt/slot tables `637.61.1.9/.23`, SFP DDM ints `637.61.1.23.10.1.2`,
**PON port optics `637.61.1.56.5.1.6/.7` as STRINGS**: "-0.34 dBm", "4.94 dBm", "No Power",
"Lane0: No-Power; Lane1: ..." — string parsing edge cases; expected JSON shows decoded values
(e.g. lt:1/1/1/2 Tx Power -5.49 dBm, divisor 1). No per-ONT optics
(`ontOpticsRxSignalLevel 637.61.1.35.10.x`) found in any public dump.

## datacom/  (DM4610 / DM4611 / DM4616 / DM4618, DmOS)

| file | device | source | license |
|---|---|---|---|
| librenms_datacom-dmos_dm4610-hw2.snmprec | DM4610 8GPON+8GX+4GT+2XS, DmOS 9.4.0 (real) | .../tests/snmpsim/datacom-dmos_dm4610-hw2.snmprec | GPL-3.0 |
| librenms_datacom-dmos_dm4611.snmprec | DM4611 4GPON, DmOS 9.0.0 | .../tests/snmpsim/datacom-dmos_dm4611.snmprec | GPL-3.0 |
| librenms_datacom-dmos_dm4616.snmprec | DM4616 4XGS-PON+4XS (XGS-PON!) | .../tests/snmpsim/datacom-dmos_dm4616.snmprec | GPL-3.0 |
| librenms_datacom-dmos_dm4618.snmprec | DM4618 32GPON | .../tests/snmpsim/datacom-dmos_dm4618.snmprec | GPL-3.0 |
| librenms_datacom.snmprec | Datacom ETH24GX+4XS+MPLS switch (non-PON, same enterprise 3709) | .../tests/snmpsim/datacom.snmprec | GPL-3.0 |
| librenms_expected_datacom-dmos_dm4610-hw2.json | ground truth (temp sensor `3709.3.6.4.1.2.1.4`) | .../tests/data/datacom-dmos_dm4610-hw2.json | GPL-3.0 |

Covers: sysObjectID `3709.1.2.137`, DmOS sensors `3709.3.6.4.x` (temperature; `.4.2.2` gauges),
ifTable for PON ports. No per-ONU optical table in these walks.

## parks/

| file | device | source | license |
|---|---|---|---|
| librenms_parks-switch.snmprec | Parks PK-700 (switch, enterprise 50224; real) | .../tests/snmpsim/parks-switch.snmprec | GPL-3.0 |
| librenms_expected_parks-switch.json | ground truth | .../tests/data/parks-switch.json | GPL-3.0 |

Covers: SFP DDM `50224.3.2.4.1.8` (-100 -> -10.0 dBm, 0.1 dBm units), `.11/.12` (tx/other,
invalid marker -2147483648 = INT32_MIN), temp `50224.3.1.1.23`. NOTE: PK-700 is a Parks
switch, not an OLT — same vendor SNMP conventions; no public Parks OLT walk found.

## vsol/  (V-SOL V1600D)

| file | device | source | license |
|---|---|---|---|
| librenms_vsolution_v1600d.snmprec | V-SOL V1600D EPON OLT (real, "V1600D_EPON") | .../tests/snmpsim/vsolution_v1600d.snmprec | GPL-3.0 |
| librenms_expected_vsolution_v1600d.json | ground truth | .../tests/data/vsolution_v1600d.json | GPL-3.0 |

Covers: enterprise `37950.1.1.5`; system `5.10.12.x` (temp `5.10.12.3`, cpu `5.10.12.5.9`),
PON module DDM `5.10.13.1.1.2..5` (temp/voltage/bias/tx per LibreNMS vsolution.yaml),
per-ONU table `5.12.2.1.8.1.x` (online status, rx `.3`, tx `.7`).

## bdcom/  (P33xx / GP3600)

| file | device | source | license |
|---|---|---|---|
| librenms_bdcom.snmprec | BDCOM GP3600-16B GPON OLT sw 74104 (real) | .../tests/snmpsim/bdcom.snmprec | GPL-3.0 |
| librenms_expected_bdcom.json | ground truth | .../tests/data/bdcom.json | GPL-3.0 |
| librenms_fs-bdcom_ies5100-16ts.snmprec | FS.com IES5100-16TS (BDCOM OEM, enterprise 52642 — same MIB layout re-rooted) | .../tests/snmpsim/fs-bdcom_ies5100-16ts.snmprec | GPL-3.0 |
| nagwiki_bdcom_p3608b_gp3600-08b_excerpts.txt | BDCOM P3608B (EPON) + GP3600-08B (GPON), NAG lab devices; CLI output cross-checks SNMP scaling | https://nag.wiki/pages/viewpage.action?pageId=38764878 | unclear |

Covers: GPON ONU tables `3320.10.2/.10.3` (in snmprec and excerpts: OLT-side per-ONU rx
`3320.10.2.3.1.3` = -121 -> -12.1 dBm; ONU DDM `3320.10.3.4.1.2/.3` = rx/tx),
EPON `3320.101.x` (onu status `101.11.4.1.5`, OLT rx per ONU `101.108.1.3` = -340 -> -34.0 dBm
**proven against CLI "show epon optical-transceiver-diagnosis" -34.0 dBm**, ONU DDM
`101.10.5.1.5/.6`), board sensors `3320.3.6.x`, FS clone identical structure under 52642.
Scaling: **0.1 dBm** units throughout.

## cdata/  (FD11xx/FD16xx)

| file | device | source | license |
|---|---|---|---|
| librenms_cdata.snmprec | CData OLT "zaporojskoe-olt" (sysObjectID 1.3.6.1.4.1.17409, real ISP device) | .../tests/snmpsim/cdata.snmprec | GPL-3.0 |
| librenms_expected_cdata.json | ground truth | .../tests/data/cdata.json | GPL-3.0 |

Covers: dual enterprise quirk (sysObjectID under 17409, data under **34592**):
versions `34592.1.3.1.5.2.1.1.x`, sensors `34592.1.3.100.1.8.x` (temp 19 C, voltage 242,
bias 86, tx-power 305 per LibreNMS cdata.yaml scaling). No per-ONU optical walk found.

## ubiquiti/  (UFiber OLT)

| file | device | source | license |
|---|---|---|---|
| librenms_edgeosolt.snmprec | Ubiquiti UFiber OLT, EdgeOS v4.4.2 (real, dozens of ONUs) | .../tests/snmpsim/edgeosolt.snmprec | GPL-3.0 |
| librenms_edgeosolt_uisp-fiber.snmprec | UISP Fiber OLT XGS 4.6.1 (XGS-PON!) | .../tests/snmpsim/edgeosolt_uisp-fiber.snmprec | GPL-3.0 |
| librenms_expected_edgeosolt.json | ground truth (rx dBm per ONU, divisor 100) | .../tests/data/edgeosolt.json | GPL-3.0 |

Covers: UBNT-UFiber MIB `41112.1.5`: ONU table `.6.2.1` indexed by ASCII serial
("UBNT20731888" encoded as length-prefixed dotted decimals!) — `.6.2.1.9` = **ONU rx power in
0.01 dBm** (-2481 -> -24.81 dBm), `.6.2.1.8` tx, `.7.2` ONU system table, `.4.2/.5.2` PON port
tables; plus UCD `2021.x`. Expected JSON confirms divisor 100.

---

## Found but inaccessible / not obtained

- **ZTE C650 full snmpwalk** referenced in https://community.librenms.org/t/-/24062
  (paste links https://p.libren.ms/view/c8eb3575, .../c2a50dbb, .../a97d423e) — p.libren.ms
  no longer resolves (service dead). Would be the best C6xx source if ever mirrored.
- **ixnfo.com** OID/DDM articles (Huawei/BDCOM/CData/V-SOL, e.g.
  https://ixnfo.com/en/huawei-olt-ddm-snmp-oid-en.html) — HTTP 403 to all fetchers; Wayback
  copy checked, contains commands/formulas but no raw output.
- **Zabbix forum** thread https://www.zabbix.com/forum/in-russian/50940-мониторинг-pon —
  redirect loop, not fetchable.
- **GitHub code search** for OID literals requires authentication (no GH token in this env);
  gist search UI yielded only the items saved above.
- **FiberHome AN55xx per-ONU optical DDM** and **Nokia ISAM per-ONT optics
  (637.61.1.35.10.x)** — no genuine public dumps found anywhere; capture from real
  devices needed.
- grep.app blocked by Vercel challenge; Sourcegraph public index has no raw OLT walks.
