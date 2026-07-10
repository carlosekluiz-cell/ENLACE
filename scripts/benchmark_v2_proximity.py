#!/usr/bin/env python3
"""Tier-2 composite scoring: measurements WITHOUT station attribution.

For each unattributed measurement, predict the total field from ALL
licensed stations within 1 km (incoherent power sum, same per-band
typical-EIRP and sector heuristic as tier-1) and store the residual as
model='composite_v2_prox'. distance_m records the strongest contributor.

Chunked and resumable: skips measurements already in rf_residuals.
Run: nohup python3 scripts/benchmark_v2_proximity.py > logs/tier2.log &
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2

from python.api.config import Settings

CHUNK = 20_000

SQL = """
WITH todo AS (
  SELECT m.id, m.lat, m.lon, m.e_field_vm
  FROM rf_measurements m
  LEFT JOIN rf_residuals r ON r.measurement_id = m.id
  WHERE r.measurement_id IS NULL
    AND m.station_number IS NULL
    AND m.e_field_vm >= 0.05
    AND m.id > %(last_id)s
  ORDER BY m.id
  LIMIT %(chunk)s
),
contrib AS (
  SELECT t.id, t.e_field_vm,
         sum(x.eirp_w / (4 * pi() * x.d * x.d)) AS s_total,
         min(x.d) FILTER (WHERE x.rnk = 1) AS d_strongest
  FROM todo t
  CROSS JOIN LATERAL (
    SELECT eirp_w, d,
           row_number() OVER (ORDER BY eirp_w / (d*d) DESC) AS rnk
    FROM (
      SELECT sum((CASE
                    WHEN g.band IN ('700','850','900') THEN 1000.0
                    WHEN g.band IN ('1800','2100') THEN 1258.9
                    WHEN g.band IN ('2300','2500') THEN 1584.9
                    WHEN g.band = '3500' THEN 3162.3
                    ELSE 1000.0
                  END) * ceil(g.cnt / 3.0)) AS eirp_w,
             greatest(min(g.dmin), 20.0) AS d
      FROM (
        SELECT a.station_number, a.band, count(*) AS cnt,
               min(earth_distance(ll_to_earth(t.lat, t.lon),
                                  ll_to_earth(a.lat, a.lon))) AS dmin
        FROM anatel_stations a
        WHERE earth_box(ll_to_earth(t.lat, t.lon), 1000) @> ll_to_earth(a.lat, a.lon)
          AND earth_distance(ll_to_earth(t.lat, t.lon), ll_to_earth(a.lat, a.lon)) <= 1000
          AND a.situacao IS DISTINCT FROM 'Cancelada'
        GROUP BY a.station_number, a.band
      ) g
      GROUP BY g.station_number
    ) per_station
  ) x
  GROUP BY t.id, t.e_field_vm
)
INSERT INTO rf_residuals
  (measurement_id, predicted_dbm, residual_db, model, distance_m)
SELECT id,
       20 * log(sqrt(377.0 * s_total)),
       20 * log(e_field_vm / sqrt(377.0 * s_total)),
       'composite_v2_prox',
       d_strongest
FROM contrib
WHERE s_total > 0
ON CONFLICT (measurement_id) DO NOTHING
RETURNING measurement_id
"""


def main() -> None:
    conn = psycopg2.connect(Settings().database_sync_url)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 0")
    total, last_id, t0 = 0, 0, time.time()
    while True:
        cur.execute(
            "SELECT max(id) FROM (SELECT m.id FROM rf_measurements m "
            "LEFT JOIN rf_residuals r ON r.measurement_id = m.id "
            "WHERE r.measurement_id IS NULL AND m.station_number IS NULL "
            "AND m.e_field_vm >= 0.05 AND m.id > %s ORDER BY m.id LIMIT %s) q",
            (last_id, CHUNK),
        )
        max_id = cur.fetchone()[0]
        if max_id is None:
            break
        cur.execute(SQL, {"last_id": last_id, "chunk": CHUNK})
        n = cur.rowcount
        conn.commit()
        total += n
        last_id = max_id
        rate = total / max(1, time.time() - t0)
        print(f"  {total:>9,} scored (last_id {last_id}, {rate:,.0f}/s)", flush=True)
    print(f"DONE: {total:,} tier-2 residuals in {time.time() - t0:,.0f}s")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
