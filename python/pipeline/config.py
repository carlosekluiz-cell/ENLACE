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
    bucket_sentinel: str = "sentinel-composites"


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

    # --- Anatel direct ZIP downloads (fallback when CKAN/dados.gov.br is blocked) ---
    anatel_broadband_zip: str = (
        "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/acessos"
        "/acessos_banda_larga_fixa.zip"
    )
    anatel_providers_zip: str = (
        "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/outorga_e_licenciamento"
        "/prestadoras_servicos_telecomunicacoes.zip"
    )
    anatel_base_stations_zip: str = (
        "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/outorga_e_licenciamento"
        "/estacoes_licenciadas.zip"
    )
    anatel_quality_zip: str = (
        "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/qualidade"
        "/indicadores_rqual.zip"
    )

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

# --- Colombia data sources ---

@dataclass
class ColombiaDataSourceURLs:
    """URLs for Colombian government open data APIs (datos.gov.co Socrata)."""
    socrata_base: str = "https://www.datos.gov.co/resource"
    mintic_broadband_dataset: str = "n48w-gutb"   # Internet Fijo accesos
    dane_divipola_dataset: str = "gdxc-w37w"      # DIVIPOLA codes
    dane_census_population: str = "vt28-sa6n"     # Census 2018 population
    igac_departments: str = "xdk5-pm3f"           # Department boundaries
    crc_postdata_base: str = "https://www.postdata.gov.co"
    # MinTIC Colombia TIC quarterly XLSX — per-operator per-municipality data
    # Each bulletin ~120-125 MB XLSX with sheets "4,1"-"4,4" (one year each)
    # containing PROVEEDOR × CÓDIGO DANE × TECNOLOGÍA × ACCESOS detail
    mintic_colombiatic_xlsx: str = (
        "https://colombiatic.mintic.gov.co/679/articles-404030_archivo_xls.xlsx"  # Q1 2025
    )
    # Sheets to parse: "4,1"=2022, "4,2"=2023, "4,3"=2024, "4,4"=2025
    mintic_colombiatic_sheets: tuple = ("4,2", "4,3", "4,4")  # 2023-2025 (skip 2022 overlap with Socrata)
    osm_geofabrik_co: str = (
        "https://download.geofabrik.de/south-america/colombia-latest-free.shp.zip"
    )
    # Intelligence layer datasets
    secop_contracts_dataset: str = "jbjy-vk9h"    # SECOP II contracts
    reps_health_dataset: str = "c36g-9fc2"        # REPS health facilities
    men_schools_dataset: str = "upkm-vdjb"        # MEN school directory
    crc_complaints_csv: str = (
        "https://www.postdata.gov.co/sites/default/files/datasets/data/T_4_3_IND_QUEJAS_4.csv"
    )
    dane_nbi_dataset: str = "vt28-sa6n"           # DANE Census 2018 / NBI
    # Phase 6: Additional intelligence sources
    ane_emf_probes_dataset: str = "xhu9-3dq9"     # ANE RNI EMF monitoring probes
    mintic_centros_digitales_dataset: str = "2f4v-3fb7"  # MinTIC Centros Digitales
    peeringdb_fac_url: str = "https://www.peeringdb.com/api/fac?country=CO"
    peeringdb_net_url: str = "https://www.peeringdb.com/api/net?country=CO"


# Colombian departments: DANE 2-digit code -> name (33 departments)
COLOMBIAN_DEPARTMENTS: Dict[str, str] = {
    "05": "Antioquia", "08": "Atlantico", "11": "Bogota D.C.",
    "13": "Bolivar", "15": "Boyaca", "17": "Caldas", "18": "Caqueta",
    "19": "Cauca", "20": "Cesar", "23": "Cordoba", "25": "Cundinamarca",
    "27": "Choco", "41": "Huila", "44": "La Guajira", "47": "Magdalena",
    "50": "Meta", "52": "Narino", "54": "Norte de Santander",
    "63": "Quindio", "66": "Risaralda", "68": "Santander", "70": "Sucre",
    "73": "Tolima", "76": "Valle del Cauca", "81": "Arauca",
    "85": "Casanare", "86": "Putumayo", "88": "San Andres y Providencia",
    "91": "Amazonas", "94": "Guainia", "95": "Guaviare",
    "97": "Vaupes", "99": "Vichada",
}

# Colombia bounding box
COLOMBIA_BBOX = {
    "min_lat": -4.23,
    "max_lat": 13.39,
    "min_lon": -81.73,
    "max_lon": -66.85,
}

