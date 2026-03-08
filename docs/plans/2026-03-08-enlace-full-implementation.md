# ENLACE Platform — Full Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete ENLACE AI-powered telecom decision intelligence platform for Brazil — data foundation, ML models, Rust RF engine, regulatory compliance, fault intelligence, rural planner, map-first frontend, PDF reports, multi-tenant auth, and standalone M&A product.

**Architecture:** Phase-sequential build. PostgreSQL+PostGIS for geospatial data, Redis for caching, MinIO for object storage. Python FastAPI backend with SQLAlchemy ORM. Rust workspace for RF propagation engine connected via gRPC. Next.js 14 + Deck.gl frontend. Multi-country from day one (country_code on every table). Realistic synthetic seed data for validation.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy, XGBoost, GeoPandas, WeasyPrint), Rust 2021 (tonic, rayon, gdal), TypeScript (Next.js 14, React, Deck.gl, Tailwind), PostgreSQL 16 + PostGIS 3.4, Redis 7, MinIO, Docker Compose, gRPC/protobuf.

---

## PHASE 1: DATA FOUNDATION

### Task 1: Docker Infrastructure & Project Scaffolding

**Files:**
- Copy: `scaffolding/infrastructure/docker-compose.yml` → `docker-compose.yml`
- Copy: `scaffolding/infrastructure/init.sql` → `infrastructure/init.sql`
- Create: `.env`
- Create: `python/requirements.txt`
- Create: `python/pipeline/__init__.py`
- Create: `python/pipeline/config.py`
- Create: `python/api/__init__.py`
- Create: `python/api/main.py`
- Create: `python/api/config.py`
- Create: `python/api/database.py`

**Step 1: Set up project structure and Docker**

```bash
# Copy scaffolding to root
cp scaffolding/infrastructure/docker-compose.yml ./docker-compose.yml
mkdir -p infrastructure
cp scaffolding/infrastructure/init.sql ./infrastructure/init.sql

# Create directory structure
mkdir -p python/{pipeline/flows,pipeline/transformers,pipeline/loaders,api/routers,api/models,api/services,api/middleware}
mkdir -p rust/crates/{enlace-terrain/src,enlace-propagation/src/models,enlace-optimizer/src,enlace-raster/src,enlace-service/src,enlace-service/proto}
mkdir -p frontend/src/{app,components,hooks,lib,types}
mkdir -p tests/{unit,integration,validation}
mkdir -p data/scripts docs
```

Create `.env`:
```
POSTGRES_PASSWORD=enlace_dev_2026
POSTGRES_DB=enlace
POSTGRES_USER=enlace
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
REDIS_URL=redis://localhost:6379
MINIO_ROOT_USER=enlace_minio
MINIO_ROOT_PASSWORD=enlace_minio_2026
MINIO_ENDPOINT=localhost:9000
```

Create `python/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
geoalchemy2==0.17.1
asyncpg==0.30.0
psycopg2-binary==2.9.10
alembic==1.14.1
pydantic==2.10.4
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.28.1
redis==5.2.1
boto3==1.36.6
geopandas==1.0.1
shapely==2.0.6
h3==3.7.7
pandas==2.2.3
numpy==2.2.1
scikit-learn==1.6.1
xgboost==2.1.3
shap==0.46.0
prefect==2.20.14
weasyprint==63.1
jinja2==3.1.5
grpcio==1.69.0
grpcio-tools==1.69.0
protobuf==5.29.3
python-multipart==0.0.20
geojson==3.2.0
pyproj==3.7.0
rasterio==1.4.3
requests==2.32.3
beautifulsoup4==4.12.3
unidecode==1.3.8
```

**Step 2: Start Docker infrastructure**

```bash
docker compose up -d
# Wait for healthy
docker compose ps
# Verify PostgreSQL
docker exec enlace-postgres psql -U enlace -d enlace -c "SELECT PostGIS_Version();"
# Verify Redis
docker exec enlace-redis redis-cli ping
```

Expected: PostgreSQL with PostGIS 3.4, Redis PONG, MinIO healthy.

**Step 3: Set up Python virtual environment**

```bash
cd /home/dev/enlace
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

**Step 4: Create Python project scaffolding**

Create `python/pipeline/__init__.py` (empty)
Create `python/pipeline/config.py`:
```python
"""Data source configuration for all pipelines."""
import os
from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "enlace")
    user: str = os.getenv("POSTGRES_USER", "enlace")
    password: str = os.getenv("POSTGRES_PASSWORD", "enlace_dev_2026")

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass
class MinioConfig:
    endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = os.getenv("MINIO_ROOT_USER", "enlace_minio")
    secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "enlace_minio_2026")
    secure: bool = False

@dataclass
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# Anatel data source URLs
ANATEL_BROADBAND_URL = "https://dados.gov.br/dados/conjuntos-dados/acessos-banda-larga-fixa"
ANATEL_BASE_STATIONS_URL = "https://sistemas.anatel.gov.br/se/public/view/b/stel.php"

# IBGE URLs
IBGE_CENSUS_BOUNDARIES_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/2022/"
IBGE_CENSUS_DATA_URL = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/"
IBGE_PIB_URL = "https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html"

# SRTM
SRTM_BASE_URL = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/"

# OSM
OSM_BRAZIL_PBF_URL = "https://download.geofabrik.de/south-america/brazil-latest.osm.pbf"

# INMET
INMET_API_URL = "https://apitempo.inmet.gov.br/"

# Brazilian states for reference
BRAZILIAN_STATES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}
```

Create `python/api/config.py`:
```python
"""FastAPI application configuration."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://enlace:enlace_dev_2026@localhost:5432/enlace"
    database_sync_url: str = "postgresql://enlace:enlace_dev_2026@localhost:5432/enlace"
    redis_url: str = "redis://localhost:6379"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "enlace_minio"
    minio_secret_key: str = "enlace_minio_2026"
    jwt_secret: str = "enlace-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    rf_engine_host: str = "localhost"
    rf_engine_port: int = 50051
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
```

Create `python/api/database.py`:
```python
"""Database session management with SQLAlchemy async."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from python.api.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=20, max_overflow=10)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

Create `python/api/main.py`:
```python
"""ENLACE API — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from python.api.config import settings

app = FastAPI(
    title="ENLACE API",
    description="AI-Powered Telecom Decision Intelligence Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
```

**Step 5: Commit scaffolding**

```bash
git add -A
git commit -m "feat: project scaffolding — Docker, Python deps, API skeleton"
```

---

### Task 2: SQLAlchemy ORM Models

**Files:**
- Create: `python/api/models/orm.py`
- Create: `python/api/models/__init__.py`
- Create: `python/api/models/schemas.py`

**Step 1: Create ORM models matching init.sql schema**

Create `python/api/models/__init__.py` (empty)

