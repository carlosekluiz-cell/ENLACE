"""
ENLACE Pipeline Configuration

Database, MinIO, Redis configuration and data source URLs.
Includes all Brazilian states and data source endpoints.
"""

import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DatabaseConfig:
    """PostgreSQL + PostGIS database configuration."""
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "enlace")
    user: str = os.getenv("POSTGRES_USER", "enlace")
    password: str = os.getenv("POSTGRES_PASSWORD", "")

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class MinIOConfig:
    """MinIO (S3-compatible) object storage configuration."""
    endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = os.getenv("MINIO_ROOT_USER", "enlace_minio")
    secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "")
    secure: bool = False

    # Bucket names
    bucket_terrain: str = "terrain"
    bucket_landcover: str = "landcover"
    bucket_coverage_maps: str = "coverage-maps"
    bucket_reports: str = "reports"
    bucket_raw_downloads: str = "raw-downloads"


@dataclass
class RedisConfig:
    """Redis cache configuration."""
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    default_ttl: int = 3600  # 1 hour default TTL


@dataclass
class DataSourceURLs:
    """URLs for all external data sources used by pipelines.

    All URLs point to real, publicly available Brazilian government APIs.
    """

    # --- Anatel CKAN dataset IDs (resolved via dados.gov.br API) ---
    anatel_ckan_base: str = "https://dados.gov.br/dados/api/3/action"
    anatel_broadband_dataset: str = "acessos---banda-larga-fixa"
    anatel_base_stations_dataset: str = "licenciamento"
    anatel_quality_dataset: str = "indicadores-de-qualidade"
    anatel_providers_dataset: str = "prestadoras"

    # --- IBGE REST APIs ---
    ibge_api_v1: str = "https://servicodados.ibge.gov.br/api/v1"
    ibge_api_v3: str = "https://servicodados.ibge.gov.br/api/v3"

    # Municipalities list
    ibge_municipalities: str = (
        "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    )
    # States list
    ibge_states: str = (
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
    )
    # State boundaries GeoJSON (template: replace {UF} with state IBGE code)
    ibge_state_boundaries: str = (
        "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
        "?formato=application/vnd.geo+json"
    )
    # Municipality boundaries GeoJSON (template: replace {id})
    ibge_municipality_boundaries: str = (
        "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{id}"
        "?formato=application/vnd.geo+json"
    )
    # Census 2022 population: agregado 4714, variavel 93, all municipalities
    ibge_census_population: str = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/4714"
        "/periodos/2022/variaveis/93"
        "?localidades=N6[all]&view=flat"
    )
    # Municipal GDP: agregado 5938, variavel 37 (PIB), latest period
    ibge_pib_municipal: str = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/5938"
        "/periodos/-1/variaveis/37"
        "?localidades=N6[all]&view=flat"
    )
    # Population estimates: agregado 6579, variavel 9324
    ibge_population_estimates: str = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
        "/periodos/-1/variaveis/9324"
        "?localidades=N6[all]&view=flat"
    )
    # State population projections
    ibge_population_projections: str = (
        "https://servicodados.ibge.gov.br/api/v1/projecoes/populacao/{uf}"
    )

    # --- SRTM terrain (OpenTopography S3, no auth) ---
    srtm_s3_bucket: str = "raster"
    srtm_s3_prefix: str = "SRTM_GL1/SRTM_GL1_srtm/"
    srtm_s3_endpoint: str = "https://opentopography.s3.sdsc.edu"

    # --- OpenStreetMap via Geofabrik regional shapefiles ---
    osm_geofabrik_base: str = "https://download.geofabrik.de/south-america/brazil"
    # Regional shapefile URLs (template: replace {region})
    osm_geofabrik_shp: str = (
        "https://download.geofabrik.de/south-america/brazil"
        "/{region}-latest-free.shp.zip"
    )

    # --- INMET weather API ---
    inmet_stations: str = "https://apitempo.inmet.gov.br/estacoes/T"
    inmet_observations: str = "https://apitempo.inmet.gov.br/estacao"

    # --- MapBiomas land cover (Google Cloud Storage, no auth) ---
    mapbiomas_gcs: str = (
        "https://storage.googleapis.com/mapbiomas-public"
        "/initiatives/brasil/collection_9/lclu/coverage"
        "/brasil_coverage_2023.tif"
    )

    # --- ANEEL SIGEL ArcGIS REST API ---
    aneel_sigel_lines: str = (
        "https://sigel.aneel.gov.br/arcgis/rest/services"
        "/PORTAL/Linhas_Transmissao/MapServer/0/query"
    )

    # --- Ookla Speedtest open data ---
    ookla_speedtest: str = "https://github.com/teamookla/ookla-open-data"


# Download cache directory for large files
DOWNLOAD_CACHE_DIR = os.getenv("DOWNLOAD_CACHE_DIR", "/tmp/enlace_cache")


# Brazilian states: code -> (name, abbreviation)
BRAZILIAN_STATES: Dict[str, str] = {
    "11": "Rondonia",
    "12": "Acre",
    "13": "Amazonas",
    "14": "Roraima",
    "15": "Para",
    "16": "Amapa",
    "17": "Tocantins",
    "21": "Maranhao",
    "22": "Piaui",
    "23": "Ceara",
    "24": "Rio Grande do Norte",
    "25": "Paraiba",
    "26": "Pernambuco",
    "27": "Alagoas",
    "28": "Sergipe",
    "29": "Bahia",
    "31": "Minas Gerais",
    "32": "Espirito Santo",
    "33": "Rio de Janeiro",
    "35": "Sao Paulo",
    "41": "Parana",
    "42": "Santa Catarina",
    "43": "Rio Grande do Sul",
    "50": "Mato Grosso do Sul",
    "51": "Mato Grosso",
    "52": "Goias",
    "53": "Distrito Federal",
}

# State abbreviation mapping
STATE_ABBREVIATIONS: Dict[str, str] = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}

# Brazil's bounding box (approximate)
BRAZIL_BBOX = {
    "min_lat": -33.77,
    "max_lat": 5.27,
    "min_lon": -73.99,
    "max_lon": -28.83,
}

# Anatel technology mapping (Portuguese -> normalized)
TECHNOLOGY_MAP: Dict[str, str] = {
    "Fibra Optica": "fiber",
    "Fibra Óptica": "fiber",
    "Cabo Coaxial": "cable",
    "Cabo Coaxial/HFC": "cable",
    "HFC": "cable",
    "Metalico": "dsl",
    "Metálico": "dsl",
    "xDSL": "dsl",
    "Radio": "wireless",
    "Rádio": "wireless",
    "Satelite": "satellite",
    "Satélite": "satellite",
    "Outros": "other",
}

# Default pipeline configuration
PIPELINE_DEFAULTS = {
    "batch_size": 10000,
    "max_retries": 3,
    "retry_delay_seconds": 60,
    "download_timeout_seconds": 300,
    "default_country": "BR",
}
