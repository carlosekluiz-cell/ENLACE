"""DATASUS/CNES Health Facilities Pipeline.

Source: CNES (Cadastro Nacional de Estabelecimentos de Saude) via S3
Format: ZIP containing CSV (cnes_estabelecimentos.zip, ~47MB)
Fields: facility name, CNES code, municipality code, coordinates, bed count,
        facility type, legal nature

Health facilities without internet connectivity are anchor-institution
opportunities. SUS-contracted hospitals and clinics often have dedicated
government funding for connectivity -- ISPs can win these contracts.
"""
import io
import logging
import zipfile
from pathlib import Path

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

# Confirmed working CNES download URL (S3 sa-east-1, ~47MB ZIP)
CNES_ZIP_URL = (
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos.zip"
)

# CNES facility type codes -> human-readable names
# Reference: http://tabnet.datasus.gov.br/cgi/cnes/tipo_estabelecimento.htm
FACILITY_TYPE_MAP = {
    "1": "Posto de Saude",
    "2": "Centro de Saude/Unidade Basica",
    "4": "Policlinica",
    "5": "Hospital Geral",
    "7": "Hospital Especializado",
    "9": "Pronto Socorro Geral",
    "11": "Pronto Socorro Especializado",
    "12": "Unidade Mista",
    "15": "Unidade Movel Fluvial",
    "20": "Pronto Socorro",
    "21": "Consultorio Isolado",
    "22": "Unidade Movel Terrestre",
    "32": "Unidade Movel de Nivel Pre-hospitalar (SAMU)",
    "36": "Clinica/Centro de Especialidade",
    "39": "Unidade de Apoio Diagnostico e Terapeutico",
    "40": "Unidade Movel Nivel Pre-hospitalar",
    "42": "Central de Regulacao",
    "43": "Cooperativa ou Empresa de Cessao de Trabalhadores",
    "50": "Unidade de Vigilancia em Saude",
    "60": "Cooperativa",
    "61": "Centro de Parto Normal",
    "62": "Hospital-Dia",
    "64": "Central de Regulacao de Servicos de Saude",
    "67": "Laboratorio Central de Saude Publica (LACEN)",
    "68": "Central de Gestao em Saude",
    "69": "Centro de Atencao Hemoterapia e/ou Hematologica",
    "70": "Centro de Atencao Psicossocial",
    "71": "Centro de Apoio a Saude da Familia",
    "72": "Unidade de Atencao a Saude Indigena",
    "73": "Pronto Atendimento",
    "74": "Polo Academia da Saude",
    "75": "Telessaude",
    "76": "Central de Abastecimento",
    "77": "Farmacia",
    "78": "Unidade de Atencao em Regime Residencial",
    "79": "Oficina Ortopedica",
    "80": "Laboratorio de Saude Publica",
    "81": "Central de Regulacao Medica de Urgencias",
    "82": "Central de Notificacao Captacao e Distrib de Orgaos Estadual",
    "83": "Polo de Prevencao de Doencas e Agravos e Promocao da Saude",
    "85": "Centro de Imunizacao",
}

# SUS legal nature codes that indicate public/SUS-contracted facilities
# 1xxx = Administracao Publica, 2xxx = Entidades empresariais SUS
SUS_NATURE_PREFIXES = ("1", "2")


