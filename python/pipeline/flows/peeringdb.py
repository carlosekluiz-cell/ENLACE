"""PeeringDB Network Facilities pipeline — all LATAM countries.

Source: PeeringDB public API (https://www.peeringdb.com/api/)
Format: JSON (REST API, no auth required)

Downloads internet exchange points, data centers, and peering facilities
for all 19 LATAM countries (BR, CO + 17 expansion countries).
Maps to admin_level_2 municipalities via city name matching.

Schedule: Monthly
"""
import logging
import time
import unicodedata

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

PEERINGDB_FAC_BASE = "https://www.peeringdb.com/api/fac"
PEERINGDB_NET_BASE = "https://www.peeringdb.com/api/net"

# All 19 LATAM country codes
LATAM_COUNTRIES = [
    "BR", "CO", "MX", "AR", "CL", "UY", "PE", "EC", "DO", "PY",
    "PA", "CR", "GT", "HN", "BO", "SV", "VE", "NI", "CU",
]

REQUEST_DELAY = 1.0  # Polite delay between country requests


def _strip_accents(text: str) -> str:
    """Strip accents for fuzzy city matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


class PeeringDBPipeline(BasePipeline):
    """Ingest network peering facilities from PeeringDB for all LATAM countries.

    Downloads facility records (IXPs, data centers, colocation sites) and
    network records for each country, cross-references to count networks per
    facility, and loads into peering_facilities table.
    """

    def __init__(self):
        super().__init__("peeringdb")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM peering_facilities")
            count = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            count = 0
        cur.close()
        conn.close()
        return count < 20

    def download(self) -> dict:
        """Download facilities and networks from PeeringDB API for all LATAM countries."""
        all_facilities = []
        all_networks = []

        with PipelineHTTPClient(timeout=60) as http:
            for country_code in LATAM_COUNTRIES:
                # Facilities
                try:
                    fac_resp = http.get_json(
                        PEERINGDB_FAC_BASE, params={"country": country_code}
                    )
                    facs = fac_resp.get("data", []) if isinstance(fac_resp, dict) else []
                    for f in facs:
                        f["_country_code"] = country_code
                    all_facilities.extend(facs)
                except Exception as e:
                    logger.warning(f"PeeringDB facilities API failed for {country_code}: {e}")

                # Networks
                try:
                    net_resp = http.get_json(
                        PEERINGDB_NET_BASE, params={"country": country_code}
                    )
                    nets = net_resp.get("data", []) if isinstance(net_resp, dict) else []
                    all_networks.extend(nets)
                except Exception as e:
                    logger.warning(f"PeeringDB networks API failed for {country_code}: {e}")

                time.sleep(REQUEST_DELAY)

        logger.info(
            f"Downloaded {len(all_facilities)} PeeringDB facilities, "
            f"{len(all_networks)} networks across {len(LATAM_COUNTRIES)} countries"
        )
        return {"facilities": all_facilities, "networks": all_networks}

    def validate_raw(self, data: dict) -> None:
        fac = data.get("facilities", [])
        if not fac:
            raise ValueError("No facility data from PeeringDB API for any LATAM country")
        logger.info(f"Validated {len(fac)} PeeringDB facilities")

    def transform(self, raw_data: dict) -> pd.DataFrame:
        """Transform PeeringDB facility records into peering_facilities schema."""
        facilities = raw_data.get("facilities", [])

        # Build city name -> l2_id lookup for all LATAM countries
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, country_code FROM admin_level_2
            WHERE country_code = ANY(%s)
        """, (LATAM_COUNTRIES,))
        country_name_to_l2 = {}
        for l2_id, name, cc in cur.fetchall():
            if name:
                country_name_to_l2.setdefault(cc, {})[name.upper().strip()] = l2_id
                stripped = _strip_accents(name.upper().strip())
                if stripped != name.upper().strip():
                    country_name_to_l2[cc][stripped] = l2_id
        cur.close()
        conn.close()

        rows = []
        seen_ids = set()
        for fac in facilities:
            pdb_id = fac.get("id")
            if not pdb_id or pdb_id in seen_ids:
                continue
            seen_ids.add(pdb_id)

            country_code = fac.get("_country_code", fac.get("country", ""))
            name = str(fac.get("name", "") or "").strip()
            city = str(fac.get("city", "") or "").strip()
            org_name = str(
                fac.get("org_name", "") or fac.get("org", {}).get("name", "") or ""
            ).strip()
            website = str(fac.get("website", "") or "").strip()
            notes = str(fac.get("notes", "") or "").strip()

            lat = None
            lon = None
            if fac.get("latitude") is not None:
                try:
                    lat = float(fac["latitude"])
                    lon = float(fac["longitude"])
                except (ValueError, TypeError):
                    pass

            net_count = 0
            netfac = fac.get("netfac_set", [])
            if isinstance(netfac, list):
                net_count = len(netfac)

            # Resolve l2_id from city name
            l2_id = None
            name_lookup = country_name_to_l2.get(country_code, {})
            if city:
                city_upper = city.upper().strip()
                l2_id = name_lookup.get(city_upper)
                if not l2_id:
                    l2_id = name_lookup.get(_strip_accents(city_upper))

            rows.append({
                "peeringdb_id": int(pdb_id),
                "name": name[:300] if name else None,
                "city": city[:200] if city else None,
                "country_code": country_code,
                "latitude": lat,
                "longitude": lon,
                "org_name": org_name[:300] if org_name else None,
                "website": website[:500] if website else None,
                "notes": notes if notes else None,
                "net_count": net_count,
                "l2_id": l2_id,
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} PeeringDB facilities across LATAM")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert PeeringDB facilities into peering_facilities table."""
        if data.empty:
            logger.warning("No PeeringDB facility data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0
        errors = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                lat = float(row["latitude"]) if pd.notna(row.get("latitude")) else None
                lng = float(row["longitude"]) if pd.notna(row.get("longitude")) else None
                geom_sql = (
                    f"ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)"
                    if lat is not None and lng is not None
                    else "NULL"
                )

                l2_val = int(row["l2_id"]) if pd.notna(row.get("l2_id")) else None

                cur.execute(f"""
                    INSERT INTO peering_facilities
                        (peeringdb_id, name, city, country_code, latitude, longitude,
                         geom, org_name, website, notes, net_count, l2_id, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, {geom_sql}, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (peeringdb_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        city = EXCLUDED.city,
                        country_code = EXCLUDED.country_code,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        geom = EXCLUDED.geom,
                        org_name = EXCLUDED.org_name,
                        website = EXCLUDED.website,
                        notes = EXCLUDED.notes,
                        net_count = EXCLUDED.net_count,
                        l2_id = EXCLUDED.l2_id,
                        updated_at = NOW()
                """, (
                    int(row["peeringdb_id"]),
                    row.get("name"),
                    row.get("city"),
                    row["country_code"],
                    lat, lng,
                    row.get("org_name"),
                    row.get("website"),
                    row.get("notes"),
                    int(row["net_count"]) if pd.notna(row.get("net_count")) else 0,
                    l2_val,
                ))
                cur.execute("RELEASE SAVEPOINT row_sp")
                loaded += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    logger.warning(
                        f"Failed to load PeeringDB facility {row.get('peeringdb_id')}: {e}"
                    )
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} PeeringDB LATAM facilities ({errors} errors)")
