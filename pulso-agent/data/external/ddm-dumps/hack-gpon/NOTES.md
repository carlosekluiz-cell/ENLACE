# NOTES — hack-gpon.org ONT/SFP reference pages

- Source repo: https://github.com/hack-gpon/hack-gpon.github.io (rendered at https://hack-gpon.org)
- License: MIT (see LICENSE in this directory, copied from repo root)
- Download date: 2026-07-02 (git shallow clone of main branch)
- What: community-documented pages for PON ONT sticks/ONTs. The stick pages contain
  **real, per-device SFF-8472 A0h/A2h EEPROM layout tables with actual byte values**,
  including DDM alarm/warning thresholds (TX/RX power, bias, temperature) — directly
  useful for SFP DDM plausibility ranges. Some pages also include real CLI optical
  readings (e.g. Sercomm FGS202 `TX POWER 2.97mW 4.73dBm / RX POWER -14.46dBm`).

| File | Device | Notes |
|---|---|---|
| ont-huawei-ma5671a.md | Huawei MA5671A GPON SFP ONT stick | Full A0h+A2h EEPROM tables with real values and DDM thresholds |
| ont-zyxel-pmg3000-d20b.md | Zyxel PMG3000-D20B GPON SFP ONT stick | Full A0h+A2h EEPROM tables, uncalibrated (all-zero calibration slopes) |
| ont-fs-com-gpon-onu-stick-with-mac.md | FS.com GPON ONU stick (with MAC) | Full A0h+A2h EEPROM tables incl. thresholds |
| ont-fibermall-gpon-onu-clb+.md | Fibermall GPON ONU CLB+ | EEPROM tables |
| ont-fibermall-gpon-onu-stb+.md | Fibermall GPON ONU STB+ | EEPROM tables |
| ont-fs-com-onu1710-1g.md | FS.com ONU1710-1G | EEPROM info, serial dumps |
| ont-bt-pon-bt-g711ax.md | BT G-711AX ONT | EEPROM/optics info |
| ont-sercomm-fgs202.md | Sercomm FGS202 ONT | Real CLI dump incl. TX/RX optical power readings |
| ont-nokia-g-010g-t.md | Nokia G-010G-T ONT | EEPROM info |
| ont-adtran-sdx-611.md | Adtran SDX 611 GPON ONT (Openreach) | Teardown, Realtek RTL9601D, U&T UTG24P05 BOSA; no DDM dump |
| ont-adtran-sdx-611q.md | Adtran SDX 611Q | Stub page |
| ont-adtran-sdx-621i.md | Adtran SDX 621i | Short page |
| serial_dump/ma5671a_minishell.txt | Huawei MA5671A | Real serial console capture |
| serial_dump/fg1000b-11_boot_cfe.txt | FG1000B-11 | Real boot log |
| serial_dump/yotcm2-2050-g40.txt, ...newrevision.txt | YOTCM2-2050-G40 | Real boot logs |
| serial_dump/fs-com-onu1710-1g/bootlog.txt, uboot-env.txt | FS.com ONU1710-1G | Real boot log + u-boot env |

Original file URLs: https://github.com/hack-gpon/hack-gpon.github.io/blob/main/_ont/<filename>
