"""INEP Schools (Censo Escolar) Pipeline.

Source: INEP Censo Escolar 2023 microdata
URL: https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2023.zip
Format: ZIP containing CSV with school-level data (~32MB download)

Fields: CO_ENTIDADE (INEP code), NO_ENTIDADE (school name), CO_MUNICIPIO (7-digit),
NU_LATITUDE/NU_LONGITUDE (coordinates), IN_INTERNET (connectivity), QT_MAT_BAS
(enrollment), TP_DEPENDENCIA (school type), TP_LOCALIZACAO (urban/rural).

Schools without internet are anchor-institution opportunities. Federal programs
like Programa de Inovacao Educacao Conectada fund school connectivity -- ISPs
competing for these contracts need this data.
"""
import logging
import zipfile
from pathlib import Path

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

INEP_CENSO_URL = (
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2023.zip"
)

# TP_DEPENDENCIA mapping (school administrative dependency)
SCHOOL_TYPE_MAP = {
    1: "federal",
    2: "estadual",
    3: "municipal",
    4: "privada",
}


class INEPSchoolsPipeline(BasePipeline):
    """Ingest INEP Censo Escolar school data with connectivity status.

    Downloads the official INEP microdata ZIP (~32MB), extracts the
    school-level CSV, and loads real school records with coordinates,
    internet status, enrollment, and school type into the schools table.
    No synthetic data is generated.
    """

    def __init__(self):
        super().__init__("inep_schools")

    def check_for_updates(self) -> bool:
        """Create table if needed, return True if data is missing or stale."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schools (
                id SERIAL PRIMARY KEY,
                inep_code VARCHAR(20) UNIQUE,
                name VARCHAR(300),
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                state_code VARCHAR(2),
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                geom GEOMETRY(Point, 4326),
                has_internet BOOLEAN,
                internet_type VARCHAR(50),
                student_count INTEGER,
                school_type VARCHAR(50),
                rural BOOLEAN DEFAULT FALSE,
                year INTEGER,
                source VARCHAR(50) DEFAULT 'inep_censo_escolar'
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_schools_l2_id ON schools(l2_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_schools_geom ON schools USING GIST(geom)")
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM schools WHERE source = 'inep_censo_escolar'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> Path:
        """Download the INEP Censo Escolar 2023 ZIP file.

        Returns the path to the downloaded ZIP. Raises on failure -- no
        synthetic fallback.
        """
        cache_path = get_cache_path("microdados_censo_escolar_2023.zip")

        # If already downloaded and non-trivial size, reuse cached file
        if cache_path.exists() and cache_path.stat().st_size > 1_000_000:
            logger.info(f"Using cached INEP ZIP: {cache_path} ({cache_path.stat().st_size:,} bytes)")
            return cache_path

        logger.info(f"Downloading INEP Censo Escolar 2023 from {INEP_CENSO_URL}")
        with PipelineHTTPClient(timeout=600) as http:
            http.download_file(INEP_CENSO_URL, cache_path, resume=True)

        if not cache_path.exists() or cache_path.stat().st_size < 1_000_000:
            raise RuntimeError(
                f"INEP download failed or file too small: {cache_path}. "
                "No synthetic fallback -- real data is required."
            )

        logger.info(f"Downloaded INEP ZIP: {cache_path.stat().st_size:,} bytes")
        return cache_path

    def _find_school_csv_in_zip(self, zip_path: Path) -> str:
        """Find the school-level CSV inside the INEP ZIP.

        The ZIP contains multiple CSVs (schools, enrollments, teachers, etc.).
        We need the school-level file, which typically contains 'ESCOLA' or
        'escola' in the filename, and has columns like CO_ENTIDADE.
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_names = zf.namelist()
            csv_files = [n for n in all_names if n.lower().endswith(".csv")]

            if not csv_files:
                raise RuntimeError(
                    f"No CSV files found in INEP ZIP. Contents: {all_names[:20]}"
                )

            logger.info(f"CSV files in ZIP: {csv_files}")

            # Priority 1: file with 'escola' in name (school-level data)
            for name in csv_files:
                lower = name.lower()
                if "escola" in lower and "turma" not in lower and "matricula" not in lower:
                    logger.info(f"Selected school CSV: {name}")
                    return name

            # Priority 2: file with 'school' in name
            for name in csv_files:
                if "school" in name.lower():
                    logger.info(f"Selected school CSV: {name}")
                    return name

            # Priority 3: smallest CSV that could be school-level
            # (school files are typically smaller than enrollment files)
            csv_sizes = []
            for name in csv_files:
                info = zf.getinfo(name)
                csv_sizes.append((info.file_size, name))
            csv_sizes.sort()

            # Take the smallest CSV that is at least 100KB (not a readme)
            for size, name in csv_sizes:
                if size > 100_000:
                    logger.info(f"Selected CSV by size heuristic: {name} ({size:,} bytes)")
                    return name

            # Last resort: first CSV
            logger.warning(f"Using first CSV as fallback: {csv_files[0]}")
            return csv_files[0]

    def transform(self, raw_data) -> pd.DataFrame:
        """Extract and transform school data from the INEP ZIP.

        raw_data is a Path to the ZIP file. We read the school CSV in chunks
        to handle the large file efficiently, extract relevant columns, and
        map municipality codes to l2_id.
        """
        zip_path = raw_data
        if not isinstance(zip_path, Path):
            zip_path = Path(zip_path)

        csv_name = self._find_school_csv_in_zip(zip_path)

        # Build municipality code -> l2_id mapping
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        l2_map = {str(row[1]).strip(): row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()

        logger.info(f"Loaded {len(l2_map)} municipality codes for mapping")

        # Columns we want to read (reduces memory usage)
        usecols_candidates = [
            "CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO",
            "NU_LATITUDE", "NU_LONGITUDE",
            "IN_INTERNET", "TP_DEPENDENCIA", "TP_LOCALIZACAO",
            "QT_MAT_BAS", "QT_MAT_INF", "QT_MAT_FUND", "QT_MAT_MED",
            "TP_SITUACAO_FUNCIONAMENTO", "IN_LABORATORIO_INFORMATICA",
        ]

        all_rows = []
        chunk_num = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(csv_name) as csv_file:
                # Try reading with the standard INEP encoding and separator
                try:
                    reader = pd.read_csv(
                        csv_file,
                        sep=";",
                        encoding="latin-1",
                        dtype=str,
                        on_bad_lines="skip",
                        chunksize=50_000,
                        low_memory=True,
                    )
                except Exception as e:
                    logger.warning(f"Failed to open CSV with latin-1/semicolon: {e}")
                    # Retry with UTF-8 and comma
                    csv_file.seek(0)
                    reader = pd.read_csv(
                        csv_file,
                        sep=",",
                        encoding="utf-8",
                        dtype=str,
                        on_bad_lines="skip",
                        chunksize=50_000,
                        low_memory=True,
                    )

                for chunk in reader:
                    chunk_num += 1
                    chunk.columns = [c.strip().upper() for c in chunk.columns]

                    # Check we have the essential column
                    if "CO_ENTIDADE" not in chunk.columns:
                        if chunk_num == 1:
                            logger.error(
                                f"CO_ENTIDADE not in columns: {list(chunk.columns)[:20]}"
                            )
                            raise RuntimeError(
                                "INEP CSV does not contain CO_ENTIDADE column. "
                                f"Available columns: {list(chunk.columns)[:20]}"
                            )
                        continue

                    # Filter to active schools only (TP_SITUACAO_FUNCIONAMENTO=1 means active)
                    if "TP_SITUACAO_FUNCIONAMENTO" in chunk.columns:
                        chunk = chunk[chunk["TP_SITUACAO_FUNCIONAMENTO"].astype(str).str.strip() == "1"]

                    rows = self._transform_chunk(chunk, l2_map)
                    all_rows.extend(rows)
                    logger.info(
                        f"Chunk {chunk_num}: processed {len(chunk)} rows, "
                        f"matched {len(rows)} schools, running total {len(all_rows)}"
                    )

        if not all_rows:
            raise RuntimeError(
                "No school records matched any municipality. "
                "Check that CO_MUNICIPIO codes in INEP data match admin_level_2.code."
            )

        self.rows_processed = len(all_rows)
        logger.info(f"Transformed {len(all_rows)} school records from INEP Censo Escolar")
        return pd.DataFrame(all_rows)

    def _transform_chunk(self, chunk: pd.DataFrame, l2_map: dict) -> list[dict]:
        """Transform a single chunk of raw INEP CSV data into school records."""
        rows = []

        for _, record in chunk.iterrows():
            # Municipality code: 7-digit IBGE code
            muni_code = str(record.get("CO_MUNICIPIO", "")).strip()
            if len(muni_code) < 6:
                continue

            # INEP data uses 7-digit codes; our DB may store 6 or 7 digits
            l2_id = l2_map.get(muni_code)
            if not l2_id and len(muni_code) == 7:
                # Try without check digit (first 6 digits)
                l2_id = l2_map.get(muni_code[:6])
            if not l2_id:
                continue

            inep_code = str(record.get("CO_ENTIDADE", "")).strip()
            if not inep_code or inep_code == "nan":
                continue

            name = str(record.get("NO_ENTIDADE", "")).strip()
            if name == "nan":
                name = ""

            # Coordinates
            lat = self._safe_float(record.get("NU_LATITUDE"))
            lng = self._safe_float(record.get("NU_LONGITUDE"))

            # Validate coordinates are within Brazil bounds
            if lat is not None and (lat < -34.0 or lat > 6.0):
                lat = None
                lng = None
            if lng is not None and (lng < -74.0 or lng > -28.0):
                lat = None
                lng = None

            # Internet access
            internet_val = str(record.get("IN_INTERNET", "0")).strip()
            has_internet = internet_val in ("1", "SIM", "S")

            # School type from TP_DEPENDENCIA
            dep_val = self._safe_int(record.get("TP_DEPENDENCIA"))
            school_type = SCHOOL_TYPE_MAP.get(dep_val)

            # Rural/urban from TP_LOCALIZACAO (1=urban, 2=rural)
            loc_val = str(record.get("TP_LOCALIZACAO", "1")).strip()
            is_rural = loc_val == "2"

            # Enrollment: try QT_MAT_BAS first (basic education total),
            # then sum component parts
            student_count = self._safe_int(record.get("QT_MAT_BAS"))
            if student_count is None or student_count == 0:
                inf = self._safe_int(record.get("QT_MAT_INF")) or 0
                fund = self._safe_int(record.get("QT_MAT_FUND")) or 0
                med = self._safe_int(record.get("QT_MAT_MED")) or 0
                total = inf + fund + med
                student_count = total if total > 0 else 0

            # State code from first 2 digits of municipality code
            state_code = muni_code[:2]

            rows.append({
                "inep_code": inep_code,
                "name": name[:300],
                "l2_id": l2_id,
                "municipality_code": muni_code,
                "state_code": state_code,
                "latitude": lat,
                "longitude": lng,
                "has_internet": has_internet,
                "internet_type": None,  # INEP data does not specify internet type
                "student_count": student_count,
                "school_type": school_type,
                "rural": is_rural,
                "year": 2023,
            })

        return rows

    @staticmethod
    def _safe_float(val) -> float | None:
        """Safely convert a value to float, returning None on failure."""
        if val is None:
            return None
        try:
            s = str(val).strip().replace(",", ".")
            if s in ("", "nan", "NaN", "None"):
                return None
            f = float(s)
            return f if f != 0.0 else None  # INEP uses 0 for missing coords
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(val) -> int | None:
        """Safely convert a value to int, returning None on failure."""
        if val is None:
            return None
        try:
            s = str(val).strip()
            if s in ("", "nan", "NaN", "None"):
                return None
            return int(float(s))
        except (ValueError, TypeError):
            return None

    def load(self, data: pd.DataFrame) -> None:
        """Load transformed school records into PostgreSQL with PostGIS geometry."""
        if data.empty:
            logger.warning("No school data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0
        batch_size = 500

        for idx, row in data.iterrows():
            try:
                lat = float(row["latitude"]) if pd.notna(row.get("latitude")) else None
                lng = float(row["longitude"]) if pd.notna(row.get("longitude")) else None
                geom_sql = f"ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)" if lat and lng else "NULL"

                cur.execute(f"""
                    INSERT INTO schools
                        (inep_code, name, l2_id, municipality_code, state_code,
                         latitude, longitude, geom, has_internet, internet_type,
                         student_count, school_type, rural, year, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, {geom_sql}, %s, %s, %s, %s, %s, %s, 'inep_censo_escolar')
                    ON CONFLICT (inep_code) DO UPDATE SET
                        name = EXCLUDED.name,
                        l2_id = EXCLUDED.l2_id,
                        municipality_code = EXCLUDED.municipality_code,
                        state_code = EXCLUDED.state_code,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        geom = EXCLUDED.geom,
                        has_internet = EXCLUDED.has_internet,
                        student_count = EXCLUDED.student_count,
                        school_type = EXCLUDED.school_type,
                        rural = EXCLUDED.rural,
                        year = EXCLUDED.year,
                        source = EXCLUDED.source
                """, (
                    str(row["inep_code"]),
                    str(row.get("name", ""))[:300],
                    int(row["l2_id"]),
                    str(row["municipality_code"]),
                    str(row.get("state_code", ""))[:2],
                    lat, lng,
                    bool(row.get("has_internet", False)),
                    str(row["internet_type"])[:50] if pd.notna(row.get("internet_type")) else None,
                    int(row.get("student_count", 0)),
                    str(row["school_type"])[:50] if pd.notna(row.get("school_type")) else None,
                    bool(row.get("rural", False)),
                    int(row.get("year", 2023)),
                ))
                loaded += 1

                # Commit in batches to avoid holding too many locks
                if loaded % batch_size == 0:
                    conn.commit()
                    logger.info(f"Committed {loaded} school records...")

            except Exception as e:
                logger.warning(f"Failed to load school {row.get('inep_code')}: {e}")
                conn.rollback()

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} school records from INEP Censo Escolar 2023")