# CRC/MinTIC technology mapping (Spanish -> normalized)
COLOMBIA_TECHNOLOGY_MAP: Dict[str, str] = {
    # Fiber variants
    "FIBER TO THE HOME (FTTH)": "fiber",
    "FIBER TO THE BUILDING O FIBER TO THE BASEMENT (FTTB)": "fiber",
    "FIBER TO THE CABINET (FTTC)": "fiber",
    "FIBER TO THE NODE (FTTN)": "fiber",
    "FIBER TO THE ANTENNA (FTTA)": "fiber",
    "FIBER TO THE PREMISES": "fiber",
    "OTRAS TECNOLOGÍAS DE FIBRA (ANTES FTTX)": "fiber",
    "Fibra optica": "fiber", "Fibra Optica": "fiber", "Fibra óptica": "fiber",
    # Cable/HFC
    "CABLE": "cable",
    "HYBRID FIBER COAXIAL (HFC)": "cable",
    "HFC": "cable", "Cable": "cable",
    # DSL
    "XDSL": "dsl", "xDSL": "dsl", "DSL": "dsl",
    # Wireless
    "WIFI": "wireless", "WIMAX": "wireless",
    "OTRAS TECNOLOGÍAS INALÁMBRICAS": "wireless",
    "Inalambrico": "wireless", "Inalámbrico": "wireless",
    # Satellite
    "SATELITAL": "satellite", "Satelital": "satellite",
    # Fixed/other
    "OTRAS TECNOLOGÍAS FIJAS": "other",
    "NA (NO APLICA)": "other",
    "Otro": "other", "Otros": "other",
}


# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Bounding Boxes
# ═══════════════════════════════════════════════════════════════════════════

MEXICO_BBOX = {
    "min_lat": 14.39, "max_lat": 32.72,
    "min_lon": -118.60, "max_lon": -86.49,
}
ARGENTINA_BBOX = {
    "min_lat": -55.06, "max_lat": -21.78,
    "min_lon": -73.59, "max_lon": -53.59,
}
CHILE_BBOX = {
    "min_lat": -55.98, "max_lat": -17.50,
    "min_lon": -75.64, "max_lon": -66.42,
}
PERU_BBOX = {
    "min_lat": -18.35, "max_lat": -0.04,
    "min_lon": -81.33, "max_lon": -68.65,
}
ECUADOR_BBOX = {
    "min_lat": -5.01, "max_lat": 1.68,
    "min_lon": -92.01, "max_lon": -75.18,
}
VENEZUELA_BBOX = {
    "min_lat": 0.63, "max_lat": 12.20,
    "min_lon": -73.38, "max_lon": -59.80,
}
BOLIVIA_BBOX = {
    "min_lat": -22.90, "max_lat": -9.68,
    "min_lon": -69.64, "max_lon": -57.45,
}
PARAGUAY_BBOX = {
    "min_lat": -27.59, "max_lat": -19.29,
    "min_lon": -62.64, "max_lon": -54.24,
}
URUGUAY_BBOX = {
    "min_lat": -35.03, "max_lat": -30.08,
    "min_lon": -58.44, "max_lon": -53.07,
}
PANAMA_BBOX = {
    "min_lat": 7.20, "max_lat": 9.65,
    "min_lon": -83.05, "max_lon": -77.17,
}
COSTA_RICA_BBOX = {
    "min_lat": 8.03, "max_lat": 11.22,
    "min_lon": -85.95, "max_lon": -82.55,
}
GUATEMALA_BBOX = {
    "min_lat": 13.74, "max_lat": 17.82,
    "min_lon": -92.23, "max_lon": -88.22,
}
HONDURAS_BBOX = {
    "min_lat": 12.98, "max_lat": 16.52,
    "min_lon": -89.36, "max_lon": -83.13,
}
EL_SALVADOR_BBOX = {
    "min_lat": 13.15, "max_lat": 14.45,
    "min_lon": -90.13, "max_lon": -87.68,
}
NICARAGUA_BBOX = {
    "min_lat": 10.71, "max_lat": 15.03,
    "min_lon": -87.69, "max_lon": -82.73,
}
DOMINICAN_REPUBLIC_BBOX = {
    "min_lat": 17.47, "max_lat": 19.93,
    "min_lon": -72.01, "max_lon": -68.32,
}
CUBA_BBOX = {
    "min_lat": 19.83, "max_lat": 23.27,
    "min_lon": -84.95, "max_lon": -74.13,
}

