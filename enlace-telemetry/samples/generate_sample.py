#!/usr/bin/env python3
"""
Generate a realistic Adtran SDX 6320 telemetry CSV for the Enlace pilot demo.

Models a small Community-Fibre-style PON deployment (~52 ONTs across 4 PON
ports) over a 7-day window, with deliberately seeded fault patterns so the
Enlace audit engine surfaces real findings:

  - Fibre cut      : 4 ONTs on CTP-0/2 go hard-offline (LOS) and stay down
  - Area power blip : CTP-0/4 mixed event — 3 LOS + 2 dying-gasp at one window
  - Degrading signal: 2 ONTs on CTP-0/1 drift from ~-22 dBm toward ~-29 dBm
  - Ghost customer  : 1 ONT online 100% but flat Rx (no real traffic)
  - Flapping ONT    : 1 ONT with a rapid up/down burst (marginal Rx)

Deterministic (fixed seed) so the committed CSV is reproducible.

Usage:  python3 generate_sample.py > community_fibre_adtran_sdx6320.csv
"""
import csv
import random
import sys
from datetime import datetime, timedelta

random.seed(42)

# 7-day window, one reading every 6 hours (29 timestamps incl. both ends).
START = datetime(2026, 3, 1, 0, 0, 0)
STEP = timedelta(hours=6)
N_STEPS = 28  # -> 29 timestamps day0 00:00 .. day7 00:00
TIMES = [START + STEP * i for i in range(N_STEPS + 1)]
END = TIMES[-1]

HEADER = [
    "timestamp", "ont_serial", "pon_port",
    "rx_power_dbm", "tx_power_dbm", "status",
    "distance", "eth_speed_mbps", "last_down_cause",
]

_serial_counter = 0
def serial():
    """Adtran-style serials with a Community Fibre 'CF' flavour."""
    global _serial_counter
    _serial_counter += 1
    return f"ADTN-CF{_serial_counter:04X}"

def fmt_ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

rows = []
def emit(ts, sn, port, rx, tx, status, dist, cause=""):
    rx_s = "" if rx is None else f"{rx:.1f}"
    tx_s = "" if tx is None else f"{tx:.1f}"
    rows.append([fmt_ts(ts), sn, port, rx_s, tx_s, status, dist, "1000", cause])

def healthy_series(sn, port, base_rx, dist):
    """Online throughout. Rx stays comfortably above -20 dBm with a gentle
    upward drift (slope > -0.01) and enough jitter to clear the ghost-variance
    floor, so the churn classifier leaves these alone."""
    tx = round(random.uniform(2.0, 3.0), 1)
    for i, ts in enumerate(TIMES):
        frac = i / N_STEPS
        rx = base_rx + 0.15 * frac + random.uniform(-0.3, 0.3)
        emit(ts, sn, port, round(rx, 1), tx, "online", dist)

# ---------------------------------------------------------------- CTP-0/1 (16)
# 14 healthy + 2 degrading-signal (churn risk)
for _ in range(14):
    healthy_series(serial(), "CTP-0/1", random.uniform(-19.0, -16.0),
                   random.randint(400, 1800))

for _ in range(2):
    sn = serial(); tx = round(random.uniform(2.0, 3.0), 1)
    dist = random.randint(1800, 2600)
    for i, ts in enumerate(TIMES):
        # Linear drift -22.0 -> -29.0 across the window
        frac = i / N_STEPS
        rx = -22.0 - 7.0 * frac + random.uniform(-0.2, 0.2)
        emit(ts, sn, "CTP-0/1", round(rx, 1), tx, "online", dist)

# ---------------------------------------------------------------- CTP-0/2 (14)
# 10 healthy + 4 fibre-cut (hard offline, LOS, stays down for last 2 windows)
for _ in range(10):
    healthy_series(serial(), "CTP-0/2", random.uniform(-19.0, -16.0),
                   random.randint(300, 1600))

cut_from = N_STEPS - 1  # second-to-last timestamp
for _ in range(4):
    sn = serial(); tx = round(random.uniform(2.0, 3.0), 1)
    dist = random.randint(900, 2200)
    base = random.uniform(-18.5, -16.5)
    for i, ts in enumerate(TIMES):
        if i >= cut_from:
            emit(ts, sn, "CTP-0/2", None, tx, "offline", dist, "los")
        else:
            rx = base + 0.15 * (i / N_STEPS) + random.uniform(-0.25, 0.25)
            emit(ts, sn, "CTP-0/2", round(rx, 1), tx, "online", dist)

# ---------------------------------------------------------------- CTP-0/3 (12)
# 10 healthy + 1 ghost (flat Rx) + 1 flapping (burst on day 3)
for _ in range(10):
    healthy_series(serial(), "CTP-0/3", random.uniform(-19.0, -16.0),
                   random.randint(350, 1700))

# Ghost: online 100%, Rx pinned flat at -20.0 (zero variance), eth link up.
ghost_sn = serial()
for ts in TIMES:
    emit(ts, ghost_sn, "CTP-0/3", -19.0, 2.5, "online", 760)

# Flapping: normal 6-hourly readings, plus a rapid up/down burst on day 3.
flap_sn = serial(); flap_tx = 2.6; flap_dist = 1450
for ts in TIMES:
    rx = -25.5 + random.uniform(-0.4, 0.4)
    emit(ts, flap_sn, "CTP-0/3", round(rx, 1), flap_tx, "online", flap_dist)
burst_start = datetime(2026, 3, 3, 14, 0, 0)
for k in range(20):  # 20 readings @ 5 min -> ~19 transitions in ~1.6h
    ts = burst_start + timedelta(minutes=5 * k)
    if k % 2 == 0:
        emit(ts, flap_sn, "CTP-0/3", round(-26.5 + random.uniform(-0.3, 0.3), 1),
             flap_tx, "offline", flap_dist, "los")
    else:
        emit(ts, flap_sn, "CTP-0/3", round(-26.0 + random.uniform(-0.3, 0.3), 1),
             flap_tx, "online", flap_dist)

# ---------------------------------------------------------------- CTP-0/4 (10)
# 5 healthy + mixed area event (3 LOS + 2 dying-gasp) at one window, then recover
for _ in range(5):
    healthy_series(serial(), "CTP-0/4", random.uniform(-19.0, -16.0),
                   random.randint(300, 1500))

outage_ts = datetime(2026, 3, 6, 6, 0, 0)  # aligns with a 6-hourly window
def area_event_series(sn, port, dist, cause):
    tx = round(random.uniform(2.0, 3.0), 1)
    base = random.uniform(-18.5, -16.5)
    for i, ts in enumerate(TIMES):
        if ts == outage_ts:
            emit(ts, sn, port, None, tx, "offline", dist, cause)
        else:
            rx = base + 0.15 * (i / N_STEPS) + random.uniform(-0.25, 0.25)
            emit(ts, sn, port, round(rx, 1), tx, "online", dist)

for _ in range(3):
    area_event_series(serial(), "CTP-0/4", random.randint(600, 1900), "los")
for _ in range(2):
    area_event_series(serial(), "CTP-0/4", random.randint(600, 1900), "dying_gasp")

# ---------------------------------------------------------------- write
rows.sort(key=lambda r: (r[0], r[2], r[1]))  # by timestamp, port, serial
w = csv.writer(sys.stdout)
w.writerow(HEADER)
w.writerows(rows)

print(f"# {len(rows)} rows, {_serial_counter} ONTs, "
      f"{fmt_ts(START)} .. {fmt_ts(END)}", file=sys.stderr)