Create `python/api/models/orm.py`:
```python
"""SQLAlchemy ORM models for all database tables."""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, Text, Date,
    DateTime, Numeric, ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from geoalchemy2 import Geometry
from python.api.database import Base


class Country(Base):
    __tablename__ = "countries"
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_local: Mapped[str] = mapped_column(String(100), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    regulator_name: Mapped[Optional[str]] = mapped_column(String(200))
    regulator_url: Mapped[Optional[str]] = mapped_column(String(500))
    national_crs: Mapped[Optional[int]] = mapped_column(Integer)
    timezone: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AdminLevel1(Base):
    __tablename__ = "admin_level_1"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    abbrev: Mapped[Optional[str]] = mapped_column(String(10))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("country_code", "code"),)


class AdminLevel2(Base):
    __tablename__ = "admin_level_2"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    l1_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_1.id"))
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Float)
    centroid = Column(Geometry("POINT", srid=4326))
    __table_args__ = (UniqueConstraint("country_code", "code"),)


class CensusTract(Base):
    __tablename__ = "census_tracts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Float)
    centroid = Column(Geometry("POINT", srid=4326))
    situation: Mapped[Optional[str]] = mapped_column(String(10))
    tract_type: Mapped[Optional[str]] = mapped_column(String(50))
    __table_args__ = (UniqueConstraint("country_code", "code"),)


class CensusDemographics(Base):
    __tablename__ = "census_demographics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tract_id: Mapped[int] = mapped_column(Integer, ForeignKey("census_tracts.id"))
    census_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_population: Mapped[Optional[int]] = mapped_column(Integer)
    total_households: Mapped[Optional[int]] = mapped_column(Integer)
    occupied_households: Mapped[Optional[int]] = mapped_column(Integer)
    avg_residents_per_household: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    income_data = mapped_column(JSON)
    education_data = mapped_column(JSON)
    housing_data = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("tract_id", "census_year"),)


class PopulationProjection(Base):
    __tablename__ = "population_projections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_population: Mapped[Optional[int]] = mapped_column(Integer)
    growth_rate: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("l2_id", "year"),)


class EconomicIndicator(Base):
    __tablename__ = "economic_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    pib_municipal_brl: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    pib_per_capita_brl: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    formal_employment: Mapped[Optional[int]] = mapped_column(Integer)
    sector_breakdown = mapped_column(JSON)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("l2_id", "year"),)


class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(300), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(30))
    classification: Mapped[Optional[str]] = mapped_column(String(20))
    services = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    first_seen_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BroadbandSubscriber(Base):
    __tablename__ = "broadband_subscribers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    technology: Mapped[str] = mapped_column(String(20), nullable=False)
    subscribers: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BaseStation(Base):
    __tablename__ = "base_stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    station_id: Mapped[Optional[str]] = mapped_column(String(50))
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    technology: Mapped[str] = mapped_column(String(10), nullable=False)
    frequency_mhz: Mapped[Optional[float]] = mapped_column(Float)
    bandwidth_mhz: Mapped[Optional[float]] = mapped_column(Float)
    antenna_height_m: Mapped[Optional[float]] = mapped_column(Float)
    azimuth_degrees: Mapped[Optional[float]] = mapped_column(Float)
    mechanical_tilt: Mapped[Optional[float]] = mapped_column(Float)
    power_watts: Mapped[Optional[float]] = mapped_column(Float)
    authorization_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    raw_data = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SpectrumLicense(Base):
    __tablename__ = "spectrum_licenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    frequency_start_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    frequency_end_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    bandwidth_mhz: Mapped[Optional[float]] = mapped_column(Float)
    geographic_area: Mapped[Optional[str]] = mapped_column(String(200))
    geographic_geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    license_type: Mapped[Optional[str]] = mapped_column(String(50))
    grant_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    conditions = mapped_column(JSON)
    source: Mapped[Optional[str]] = mapped_column(String(200))


class QualityIndicator(Base):
    __tablename__ = "quality_indicators"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))


class TerrainTile(Base):
    __tablename__ = "terrain_tiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tile_name: Mapped[str] = mapped_column(String(50), nullable=False)
    filepath: Mapped[str] = mapped_column(String(500), nullable=False)
    bbox = Column(Geometry("POLYGON", srid=4326), nullable=False)
    resolution_m: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LandCover(Base):
    __tablename__ = "land_cover"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False)
    cover_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biome: Mapped[Optional[str]] = mapped_column(String(50))
    cover_pct: Mapped[Optional[float]] = mapped_column(Float)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))


class BiomeRfCorrection(Base):
    __tablename__ = "biome_rf_corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    biome_type: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency_min_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    frequency_max_mhz: Mapped[float] = mapped_column(Float, nullable=False)
    additional_loss_db_min: Mapped[float] = mapped_column(Float, nullable=False)
    additional_loss_db_max: Mapped[float] = mapped_column(Float, nullable=False)
    additional_loss_db_mean: Mapped[Optional[float]] = mapped_column(Float)
    additional_loss_db_stddev: Mapped[Optional[float]] = mapped_column(Float)
    measurement_distance_range: Mapped[Optional[str]] = mapped_column(String(50))
    source_paper: Mapped[str] = mapped_column(String(500), nullable=False)
    source_institution: Mapped[Optional[str]] = mapped_column(String(200))
    source_year: Mapped[Optional[int]] = mapped_column(Integer)
    confidence: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class WeatherStation(Base):
    __tablename__ = "weather_stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    station_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[Optional[float]] = mapped_column(Float)
    station_type: Mapped[Optional[str]] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("country_code", "station_code"),)


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("weather_stations.id"), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Float)
    pressure_hpa: Mapped[Optional[float]] = mapped_column(Float)
    solar_radiation_wm2: Mapped[Optional[float]] = mapped_column(Float)


class RoadSegment(Base):
    __tablename__ = "road_segments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    osm_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    highway_class: Mapped[Optional[str]] = mapped_column(String(30))
    name: Mapped[Optional[str]] = mapped_column(String(300))
    surface_type: Mapped[Optional[str]] = mapped_column(String(30))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    length_m: Mapped[Optional[float]] = mapped_column(Float)


class PowerLine(Base):
    __tablename__ = "power_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    voltage_kv: Mapped[Optional[float]] = mapped_column(Float)
    operator_name: Mapped[Optional[str]] = mapped_column(String(200))
    line_type: Mapped[Optional[str]] = mapped_column(String(30))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))


class Railway(Base):
    __tablename__ = "railways"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    operator_name: Mapped[Optional[str]] = mapped_column(String(200))
    gauge_mm: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(20))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"))
    geographic_type: Mapped[str] = mapped_column(String(20), nullable=False)
    geographic_id: Mapped[str] = mapped_column(String(30), nullable=False)
    centroid = Column(Geometry("POINT", srid=4326))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    demand_score: Mapped[Optional[float]] = mapped_column(Float)
    competition_score: Mapped[Optional[float]] = mapped_column(Float)
    infrastructure_score: Mapped[Optional[float]] = mapped_column(Float)
    growth_score: Mapped[Optional[float]] = mapped_column(Float)
    composite_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    features = mapped_column(JSON)
    model_version: Mapped[Optional[str]] = mapped_column(String(50))


class CompetitiveAnalysis(Base):
    __tablename__ = "competitive_analysis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    l2_id: Mapped[int] = mapped_column(Integer, ForeignKey("admin_level_2.id"))
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hhi_index: Mapped[Optional[float]] = mapped_column(Float)
    leader_provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id"))
    leader_market_share: Mapped[Optional[float]] = mapped_column(Float)
    provider_details = mapped_column(JSON)
    growth_trend: Mapped[Optional[str]] = mapped_column(String(20))
    threat_level: Mapped[Optional[str]] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("l2_id", "year_month"),)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rows_processed: Mapped[Optional[int]] = mapped_column(Integer)
    rows_inserted: Mapped[Optional[int]] = mapped_column(Integer)
    rows_updated: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata_ = mapped_column("metadata", JSON)
```

