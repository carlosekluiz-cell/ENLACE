"""Data ingestion pipeline flows for all data sources."""
from python.pipeline.flows.anatel_broadband import AnatelBroadbandPipeline
from python.pipeline.flows.anatel_base_stations import AnatelBaseStationsPipeline
from python.pipeline.flows.anatel_quality import AnatelQualityPipeline
from python.pipeline.flows.anatel_providers import AnatelProvidersPipeline
from python.pipeline.flows.ibge_census import IBGECensusPipeline
from python.pipeline.flows.ibge_pib import IBGEPIBPipeline
from python.pipeline.flows.ibge_projections import IBGEProjectionsPipeline
from python.pipeline.flows.srtm_terrain import SRTMTerrainPipeline
from python.pipeline.flows.mapbiomas_landcover import MapBiomasLandCoverPipeline
from python.pipeline.flows.osm_roads import OSMRoadsPipeline
from python.pipeline.flows.aneel_power import ANEELPowerPipeline
from python.pipeline.flows.inmet_weather import INMETWeatherPipeline