# All LATAM bounding boxes for multi-country operations
ALL_LATAM_BBOXES = {
    "BR": BRAZIL_BBOX, "CO": COLOMBIA_BBOX,
    "MX": MEXICO_BBOX, "AR": ARGENTINA_BBOX, "CL": CHILE_BBOX,
    "PE": PERU_BBOX, "EC": ECUADOR_BBOX, "VE": VENEZUELA_BBOX,
    "BO": BOLIVIA_BBOX, "PY": PARAGUAY_BBOX, "UY": URUGUAY_BBOX,
    "PA": PANAMA_BBOX, "CR": COSTA_RICA_BBOX, "GT": GUATEMALA_BBOX,
    "HN": HONDURAS_BBOX, "SV": EL_SALVADOR_BBOX, "NI": NICARAGUA_BBOX,
    "DO": DOMINICAN_REPUBLIC_BBOX, "CU": CUBA_BBOX,
}

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Admin Level 1 Dictionaries
# ═══════════════════════════════════════════════════════════════════════════

MEXICO_STATES: Dict[str, str] = {
    "01": "Aguascalientes", "02": "Baja California", "03": "Baja California Sur",
    "04": "Campeche", "05": "Coahuila", "06": "Colima", "07": "Chiapas",
    "08": "Chihuahua", "09": "Ciudad de Mexico", "10": "Durango",
    "11": "Guanajuato", "12": "Guerrero", "13": "Hidalgo", "14": "Jalisco",
    "15": "Mexico", "16": "Michoacan", "17": "Morelos", "18": "Nayarit",
    "19": "Nuevo Leon", "20": "Oaxaca", "21": "Puebla", "22": "Queretaro",
    "23": "Quintana Roo", "24": "San Luis Potosi", "25": "Sinaloa",
    "26": "Sonora", "27": "Tabasco", "28": "Tamaulipas", "29": "Tlaxcala",
    "30": "Veracruz", "31": "Yucatan", "32": "Zacatecas",
}

ARGENTINA_PROVINCES: Dict[str, str] = {
    "02": "Ciudad Autonoma de Buenos Aires", "06": "Buenos Aires",
    "10": "Catamarca", "14": "Cordoba", "18": "Corrientes", "22": "Chaco",
    "26": "Chubut", "30": "Entre Rios", "34": "Formosa", "38": "Jujuy",
    "42": "La Pampa", "46": "La Rioja", "50": "Mendoza", "54": "Misiones",
    "58": "Neuquen", "62": "Rio Negro", "66": "Salta", "70": "San Juan",
    "74": "San Luis", "78": "Santa Cruz", "82": "Santa Fe",
    "86": "Santiago del Estero", "90": "Tucuman",
    "94": "Tierra del Fuego",
}

CHILE_REGIONS: Dict[str, str] = {
    "15": "Arica y Parinacota", "01": "Tarapaca", "02": "Antofagasta",
    "03": "Atacama", "04": "Coquimbo", "05": "Valparaiso",
    "13": "Metropolitana de Santiago", "06": "O'Higgins", "07": "Maule",
    "16": "Nuble", "08": "Biobio", "09": "La Araucania",
    "14": "Los Rios", "10": "Los Lagos", "11": "Aysen",
    "12": "Magallanes y la Antartica Chilena",
}

PERU_REGIONS: Dict[str, str] = {
    "01": "Amazonas", "02": "Ancash", "03": "Apurimac", "04": "Arequipa",
    "05": "Ayacucho", "06": "Cajamarca", "07": "Callao", "08": "Cusco",
    "09": "Huancavelica", "10": "Huanuco", "11": "Ica", "12": "Junin",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martin", "23": "Tacna", "24": "Tumbes",
    "25": "Ucayali",
}

ECUADOR_PROVINCES: Dict[str, str] = {
    "01": "Azuay", "02": "Bolivar", "03": "Canar", "04": "Carchi",
    "05": "Cotopaxi", "06": "Chimborazo", "07": "El Oro", "08": "Esmeraldas",
    "09": "Guayas", "10": "Imbabura", "11": "Loja", "12": "Los Rios",
    "13": "Manabi", "14": "Morona Santiago", "15": "Napo", "16": "Pastaza",
    "17": "Pichincha", "18": "Tungurahua", "19": "Zamora Chinchipe",
    "20": "Galapagos", "21": "Sucumbios", "22": "Orellana",
    "23": "Santo Domingo de los Tsachilas", "24": "Santa Elena",
}

VENEZUELA_STATES: Dict[str, str] = {
    "01": "Distrito Capital", "02": "Amazonas", "03": "Anzoategui",
    "04": "Apure", "05": "Aragua", "06": "Barinas", "07": "Bolivar",
    "08": "Carabobo", "09": "Cojedes", "10": "Delta Amacuro",
    "11": "Falcon", "12": "Guarico", "13": "Lara", "14": "Merida",
    "15": "Miranda", "16": "Monagas", "17": "Nueva Esparta",
    "18": "Portuguesa", "19": "Sucre", "20": "Tachira", "21": "Trujillo",
    "22": "Vargas", "23": "Yaracuy", "24": "Zulia",
}

