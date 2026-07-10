#!/usr/bin/env python3
"""Classify environment + clutter for scored residuals via MapBiomas.

For every rf_residuals row: clutter class from the measurement point's
MapBiomas pixel, environment from a 5x5 sample over a ~300 m box
(urban fraction thresholds, same rule the coverage engine uses).
Processes tile-by-tile (ORDER BY tile) so the memmap LRU stays warm.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
import psycopg2.extras

from python.api.config import Settings
from python.api.services import clutter as clutter_svc
from python.api.services.terrain_reader import LandcoverReader

BATCH = 20_000


def main() -> None:
    # Separate connections: committing on the writer must not invalidate
    # the reader's server-side cursor.
    read_conn = psycopg2.connect(Settings().database_sync_url)
    conn = psycopg2.connect(Settings().database_sync_url)
    cur = read_conn.cursor("fetch")  # server-side cursor
    cur.itersize = BATCH
    cur.execute("""
        SELECT r.measurement_id, m.lat, m.lon
        FROM rf_residuals r
        JOIN rf_measurements m ON m.id = r.measurement_id
        WHERE r.model = 'composite_v1' AND r.clutter IS NULL
        ORDER BY floor(m.lat), floor(m.lon)
    """)
    upd = conn.cursor()
    lc = LandcoverReader()
    t0, total, updates = time.time(), 0, []

    def flush():
        nonlocal updates, total
        if not updates:
            return
        psycopg2.extras.execute_values(
            upd,
            """
            UPDATE rf_residuals r SET environment = v.env, clutter = v.clu
            FROM (VALUES %s) AS v(mid, env, clu)
            WHERE r.measurement_id = v.mid
            """,
            updates,
        )
        conn.commit()
        total += len(updates)
        updates = []
        print(f"  {total:>9,} classified ({total / max(1, time.time() - t0):,.0f}/s)", flush=True)

    for mid, lat, lon in cur:
        code = lc.code(lat, lon)
        if code is None:
            continue
        clu = clutter_svc.classify(code).key
        # environment: 5x5 samples over ~300 m box
        codes = []
        for i in range(5):
            for j in range(5):
                c = lc.code(lat - 0.0014 + 0.0007 * i, lon - 0.0014 + 0.0007 * j)
                if c is not None:
                    codes.append(c)
        env = clutter_svc.infer_environment(codes)
        updates.append((mid, env, clu))
        if len(updates) >= BATCH:
            flush()
    flush()
    print(f"DONE: {total:,} residuals classified in {time.time() - t0:,.0f}s")


if __name__ == "__main__":
    main()
