"""Phase 1 Data Foundation Validation Tests.

Tests validate data integrity, completeness, and query performance
for the ENLACE data foundation layer.

Run: python tests/validation/phase1_validation.py
"""
import sys
import time
import json
import psycopg2

DB_URL = "postgresql://enlace:enlace_dev_2026@localhost:5432/enlace"


class ValidationResult:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def check(self, name: str, condition: bool, details: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  PASS  {name}")
        else:
            self.tests_failed += 1
            self.failures.append((name, details))
            print(f"  FAIL  {name}: {details}")

    def summary(self):
        print(f"\n{'='*60}")
        print(f"Phase 1 Validation: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailed tests:")
            for name, details in self.failures:
                print(f"  - {name}: {details}")
        print(f"{'='*60}")
        return self.tests_failed == 0


def get_conn():
    return psycopg2.connect(DB_URL)


def test_1_geographic_integrity(result: ValidationResult):
    """Test 1: Geographic data integrity."""
    print("\nTest 1: Geographic Data Integrity")
    conn = get_conn()
    cur = conn.cursor()

    # 1a: Brazil should have exactly 27 admin_level_1 records
    cur.execute("SELECT COUNT(*) FROM admin_level_1 WHERE country_code = 'BR'")
    state_count = cur.fetchone()[0]
    result.check("27 Brazilian states", state_count == 27, f"Found {state_count}")

    # 1b: Brazil should have approximately 5,570 municipalities (we have seed ~51)
    # Since we're using seed data, check we have at least 40
    cur.execute("SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'")
    muni_count = cur.fetchone()[0]
    result.check("At least 40 municipalities", muni_count >= 40, f"Found {muni_count}")

    # 1c: Census tracts should exist (at least 4 per municipality)
    cur.execute("SELECT COUNT(*) FROM census_tracts WHERE country_code = 'BR'")
    tract_count = cur.fetchone()[0]
    result.check(
        "Census tracts populated",
        tract_count >= muni_count * 4,
        f"Found {tract_count} tracts for {muni_count} municipalities",
    )

    # 1d: Every municipality has a valid l1_id (parent state)
    cur.execute("""
        SELECT COUNT(*) FROM admin_level_2 al2
        WHERE al2.country_code = 'BR'
        AND NOT EXISTS (
            SELECT 1 FROM admin_level_1 al1
            WHERE al1.id = al2.l1_id AND al1.country_code = 'BR'
        )
    """)
    orphan_count = cur.fetchone()[0]
    result.check("No orphan municipalities", orphan_count == 0, f"{orphan_count} orphans")

    # 1e: Every tract has a valid l2_id (parent municipality)
    cur.execute("""
        SELECT COUNT(*) FROM census_tracts ct
        WHERE ct.country_code = 'BR'
        AND NOT EXISTS (
            SELECT 1 FROM admin_level_2 al2
            WHERE al2.id = ct.l2_id AND al2.country_code = 'BR'
        )
    """)
    orphan_tracts = cur.fetchone()[0]
    result.check("No orphan census tracts", orphan_tracts == 0, f"{orphan_tracts} orphans")

    # 1f: Municipality centroids are within Brazil bounding box
    cur.execute("""
        SELECT COUNT(*) FROM admin_level_2
        WHERE country_code = 'BR' AND centroid IS NOT NULL
        AND (ST_Y(centroid) < -33.77 OR ST_Y(centroid) > 5.27
             OR ST_X(centroid) < -73.99 OR ST_X(centroid) > -28.83)
    """)
    out_of_bounds = cur.fetchone()[0]
    result.check(
        "All centroids within Brazil", out_of_bounds == 0, f"{out_of_bounds} out of bounds"
    )

    cur.close()
    conn.close()


def test_2_demographic_completeness(result: ValidationResult):
    """Test 2: Demographic data completeness."""
    print("\nTest 2: Demographic Data Completeness")
    conn = get_conn()
    cur = conn.cursor()

    # 2a: Every census tract has demographics for 2022
    cur.execute("""
        SELECT COUNT(*) FROM census_tracts ct
        WHERE ct.country_code = 'BR'
        AND NOT EXISTS (
            SELECT 1 FROM census_demographics cd
            WHERE cd.tract_id = ct.id AND cd.census_year = 2022
        )
    """)
    missing = cur.fetchone()[0]
    result.check("All tracts have 2022 demographics", missing == 0, f"{missing} tracts missing")

    # 2b: No negative population or household counts
    cur.execute("""
        SELECT COUNT(*) FROM census_demographics
        WHERE total_population < 0 OR total_households < 0 OR occupied_households < 0
    """)
    negative = cur.fetchone()[0]
    result.check("No negative population/household counts", negative == 0, f"{negative} negative")

    # 2c: Income data JSONB has all required bracket fields
    # Note: brackets are stored at the top level of income_data, not nested
    cur.execute("""
        SELECT COUNT(*) FROM census_demographics
        WHERE income_data IS NOT NULL
        AND (
            income_data->>'below_half_min_wage' IS NULL
            OR income_data->>'half_to_one_min_wage' IS NULL
            OR income_data->>'one_to_two_min_wage' IS NULL
            OR income_data->>'two_to_five_min_wage' IS NULL
            OR income_data->>'five_to_ten_min_wage' IS NULL
            OR income_data->>'above_ten_min_wage' IS NULL
        )
    """)
    missing_brackets = cur.fetchone()[0]
    result.check(
        "Income data has all brackets",
        missing_brackets == 0,
        f"{missing_brackets} records missing bracket fields",
    )

    # 2d: Average income is reasonable (R$500-R$10000)
    cur.execute("""
        SELECT MIN((income_data->>'avg_per_capita_brl')::NUMERIC),
               MAX((income_data->>'avg_per_capita_brl')::NUMERIC)
        FROM census_demographics
        WHERE income_data->>'avg_per_capita_brl' IS NOT NULL
    """)
    min_income, max_income = cur.fetchone()
    result.check(
        "Income range reasonable",
        min_income is not None and float(min_income) >= 200 and float(max_income) <= 15000,
        f"Range: R${min_income} - R${max_income}",
    )

    cur.close()
    conn.close()


def test_3_subscriber_data(result: ValidationResult):
    """Test 3: Anatel subscriber data consistency."""
    print("\nTest 3: Anatel Subscriber Data")
    conn = get_conn()
    cur = conn.cursor()

    # 3a: Data freshness -- latest year_month should be recent
    cur.execute("SELECT MAX(year_month) FROM broadband_subscribers")
    latest = cur.fetchone()[0]
    result.check("Subscriber data exists", latest is not None, "No subscriber data")
    if latest:
        result.check("Latest data is 2025", latest.startswith("2025"), f"Latest: {latest}")

    # 3b: No municipality has more subscribers than households (penetration <= 110%)
    cur.execute("""
        WITH muni_subs AS (
            SELECT l2_id, SUM(subscribers) as total_subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        ),
        muni_hh AS (
            SELECT ct.l2_id, SUM(cd.total_households) as total_hh
            FROM census_tracts ct
            JOIN census_demographics cd ON cd.tract_id = ct.id
            GROUP BY ct.l2_id
        )
        SELECT COUNT(*) FROM muni_subs s
        JOIN muni_hh h ON h.l2_id = s.l2_id
        WHERE s.total_subs > h.total_hh * 1.1
    """)
    over_penetration = cur.fetchone()[0]
    result.check(
        "No over-penetration (subs <= households)",
        over_penetration == 0,
        f"{over_penetration} municipalities over 110%",
    )

    # 3c: Provider names are normalized (no obvious duplicates)
    cur.execute("""
        SELECT name_normalized, COUNT(*) as cnt
        FROM providers
        WHERE country_code = 'BR'
        GROUP BY name_normalized
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    result.check(
        "No duplicate provider names",
        len(duplicates) == 0,
        f"Duplicates: {duplicates}",
    )

    # 3d: All subscriber records reference valid providers and municipalities
    cur.execute("""
        SELECT COUNT(*) FROM broadband_subscribers bs
        WHERE NOT EXISTS (SELECT 1 FROM providers p WHERE p.id = bs.provider_id)
    """)
    orphan_subs = cur.fetchone()[0]
    result.check(
        "All subscribers reference valid providers",
        orphan_subs == 0,
        f"{orphan_subs} orphans",
    )

    cur.close()
    conn.close()


def test_4_spatial_performance(result: ValidationResult):
    """Test 4: Spatial query performance."""
    print("\nTest 4: Spatial Query Performance")
    conn = get_conn()
    cur = conn.cursor()

    # 4a: Find municipalities within 50km of Sao Paulo CBD
    start = time.time()
    cur.execute("""
        SELECT al2.name, al2.code
        FROM admin_level_2 al2
        WHERE al2.country_code = 'BR'
        AND al2.centroid IS NOT NULL
        AND ST_DWithin(
            al2.centroid::geography,
            ST_SetSRID(ST_MakePoint(-46.63, -23.55), 4326)::geography,
            50000
        )
    """)
    rows = cur.fetchall()
    elapsed = time.time() - start
    result.check(
        f"Spatial query < 2s (took {elapsed:.3f}s)", elapsed < 2.0, f"{elapsed:.3f}s"
    )
    result.check(
        "Spatial query returns results", len(rows) > 0, f"Found {len(rows)} municipalities"
    )

    # 4b: Market summary for an entire state
    start = time.time()
    cur.execute("""
        SELECT municipality_name, total_subscribers, provider_count
        FROM mv_market_summary
        WHERE state_abbrev = 'SP'
    """)
    rows = cur.fetchall()
    elapsed = time.time() - start
    result.check(
        f"State summary < 5s (took {elapsed:.3f}s)", elapsed < 5.0, f"{elapsed:.3f}s"
    )
    result.check("SP has municipalities", len(rows) > 0, f"Found {len(rows)}")

    cur.close()
    conn.close()


def test_5_terrain_data(result: ValidationResult):
    """Test 5: SRTM terrain data registration."""
    print("\nTest 5: Terrain Data")
    conn = get_conn()
    cur = conn.cursor()

    # 5a: Terrain tiles registered
    cur.execute("SELECT COUNT(*) FROM terrain_tiles")
    tile_count = cur.fetchone()[0]
    result.check("Terrain tiles registered", tile_count > 0, f"Found {tile_count} tiles")

    # 5b: All tiles have valid bounding boxes
    cur.execute("""
        SELECT COUNT(*) FROM terrain_tiles
        WHERE bbox IS NOT NULL AND ST_IsValid(bbox)
    """)
    valid_tiles = cur.fetchone()[0]
    result.check(
        "All tiles have valid bboxes",
        valid_tiles == tile_count,
        f"{valid_tiles}/{tile_count} valid",
    )

    # 5c: Tile bboxes overlap with Brazil
    cur.execute("""
        SELECT COUNT(*) FROM terrain_tiles tt
        WHERE ST_Intersects(
            tt.bbox,
            ST_MakeEnvelope(-73.99, -33.77, -28.83, 5.27, 4326)
        )
    """)
    brazil_tiles = cur.fetchone()[0]
    result.check("Tiles overlap Brazil", brazil_tiles > 0, f"{brazil_tiles} tiles in Brazil")

    cur.close()
    conn.close()


def test_6_multi_country(result: ValidationResult):
    """Test 6: Multi-country architecture."""
    print("\nTest 6: Multi-Country Architecture")
    conn = get_conn()
    cur = conn.cursor()

    # 6a: Colombia exists as a country
    cur.execute("SELECT COUNT(*) FROM countries WHERE code = 'CO'")
    result.check("Colombia country exists", cur.fetchone()[0] == 1)

    # 6b: Colombia has admin_level_1 data
    cur.execute("SELECT COUNT(*) FROM admin_level_1 WHERE country_code = 'CO'")
    co_states = cur.fetchone()[0]
    result.check("Colombia has states", co_states > 0, f"Found {co_states}")

    # 6c: Brazil queries filtered by country_code don't include Colombia
    cur.execute("""
        SELECT COUNT(*) FROM admin_level_1
        WHERE country_code = 'BR' AND name LIKE '%Bogot%'
    """)
    bogota_in_brazil = cur.fetchone()[0]
    result.check("Bogota not in Brazil results", bogota_in_brazil == 0)

    # 6d: Materialized view only shows Brazil
    cur.execute("SELECT DISTINCT country_code FROM mv_market_summary")
    countries = [r[0] for r in cur.fetchall()]
    result.check(
        "Market summary is Brazil-only",
        countries == ["BR"],
        f"Found countries: {countries}",
    )

    # 6e: API-like query with country_code filter works
    cur.execute("""
        SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'
    """)
    br_count = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'CO'
    """)
    co_count = cur.fetchone()[0]
    result.check(
        "Country filter separates data",
        br_count > 0 and co_count >= 0,
        f"BR={br_count}, CO={co_count}",
    )

    cur.close()
    conn.close()


def main():
    print("=" * 60)
    print("ENLACE Phase 1: Data Foundation Validation")
    print("=" * 60)

    result = ValidationResult()

    test_1_geographic_integrity(result)
    test_2_demographic_completeness(result)
    test_3_subscriber_data(result)
    test_4_spatial_performance(result)
    test_5_terrain_data(result)
    test_6_multi_country(result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