BOLIVIA_DEPARTMENTS: Dict[str, str] = {
    "01": "Chuquisaca", "02": "La Paz", "03": "Cochabamba",
    "04": "Oruro", "05": "Potosi", "06": "Tarija",
    "07": "Santa Cruz", "08": "Beni", "09": "Pando",
}

PARAGUAY_DEPARTMENTS: Dict[str, str] = {
    "00": "Asuncion", "01": "Concepcion", "02": "San Pedro",
    "03": "Cordillera", "04": "Guaira", "05": "Caaguazu",
    "06": "Caazapa", "07": "Itapua", "08": "Misiones",
    "09": "Paraguari", "10": "Alto Parana", "11": "Central",
    "12": "Neembucu", "13": "Amambay", "14": "Canindeyu",
    "15": "Presidente Hayes", "16": "Alto Paraguay", "17": "Boqueron",
}

URUGUAY_DEPARTMENTS: Dict[str, str] = {
    "01": "Montevideo", "02": "Artigas", "03": "Canelones",
    "04": "Cerro Largo", "05": "Colonia", "06": "Durazno",
    "07": "Flores", "08": "Florida", "09": "Lavalleja",
    "10": "Maldonado", "11": "Paysandu", "12": "Rio Negro",
    "13": "Rivera", "14": "Rocha", "15": "Salto",
    "16": "San Jose", "17": "Soriano", "18": "Tacuarembo",
    "19": "Treinta y Tres",
}

PANAMA_PROVINCES: Dict[str, str] = {
    "01": "Bocas del Toro", "02": "Cocle", "03": "Colon",
    "04": "Chiriqui", "05": "Darien", "06": "Herrera",
    "07": "Los Santos", "08": "Panama", "09": "Veraguas",
    "10": "Panama Oeste", "11": "Comarca Guna Yala",
    "12": "Comarca Embera-Wounaan", "13": "Comarca Ngabe-Bugle",
}

COSTA_RICA_PROVINCES: Dict[str, str] = {
    "01": "San Jose", "02": "Alajuela", "03": "Cartago",
    "04": "Heredia", "05": "Guanacaste", "06": "Puntarenas",
    "07": "Limon",
}

GUATEMALA_DEPARTMENTS: Dict[str, str] = {
    "01": "Guatemala", "02": "El Progreso", "03": "Sacatepequez",
    "04": "Chimaltenango", "05": "Escuintla", "06": "Santa Rosa",
    "07": "Solola", "08": "Totonicapan", "09": "Quetzaltenango",
    "10": "Suchitepequez", "11": "Retalhuleu", "12": "San Marcos",
    "13": "Huehuetenango", "14": "Quiche", "15": "Baja Verapaz",
    "16": "Alta Verapaz", "17": "Peten", "18": "Izabal",
    "19": "Zacapa", "20": "Chiquimula", "21": "Jalapa",
    "22": "Jutiapa",
}

HONDURAS_DEPARTMENTS: Dict[str, str] = {
    "01": "Atlantida", "02": "Colon", "03": "Comayagua",
    "04": "Copan", "05": "Cortes", "06": "Choluteca",
    "07": "El Paraiso", "08": "Francisco Morazan", "09": "Gracias a Dios",
    "10": "Intibuca", "11": "Islas de la Bahia", "12": "La Paz",
    "13": "Lempira", "14": "Ocotepeque", "15": "Olancho",
    "16": "Santa Barbara", "17": "Valle", "18": "Yoro",
}

EL_SALVADOR_DEPARTMENTS: Dict[str, str] = {
    "01": "Ahuachapan", "02": "Santa Ana", "03": "Sonsonate",
    "04": "Chalatenango", "05": "La Libertad", "06": "San Salvador",
    "07": "Cuscatlan", "08": "La Paz", "09": "Cabanas",
    "10": "San Vicente", "11": "Usulutan", "12": "San Miguel",
    "13": "Morazan", "14": "La Union",
}

NICARAGUA_DEPARTMENTS: Dict[str, str] = {
    "01": "Boaco", "02": "Carazo", "03": "Chinandega",
    "04": "Chontales", "05": "Esteli", "06": "Granada",
    "07": "Jinotega", "08": "Leon", "09": "Madriz",
    "10": "Managua", "11": "Masaya", "12": "Matagalpa",
    "13": "Nueva Segovia", "14": "Rio San Juan", "15": "Rivas",
    "16": "RACCN", "17": "RACCS",
}

