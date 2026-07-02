# NOTES — real `ethtool -m` dumps extracted from public GitHub issues

All files: raw fenced code blocks containing SFF-8472 `ethtool -m` output, extracted
verbatim from public GitHub issue bodies/comments (source URL and commenter recorded
in each file header). Download date: 2026-07-02. License: user-posted content on
GitHub — **unclear**, treat as quotable reference only, do not redistribute.

| File | Device / module | What it shows |
|---|---|---|
| openwrt_openwrt_issue17733.txt | Zyxel PMG3000-D20B GPON SFP ONT stick | Full ethtool -m dump: 1000BASE-LX PON stick, 1310nm, SC, DDM readings (incl. odd 0.000 mA bias + -inf RX while dumped out-of-slot) |
| openwrt_openwrt_issue17673.txt | OEM "SFP+-T30" 10GBase-SR module on Banana Pi R4 | Full dumps incl. DDM readings and alarm/warning thresholds |
| frank-w_BPI-Router-Linux_issue185.txt | 1000BASE-LX/FC SFP on BPI-R4 | Dump with DDM section |
| openwrt_mt76_issue732.txt | FS SFP-GE-BX 1000BASE-BX10 BiDi (1310nm TX) on BPI-R3 | Two full dumps incl. DDM + thresholds (BiDi example) |

Not found despite targeted search: a public raw `ethtool -m pon0` dump of a WAS-110 /
X-ONU-SFPP XGS-PON stick. pon.wiki documents the commands and the expected optical
spec ranges but publishes no sample output:
- https://pon.wiki/xgs-pon/ont/bfw-solutions/was-110/
- https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/
  (contains min/max optical spec table for WAS-110; license CC BY-NC-SA 4.0)
- Markdown source: https://github.com/up-n-atom/PONwiki (CC BY-NC-SA 4.0)