class DATASUSHealthPipeline(BasePipeline):
    """Ingest DATASUS CNES health facility data from real CNES S3 export."""

    def __init__(self):
        super().__init__("datasus_health")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_facilities (
                id SERIAL PRIMARY KEY,
                cnes_code VARCHAR(20) UNIQUE,
                name VARCHAR(300),
                facility_type VARCHAR(100),
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                state_code VARCHAR(2),
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                geom GEOMETRY(Point, 4326),
                has_internet BOOLEAN,
                bed_count INTEGER DEFAULT 0,
                sus_contract BOOLEAN DEFAULT FALSE,
                year INTEGER,
                source VARCHAR(50) DEFAULT 'datasus_cnes'
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_health_facilities_l2_id ON health_facilities(l2_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_health_facilities_geom ON health_facilities USING GIST(geom)")
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM health_facilities")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> Path:
        """Download CNES ZIP from S3, returning path to the cached ZIP file.

        Uses streaming download with resume support to handle the 47MB file
        efficiently. The file is cached so re-runs don't re-download.
        """
        zip_path = get_cache_path("cnes_estabelecimentos.zip")

        with PipelineHTTPClient(timeout=600) as http:
            logger.info(f"Downloading CNES ZIP from {CNES_ZIP_URL} ...")
            http.download_file(CNES_ZIP_URL, zip_path, resume=True)

        # Verify the ZIP is valid before returning
        if not zip_path.exists() or zip_path.stat().st_size < 1_000_000:
            raise RuntimeError(
                f"CNES ZIP download failed or file too small "
                f"({zip_path.stat().st_size if zip_path.exists() else 0} bytes). "
                f"Expected ~47MB from {CNES_ZIP_URL}"
            )

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                logger.info(
                    f"CNES ZIP valid: {len(names)} file(s) inside: {names}"
                )
        except zipfile.BadZipFile as e:
            # Remove corrupted file so next run re-downloads
            zip_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Downloaded CNES ZIP is corrupted: {e}. "
                f"Deleted cached file; re-run to retry download."
            ) from e

        return zip_path

    def validate_raw(self, data) -> None:
        """Validate that the ZIP path exists and is a valid ZIP."""
        if not isinstance(data, Path):
            raise TypeError(f"Expected Path from download(), got {type(data)}")
        if not data.exists():
            raise FileNotFoundError(f"CNES ZIP not found at {data}")

    def transform(self, raw_data: Path) -> pd.DataFrame:
        """Extract CSV from CNES ZIP and transform into load-ready DataFrame.

        Reads the CSV in chunks (50K rows) to limit memory usage, maps
        municipality codes to l2_id, and normalizes facility types.
        """
        zip_path = raw_data

        # Build l2_id lookup from admin_level_2 table
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        # Build maps for both 7-digit and 6-digit codes (IBGE uses 7 digits,
        # CNES sometimes uses 6 by dropping the check digit)
        l2_map_7 = {}  # 7-digit IBGE code -> l2_id
        l2_map_6 = {}  # 6-digit (first 6 of IBGE code) -> l2_id
        for row in cur.fetchall():
            l2_id, code = row[0], str(row[1]).strip()
            l2_map_7[code] = l2_id
            if len(code) >= 6:
                l2_map_6[code[:6]] = l2_id
        cur.close()
        conn.close()

        logger.info(
            f"Loaded {len(l2_map_7)} municipality codes for mapping "
            f"({len(l2_map_6)} at 6-digit level)"
        )

        # Find the CSV inside the ZIP
        csv_filename = None
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                lower = name.lower()
                if lower.endswith(".csv"):
                    csv_filename = name
                    break
            if not csv_filename:
                # If no .csv, try the first file that isn't a directory
                for name in zf.namelist():
                    if not name.endswith("/"):
                        csv_filename = name
                        break

        if not csv_filename:
            raise RuntimeError(
                f"No CSV file found inside CNES ZIP. Contents: {zf.namelist()}"
            )

        logger.info(f"Extracting CSV: {csv_filename}")

        # Read the CSV in chunks to handle potentially large files
        all_rows = []
        total_raw = 0
        skipped_no_l2 = 0
        chunk_size = 50_000

        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(csv_filename) as csv_file:
                # Wrap in TextIOWrapper to handle encoding
                # CNES CSVs are typically latin-1 or utf-8 encoded
                text_stream = io.TextIOWrapper(csv_file, encoding="latin-1", errors="replace")

                # Peek at the first line to detect separator
                first_line = text_stream.readline()
                text_stream.seek(0)

                sep = ";" if ";" in first_line else ","

                reader = pd.read_csv(
                    text_stream,
                    sep=sep,
                    dtype=str,
                    on_bad_lines="skip",
                    chunksize=chunk_size,
                    low_memory=True,
                )

                column_map = None
                for chunk_num, chunk in enumerate(reader):
                    total_raw += len(chunk)

                    # On first chunk, discover column names
                    if column_map is None:
                        column_map = self._discover_columns(chunk.columns.tolist())
                        logger.info(
                            f"CSV columns detected: {list(chunk.columns)}"
                        )
                        logger.info(f"Column mapping: {column_map}")

                        if not column_map.get("municipality_code"):
                            raise RuntimeError(
                                f"Cannot find municipality code column in CNES CSV. "
                                f"Available columns: {list(chunk.columns)}"
                            )

                    rows = self._transform_chunk(
                        chunk, column_map, l2_map_7, l2_map_6
                    )
                    skipped_no_l2 += len(chunk) - len(rows)
                    all_rows.extend(rows)

                    if (chunk_num + 1) % 5 == 0:
                        logger.info(
                            f"  Processed {total_raw:,} raw rows -> "
                            f"{len(all_rows):,} matched so far"
                        )

        logger.info(
            f"CNES transform complete: {total_raw:,} raw rows -> "
            f"{len(all_rows):,} facilities matched to municipalities "
            f"({skipped_no_l2:,} skipped, no l2_id match)"
        )

        self.rows_processed = len(all_rows)

        if not all_rows:
            logger.warning("No facilities matched to municipalities!")
            return pd.DataFrame()

        return pd.DataFrame(all_rows)

    def _discover_columns(self, columns: list[str]) -> dict:
        """Map actual CSV column names to our semantic names.

        CNES CSVs may vary in column naming across releases, so we check
        multiple candidates for each field.
        """
        upper_map = {c.upper().strip(): c for c in columns}
        mapping = {}

        # CNES code (unique facility identifier)
        for candidate in [
            "CO_CNES", "CNES", "CODE_CNES", "COD_CNES", "CO_UNIDADE",
        ]:
            if candidate in upper_map:
                mapping["cnes_code"] = upper_map[candidate]
                break

        # Facility name
        for candidate in [
            "NO_FANTASIA", "NO_RAZAO_SOCIAL", "NOME_FANTASIA",
            "RAZAO_SOCIAL", "NOME", "NM_FANTASIA",
        ]:
            if candidate in upper_map:
                mapping["name"] = upper_map[candidate]
                break

        # Municipality code (6 or 7 digit IBGE code)
        for candidate in [
            "CO_MUNICIPIO_GESTOR", "CO_IBGE", "CO_MUNICIPIO",
            "CODUFMUN", "COD_MUNICIPIO", "IBGE", "CO_CEP_MUNICIPIO",
        ]:
            if candidate in upper_map:
                mapping["municipality_code"] = upper_map[candidate]
                break

        # Facility type code
        for candidate in [
            "TP_UNIDADE", "TIPO_UNIDADE", "CO_TIPO_UNIDADE",
            "TP_ESTABELECIMENTO",
        ]:
            if candidate in upper_map:
                mapping["facility_type"] = upper_map[candidate]
                break

        # Legal nature (to determine SUS contract)
        for candidate in [
            "CO_NATUREZA_JUR", "CO_NATUREZA_JURIDICA", "NATUREZA_JURIDICA",
            "TP_NATUREZA_JUR",
        ]:
            if candidate in upper_map:
                mapping["legal_nature"] = upper_map[candidate]
                break

        # Latitude
        for candidate in [
            "NU_LATITUDE", "LATITUDE", "LAT",
        ]:
            if candidate in upper_map:
                mapping["latitude"] = upper_map[candidate]
                break

        # Longitude
        for candidate in [
            "NU_LONGITUDE", "LONGITUDE", "LON", "LNG",
        ]:
            if candidate in upper_map:
                mapping["longitude"] = upper_map[candidate]
                break

        # Bed count
        for candidate in [
            "QT_LEITOS", "QT_LEITOS_INTERNACAO", "LEITOS", "QT_LEITO_TOTAL",
        ]:
            if candidate in upper_map:
                mapping["bed_count"] = upper_map[candidate]
                break

        # Internet access (may not be present in all CNES exports)
        for candidate in [
            "IN_INTERNET", "TEM_INTERNET", "ST_INTERNET",
        ]:
            if candidate in upper_map:
                mapping["has_internet"] = upper_map[candidate]
                break

        # State code (UF)
        for candidate in [
            "CO_ESTADO_GESTOR", "CO_UF", "UF", "SG_UF",
        ]:
            if candidate in upper_map:
                mapping["state_code"] = upper_map[candidate]
                break

        return mapping

    def _transform_chunk(
        self,
        chunk: pd.DataFrame,
        col_map: dict,
        l2_map_7: dict,
        l2_map_6: dict,
    ) -> list[dict]:
        """Transform a chunk of raw CNES CSV rows into load-ready dicts."""
        rows = []
        muni_col = col_map["municipality_code"]

        for _, record in chunk.iterrows():
            # Municipality code lookup: try 7-digit first, then 6-digit
            raw_code = str(record.get(muni_col, "")).strip()
            if not raw_code or raw_code == "nan":
                continue

            l2_id = l2_map_7.get(raw_code)
            if not l2_id and len(raw_code) >= 6:
                l2_id = l2_map_6.get(raw_code[:6])
            if not l2_id and len(raw_code) == 7:
                # Try without check digit (last digit)
                l2_id = l2_map_6.get(raw_code[:6])
            if not l2_id:
                continue

            # CNES code
            cnes_code = None
            if "cnes_code" in col_map:
                cnes_code = str(record.get(col_map["cnes_code"], "")).strip()
                if cnes_code == "nan" or not cnes_code:
                    cnes_code = None
            if not cnes_code:
                # Skip facilities without a CNES code (can't deduplicate)
                continue

            # Name
            name = ""
            if "name" in col_map:
                name = str(record.get(col_map["name"], "")).strip()
                if name == "nan":
                    name = ""

            # Facility type
            facility_type = ""
            if "facility_type" in col_map:
                raw_type = str(record.get(col_map["facility_type"], "")).strip()
                if raw_type != "nan":
                    facility_type = FACILITY_TYPE_MAP.get(raw_type, raw_type)

            # Coordinates
            lat = self._parse_float(record, col_map.get("latitude"))
            lng = self._parse_float(record, col_map.get("longitude"))

            # Validate coordinates are within Brazil bounds
            if lat is not None and lng is not None:
                if not (-34.0 <= lat <= 6.0 and -74.0 <= lng <= -28.0):
                    lat, lng = None, None

            # Bed count
            bed_count = 0
            if "bed_count" in col_map:
                try:
                    val = str(record.get(col_map["bed_count"], "0")).strip()
                    if val and val != "nan":
                        bed_count = max(0, int(float(val)))
                except (ValueError, TypeError):
                    bed_count = 0

            # SUS contract: infer from legal nature code
            sus_contract = False
            if "legal_nature" in col_map:
                nature = str(record.get(col_map["legal_nature"], "")).strip()
                if nature and nature != "nan":
                    sus_contract = nature[:1] in SUS_NATURE_PREFIXES

            # Internet: only set if column exists in the CSV
            has_internet = None
            if "has_internet" in col_map:
                inet_val = str(record.get(col_map["has_internet"], "")).strip().upper()
                if inet_val in ("1", "SIM", "S", "TRUE"):
                    has_internet = True
                elif inet_val in ("0", "NAO", "N", "FALSE"):
                    has_internet = False
                # else remains None (unknown)

            # State code: extract from municipality code if not in CSV
            state_code = ""
            if "state_code" in col_map:
                state_code = str(record.get(col_map["state_code"], "")).strip()
                if state_code == "nan":
                    state_code = ""
            if not state_code and len(raw_code) >= 2:
                state_code = raw_code[:2]

            rows.append({
                "cnes_code": cnes_code,
                "name": name[:300],
                "facility_type": facility_type[:100],
                "l2_id": l2_id,
                "municipality_code": raw_code[:10],
                "state_code": state_code[:2],
                "latitude": lat,
                "longitude": lng,
                "has_internet": has_internet,
                "bed_count": bed_count,
                "sus_contract": sus_contract,
                "year": 2024,
            })

        return rows

    @staticmethod
    def _parse_float(record, col_name: str | None) -> float | None:
        """Safely parse a float from a CSV record column."""
        if col_name is None:
            return None
        try:
            val = str(record.get(col_name, "")).strip().replace(",", ".")
            if not val or val == "nan" or val == "":
                return None
            return float(val)
        except (ValueError, TypeError):
            return None

    def load(self, data: pd.DataFrame) -> None:
        """Load transformed health facilities into PostgreSQL with PostGIS geometry.

        Uses batch inserts with ON CONFLICT to upsert by cnes_code.
        Commits every 5,000 rows to avoid holding large transactions.
        """
        if data.empty:
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0
        batch_size = 5000
        errors = 0

        for idx, row in data.iterrows():
            try:
                lat = float(row["latitude"]) if pd.notna(row.get("latitude")) else None
                lng = float(row["longitude"]) if pd.notna(row.get("longitude")) else None
                geom_sql = (
                    f"ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)"
                    if lat is not None and lng is not None
                    else "NULL"
                )

                # has_internet: pass None for NULL, else boolean
                has_internet = row.get("has_internet")
                if pd.isna(has_internet):
                    has_internet = None
                elif has_internet is not None:
                    has_internet = bool(has_internet)

                cur.execute(f"""
                    INSERT INTO health_facilities
                        (cnes_code, name, facility_type, l2_id, municipality_code,
                         state_code, latitude, longitude, geom, has_internet,
                         bed_count, sus_contract, year, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {geom_sql}, %s, %s, %s, %s,
                            'datasus_cnes')
                    ON CONFLICT (cnes_code) DO UPDATE SET
                        name = EXCLUDED.name,
                        facility_type = EXCLUDED.facility_type,
                        l2_id = EXCLUDED.l2_id,
                        has_internet = EXCLUDED.has_internet,
                        bed_count = EXCLUDED.bed_count,
                        sus_contract = EXCLUDED.sus_contract,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        geom = EXCLUDED.geom,
                        year = EXCLUDED.year
                """, (
                    str(row["cnes_code"]),
                    str(row.get("name", ""))[:300],
                    str(row.get("facility_type", ""))[:100],
                    int(row["l2_id"]),
                    str(row["municipality_code"])[:10],
                    str(row.get("state_code", ""))[:2],
                    lat, lng,
                    has_internet,
                    int(row.get("bed_count", 0)),
                    bool(row.get("sus_contract", False)),
                    int(row.get("year", 2024)),
                ))
                loaded += 1

                # Commit in batches to avoid huge transactions
                if loaded % batch_size == 0:
                    conn.commit()
                    logger.info(f"  Committed {loaded:,} facilities...")

            except Exception as e:
                errors += 1
                if errors <= 10:
                    logger.warning(
                        f"Failed to load facility {row.get('cnes_code')}: {e}"
                    )
                elif errors == 11:
                    logger.warning("Suppressing further individual load errors...")
                conn.rollback()

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(
            f"Loaded {loaded:,} health facility records "
            f"({errors:,} errors) from CNES"
        )