DOMINICAN_REPUBLIC_PROVINCES: Dict[str, str] = {
    "01": "Distrito Nacional", "02": "Azua", "03": "Baoruco",
    "04": "Barahona", "05": "Dajabon", "06": "Duarte",
    "07": "Elias Pina", "08": "El Seibo", "09": "Espaillat",
    "10": "Hato Mayor", "11": "Hermanas Mirabal", "12": "Independencia",
    "13": "La Altagracia", "14": "La Romana", "15": "La Vega",
    "16": "Maria Trinidad Sanchez", "17": "Monsenor Nouel",
    "18": "Monte Cristi", "19": "Monte Plata", "20": "Pedernales",
    "21": "Peravia", "22": "Puerto Plata", "23": "Samana",
    "24": "San Cristobal", "25": "San Jose de Ocoa", "26": "San Juan",
    "27": "San Pedro de Macoris", "28": "Sanchez Ramirez",
    "29": "Santiago", "30": "Santiago Rodriguez", "31": "Santo Domingo",
    "32": "Valverde",
}

CUBA_PROVINCES: Dict[str, str] = {
    "01": "Pinar del Rio", "02": "Artemisa", "03": "La Habana",
    "04": "Mayabeque", "05": "Matanzas", "06": "Villa Clara",
    "07": "Cienfuegos", "08": "Sancti Spiritus", "09": "Ciego de Avila",
    "10": "Camaguey", "11": "Las Tunas", "12": "Holguin",
    "13": "Granma", "14": "Santiago de Cuba", "15": "Guantanamo",
    "16": "Isla de la Juventud",
}

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Data Source URL Classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MexicoDataSourceURLs:
    """URLs for Mexican government open data APIs."""
    inegi_api_base: str = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR"
    datos_gob_mx_ckan: str = "https://datos.gob.mx/busca/api/3/action"
    ift_bit_todo_zip: str = "https://bit.ift.org.mx/descargas/datos/tabs/TODO.zip"
    ift_bit_baf_csv: str = "TODO/TD_ACC_BAF_ITE_VA.csv"  # inside ZIP: broadband access by operator/municipality
    compras_mx_ocds: str = "https://api.datos.gob.mx/v1/contratacionesabiertas"

    # CLUES health facilities — DGIS direct CSV (canonical, ~10MB)
    # Pattern: CLUES_{year}.csv  (available for 2016-2024)
    clues_health: str = "http://www.dgis.salud.gob.mx/descargas/datosabiertos/recursosSalud/CLUES_2024.csv"
    clues_health_years: tuple = (2024, 2023, 2022)

    # SIGED/SEP school catalog — repodatos mirror (canonical, ~170MB)
    siged_schools: str = (
        "https://repodatos.atdt.gob.mx/api_update/sep/"
        "catalogo_centros_trabajo_sep/CNCT_DA_2025_13112025.csv"
    )
    siged_schools_fallback: str = (
        "https://repodatos.atdt.gob.mx/api_update/sep/"
        "catalogo_centros_trabajo_sep/Catalogo_SIC_2024.csv"
    )
    siged_schools_split_01_16: str = (
        "https://repodatos.atdt.gob.mx/all_data/secretaria_educacion/"
        "2a1d047c-546b-4293-971a-c835689a37a5/CATALOGO_CENTRO_TRABAJO_01_16_CSV.csv"
    )
    siged_schools_split_17_32: str = (
        "https://repodatos.atdt.gob.mx/all_data/secretaria_educacion/"
        "2a1d047c-546b-4293-971a-c835689a37a5/CATALOGO_CENTRO_TRABAJO_17_32_CSV.csv"
    )

    # PROFECO telecom complaints — repodatos mirror (canonical, ~13MB)
    profeco_complaints: str = (
        "https://repodatos.atdt.gob.mx/api_update/profeco/"
        "quejas_materia_telecomunicaciones/quejas_telecomunicaciones_2022_2025.csv"
    )
    profeco_complaints_legacy: str = "https://datos.profeco.gob.mx/datos_abiertos/quejas.csv"

    osm_geofabrik_mx: str = "https://download.geofabrik.de/north-america/mexico-latest-free.shp.zip"


