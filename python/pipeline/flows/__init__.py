"""Data ingestion pipeline flows for all data sources."""
from python.pipeline.flows.anatel_broadband import AnatelBroadbandPipeline
from python.pipeline.flows.anatel_base_stations import AnatelBaseStationsPipeline
from python.pipeline.flows.anatel_quality import AnatelQualityPipeline
from python.pipeline.flows.anatel_providers import AnatelProvidersPipeline
from python.pipeline.flows.ibge_census import IBGECensusPipeline
from python.pipeline.flows.ibge_pib import IBGEPIBPipeline
from python.pipeline.flows.ibge_projections import IBGEProjectionsPipeline
from python.pipeline.flows.ibge_pof import IBGEPOFPipeline
from python.pipeline.flows.srtm_terrain import SRTMTerrainPipeline
from python.pipeline.flows.mapbiomas_landcover import MapBiomasLandCoverPipeline
from python.pipeline.flows.osm_roads import OSMRoadsPipeline
from python.pipeline.flows.aneel_power import ANEELPowerPipeline
from python.pipeline.flows.inmet_weather import INMETWeatherPipeline
from python.pipeline.flows.snis_sanitation import SNISSanitationPipeline
from python.pipeline.flows.anp_fuel import ANPFuelPipeline
try:
    from python.pipeline.flows.sentinel_growth import SentinelGrowthPipeline
except ImportError:
    SentinelGrowthPipeline = None  # type: ignore[assignment,misc]

# --- Sprint 14: New data sources ---
from python.pipeline.flows.cnpj_enrichment import CNPJEnrichmentPipeline
from python.pipeline.flows.anatel_rqual import AnatelRQUALPipeline
from python.pipeline.flows.pncp_contracts import PNCPContractsPipeline
from python.pipeline.flows.transparencia_fust import TransparenciaFUSTPipeline
from python.pipeline.flows.bndes_loans import BNDESLoansPipeline
from python.pipeline.flows.anatel_backhaul import AnatelBackhaulPipeline
from python.pipeline.flows.inep_schools import INEPSchoolsPipeline
from python.pipeline.flows.datasus_health import DATASUSHealthPipeline
from python.pipeline.flows.ibge_munic import IBGEMUNICPipeline
from python.pipeline.flows.caged_employment import CAGEDEmploymentPipeline
from python.pipeline.flows.atlas_violencia import AtlasViolenciaPipeline
from python.pipeline.flows.dou_anatel import DOUAnatelPipeline
from python.pipeline.flows.querido_diario import QueridoDiarioPipeline
from python.pipeline.flows.ibge_cnefe import IBGECNEFEPipeline

# --- M&A Due Diligence sources ---
from python.pipeline.flows.pgfn_divida_ativa import PGFNDividaAtivaPipeline
from python.pipeline.flows.sanctions_check import SanctionsCheckPipeline
from python.pipeline.flows.consumer_complaints import ConsumerComplaintsPipeline
from python.pipeline.flows.rf_ownership import RFOwnershipPipeline
from python.pipeline.flows.opencellid import OpenCelliDPipeline