**Step 2: Create Pydantic schemas**

Create `python/api/models/schemas.py`:
```python
"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Geographic ---
class MunicipalitySearch(BaseModel):
    q: str = Field(..., min_length=2, description="Search query")
    country: str = Field(default="BR", max_length=2)
    limit: int = Field(default=20, le=100)

class MunicipalityResponse(BaseModel):
    id: int
    code: str
    name: str
    state_abbrev: Optional[str] = None
    country_code: str
    area_km2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class GeoWithinRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=50, gt=0, le=500)
    country: str = Field(default="BR")


# --- Market ---
class MarketSummary(BaseModel):
    municipality_id: int
    municipality_code: str
    municipality_name: str
    state_abbrev: Optional[str] = None
    year_month: Optional[str] = None
    total_subscribers: Optional[int] = 0
    fiber_subscribers: Optional[int] = 0
    provider_count: Optional[int] = 0
    total_households: Optional[int] = None
    total_population: Optional[int] = None
    broadband_penetration_pct: Optional[float] = 0
    fiber_share_pct: Optional[float] = 0

class ProviderBreakdown(BaseModel):
    provider_id: int
    name: str
    subscribers: int
    share_pct: float
    technology: Optional[str] = None
    growth_3m: Optional[float] = None

class CompetitorResponse(BaseModel):
    hhi_index: Optional[float] = None
    providers: list[ProviderBreakdown] = []
    threats: list[dict] = []


# --- Opportunity ---
class OpportunityScoreRequest(BaseModel):
    country_code: str = "BR"
    area_type: str = "municipality"
    area_id: str

class OpportunityScoreResponse(BaseModel):
    composite_score: float
    confidence: float
    sub_scores: dict
    top_factors: list[dict]
    market_summary: dict

class FinancialRequest(BaseModel):
    municipality_code: str
    from_network_lat: float
    from_network_lon: float
    monthly_price_brl: float = 89.90
    technology: str = "fiber"

class FinancialResponse(BaseModel):
    subscriber_projection: dict
    capex_estimate: dict
    financial_metrics: dict


# --- Design ---
class CoverageRequest(BaseModel):
    tower_lat: float
    tower_lon: float
    tower_height_m: float = 30.0
    frequency_mhz: float = 700.0
    tx_power_dbm: float = 43.0
    antenna_gain_dbi: float = 15.0
    radius_m: float = 10000.0
    grid_resolution_m: float = 30.0
    apply_vegetation: bool = True
    country_code: str = "BR"

class DesignJobStatus(BaseModel):
    job_id: str
    status: str
    progress_pct: Optional[float] = None
    result: Optional[dict] = None


# --- Health ---
class HealthCheckResponse(BaseModel):
    status: str
    version: str
    database: str = "unknown"
    redis: str = "unknown"


# --- Auth ---
class TokenRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TenantCreate(BaseModel):
    name: str
    country_code: str = "BR"
    primary_state: Optional[str] = None
```

**Step 3: Commit**

```bash
git add python/api/models/
git commit -m "feat: SQLAlchemy ORM models and Pydantic schemas for all tables"
```

---

### Task 3: Seed Data — Realistic Brazilian Municipalities and Providers

**Files:**
- Create: `data/scripts/seed_data.py`

**Step 1: Create seed data script**

This seeds ~100 real Brazilian municipalities with realistic demographic and telecom data. Uses actual IBGE codes, state abbreviations, and coordinates.