@dataclass
class ArgentinaDataSourceURLs:
    """URLs for Argentine government open data APIs."""
    datos_gob_ar_ckan: str = "https://datos.gob.ar/api/3/action"
    georef_api: str = "https://apis.datos.gob.ar/georef/api"
    # ENACOM migrated from datosabiertos.enacom.gob.ar (dead Junar API) to
    # indicadores.enacom.gob.ar which serves HTML tables with DataTables export.
    enacom_localidades_url: str = (
        "https://indicadores.enacom.gob.ar/DatosAbiertos/Internet"
        "/accesos-tecnologias-localidades"
    )
    enacom_provincias_url: str = (
        "https://indicadores.enacom.gob.ar/DatosAbiertos/Internet"
        "/accesos-tecnologias-provincias"
    )
    # Direct CSV downloads (more reliable than HTML scraping)
    enacom_provincias_csv: str = (
        "https://indicadores.enacom.gob.ar/Files/DatosAbiertos/"
        "internet_accesos_tecnologias_provincias.csv"
    )
    enacom_localidades_csv: str = (
        "https://indicadores.enacom.gob.ar/Files/DatosAbiertos/"
        "internet_accesos_tecnologias_localidades.csv"
    )
    comprar_ocds: str = "https://comprar.gob.ar/OCDS"
    refes_health: str = "https://datos.gob.ar/api/3/action/package_show?id=salud-listado-establecimientos-salud-asentados-registro-federal-refes"
    padron_schools: str = "https://datos.gob.ar/api/3/action/package_show?id=educacion-padron-oficial-establecimientos-educativos"
    osm_geofabrik_ar: str = "https://download.geofabrik.de/south-america/argentina-latest-free.shp.zip"


@dataclass
class ChileDataSourceURLs:
    """URLs for Chilean government open data APIs."""
    datos_gob_cl_ckan: str = "https://datos.gob.cl/api/3/action"
    # Direct SUBTEL Excel download — file name updated each quarter
    # Pattern: 1_SERIES_CONEXIONES_INTERNET_FIJA_{PERIOD}.xlsx
    subtel_broadband_xlsx: str = (
        "https://www.subtel.gob.cl/wp-content/uploads/2026/03"
        "/1_SERIES_CONEXIONES_INTERNET_FIJA_DIC25.xlsx"
    )
    # Fallback: previous quarter file
    subtel_broadband_xlsx_fallback: str = (
        "https://www.subtel.gob.cl/wp-content/uploads/2025/06"
        "/1_SERIES_CONEXIONES_INTERNET_FIJA_MAR25.xlsx"
    )
    # Landing page (used to discover latest download URL)
    subtel_stats_page: str = "https://www.subtel.gob.cl/estudios-y-estadisticas/internet"
    chilecompra_api: str = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
    chilecompra_ticket: str = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
    deis_health: str = "https://datos.gob.cl/api/3/action/package_show?id=establecimientos-de-salud-vigentes"
    sernac_complaints: str = "https://datos.gob.cl/api/3/action/package_show?id=f06210fe-d48a-44c7-b051-c79fa57c453d"
    osm_geofabrik_cl: str = "https://download.geofabrik.de/south-america/chile-latest-free.shp.zip"


@dataclass
class UruguayDataSourceURLs:
    """URLs for Uruguayan government open data APIs."""
    catalogo_datos_ckan: str = "https://catalogodatos.gub.uy/api/3/action"
    # CKAN dataset: fixed telecom subscribers (internet + telephony) by month/department/operator
    ursec_fixed_telecom_dataset: str = "ursec-suscriptores-mensuales-por-servicios-de-telecomunicaciones-fijas"
    ursec_fixed_telecom_csv: str = (
        "https://catalogodatos.gub.uy/dataset/919bde39-a073-4895-918e-d6c59ce7b92f"
        "/resource/37a1628d-8e29-41b3-bade-5573fcc2880f/download/suscripciones-fijas.csv"
    )
    ursec_fixed_telecom_xlsx: str = (
        "https://catalogodatos.gub.uy/dataset/919bde39-a073-4895-918e-d6c59ce7b92f"
        "/resource/a4f3b104-9a22-4457-9cc2-bf746b09ce15/download/suscripciones-fijas.xlsx"
    )
    ursec_stats: str = "https://www.gub.uy/unidad-reguladora-servicios-comunicaciones/datos-y-estadisticas/estadisticas"
    arce_compras: str = "https://www.comprasestatales.gub.uy/consultas/buscar"
    osm_geofabrik_uy: str = "https://download.geofabrik.de/south-america/uruguay-latest-free.shp.zip"


