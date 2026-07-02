# NOTES — Debian BTS ethtool -m dumps

| File | What | Source | License | Date |
|---|---|---|---|---|
| debian_bug960702_ethtool_dumps.txt | Two full `ethtool -m` dumps of 10GBASE-SR modules (Pureoptics EX-SFP-10GE-SR, FiberStore SFP-10GSR-85) on an mlx4_en NIC. IMPORTANT: some DDM values are corrupted — the mlx4 driver leaked uninitialized kernel memory on failed EEPROM reads (values change between reads, e.g. 1.2336 V module voltage). Genuine real-world NEGATIVE test case for DDM plausibility checks. | https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=960702 | user-posted content on Debian BTS, unclear | 2026-07-02 |
