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

# --- Speedtest ---
from python.pipeline.flows.ookla_speedtest import OoklaSpeedtestPipeline

# --- Colombia pipelines ---
from python.pipeline.flows.dane_census import DANECensusPipeline
from python.pipeline.flows.crc_providers import CRCProvidersPipeline
from python.pipeline.flows.mintic_broadband import MinTICBroadbandPipeline

# --- Colombia intelligence layers ---
from python.pipeline.flows.secop_contracts import SECOPContractsPipeline
from python.pipeline.flows.reps_health import REPSHealthPipeline
from python.pipeline.flows.men_schools import MENSchoolsPipeline
from python.pipeline.flows.crc_complaints import CRCComplaintsPipeline
from python.pipeline.flows.dane_nbi import DANENBIPipeline

# --- Colombia Phase 6: Additional intelligence sources ---
from python.pipeline.flows.ane_emf_probes import ANEEMFProbesPipeline
from python.pipeline.flows.mintic_centros_digitales import MinTICCentrosDigitalesPipeline
from python.pipeline.flows.co_quality_indicators import COQualityIndicatorsPipeline
from python.pipeline.flows.peeringdb_co import PeeringDBCOPipeline

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Census pipelines (17 countries)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.mx_inegi_census import MXINEGICensusPipeline
from python.pipeline.flows.ar_indec_census import ARINDECCensusPipeline
from python.pipeline.flows.cl_ine_census import CLINECensusPipeline
from python.pipeline.flows.uy_ine_census import UYINECensusPipeline
from python.pipeline.flows.pe_inei_census import PEINEICensusPipeline
from python.pipeline.flows.ec_inec_census import ECINECCensusPipeline
from python.pipeline.flows.do_one_census import DOONECensusPipeline
from python.pipeline.flows.py_ine_census import PYINECensusPipeline
from python.pipeline.flows.pa_inec_census import PAINECCensusPipeline
from python.pipeline.flows.cr_inec_census import CRINECCensusPipeline
from python.pipeline.flows.gt_ine_census import GTINECensusPipeline
from python.pipeline.flows.hn_ine_census import HNINECensusPipeline
from python.pipeline.flows.bo_ine_census import BOINECensusPipeline
from python.pipeline.flows.sv_census import SVCensusPipeline
from python.pipeline.flows.ve_ine_census import VEINECensusPipeline
from python.pipeline.flows.ni_inide_census import NIINIDECensusPipeline
from python.pipeline.flows.cu_onei_census import CUONEICensusPipeline

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Broadband/telecom pipelines (10 countries)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.mx_ift_broadband import MXIFTBroadbandPipeline
from python.pipeline.flows.ar_enacom_broadband import ARENACOMBroadbandPipeline
from python.pipeline.flows.cl_subtel_broadband import CLSUBTELBroadbandPipeline
from python.pipeline.flows.uy_ursec_broadband import UYURSECBroadbandPipeline
from python.pipeline.flows.pe_osiptel_broadband import PEOSIPTELBroadbandPipeline
from python.pipeline.flows.ec_arcotel_broadband import ECARCOTELBroadbandPipeline
from python.pipeline.flows.do_indotel_broadband import DOINDOTELBroadbandPipeline
from python.pipeline.flows.py_conatel_broadband import PYCONATELBroadbandPipeline
from python.pipeline.flows.pa_asep_broadband import PAASEPBroadbandPipeline
from python.pipeline.flows.cr_sutel_broadband import CRSUTELBroadbandPipeline

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Government contracts pipelines (8 countries)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.mx_compras_contracts import MXComprasContractsPipeline
from python.pipeline.flows.ar_comprar_contracts import ARComprarContractsPipeline
from python.pipeline.flows.cl_chilecompra_contracts import CLChileCompraContractsPipeline
from python.pipeline.flows.uy_arce_contracts import UYARCEContractsPipeline
from python.pipeline.flows.pe_seace_contracts import PESEACEContractsPipeline
from python.pipeline.flows.ec_sercop_contracts import ECSERCOPContractsPipeline
from python.pipeline.flows.do_dgcp_contracts import DODGCPContractsPipeline
from python.pipeline.flows.py_dncp_contracts import PYDNCPContractsPipeline

# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Health, schools, complaints (8 pipelines)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.mx_clues_health import MXCLUESHealthPipeline
from python.pipeline.flows.ar_refes_health import ARREFESHealthPipeline
from python.pipeline.flows.cl_deis_health import CLDEISHealthPipeline
from python.pipeline.flows.pe_renipress_health import PERENIPRESSHealthPipeline
from python.pipeline.flows.mx_siged_schools import MXSIGEDSchoolsPipeline
from python.pipeline.flows.ar_padron_schools import ARPadronSchoolsPipeline
from python.pipeline.flows.mx_profeco_complaints import MXPROFECOComplaintsPipeline
from python.pipeline.flows.cl_sernac_complaints import CLSERNACComplaintsPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase A: Globalized pipelines (PeeringDB, Quality Indicators)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.peeringdb import PeeringDBPipeline
from python.pipeline.flows.quality_indicators import QualityIndicatorsPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase B: LATAM provider extraction
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.latam_providers import LATAMProvidersPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase C: Census demographics / NBI poverty pipelines (8 countries)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.mx_inegi_nbi import MXINEGINBIPipeline
from python.pipeline.flows.ar_indec_nbi import ARINDECNBIPipeline
from python.pipeline.flows.cl_ine_casen import CLINECASENPipeline
from python.pipeline.flows.pe_inei_poverty import PEINEIPovertyPipeline
from python.pipeline.flows.uy_ine_nbi import UYINENBIPipeline
from python.pipeline.flows.ec_inec_nbi import ECINECNBIPipeline
from python.pipeline.flows.do_one_nbi import DOONENBIPipeline
from python.pipeline.flows.py_ine_nbi import PYINENBIPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase D: Additional contracts (PA, CR, GT, BO)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.pa_panamacompra_contracts import PAPanamaCompraContractsPipeline
from python.pipeline.flows.cr_sicop_contracts import CRSICOPContractsPipeline
from python.pipeline.flows.gt_guatecompras_contracts import GTGuateComprasContractsPipeline
from python.pipeline.flows.bo_sicoes_contracts import BOSICOESContractsPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase D: Additional health (UY, EC, DO)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.uy_asse_health import UYASSEHealthPipeline
from python.pipeline.flows.ec_msp_health import ECMSPHealthPipeline
from python.pipeline.flows.do_senasa_health import DOSENASAHealthPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase D: Additional schools (CL, PE, UY, EC)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.cl_mineduc_schools import CLMINEDUCSchoolsPipeline
from python.pipeline.flows.pe_escale_schools import PEEscaleSchoolsPipeline
from python.pipeline.flows.uy_anep_schools import UYANEPSchoolsPipeline
from python.pipeline.flows.ec_mineduc_schools import ECMINEDUCSchoolsPipeline

# ═══════════════════════════════════════════════════════════════════════════
# Parity Phase D: Additional complaints (AR, PE)
# ═══════════════════════════════════════════════════════════════════════════
from python.pipeline.flows.ar_consumidor_complaints import ARConsumidorComplaintsPipeline
from python.pipeline.flows.pe_osiptel_complaints import PEOSIPTELComplaintsPipeline