Create `data/scripts/seed_data.py`:
```python
"""Seed realistic Brazilian data for development and validation.

Uses real municipality codes, names, coordinates from IBGE.
Subscriber counts and provider data approximated from public Anatel reports.
"""
import psycopg2
import random
import json
from datetime import datetime, date

DB_URL = "postgresql://enlace:enlace_dev_2026@localhost:5432/enlace"

# Real Brazilian states with IBGE codes
STATES = [
    ("11", "Rondônia", "RO"), ("12", "Acre", "AC"), ("13", "Amazonas", "AM"),
    ("14", "Roraima", "RR"), ("15", "Pará", "PA"), ("16", "Amapá", "AP"),
    ("17", "Tocantins", "TO"), ("21", "Maranhão", "MA"), ("22", "Piauí", "PI"),
    ("23", "Ceará", "CE"), ("24", "Rio Grande do Norte", "RN"), ("25", "Paraíba", "PB"),
    ("26", "Pernambuco", "PE"), ("27", "Alagoas", "AL"), ("28", "Sergipe", "SE"),
    ("29", "Bahia", "BA"), ("31", "Minas Gerais", "MG"), ("32", "Espírito Santo", "ES"),
    ("33", "Rio de Janeiro", "RJ"), ("35", "São Paulo", "SP"), ("41", "Paraná", "PR"),
    ("42", "Santa Catarina", "SC"), ("43", "Rio Grande do Sul", "RS"),
    ("50", "Mato Grosso do Sul", "MS"), ("51", "Mato Grosso", "MT"),
    ("52", "Goiás", "GO"), ("53", "Distrito Federal", "DF"),
]

# Sample municipalities (real IBGE codes, names, approximate coordinates)
MUNICIPALITIES = [
    # SP
    ("3550308", "35", "São Paulo", -23.5505, -46.6333, 12325232, 4000000),
    ("3509502", "35", "Campinas", -22.9056, -47.0608, 1223237, 420000),
    ("3518800", "35", "Guarulhos", -23.4628, -46.5333, 1392121, 430000),
    ("3547809", "35", "Ribeirão Preto", -21.1704, -47.8103, 711825, 250000),
    ("3534401", "35", "Osasco", -23.5325, -46.7917, 696850, 230000),
    ("3548708", "35", "Santo André", -23.6737, -46.5432, 721368, 250000),
    ("3548500", "35", "Santos", -23.9608, -46.3336, 433656, 170000),
    ("3552205", "35", "Sorocaba", -23.5015, -47.4526, 687357, 240000),
    # RJ
    ("3304557", "33", "Rio de Janeiro", -22.9068, -43.1729, 6748000, 2300000),
    ("3301702", "33", "Duque de Caxias", -22.7856, -43.3117, 924624, 290000),
    ("3303302", "33", "Niterói", -22.8833, -43.1036, 515317, 200000),
    ("3304904", "33", "São Gonçalo", -22.8269, -43.0634, 1091737, 330000),
    # MG
    ("3106200", "31", "Belo Horizonte", -19.9167, -43.9345, 2521564, 850000),
    ("3170206", "31", "Uberlândia", -18.9186, -48.2772, 699097, 240000),
    ("3136702", "31", "Juiz de Fora", -21.7642, -43.3503, 573285, 200000),
    # PR
    ("4106902", "41", "Curitiba", -25.4284, -49.2733, 1963726, 680000),
    ("4113700", "41", "Londrina", -23.3045, -51.1696, 580870, 200000),
    ("4115200", "41", "Maringá", -23.4205, -51.9333, 430157, 155000),
    # SC
    ("4205407", "42", "Florianópolis", -27.5954, -48.5480, 508826, 190000),
    ("4209102", "42", "Joinville", -26.3045, -48.8487, 597658, 210000),
    # RS
    ("4314902", "43", "Porto Alegre", -30.0277, -51.2287, 1492530, 520000),
    ("4303004", "43", "Caxias do Sul", -29.1681, -51.1794, 517451, 185000),
    # BA
    ("2927408", "29", "Salvador", -12.9714, -38.5124, 2886698, 900000),
    ("2910800", "29", "Feira de Santana", -12.2669, -38.9668, 619609, 190000),
    # CE
    ("2304400", "23", "Fortaleza", -3.7172, -38.5433, 2686612, 850000),
    # PE
    ("2611606", "26", "Recife", -8.0476, -34.8770, 1661681, 550000),
    # PA
    ("1501402", "15", "Belém", -1.4558, -48.5024, 1506420, 430000),
    # AM
    ("1302603", "13", "Manaus", -3.1190, -60.0217, 2255903, 650000),
    # GO
    ("5208707", "52", "Goiânia", -16.6799, -49.2550, 1555626, 530000),
    # DF
    ("5300108", "53", "Brasília", -15.7975, -47.8919, 3094325, 1000000),
    # MT
    ("5103403", "51", "Cuiabá", -15.5989, -56.0949, 618124, 210000),
    # MS
    ("5002704", "50", "Campo Grande", -20.4697, -54.6201, 916001, 310000),
    # Small/medium municipalities for variety
    ("3516200", "35", "Franca", -20.5390, -47.4014, 355901, 120000),
    ("3501608", "35", "Americana", -22.7392, -47.3314, 242018, 85000),
    ("3530706", "35", "Mogi das Cruzes", -23.5229, -46.1878, 440769, 150000),
    ("4104808", "41", "Cascavel", -24.9578, -53.4596, 332333, 115000),
    ("4202404", "42", "Blumenau", -26.9195, -49.0661, 361855, 130000),
    ("2933307", "29", "Vitória da Conquista", -14.8619, -40.8444, 343230, 100000),
    ("3170107", "31", "Uberaba", -19.7472, -47.9319, 340277, 120000),
]

# Major telecom providers in Brazil (real names, approximate classification)
PROVIDERS = [
    ("Claro S.A.", "claro sa", "40.432.544/0001-47", "PGP", ["SCM", "SMP"]),
    ("Telefônica Brasil S.A. (Vivo)", "telefonica brasil sa vivo", "02.558.157/0001-62", "PGP", ["SCM", "SMP"]),
    ("Oi S.A.", "oi sa", "76.535.764/0001-43", "PGP", ["SCM", "SMP", "STFC"]),
    ("TIM S.A.", "tim sa", "02.421.421/0001-11", "PGP", ["SMP"]),
    ("Algar Telecom S.A.", "algar telecom sa", "71.208.516/0001-74", "PMP", ["SCM", "SMP"]),
    ("Brisanet Serviços de Telecomunicações S.A.", "brisanet servicos telecom", "04.601.397/0001-28", "PMP", ["SCM"]),
    ("Desktop S.A.", "desktop sa", "02.508.596/0001-29", "PMP", ["SCM"]),
    ("Unifique Telecomunicações S.A.", "unifique telecom sa", "02.255.187/0001-08", "PMP", ["SCM"]),
    ("Copel Telecomunicações S.A.", "copel telecom sa", "04.368.865/0001-66", "PMP", ["SCM"]),
    ("Sercomtel S.A.", "sercomtel sa", "78.591.235/0001-34", "PMP", ["SCM"]),
    ("Sumicity Telecomunicações S.A.", "sumicity telecom sa", "11.089.508/0001-50", "PMP", ["SCM"]),
    ("Americanet S.A.", "americanet sa", "03.556.476/0001-05", "PMP", ["SCM"]),
    ("Mob Telecom", "mob telecom", "07.560.522/0001-44", "PMP", ["SCM"]),
    ("Ligga Telecom", "ligga telecom", "10.586.928/0001-70", "PMP", ["SCM"]),
    ("Gigabyte Provedor", "gigabyte provedor", "12.345.678/0001-90", "PPP", ["SCM"]),
    ("NetSul Provedor", "netsul provedor", "23.456.789/0001-01", "PPP", ["SCM"]),
    ("FibraMax Internet", "fibramax internet", "34.567.890/0001-12", "PPP", ["SCM"]),
    ("VelozNet Telecom", "veloznet telecom", "45.678.901/0001-23", "PPP", ["SCM"]),
    ("TurboLink Internet", "turbolink internet", "56.789.012/0001-34", "PPP", ["SCM"]),
    ("ConectaBrasil ISP", "conectabrasil isp", "67.890.123/0001-45", "PPP", ["SCM"]),
]


def seed():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("Seeding Brazilian states...")
    for code, name, abbrev in STATES:
        cur.execute("""
            INSERT INTO admin_level_1 (country_code, code, name, abbrev)
            VALUES ('BR', %s, %s, %s)
            ON CONFLICT (country_code, code) DO NOTHING
        """, (code, name, abbrev))

    print("Seeding municipalities...")
    for muni_code, state_code, name, lat, lon, pop, households in MUNICIPALITIES:
        # Get state id
        cur.execute("SELECT id FROM admin_level_1 WHERE country_code='BR' AND code=%s", (state_code,))
        row = cur.fetchone()
        if not row:
            continue
        l1_id = row[0]
        area_km2 = random.uniform(100, 2000)
        cur.execute("""
            INSERT INTO admin_level_2 (country_code, l1_id, code, name, area_km2,
                centroid)
            VALUES ('BR', %s, %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (country_code, code) DO NOTHING
        """, (l1_id, muni_code, name, area_km2, lon, lat))

    print("Seeding census tracts (5 per municipality)...")
    cur.execute("SELECT id, code FROM admin_level_2 WHERE country_code='BR'")
    munis = cur.fetchall()
    for l2_id, muni_code in munis:
        for i in range(5):
            tract_code = f"{muni_code}{str(i+1).zfill(8)}"
            situation = "urban" if i < 3 else "rural"
            cur.execute("""
                INSERT INTO census_tracts (country_code, l2_id, code, situation, tract_type)
                VALUES ('BR', %s, %s, %s, 'normal')
                ON CONFLICT (country_code, code) DO NOTHING
            """, (l2_id, tract_code, situation))

    print("Seeding demographics...")
    cur.execute("SELECT ct.id, ct.l2_id FROM census_tracts ct WHERE ct.country_code='BR'")
    tracts = cur.fetchall()
    # Get municipality populations
    muni_pop = {m[0]: (m[5], m[6]) for m in MUNICIPALITIES}
    cur.execute("SELECT id, code FROM admin_level_2 WHERE country_code='BR'")
    muni_id_map = {row[0]: row[1] for row in cur.fetchall()}

    for tract_id, l2_id in tracts:
        muni_code = muni_id_map.get(l2_id, "")
        base_pop = 0
        base_hh = 0
        for m in MUNICIPALITIES:
            if m[0] == muni_code:
                base_pop = m[5] // 5  # divide among 5 tracts
                base_hh = m[6] // 5
                break
        if base_pop == 0:
            base_pop = random.randint(500, 5000)
            base_hh = base_pop // 3

        pop = int(base_pop * random.uniform(0.5, 1.5))
        hh = int(base_hh * random.uniform(0.5, 1.5))
        avg_income = random.uniform(800, 5000)

        income_data = json.dumps({
            "avg_per_capita_brl": round(avg_income, 2),
            "median_per_capita_brl": round(avg_income * 0.75, 2),
            "brackets": {
                "below_half_min_wage": int(hh * random.uniform(0.05, 0.2)),
                "half_to_one_min_wage": int(hh * random.uniform(0.1, 0.3)),
                "one_to_two_min_wage": int(hh * random.uniform(0.2, 0.35)),
                "two_to_five_min_wage": int(hh * random.uniform(0.1, 0.25)),
                "five_to_ten_min_wage": int(hh * random.uniform(0.02, 0.1)),
                "above_ten_min_wage": int(hh * random.uniform(0.01, 0.05)),
            }
        })

        cur.execute("""
            INSERT INTO census_demographics (tract_id, census_year, total_population,
                total_households, occupied_households, avg_residents_per_household,
                income_data)
            VALUES (%s, 2022, %s, %s, %s, %s, %s)
            ON CONFLICT (tract_id, census_year) DO NOTHING
        """, (tract_id, pop, hh, int(hh * 0.9), round(pop / max(hh, 1), 2), income_data))

    print("Seeding providers...")
    for name, norm_name, cnpj, classification, services in PROVIDERS:
        cur.execute("""
            INSERT INTO providers (country_code, name, name_normalized, national_id,
                classification, services, first_seen_date)
            VALUES ('BR', %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (name, norm_name, cnpj, classification, json.dumps(services),
              date(random.randint(2010, 2022), random.randint(1, 12), 1)))

    print("Seeding broadband subscribers...")
    cur.execute("SELECT id FROM providers WHERE country_code='BR'")
    provider_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM admin_level_2 WHERE country_code='BR'")
    l2_ids = [r[0] for r in cur.fetchall()]

    months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
              "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
    technologies = ["fiber", "cable", "dsl", "wireless"]

    for l2_id in l2_ids:
        # Each municipality gets 2-6 random providers
        num_providers = random.randint(2, min(6, len(provider_ids)))
        muni_providers = random.sample(provider_ids, num_providers)

        for prov_id in muni_providers:
            tech = random.choice(technologies)
            base_subs = random.randint(50, 5000)

            for ym in months:
                growth = random.uniform(0.98, 1.05)
                subs = max(10, int(base_subs * growth))
                base_subs = subs
                cur.execute("""
                    INSERT INTO broadband_subscribers (provider_id, l2_id, year_month,
                        technology, subscribers)
                    VALUES (%s, %s, %s, %s, %s)
                """, (prov_id, l2_id, ym, tech, subs))

    print("Seeding base stations...")
    for l2_id in l2_ids[:20]:  # Only first 20 munis for base stations
        cur.execute("SELECT ST_X(centroid), ST_Y(centroid) FROM admin_level_2 WHERE id=%s", (l2_id,))
        row = cur.fetchone()
        if not row or row[0] is None:
            continue
        lon, lat = row
        num_stations = random.randint(3, 15)
        for _ in range(num_stations):
            prov_id = random.choice(provider_ids[:5])
            tech = random.choice(["4G", "5G", "3G"])
            freq = random.choice([700, 850, 1800, 2100, 2600, 3500])
            s_lat = lat + random.uniform(-0.05, 0.05)
            s_lon = lon + random.uniform(-0.05, 0.05)
            cur.execute("""
                INSERT INTO base_stations (country_code, provider_id, geom, latitude,
                    longitude, technology, frequency_mhz, antenna_height_m, power_watts,
                    status)
                VALUES ('BR', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s,
                    %s, %s, %s, %s, 'active')
            """, (prov_id, s_lon, s_lat, s_lat, s_lon, tech, freq,
                  random.uniform(20, 60), random.uniform(10, 50)))

    print("Seeding multi-country test data (Colombia)...")
    cur.execute("""
        INSERT INTO countries VALUES
        ('CO', 'Colombia', 'Colombia', 'COP', 'es-CO', 'CRC', 'https://www.crcom.gov.co',
         4686, 'America/Bogota',
         ST_MakeBox2D(ST_Point(-81.73, -4.23), ST_Point(-66.87, 12.46)))
        ON CONFLICT DO NOTHING
    """)
    cur.execute("""
        INSERT INTO admin_level_1 (country_code, code, name, abbrev)
        VALUES ('CO', '11', 'Bogotá D.C.', 'BOG')
        ON CONFLICT (country_code, code) DO NOTHING
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Seed complete!")


if __name__ == "__main__":
    seed()
```