@dataclass
class PeruDataSourceURLs:
    """URLs for Peruvian government open data APIs."""
    datos_abiertos_ckan: str = "https://www.datosabiertos.gob.pe/api/3/action"
    # District-level broadband CSV from datosabiertos.gob.pe (updated quarterly)
    osiptel_broadband_csv: str = (
        "https://www.datosabiertos.gob.pe/sites/default/files/"
        "CANTIDAD%20DE%20CONEXIONES%20EN%20SERVICIO%20DE%20INTERNET%20FIJO"
        "%20POR%20VELOCIDAD%20DE%20BAJADA%2C%20EMPRESA%20OPERADORA%20Y%20DISTRITO.csv"
    )
    # Monthly Excel (department-level, older data up to 2019)
    osiptel_monthly_xlsx: str = (
        "https://www.datosabiertos.gob.pe/sites/default/files/"
        "5.%20CONEXIONES%20DE%20INTERNET%20FIJO.xlsx"
    )
    # SharePoint folder with additional OSIPTEL datasets
    osiptel_sharepoint: str = (
        "https://osiptelgobpe.sharepoint.com/:f:/s/RepositoriodeDatosAbiertosdelOSIPTEL/"
        "Eop-B2IYHMRElH0awSC2JNQBNjgCCudxvWPATpChZJ-Pcw"
    )
    osiptel_repository: str = "https://repositorio.osiptel.gob.pe"
    seace_ocds: str = "https://contratacionesabiertas.osce.gob.pe"
    renipress_health: str = "https://www.datosabiertos.gob.pe/api/3/action/package_show?id=registro-nacional-de-ipress-renipress"
    osm_geofabrik_pe: str = "https://download.geofabrik.de/south-america/peru-latest-free.shp.zip"


@dataclass
class EcuadorDataSourceURLs:
    """URLs for Ecuadorian government open data APIs."""
    datos_abiertos_ckan: str = "https://www.datosabiertos.gob.ec/api/3/action"
    arcotel_dataset: str = "cuentas-internet-fijos-y-moviles"
    # Direct ARCOTEL Excel download — file name updated each quarter
    arcotel_broadband_xlsx: str = (
        "https://www.arcotel.gob.ec/wp-content/uploads/2025/11"
        "/3-1-1-Cuentas-internet-fijos-y-moviles_sep_2025.xlsx"
    )
    # Previous period fallback
    arcotel_broadband_xlsx_fallback: str = (
        "https://www.arcotel.gob.ec/wp-content/uploads/2025/03"
        "/3-1-1-Cuentas-internet-fijos-y-moviles_dic_2024_FIN.xlsx"
    )
    sercop_ocds: str = "https://datosabiertos.compraspublicas.gob.ec"
    osm_geofabrik_ec: str = "https://download.geofabrik.de/south-america/ecuador-latest-free.shp.zip"


@dataclass
class DominicanRepublicDataSourceURLs:
    """URLs for Dominican Republic government open data APIs."""
    datos_gob_do_ckan: str = "https://datos.gob.do/api/3/action"
    # INDOTEL quarterly telecom indicators (fixed internet, telephony, etc.)
    indotel_stats_xlsx: str = (
        "https://www.indotel.gob.do/media/10045"
        "/indicadores-estad%C3%ADsticos-de-telecomunicaciones.xlsx"
    )
    # Quarterly indicators (older pattern — Q1 2022 example)
    indotel_quarterly_xlsx: str = (
        "https://indotel.gob.do/wp-content/uploads/2022/10"
        "/indicadores-estadisticos-de-telecomunicaciones-trimestrales-enero-marzo-2022-res-026-21-web.xlsx"
    )
    indotel_stats: str = "https://indotel.gob.do/transparencia/documentos/indicadores-estadisticos-trimestrales/"
    dgcp_ocds: str = "https://www.dgcp.gob.do"
    osm_geofabrik_do: str = "https://download.geofabrik.de/central-america/haiti-and-domrep-latest-free.shp.zip"


@dataclass
class ParaguayDataSourceURLs:
    """URLs for Paraguayan government open data APIs."""
    datos_gov_py_ckan: str = "https://www.datos.gov.py/api/3/action"
    # CONATEL market indicators XLSX — updated annually; includes internet fijo by department
    conatel_market_xlsx: str = (
        "https://www.conatel.gov.py/wp-content/uploads/2026/01"
        "/Mercados-2024-V3.xlsx"
    )
    # Fallback: previous version (2023)
    conatel_market_xlsx_fallback: str = (
        "https://www.conatel.gov.py/conatel/wp-content/uploads/2024/07"
        "/mercados-2023-actualizado-primera-actualizacion.xlsx"
    )
    # CONATEL fixed internet PDF reports (fallback for parsing)
    conatel_internet_fijo_pdf: str = (
        "https://www.conatel.gov.py/conatel/wp-content/uploads/2025/02"
        "/informe-de-internet-fijo-2024.pdf"
    )
    conatel_stats: str = "https://www.conatel.gov.py/conatel/indicadores/"
    dncp_datos_abiertos: str = "https://www.contrataciones.gov.py/datos"
    osm_geofabrik_py: str = "https://download.geofabrik.de/south-america/paraguay-latest-free.shp.zip"


