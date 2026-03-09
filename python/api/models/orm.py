"""
ENLACE ORM Models

SQLAlchemy ORM models for all 23 database tables.
Uses GeoAlchemy2 for PostGIS geometry columns.
"""

from datetime import date, datetime
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    Double,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from python.api.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# Users & Auth
# ═══════════════════════════════════════════════════════════════════════════════


class User(Base):
    """Platform user with role-based access control."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", "tenant_id", name="uq_users_email_tenant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "manager", "analyst", "viewer", name="user_role", create_type=False),
        nullable=False,
        server_default="viewer",
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    preferences: Mapped[Optional[Any]] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """Tracks active user sessions for audit and revocation."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


# ═══════════════════════════════════════════════════════════════════════════════
# Geographic Entities
# ═══════════════════════════════════════════════════════════════════════════════


class Country(Base):
    """Country reference table."""

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
    # bounding_box is BOX2D — not mapped as a standard Geometry; skip or use raw
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    # Relationships
    admin_level_1s: Mapped[list["AdminLevel1"]] = relationship(back_populates="country")
    admin_level_2s: Mapped[list["AdminLevel2"]] = relationship(back_populates="country")
    census_tracts: Mapped[list["CensusTract"]] = relationship(back_populates="country")
    providers: Mapped[list["Provider"]] = relationship(back_populates="country")
    base_stations: Mapped[list["BaseStation"]] = relationship(back_populates="country")
    spectrum_licenses: Mapped[list["SpectrumLicense"]] = relationship(
        back_populates="country"
    )
    biome_rf_corrections: Mapped[list["BiomeRfCorrection"]] = relationship(
        back_populates="country"
    )
    weather_stations: Mapped[list["WeatherStation"]] = relationship(
        back_populates="country"
    )
    road_segments: Mapped[list["RoadSegment"]] = relationship(back_populates="country")
    power_lines: Mapped[list["PowerLine"]] = relationship(back_populates="country")
    railways: Mapped[list["Railway"]] = relationship(back_populates="country")
    opportunity_scores: Mapped[list["OpportunityScore"]] = relationship(
        back_populates="country"
    )


class AdminLevel1(Base):
    """First administrative level (e.g., Brazilian states)."""

    __tablename__ = "admin_level_1"
    __table_args__ = (UniqueConstraint("country_code", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    abbrev: Mapped[Optional[str]] = mapped_column(String(10))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Double)

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="admin_level_1s")
    admin_level_2s: Mapped[list["AdminLevel2"]] = relationship(
        back_populates="admin_level_1"
    )


class AdminLevel2(Base):
    """Second administrative level (e.g., Brazilian municipalities)."""

    __tablename__ = "admin_level_2"
    __table_args__ = (UniqueConstraint("country_code", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    l1_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_1.id")
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Double)
    centroid = Column(Geometry("POINT", srid=4326))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="admin_level_2s")
    admin_level_1: Mapped[Optional["AdminLevel1"]] = relationship(
        back_populates="admin_level_2s"
    )
    census_tracts: Mapped[list["CensusTract"]] = relationship(
        back_populates="admin_level_2"
    )
    broadband_subscribers: Mapped[list["BroadbandSubscriber"]] = relationship(
        back_populates="admin_level_2"
    )
    population_projections: Mapped[list["PopulationProjection"]] = relationship(
        back_populates="admin_level_2"
    )
    economic_indicators: Mapped[list["EconomicIndicator"]] = relationship(
        back_populates="admin_level_2"
    )
    quality_indicators: Mapped[list["QualityIndicator"]] = relationship(
        back_populates="admin_level_2"
    )
    competitive_analyses: Mapped[list["CompetitiveAnalysis"]] = relationship(
        back_populates="admin_level_2"
    )