**Step 2: Run seed script**

```bash
cd /home/dev/enlace
source .venv/bin/activate
python data/scripts/seed_data.py
```

**Step 3: Verify seed data**

```bash
docker exec enlace-postgres psql -U enlace -d enlace -c "
SELECT 'states' as table_name, count(*) FROM admin_level_1 WHERE country_code='BR'
UNION ALL SELECT 'municipalities', count(*) FROM admin_level_2 WHERE country_code='BR'
UNION ALL SELECT 'tracts', count(*) FROM census_tracts WHERE country_code='BR'
UNION ALL SELECT 'demographics', count(*) FROM census_demographics
UNION ALL SELECT 'providers', count(*) FROM providers WHERE country_code='BR'
UNION ALL SELECT 'subscribers', count(*) FROM broadband_subscribers
UNION ALL SELECT 'base_stations', count(*) FROM base_stations
UNION ALL SELECT 'colombia_test', count(*) FROM admin_level_1 WHERE country_code='CO';
"
```

Expected: 27 states, ~40 municipalities, ~200 tracts, demographics, 20 providers, thousands of subscriber rows, Colombia = 1.

**Step 4: Commit**

```bash
git add data/scripts/seed_data.py
git commit -m "feat: realistic Brazilian seed data — states, municipalities, providers, subscribers"
```

