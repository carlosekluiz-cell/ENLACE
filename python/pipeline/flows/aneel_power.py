"""ANEEL power grid corridors pipeline.

Source: SIGEL (Sistema de Informacoes Geograficas do Setor Eletrico)
URL: https://sigel.aneel.gov.br/arcgis/rest/services/PORTAL/Linhas_Transmissao/MapServer/0/query
Format: ArcGIS REST paginated GeoJSON
Fields: TENSAO (kV), PROPRIETAR (operator), geometry (LineString)

Fiber-optic cables are frequently co-deployed along power transmission
corridors (OPGW), making power grid data valuable for identifying
potential fiber routes and infrastructure sharing opportunities.
"""
import json
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


def classify_voltage(voltage_kv: float) -> str:
    """Classify power line type based on voltage."""
    if voltage_kv >= 230:
        return "transmission"
    elif voltage_kv >= 69:
        return "subtransmission"
    else:
        return "distribution"


class ANEELPowerPipeline(BasePipeline):
    """Ingest real ANEEL power grid data from SIGEL ArcGIS REST API."""

    def __init__(self):
        super().__init__("aneel_power")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM power_lines WHERE source = 'sigel_aneel'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> list[dict]:
        """Fetch paginated power line features from SIGEL ArcGIS REST."""
        with PipelineHTTPClient(timeout=300) as http:
            logger.info("Fetching power lines from SIGEL ArcGIS REST API...")
            features = http.get_paginated_geojson(
                base_url=self.urls.aneel_sigel_lines,
                page_size=1000,
                where="1=1",
                out_fields="*",
            )
            logger.info(f"Fetched {len(features)} power line features")

        return features

    def validate_raw(self, data: list[dict]) -> None:
        if not data:
            raise ValueError("No power line features returned from SIGEL")
        # Check that features have geometry
        with_geom = sum(1 for f in data if f.get("geometry"))
        logger.info(f"{with_geom}/{len(data)} features have geometry")

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Extract voltage, operator, geometry from GeoJSON features."""
        rows = []
        for feature in raw_data:
            props = feature.get("properties", {})
            geometry = feature.get("geometry")
            if not geometry:
                continue

            # Extract voltage (field name may vary: TENSAO, TensaoKV, etc.)
            voltage_kv = 0
            for key in ("TENSAO", "TensaoKV", "tensao", "TENSAO_KV"):
                val = props.get(key)
                if val is not None:
                    try:
                        voltage_kv = float(val)
                        break
                    except (ValueError, TypeError):
                        pass

            # Extract operator name
            operator = ""
            for key in ("PROPRIETAR", "Proprietario", "OPERADORA", "proprietar"):
                val = props.get(key)
                if val and str(val).strip() not in ("None", "null", ""):
                    operator = str(val).strip()
                    break

            line_type = classify_voltage(voltage_kv)

            # Convert geometry to EWKT
            geom_type = geometry.get("type", "")
            coords = geometry.get("coordinates", [])
            if geom_type == "LineString" and coords:
                coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
                geom_wkt = f"SRID=4326;LINESTRING({coord_str})"
            elif geom_type == "MultiLineString" and coords:
                # Take the first line
                first_line = coords[0]
                coord_str = ", ".join(f"{c[0]} {c[1]}" for c in first_line)
                geom_wkt = f"SRID=4326;LINESTRING({coord_str})"
            else:
                continue

            rows.append({
                "country_code": "BR",
                "voltage_kv": voltage_kv,
                "operator_name": operator,
                "line_type": line_type,
                "geom_wkt": geom_wkt,
                "source": "sigel_aneel",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} power lines")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Insert power line records."""
        if data.empty:
            logger.warning("No power lines to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        # Clear existing SIGEL data
        cur.execute("DELETE FROM power_lines WHERE source = 'sigel_aneel'")
        conn.commit()

        from psycopg2.extras import execute_values
        values = []
        for _, row in data.iterrows():
            values.append((
                row["country_code"], row["voltage_kv"], row["operator_name"],
                row["line_type"], row["geom_wkt"], row["source"],
            ))

        execute_values(cur, """
            INSERT INTO power_lines
            (country_code, voltage_kv, operator_name, line_type, geom, source)
            VALUES %s
        """, values, template=(
            "(%s, %s, %s, %s, ST_GeomFromEWKT(%s), %s)"
        ), page_size=1000)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} power lines")
