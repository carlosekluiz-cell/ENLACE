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
    """URLs for all external data sources used by pipelines."""

    # Anatel (Brazilian telecom regulator) open data
    anatel_broadband: str = (
        "https://dados.gov.br/dados/conjuntos-dados/acessos-banda-larga-fixa"
    )
    anatel_base_stations: str = (
        "https://sistemas.anatel.gov.br/se/public/view/b/licenciamento.php"
    )
    anatel_quality: str = (
        "https://dados.gov.br/dados/conjuntos-dados/indicadores-de-qualidade"
    )
    anatel_providers: str = (
        "https://dados.gov.br/dados/conjuntos-dados/prestadoras"
    )

    # IBGE (Brazilian Institute of Geography and Statistics)
    ibge_census_boundaries: str = (
        "https://www.ibge.gov.br/geociencias/organizacao-do-territorio/"
        "malhas-territoriais/26565-malhas-de-setores-censitarios-"
        "divisoes-intramunicipais.html"
    )
    ibge_census_demographics: str = (
        "https://www.ibge.gov.br/estatisticas/sociais/saude/"
        "22827-censo-demografico-2022.html"
    )
    ibge_pib_municipal: str = (
        "https://www.ibge.gov.br/estatisticas/economicas/"
        "contas-nacionais/9088-produto-interno-bruto-dos-municipios.html"
    )
    ibge_population_projections: str = (
        "https://www.ibge.gov.br/estatisticas/sociais/populacao/"
        "9109-projecao-da-populacao.html"
    )
    ibge_api_base: str = "https://servicodados.ibge.gov.br/api/v1"

    # SRTM terrain elevation data
    srtm_nasa: str = (
        "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/"
    )
    srtm_alternative: str = "https://dwtkns.com/srtm30m/"

    # OpenStreetMap via Geofabrik
    osm_brazil_pbf: str = (
        "https://download.geofabrik.de/south-america/brazil-latest.osm.pbf"
    )

    # INMET (Brazilian National Institute of Meteorology)
    inmet_stations: str = (
        "https://apitempo.inmet.gov.br/estacoes/T"
    )
    inmet_observations: str = (
        "https://apitempo.inmet.gov.br/estacao"
    )

    # MapBiomas land cover
    mapbiomas: str = "https://mapbiomas.org/"

    # ANEEL power grid
    aneel_power: str = (
        "https://dadosabertos.aneel.gov.br/"
    )

    # Ookla Speedtest open data
    ookla_speedtest: str = (
        "https://github.com/teamookla/ookla-open-data"
    )


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