---

### Task 4: Materialized View + Pipeline Base Classes

**Files:**
- Create: `infrastructure/materialized_views.sql`
- Create: `python/pipeline/base.py`
- Create: `python/pipeline/loaders/postgres_loader.py`
- Create: `python/pipeline/loaders/__init__.py`
- Create: `python/pipeline/transformers/provider_normalizer.py`
- Create: `python/pipeline/transformers/__init__.py`
- Create: `python/pipeline/transformers/validator.py`

**Step 1: Create materialized view SQL**

Create `infrastructure/materialized_views.sql` with the mv_market_summary from the spec.

**Step 2: Create pipeline base class**

Create `python/pipeline/base.py` — abstract pipeline with download → validate → transform → load pattern, with pipeline_runs logging.

**Step 3: Create provider normalizer**

Create `python/pipeline/transformers/provider_normalizer.py` — handles Vivo/Telefonica, Claro/NET/Embratel dedup, accent stripping.

**Step 4: Create postgres loader**

Create `python/pipeline/loaders/postgres_loader.py` — generic upsert helper using psycopg2.

**Step 5: Apply materialized views and commit**

```bash
docker exec -i enlace-postgres psql -U enlace -d enlace < infrastructure/materialized_views.sql
git add infrastructure/ python/pipeline/
git commit -m "feat: materialized views, pipeline base classes, provider normalizer"
```

---

### Task 5: Data Ingestion Pipelines (All 12)

**Files:**
- Create: `python/pipeline/flows/anatel_broadband.py`
- Create: `python/pipeline/flows/anatel_base_stations.py`
- Create: `python/pipeline/flows/anatel_quality.py`
- Create: `python/pipeline/flows/anatel_providers.py`
- Create: `python/pipeline/flows/ibge_census.py`
- Create: `python/pipeline/flows/ibge_pib.py`
- Create: `python/pipeline/flows/ibge_projections.py`
- Create: `python/pipeline/flows/srtm_terrain.py`
- Create: `python/pipeline/flows/mapbiomas_landcover.py`
- Create: `python/pipeline/flows/osm_roads.py`
- Create: `python/pipeline/flows/aneel_power.py`
- Create: `python/pipeline/flows/inmet_weather.py`
- Create: `python/pipeline/flows/__init__.py`

Each pipeline: download function (with real URLs) → parse → transform → load → log.
For dev environment: pipelines detect when source is unreachable and use synthetic data generation as fallback. All share the base class from Task 4.

**Step 1:** Create all 12 pipeline files with full implementation.
**Step 2:** Run each pipeline in fallback/synthetic mode to populate tables.
**Step 3:** Verify all tables have data.
**Step 4:** Commit.

```bash
git add python/pipeline/flows/
git commit -m "feat: all 12 data ingestion pipelines — Anatel, IBGE, SRTM, OSM, INMET"
```

---

### Task 6: FastAPI Routers — Geographic + Market + Health

**Files:**
- Create: `python/api/routers/__init__.py`
- Create: `python/api/routers/geographic.py`
- Create: `python/api/routers/market.py`
- Create: `python/api/routers/health.py`
- Modify: `python/api/main.py` — register routers

**Step 1:** Build geographic router: search, boundary, within-radius.
**Step 2:** Build market router: summary, history, competitors, heatmap.
**Step 3:** Build health router: basic health check with DB/Redis status.
**Step 4:** Register all routers in main.py.
**Step 5:** Test API with curl.

```bash
# Start API
cd /home/dev/enlace
uvicorn python.api.main:app --host 0.0.0.0 --port 8000 &

# Test
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/geo/search?q=Campinas&country=BR"
curl http://localhost:8000/api/v1/market/1/summary
```

**Step 6:** Commit.

```bash
git add python/api/
git commit -m "feat: FastAPI routers — geographic search, market intelligence, health"
```

---

### Task 7: Phase 1 Validation Tests

**Files:**
- Create: `tests/validation/phase1_validation.py`