class CensusTract(Base):
    """Census tract boundaries."""

    __tablename__ = "census_tracts"
    __table_args__ = (UniqueConstraint("country_code", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2: Mapped[Optional[float]] = mapped_column(Double)
    centroid = Column(Geometry("POINT", srid=4326))
    situation: Mapped[Optional[str]] = mapped_column(String(10))
    tract_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="census_tracts")
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="census_tracts"
    )
    demographics: Mapped[list["CensusDemographics"]] = relationship(
        back_populates="census_tract"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Demographics
# ═══════════════════════════════════════════════════════════════════════════════


class CensusDemographics(Base):
    """Census demographic data per tract and year."""

    __tablename__ = "census_demographics"
    __table_args__ = (UniqueConstraint("tract_id", "census_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tract_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("census_tracts.id")
    )
    census_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_population: Mapped[Optional[int]] = mapped_column(Integer)
    total_households: Mapped[Optional[int]] = mapped_column(Integer)
    occupied_households: Mapped[Optional[int]] = mapped_column(Integer)
    avg_residents_per_household: Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    income_data: Mapped[Optional[Any]] = mapped_column(JSONB)
    education_data: Mapped[Optional[Any]] = mapped_column(JSONB)
    housing_data: Mapped[Optional[Any]] = mapped_column(JSONB)

    # Relationships
    census_tract: Mapped[Optional["CensusTract"]] = relationship(
        back_populates="demographics"
    )


class PopulationProjection(Base):
    """Population projections by municipality and year."""

    __tablename__ = "population_projections"
    __table_args__ = (UniqueConstraint("l2_id", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_population: Mapped[Optional[int]] = mapped_column(Integer)
    growth_rate: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="population_projections"
    )


class EconomicIndicator(Base):
    """Economic indicators by municipality and year."""

    __tablename__ = "economic_indicators"
    __table_args__ = (UniqueConstraint("l2_id", "year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    pib_municipal_brl: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    pib_per_capita_brl: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    formal_employment: Mapped[Optional[int]] = mapped_column(Integer)
    sector_breakdown: Mapped[Optional[Any]] = mapped_column(JSONB)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="economic_indicators"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Telecom Market
# ═══════════════════════════════════════════════════════════════════════════════


class Provider(Base):
    """Telecom service provider."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(300), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(30))
    classification: Mapped[Optional[str]] = mapped_column(String(20))
    services: Mapped[Optional[Any]] = mapped_column(JSONB)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default="active")
    first_seen_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="providers")
    broadband_subscribers: Mapped[list["BroadbandSubscriber"]] = relationship(
        back_populates="provider"
    )
    base_stations: Mapped[list["BaseStation"]] = relationship(
        back_populates="provider"
    )
    spectrum_licenses: Mapped[list["SpectrumLicense"]] = relationship(
        back_populates="provider"
    )
    quality_indicators: Mapped[list["QualityIndicator"]] = relationship(
        back_populates="provider"
    )
    led_competitive_analyses: Mapped[list["CompetitiveAnalysis"]] = relationship(
        back_populates="leader_provider"
    )


class BroadbandSubscriber(Base):
    """Broadband subscriber counts by provider, municipality, month, technology."""

    __tablename__ = "broadband_subscribers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    technology: Mapped[str] = mapped_column(String(20), nullable=False)
    subscribers: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    # Relationships
    provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="broadband_subscribers"
    )
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="broadband_subscribers"
    )


class BaseStation(Base):
    """Cell tower / base station location and parameters."""

    __tablename__ = "base_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    station_id: Mapped[Optional[str]] = mapped_column(String(50))
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = mapped_column(Double, nullable=False)
    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    technology: Mapped[str] = mapped_column(String(10), nullable=False)
    frequency_mhz: Mapped[Optional[float]] = mapped_column(Double)
    bandwidth_mhz: Mapped[Optional[float]] = mapped_column(Double)
    antenna_height_m: Mapped[Optional[float]] = mapped_column(Double)
    azimuth_degrees: Mapped[Optional[float]] = mapped_column(Double)
    mechanical_tilt: Mapped[Optional[float]] = mapped_column(Double)
    power_watts: Mapped[Optional[float]] = mapped_column(Double)
    authorization_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default="active")
    raw_data: Mapped[Optional[Any]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="base_stations")
    provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="base_stations"
    )


class SpectrumLicense(Base):
    """Spectrum license allocations."""

    __tablename__ = "spectrum_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    frequency_start_mhz: Mapped[float] = mapped_column(Double, nullable=False)
    frequency_end_mhz: Mapped[float] = mapped_column(Double, nullable=False)
    bandwidth_mhz: Mapped[Optional[float]] = mapped_column(Double)
    geographic_area: Mapped[Optional[str]] = mapped_column(String(200))
    geographic_geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    license_type: Mapped[Optional[str]] = mapped_column(String(50))
    grant_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    conditions: Mapped[Optional[Any]] = mapped_column(JSONB)
    source: Mapped[Optional[str]] = mapped_column(String(200))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(
        back_populates="spectrum_licenses"
    )
    provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="spectrum_licenses"
    )


class QualityIndicator(Base):
    """Quality of service metrics by provider and municipality."""

    __tablename__ = "quality_indicators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Double, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="quality_indicators"
    )
    provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="quality_indicators"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Terrain & Environment
# ═══════════════════════════════════════════════════════════════════════════════


class TerrainTile(Base):
    """Digital elevation model (DEM) tile metadata."""

    __tablename__ = "terrain_tiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tile_name: Mapped[str] = mapped_column(String(50), nullable=False)
    filepath: Mapped[str] = mapped_column(String(500), nullable=False)
    bbox = Column(Geometry("POLYGON", srid=4326), nullable=False)
    resolution_m: Mapped[float] = mapped_column(Double, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    loaded_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )


class LandCover(Base):
    """Land cover classification per H3 hex cell."""

    __tablename__ = "land_cover"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False)
    cover_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biome: Mapped[Optional[str]] = mapped_column(String(50))
    cover_pct: Mapped[Optional[float]] = mapped_column(Double)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))


class BiomeRfCorrection(Base):
    """RF propagation correction factors by biome type."""

    __tablename__ = "biome_rf_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    biome_type: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency_min_mhz: Mapped[float] = mapped_column(Double, nullable=False)
    frequency_max_mhz: Mapped[float] = mapped_column(Double, nullable=False)
    additional_loss_db_min: Mapped[float] = mapped_column(Double, nullable=False)
    additional_loss_db_max: Mapped[float] = mapped_column(Double, nullable=False)
    additional_loss_db_mean: Mapped[Optional[float]] = mapped_column(Double)
    additional_loss_db_stddev: Mapped[Optional[float]] = mapped_column(Double)
    measurement_distance_range: Mapped[Optional[str]] = mapped_column(String(50))
    source_paper: Mapped[str] = mapped_column(String(500), nullable=False)
    source_institution: Mapped[Optional[str]] = mapped_column(String(200))
    source_year: Mapped[Optional[int]] = mapped_column(Integer)
    confidence: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(
        back_populates="biome_rf_corrections"
    )


class WeatherStation(Base):
    """Weather station locations."""

    __tablename__ = "weather_stations"
    __table_args__ = (UniqueConstraint("country_code", "station_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    station_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = mapped_column(Double, nullable=False)
    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    elevation_m: Mapped[Optional[float]] = mapped_column(Double)
    station_type: Mapped[Optional[str]] = mapped_column(String(50))
    active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default="true")

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(
        back_populates="weather_stations"
    )
    observations: Mapped[list["WeatherObservation"]] = relationship(
        back_populates="station"
    )


class WeatherObservation(Base):
    """Weather observation time-series data. Composite PK (station_id, observed_at)."""

    __tablename__ = "weather_observations"

    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("weather_stations.id"), primary_key=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True
    )
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Double)
    temperature_c: Mapped[Optional[float]] = mapped_column(Double)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Double)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Double)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Double)
    pressure_hpa: Mapped[Optional[float]] = mapped_column(Double)
    solar_radiation_wm2: Mapped[Optional[float]] = mapped_column(Double)

    # Relationships
    station: Mapped["WeatherStation"] = relationship(back_populates="observations")


# ═══════════════════════════════════════════════════════════════════════════════
# Infrastructure Corridors
# ═══════════════════════════════════════════════════════════════════════════════


class RoadSegment(Base):
    """Road network segments from OpenStreetMap."""

    __tablename__ = "road_segments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    osm_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    highway_class: Mapped[Optional[str]] = mapped_column(String(30))
    name: Mapped[Optional[str]] = mapped_column(String(300))
    surface_type: Mapped[Optional[str]] = mapped_column(String(30))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    length_m: Mapped[Optional[float]] = mapped_column(Double)

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="road_segments")


class PowerLine(Base):
    """Power transmission/distribution lines."""

    __tablename__ = "power_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    voltage_kv: Mapped[Optional[float]] = mapped_column(Double)
    operator_name: Mapped[Optional[str]] = mapped_column(String(200))
    line_type: Mapped[Optional[str]] = mapped_column(String(30))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="power_lines")


class Railway(Base):
    """Railway network segments."""

    __tablename__ = "railways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    operator_name: Mapped[Optional[str]] = mapped_column(String(200))
    gauge_mm: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(20))
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(back_populates="railways")


# ═══════════════════════════════════════════════════════════════════════════════
# Computed Metrics
# ═══════════════════════════════════════════════════════════════════════════════


class OpportunityScore(Base):
    """Pre-computed opportunity scores for geographic areas."""

    __tablename__ = "opportunity_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country_code: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("countries.code")
    )
    geographic_type: Mapped[str] = mapped_column(String(20), nullable=False)
    geographic_id: Mapped[str] = mapped_column(String(30), nullable=False)
    centroid = Column(Geometry("POINT", srid=4326))
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    demand_score: Mapped[Optional[float]] = mapped_column(Double)
    competition_score: Mapped[Optional[float]] = mapped_column(Double)
    infrastructure_score: Mapped[Optional[float]] = mapped_column(Double)
    growth_score: Mapped[Optional[float]] = mapped_column(Double)
    composite_score: Mapped[Optional[float]] = mapped_column(Double)
    confidence: Mapped[Optional[float]] = mapped_column(Double)
    features: Mapped[Optional[Any]] = mapped_column(JSONB)
    model_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    country: Mapped[Optional["Country"]] = relationship(
        back_populates="opportunity_scores"
    )


class CompetitiveAnalysis(Base):
    """Competitive landscape analysis per municipality and month."""

    __tablename__ = "competitive_analysis"
    __table_args__ = (UniqueConstraint("l2_id", "year_month"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    l2_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_level_2.id")
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    hhi_index: Mapped[Optional[float]] = mapped_column(Double)
    leader_provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    leader_market_share: Mapped[Optional[float]] = mapped_column(Double)
    provider_details: Mapped[Optional[Any]] = mapped_column(JSONB)
    growth_trend: Mapped[Optional[str]] = mapped_column(String(20))
    threat_level: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    admin_level_2: Mapped[Optional["AdminLevel2"]] = relationship(
        back_populates="competitive_analyses"
    )
    leader_provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="led_competitive_analyses"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Tracking
# ═══════════════════════════════════════════════════════════════════════════════


class PipelineRun(Base):
    """ETL pipeline execution tracking."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rows_processed: Mapped[Optional[int]] = mapped_column(Integer)
    rows_inserted: Mapped[Optional[int]] = mapped_column(Integer)
    rows_updated: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSONB)
