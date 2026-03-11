"""H3 hexagonal grid computation pipeline.

Batch-computes H3 grids for all municipalities at resolution 7 and 9.
For each municipality:
  1. Polyfill geometry with H3 cells using PostgreSQL h3_polygon_to_cells
  2. Count base stations (towers) per hex cell
  3. Distribute subscriber count across cells
  4. Distribute population across cells
  5. Compute penetration percentages

Dependencies:
  - admin_level_2 must have geometries loaded (ibge_census pipeline)
  - broadband_subscribers must have data (anatel_broadband pipeline)
  - base_stations must have data (anatel_base_stations pipeline)

Sources:
  - H3 cells: computed from admin_level_2.geom via h3_polygon_to_cells
  - Subscribers: broadband_subscribers aggregated per municipality
  - Towers: base_stations point-in-polygon matched to municipalities
"""

import logging
from typing import Any

from python.pipeline.base import BasePipeline

logger = logging.getLogger(__name__)

# Resolutions to compute: 7 (~5.16 km2 per cell) and 9 (~0.105 km2 per cell)
TARGET_RESOLUTIONS = [7, 9]

# Process municipalities in batches
BATCH_SIZE = 50


class H3GridPipeline(BasePipeline):
    """Batch compute H3 hexagonal grids for all municipalities."""

    def __init__(self):
        super().__init__("h3_grid")

    def check_for_updates(self) -> bool:
        """Check if H3 grid computation is needed.

        Returns True if fewer than half of municipalities with geometry
        have H3 cells at resolution 7, indicating the grid needs to be
        (re)computed.
        """
        conn = self._get_connection()
        cur = conn.cursor()

        # Count municipalities that have geometry
        cur.execute(
            "SELECT COUNT(*) FROM admin_level_2 WHERE geom IS NOT NULL"
        )
        total_with_geom = cur.fetchone()[0]

        # Count municipalities that have H3 cells at resolution 7
        cur.execute("""
            SELECT COUNT(DISTINCT l2_id) FROM h3_cells WHERE resolution = 7
        """)
        computed_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        if total_with_geom == 0:
            logger.warning("No municipalities have geometry — cannot compute H3 grid")
            return False

        ratio = computed_count / total_with_geom
        logger.info(
            f"H3 coverage: {computed_count}/{total_with_geom} municipalities "
            f"({ratio:.1%}) have res-7 cells"
        )
        return ratio < 0.5

    def download(self) -> Any:
        """No external download needed — all data is already in PostgreSQL.

        Returns a list of (municipality_id, code, name) tuples for
        municipalities that have geometry.
        """
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT a2.id, a2.code, a2.name
            FROM admin_level_2 a2
            WHERE a2.geom IS NOT NULL
            ORDER BY a2.id
        """)
        municipalities = cur.fetchall()

        cur.close()
        conn.close()

        logger.info(f"Found {len(municipalities)} municipalities with geometry")
        return municipalities

    def validate_raw(self, data: Any) -> None:
        """Validate that we have municipalities to process."""
        if not data:
            raise ValueError("No municipalities with geometry found in database")
        logger.info(f"Will compute H3 grids for {len(data)} municipalities")

    def transform(self, raw_data: Any) -> Any:
        """No transformation needed — computation happens in load()."""
        self.rows_processed = len(raw_data) * len(TARGET_RESOLUTIONS)
        return raw_data

    def load(self, data: Any) -> None:
        """Compute H3 grids for all municipalities at target resolutions.

        For each municipality and resolution:
        1. Polyfill geometry with H3 cells
        2. Aggregate tower counts per cell
        3. Distribute subscribers and population across cells
        4. Compute penetration percentage
        """
        conn = self._get_connection()
        cur = conn.cursor()

        total_cells_inserted = 0
        total_municipalities = len(data)

        for resolution in TARGET_RESOLUTIONS:
            logger.info(
                f"Computing H3 grid at resolution {resolution} "
                f"for {total_municipalities} municipalities..."
            )

            failed = 0
            for batch_start in range(0, total_municipalities, BATCH_SIZE):
                batch = data[batch_start:batch_start + BATCH_SIZE]

                for mun_id, mun_code, mun_name in batch:
                    try:
                        cells = self._compute_municipality(
                            cur, conn, mun_id, resolution
                        )
                        total_cells_inserted += cells
                    except Exception as e:
                        logger.warning(
                            f"Failed to compute H3 for {mun_name} "
                            f"(id={mun_id}): {e}"
                        )
                        conn.rollback()
                        failed += 1
                        continue

                # Progress log per batch
                processed = min(batch_start + BATCH_SIZE, total_municipalities)
                logger.info(
                    f"Resolution {resolution}: {processed}/{total_municipalities} "
                    f"municipalities processed ({total_cells_inserted:,} cells total)"
                )

            if failed > 0:
                logger.warning(
                    f"Resolution {resolution}: {failed} municipalities failed"
                )

        self.rows_inserted = total_cells_inserted
        cur.close()
        conn.close()
        logger.info(
            f"H3 grid computation complete: {total_cells_inserted:,} cells "
            f"across {total_municipalities} municipalities at resolutions "
            f"{TARGET_RESOLUTIONS}"
        )

    def _compute_municipality(
        self, cur, conn, municipality_id: int, resolution: int
    ) -> int:
        """Compute H3 grid for a single municipality.

        Returns the number of cells created/updated.
        """
        # Step 1: Polyfill geometry with H3 cells.
        # ST_Dump handles MultiPolygon geometries (all municipalities use
        # MultiPolygon in our database).
        cur.execute("""
            INSERT INTO h3_cells (h3_index, resolution, l2_id, computed_at)
            SELECT DISTINCT
                cell::text,
                %s,
                %s,
                NOW()
            FROM admin_level_2 a2,
                 LATERAL ST_Dump(a2.geom) AS dump,
                 LATERAL h3_polygon_to_cells(dump.geom, %s) AS cell
            WHERE a2.id = %s
            ON CONFLICT (h3_index, resolution) DO UPDATE
            SET l2_id = %s,
                computed_at = NOW()
        """, (resolution, municipality_id, resolution, municipality_id, municipality_id))
        cell_count = cur.rowcount
        conn.commit()

        if cell_count == 0:
            return 0

        # Step 2: Count towers per H3 cell.
        cur.execute("""
            UPDATE h3_cells hc
            SET tower_count = tower_data.cnt
            FROM (
                SELECT
                    h3_lat_lng_to_cell(
                        ST_MakePoint(bs.longitude, bs.latitude)::point,
                        %s
                    )::text AS cell_index,
                    COUNT(*) AS cnt
                FROM base_stations bs
                JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
                WHERE a2.id = %s
                GROUP BY cell_index
            ) tower_data
            WHERE hc.h3_index = tower_data.cell_index
              AND hc.resolution = %s
        """, (resolution, municipality_id, resolution))
        conn.commit()

        # Step 3: Distribute subscribers evenly across cells.
        # This is an approximation; real distribution would require
        # address-level data.
        cur.execute("""
            UPDATE h3_cells hc
            SET subscribers = sub_data.per_cell_subs
            FROM (
                SELECT
                    hc2.id AS cell_id,
                    COALESCE(
                        (SELECT SUM(bs.subscribers)
                         FROM broadband_subscribers bs
                         WHERE bs.l2_id = %s
                           AND bs.year_month = (
                               SELECT MAX(bs2.year_month)
                               FROM broadband_subscribers bs2
                               WHERE bs2.l2_id = %s
                           )
                        ) / NULLIF(
                            (SELECT COUNT(*) FROM h3_cells
                             WHERE l2_id = %s AND resolution = %s),
                            0
                        ),
                        0
                    ) AS per_cell_subs
                FROM h3_cells hc2
                WHERE hc2.l2_id = %s
                  AND hc2.resolution = %s
            ) sub_data
            WHERE hc.id = sub_data.cell_id
        """, (
            municipality_id, municipality_id,
            municipality_id, resolution,
            municipality_id, resolution,
        ))
        conn.commit()

        # Step 4: Distribute population evenly across cells.
        cur.execute("""
            UPDATE h3_cells hc
            SET population_estimate = pop_data.per_cell_pop
            FROM (
                SELECT
                    hc2.id AS cell_id,
                    COALESCE(
                        (SELECT a2.population FROM admin_level_2 a2
                         WHERE a2.id = %s
                        ) / NULLIF(
                            (SELECT COUNT(*) FROM h3_cells
                             WHERE l2_id = %s AND resolution = %s),
                            0
                        ),
                        0
                    ) AS per_cell_pop
                FROM h3_cells hc2
                WHERE hc2.l2_id = %s
                  AND hc2.resolution = %s
            ) pop_data
            WHERE hc.id = pop_data.cell_id
        """, (
            municipality_id,
            municipality_id, resolution,
            municipality_id, resolution,
        ))
        conn.commit()

        # Step 5: Compute penetration percentage.
        cur.execute("""
            UPDATE h3_cells hc
            SET penetration_pct = CASE
                WHEN hc.population_estimate > 0 AND hc.subscribers > 0
                THEN ROUND((hc.subscribers::numeric / hc.population_estimate * 100), 2)
                ELSE 0
            END
            WHERE hc.l2_id = %s
              AND hc.resolution = %s
        """, (municipality_id, resolution))
        conn.commit()

        return cell_count

    def post_load(self) -> None:
        """Log final summary after all computations."""
        conn = self._get_connection()
        cur = conn.cursor()

        for res in TARGET_RESOLUTIONS:
            cur.execute(
                "SELECT COUNT(*), COUNT(DISTINCT l2_id) FROM h3_cells WHERE resolution = %s",
                (res,),
            )
            total_cells, total_munis = cur.fetchone()
            logger.info(
                f"Resolution {res}: {total_cells:,} cells across "
                f"{total_munis:,} municipalities"
            )

        cur.close()
        conn.close()