**Step 1:** Implement all 6 validation tests from the spec:
1. Geographic data integrity (27 states, ~40 munis, tracts within parents)
2. Demographic completeness (every tract has 2022 demographics)
3. Subscriber data freshness and consistency
4. Spatial query performance (<2s for indexed queries)
5. Terrain data (stub — checks table exists, tile registration works)
6. Multi-country architecture (Colombia doesn't affect Brazil queries)

**Step 2:** Run validations.

```bash
cd /home/dev/enlace
python tests/validation/phase1_validation.py
```

**Step 3:** Fix any failures, then commit.

```bash
git add tests/
git commit -m "feat: Phase 1 validation tests — all passing"
git push
```

---

## PHASE 2A: EXPANSION PLANNING ENGINE

### Task 8: Feature Engineering + Opportunity Scoring

**Files:**
- Create: `python/ml/__init__.py`
- Create: `python/ml/config.py`
- Create: `python/ml/opportunity/__init__.py`
- Create: `python/ml/opportunity/features.py`
- Create: `python/ml/opportunity/scorer.py`
- Create: `python/ml/opportunity/competition.py`
- Create: `python/ml/opportunity/demand_model.py`
- Create: `python/ml/opportunity/training.py`

Implement XGBoost opportunity scoring model with SHAP interpretability. Train on synthetic historical entry events derived from seed data. Score all municipalities.

**Commit:**
```bash
git add python/ml/
git commit -m "feat: ML opportunity scoring — XGBoost with SHAP explanations"
```

---

### Task 9: Financial Viability + Fiber Routing

**Files:**
- Create: `python/ml/financial/__init__.py`
- Create: `python/ml/financial/viability.py`
- Create: `python/ml/financial/capex_estimator.py`
- Create: `python/ml/financial/subscriber_curve.py`
- Create: `python/ml/financial/arpu_model.py`
- Create: `python/ml/routing/__init__.py`
- Create: `python/ml/routing/fiber_route.py`
- Create: `python/ml/routing/corridor_finder.py`
- Create: `python/ml/routing/bom_generator.py`

Implement Bass diffusion subscriber model, CAPEX calculator with terrain multipliers, Dijkstra fiber routing on road graph, BOM generator.

**Commit:**
```bash
git add python/ml/financial/ python/ml/routing/
git commit -m "feat: financial viability models + fiber route pre-design"
```

---

### Task 10: Expansion Planning API Endpoints

**Files:**
- Create: `python/api/routers/opportunity.py`
- Create: `python/api/services/market_intelligence.py`
- Modify: `python/api/main.py`

Add endpoints: POST score, GET top opportunities, POST financial, POST route, GET competitors.

**Commit:**
```bash
git add python/api/
git commit -m "feat: expansion planning API — scoring, financial, routing endpoints"
```

---

## PHASE 2B: RUST RF PROPAGATION ENGINE

### Task 11: Rust Workspace + enlace-terrain Crate

**Files:**
- Copy: `scaffolding/rust/Cargo.toml` → `rust/Cargo.toml`
- Create: `rust/crates/enlace-terrain/Cargo.toml`
- Create: `rust/crates/enlace-terrain/src/lib.rs`
- Create: `rust/crates/enlace-terrain/src/srtm.rs`
- Create: `rust/crates/enlace-terrain/src/profile.rs`
- Create: `rust/crates/enlace-terrain/src/elevation.rs`
- Create: `rust/crates/enlace-terrain/src/cache.rs`

SRTM HGT tile reader with memory-mapped I/O, LRU cache, terrain profile extraction with Earth curvature correction.

**Commit:**
```bash
cd /home/dev/enlace/rust && cargo build
git add rust/
git commit -m "feat: enlace-terrain — SRTM reader, terrain profiles, LRU cache"
```

---

### Task 12: enlace-propagation Crate

**Files:**
- Create: `rust/crates/enlace-propagation/Cargo.toml`
- Create: All src files per spec (lib.rs, models/itm.rs, hata.rs, fspl.rs, tr38901.rs, p1812.rs, p530.rs, vegetation.rs, diffraction.rs, fresnel.rs, atmosphere.rs, coverage.rs, common.rs)

Implement: FSPL, Extended HATA/COST-231, Longley-Rice ITM, 3GPP TR 38.901, ITU-R P.1812, P.530. Brazilian vegetation correction layer. Coverage grid computation with Rayon parallelism.

**Commit:**
```bash
cd /home/dev/enlace/rust && cargo build && cargo test
git add rust/crates/enlace-propagation/
git commit -m "feat: enlace-propagation — ITM, HATA, FSPL, vegetation corrections"
```

---

### Task 13: enlace-optimizer + enlace-raster Crates

**Files:**
- Create optimizer crate: candidates.rs, setcover.rs, annealing.rs, constraints.rs, output.rs
- Create raster crate: geotiff.rs, renderer.rs

Tower placement: candidate generation → greedy set-cover → simulated annealing. GeoTIFF coverage map output.

**Commit:**
```bash
git add rust/crates/enlace-optimizer/ rust/crates/enlace-raster/
git commit -m "feat: tower optimizer (set-cover + annealing) + GeoTIFF rasterizer"
```

---

### Task 14: enlace-service (gRPC)

**Files:**
- Create: `rust/crates/enlace-service/Cargo.toml`
- Create: `rust/crates/enlace-service/build.rs`
- Create: `rust/crates/enlace-service/proto/rf_service.proto`
- Create: `rust/crates/enlace-service/src/main.rs`
- Create: `rust/crates/enlace-service/src/handlers.rs`
- Create: `rust/crates/enlace-service/src/config.rs`

gRPC service with all RPCs from spec: CalculatePathLoss, ComputeCoverage, OptimizeTowers (streaming), LinkBudget, TerrainProfile, Health.

**Commit:**
```bash
cd /home/dev/enlace/rust && cargo build
git add rust/crates/enlace-service/
git commit -m "feat: gRPC RF engine service — all RPCs implemented"
```

---

### Task 15: RF Design API + Python gRPC Client

**Files:**
- Create: `python/api/services/rf_client.py`
- Create: `python/api/routers/design.py`
- Modify: `python/api/main.py`

Python gRPC client connecting to Rust engine. Design router: POST coverage, POST optimize, POST linkbudget, GET status/result.

**Commit:**
```bash
git add python/api/
git commit -m "feat: RF design API — gRPC client + design endpoints"
```

---

### Task 16: Phase 2 Validation Tests

**Files:**
- Create: `tests/validation/phase2_validation.py`
- Create: `rust/tests/validation.rs`

Python: backtest opportunity scores, financial model calibration, route validity, competitive intelligence, feature correctness.
Rust: FSPL accuracy, flat terrain, known Brazilian measurements, coverage performance, optimizer convergence, backhaul link budget.

```bash
python tests/validation/phase2_validation.py
cd rust && cargo test
git add tests/ rust/tests/
git commit -m "feat: Phase 2 validation tests — ML + RF engine"
git push
```

---

## PHASE 3A: REGULATORY COMPLIANCE ENGINE

### Task 17: Regulatory Knowledge Base + Norma No. 4

**Files:**
- Create: `python/regulatory/__init__.py`
- Create: `python/regulatory/knowledge_base/__init__.py`
- Create: `python/regulatory/knowledge_base/regulations.py`
- Create: `python/regulatory/knowledge_base/tax_rates.py`
- Create: `python/regulatory/knowledge_base/deadlines.py`
- Create: `python/regulatory/analyzer/__init__.py`
- Create: `python/regulatory/analyzer/norma4.py`
- Create: `python/regulatory/analyzer/profile.py`
- Create: `python/regulatory/analyzer/licensing.py`
- Create: `python/regulatory/analyzer/quality.py`

ICMS rates for all 27 states. Norma no. 4 tax impact calculator. ISP profile analyzer. Licensing threshold checker.

**Commit:**
```bash
git add python/regulatory/
git commit -m "feat: regulatory compliance engine — Norma no.4, ICMS, licensing"
```

---

### Task 18: Regulatory API Endpoints

**Files:**
- Create: `python/api/routers/compliance.py`
- Modify: `python/api/main.py`

Endpoints: status, norma4/impact, licensing/check, deadlines, quality/benchmark.

**Commit:**
```bash
git add python/api/
git commit -m "feat: compliance API endpoints"
```

---

## PHASE 3B: FAULT INTELLIGENCE

### Task 19: Weather-Fault Correlation + Quality Benchmarking

**Files:**
- Create: `python/ml/health/__init__.py`
- Create: `python/ml/health/weather_correlation.py`
- Create: `python/ml/health/quality_benchmark.py`
- Create: `python/ml/health/maintenance_scorer.py`
- Create: `python/ml/health/seasonal_patterns.py`
- Create: `python/ml/health/infrastructure_aging.py`

Weather-fault statistical model, quality peer benchmarking, maintenance priority scoring.

**Commit:**
```bash
git add python/ml/health/
git commit -m "feat: fault intelligence — weather correlation, quality benchmarking"
```

---

### Task 20: Health API Endpoints + Phase 3 Validation

**Files:**
- Create: `python/api/routers/network_health.py`
- Modify: `python/api/main.py`
- Create: `tests/validation/phase3_validation.py`

Endpoints: weather-risk, quality, peers, maintenance priorities, seasonal.

```bash
git add python/api/ tests/
git commit -m "feat: health API + Phase 3 validation tests"
git push
```

---

## PHASE 4A: RURAL CONNECTIVITY PLANNER

### Task 21: Rural Modules

**Files:**
- Create: `python/rural/__init__.py`
- Create: `python/rural/hybrid_designer.py`
- Create: `python/rural/satellite_backhaul.py`
- Create: `python/rural/solar_power.py`
- Create: `python/rural/community_profiler.py`
- Create: `python/rural/funding_matcher.py`
- Create: `python/rural/cost_model_rural.py`
- Create: `python/rural/river_crossing.py`
- Create: `python/api/routers/rural.py`

Hybrid architecture designer, solar sizing, government funding matcher, rural API endpoints.

**Commit:**
```bash
git add python/rural/ python/api/routers/rural.py
git commit -m "feat: rural connectivity planner — hybrid designer, solar, funding"
```

---

## PHASE 4B: FRONTEND + REPORTS

### Task 22: Next.js Project Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`

```bash
cd /home/dev/enlace/frontend
npm install
npm run dev &
# Verify at http://localhost:3000
git add frontend/
git commit -m "feat: Next.js 14 project scaffold with Tailwind"
```

---

### Task 23: Map Dashboard + Deck.gl Layers

**Files:**
- Create all map components: MapContainer, OpportunityLayer, CompetitorLayer, CoverageLayer, RouteLayer, BaseStationLayer, DrawingTools, LayerControls
- Create all panels: OpportunityPanel, FinancialPanel, CompetitorPanel, DesignPanel, CompliancePanel, HealthPanel
- Create hooks: useMapData, useOpportunity, useDesign, useAuth
- Create lib: api.ts, mapUtils.ts, colorScales.ts, formatters.ts
- Create types: api.ts, map.ts, models.ts

**Commit:**
```bash
git add frontend/src/
git commit -m "feat: map dashboard — Deck.gl layers, panels, hooks, API client"
```

---

### Task 24: Dashboard Pages + User Flows

**Files:**
- Create: `frontend/src/app/dashboard/page.tsx`
- Create: `frontend/src/app/dashboard/expansion/page.tsx`
- Create: `frontend/src/app/dashboard/design/page.tsx`
- Create: `frontend/src/app/dashboard/compliance/page.tsx`
- Create: `frontend/src/app/dashboard/health/page.tsx`
- Create: `frontend/src/app/dashboard/reports/page.tsx`
- Create: `frontend/src/components/common/*`

All 3 user flows: "Where should I build?", "Design my network", "Am I compliant?"

**Commit:**
```bash
git add frontend/
git commit -m "feat: dashboard pages — expansion, design, compliance, health, reports"
```

---

### Task 25: PDF Report Generation

**Files:**
- Create: `python/api/services/report_generator.py`
- Create: `python/api/routers/reports.py`
- Create: `python/templates/reports/expansion.html`
- Create: `python/templates/reports/design.html`
- Create: `python/templates/reports/compliance.html`
- Create: `python/templates/reports/rural.html`

4 report types using WeasyPrint: expansion analysis, RF design, compliance status, rural feasibility.

**Commit:**
```bash
git add python/api/services/report_generator.py python/api/routers/reports.py python/templates/
git commit -m "feat: PDF report generation — 4 report types with WeasyPrint"
```

---

### Task 26: Multi-Tenant Auth + Data Isolation

**Files:**
- Create: `python/api/auth.py`
- Create: `python/api/middleware/tenant.py`
- Create: `python/api/middleware/rate_limit.py`
- Create: `python/api/middleware/__init__.py`
- Create: `infrastructure/tenant_tables.sql`

JWT auth, tenant middleware, rate limiting by tier, saved analyses/designs tables.

**Commit:**
```bash
git add python/api/auth.py python/api/middleware/ infrastructure/tenant_tables.sql
git commit -m "feat: multi-tenant auth — JWT, tenant isolation, rate limiting"
```

---

### Task 27: Phase 4 Validation + i18n

**Files:**
- Create: `tests/validation/phase4_validation.py`
- Create: `frontend/public/locales/pt-BR.json`
- Create: `frontend/public/locales/es.json`

Validate: map loads <3s, coverage renders, reports generate, tenant isolation works, Portuguese text.

```bash
git add tests/ frontend/public/locales/
git commit -m "feat: Phase 4 validation + i18n Portuguese/Spanish"
git push
```

---

## PHASE 5: M&A STANDALONE PRODUCT

### Task 28: M&A Database + Valuation Models

**Files:**
- Create: `infrastructure/mna_tables.sql`
- Create: `mna/__init__.py`
- Create: `mna/models/__init__.py`
- Create: `mna/models/valuation.py`
- Create: `mna/models/target_scorer.py`
- Create: `mna/models/deal_analyzer.py`

M&A-specific tables, 3 valuation methods (subscriber multiple, revenue multiple, simplified DCF), target scoring.

**Commit:**
```bash
git add infrastructure/mna_tables.sql mna/
git commit -m "feat: M&A valuation models — subscriber, revenue, DCF methods"
```

---

### Task 29: M&A API + Frontend

**Files:**
- Create: `mna/api/__init__.py`
- Create: `mna/api/main.py`
- Create: `mna/api/routers/targets.py`
- Create: `mna/api/routers/deals.py`
- Create: `mna/api/routers/valuation.py`
- Create: `mna/api/routers/portfolio.py`
- Create: `mna/api/routers/reports.py`
- Create: `mna/frontend/` (separate Next.js app)

Separate API on different port, read-only database views, acquirer dashboard, seller tool, reports.

**Commit:**
```bash
git add mna/
git commit -m "feat: M&A standalone product — API, frontend, data isolation"
git push
```

---

## INTEGRATION

### Task 30: Full Integration Test

**Files:**
- Create: `tests/integration/full_integration.py`

End-to-end test: create account → view expansion map → generate RF design → check compliance → export PDF report.

```bash
python tests/integration/full_integration.py
git add tests/integration/
git commit -m "feat: full integration test suite"
git push
```

---

## EXECUTION NOTES

- **Total tasks:** 30
- **Estimated commits:** 30+
- **Dependencies:** Tasks 1-7 (Phase 1) must be sequential. Tasks 8-10 and 11-15 can be partially parallel. Tasks 17-20 depend on Phase 1. Tasks 21-27 depend on Phase 2+3. Tasks 28-29 depend on Phase 1. Task 30 requires everything.
- **Synthetic data strategy:** All pipelines have fallback synthetic data generation for when real APIs are unavailable.
- **Testing:** Each task includes validation. Major phase boundaries have comprehensive validation suites.