@dataclass
class PanamaDataSourceURLs:
    """URLs for Panamanian government open data sources."""
    # CKAN open data portal — internet indicators dataset
    datos_abiertos_ckan: str = "https://www.datosabiertos.gob.pa/api/3/action"
    asep_internet_dataset: str = "asep-indicadores-del-servicio-de-internet-desde-2016-2022"
    # Direct XLSX download from CKAN (2016-2024 technology breakdown)
    asep_internet_xlsx: str = (
        "https://www.datosabiertos.gob.pa/dataset/7528d519-e59f-4dd0-8d95-85a1e02b527b"
        "/resource/b8fbcb59-f754-4684-b613-5bd3a57212d2/download"
        "/indicadores-de-internet-por-tecnologia-desde-el-ano-2016_2024.xlsx"
    )
    # Fallback: ASEP statistics page (Excel/PDF downloads)
    asep_stats: str = "https://www.asep.gob.pa/?page_id=13119"
    inec_stats: str = "https://www.inec.gob.pa"
    osm_geofabrik_pa: str = "https://download.geofabrik.de/central-america-latest-free.shp.zip"


@dataclass
class CostaRicaDataSourceURLs:
    """URLs for Costa Rican government open data sources."""
    inec_stats: str = "https://www.inec.cr"
    # SUTEL annual telecom statistics PDF (contains internet fijo tables)
    sutel_stats_pdf: str = (
        "https://sutel.go.cr/sites/default/files"
        "/estadisticas-sector-telecomunicaciones-2024.pdf"
    )
    # SUTEL statistics landing page
    sutel_stats: str = "https://sutel.go.cr/informes-indicadores"
    # SUTEL broadband map API (has operator-level data by canton)
    sutel_broadband_map: str = "https://mapabandaancha.sutel.go.cr"
    osm_geofabrik_cr: str = "https://download.geofabrik.de/central-america-latest-free.shp.zip"


@dataclass
class GuatemalaDataSourceURLs:
    """URLs for Guatemalan government open data sources."""
    ine_api: str = "https://datos.ine.gob.gt/api/3/action"
    osm_geofabrik_gt: str = "https://download.geofabrik.de/central-america-latest-free.shp.zip"


@dataclass
class HondurasDataSourceURLs:
    """URLs for Honduran government open data sources."""
    datos_gob_hn_ckan: str = "https://datos.gob.hn/api/3/action"
    osm_geofabrik_hn: str = "https://download.geofabrik.de/central-america-latest-free.shp.zip"


@dataclass
class BoliviaDataSourceURLs:
    """URLs for Bolivian government open data sources."""
    datos_gob_bo_ckan: str = "https://datos.gob.bo/api/3/action"
    osm_geofabrik_bo: str = "https://download.geofabrik.de/south-america/bolivia-latest-free.shp.zip"


# Spanish LATAM generic technology mapping (used by most LATAM countries)
LATAM_TECHNOLOGY_MAP: Dict[str, str] = {
    "Fibra optica": "fiber", "Fibra Optica": "fiber", "Fibra óptica": "fiber",
    "Fibra Óptica": "fiber", "FIBRA OPTICA": "fiber",
    "FTTH": "fiber", "FTTB": "fiber", "FTTC": "fiber", "FTTN": "fiber",
    "FTTx": "fiber", "Fibra": "fiber",
    "Cable": "cable", "HFC": "cable", "Cable coaxial": "cable",
    "Cablemódem": "cable", "Cablemodem": "cable", "Cable Módem": "cable",
    "CABLEMODEM": "cable",
    "xDSL": "dsl", "DSL": "dsl", "ADSL": "dsl", "VDSL": "dsl",
    "Inalambrico": "wireless", "Inalámbrico": "wireless",
    "WiFi": "wireless", "WiMAX": "wireless", "Wimax": "wireless", "Radio": "wireless",
    "WIRELESS": "wireless", "CELULAR": "wireless",
    "Satelital": "satellite", "Satélite": "satellite", "Satellite": "satellite",
    "SATELITAL": "satellite",
    "Terrestre fijo inalámbrico": "wireless", "Terrestre fijo inalambrico": "wireless",
    "Tecnología móvil": "wireless", "Tecnología Móvil": "wireless",
    "Tecnologia movil": "wireless",
    "Sin tecnología especificada": "other", "Sin tecnologia especificada": "other",
    "Cable Coaxial": "cable",
    "Otro": "other", "Otros": "other", "Other": "other",
    "Otras Tecnologías": "other", "Otras tecnologías": "other", "Otras tecnologias": "other",
    "DIAL UP": "dsl",
}


# Default pipeline configuration
PIPELINE_DEFAULTS = {
    "batch_size": 10000,
    "max_retries": 3,
    "retry_delay_seconds": 60,
    "download_timeout_seconds": 300,
    "default_country": "BR",
}
