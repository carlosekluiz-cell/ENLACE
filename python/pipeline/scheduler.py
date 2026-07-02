"""Pipeline scheduler — runs data pipelines on a cron schedule.

Usage:
    python -m python.pipeline.scheduler        # start scheduler
    python -m python.pipeline.scheduler --once  # run all once and exit
"""
import logging
import os
import sys
import argparse

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from python.pipeline.flows import (
    ANEELPowerPipeline,
    ANPFuelPipeline,
    AnatelBaseStationsPipeline,
    AnatelBroadbandPipeline,
    AnatelProvidersPipeline,
    AnatelQualityPipeline,
    IBGECensusPipeline,
    IBGEPIBPipeline,
    IBGEPOFPipeline,
    IBGEProjectionsPipeline,
    INMETWeatherPipeline,
    MapBiomasLandCoverPipeline,
    OSMRoadsPipeline,
    SNISSanitationPipeline,
    SentinelGrowthPipeline,
    SRTMTerrainPipeline,
    # Sprint 14: New data sources
    CNPJEnrichmentPipeline,
    AnatelRQUALPipeline,
    PNCPContractsPipeline,
    TransparenciaFUSTPipeline,
    BNDESLoansPipeline,
    AnatelBackhaulPipeline,
    INEPSchoolsPipeline,
    DATASUSHealthPipeline,
    IBGEMUNICPipeline,
    CAGEDEmploymentPipeline,
    AtlasViolenciaPipeline,
    DOUAnatelPipeline,
    QueridoDiarioPipeline,
    IBGECNEFEPipeline,
    # M&A Due Diligence sources
    PGFNDividaAtivaPipeline,
    SanctionsCheckPipeline,
    ConsumerComplaintsPipeline,
    RFOwnershipPipeline,
    OpenCelliDPipeline,
    # Speedtest
    OoklaSpeedtestPipeline,
    # Colombia
    DANECensusPipeline,
    CRCProvidersPipeline,
    MinTICBroadbandPipeline,
    # Colombia intelligence layers
    SECOPContractsPipeline,
    REPSHealthPipeline,
    MENSchoolsPipeline,
    CRCComplaintsPipeline,
    DANENBIPipeline,
    # Colombia Phase 6: Additional intelligence sources
    ANEEMFProbesPipeline,
    MinTICCentrosDigitalesPipeline,
    COQualityIndicatorsPipeline,
    PeeringDBCOPipeline,
    # LATAM Expansion — Census pipelines
    MXINEGICensusPipeline,
    ARINDECCensusPipeline,
    CLINECensusPipeline,
    UYINECensusPipeline,
    PEINEICensusPipeline,
    ECINECCensusPipeline,
    DOONECensusPipeline,
    PYINECensusPipeline,
    PAINECCensusPipeline,
    CRINECCensusPipeline,
    GTINECensusPipeline,
    HNINECensusPipeline,
    BOINECensusPipeline,
    SVCensusPipeline,
    VEINECensusPipeline,
    NIINIDECensusPipeline,
    CUONEICensusPipeline,
    # LATAM Expansion — Broadband pipelines
    MXIFTBroadbandPipeline,
    ARENACOMBroadbandPipeline,
    CLSUBTELBroadbandPipeline,
    UYURSECBroadbandPipeline,
    PEOSIPTELBroadbandPipeline,
    ECARCOTELBroadbandPipeline,
    DOINDOTELBroadbandPipeline,
    PYCONATELBroadbandPipeline,
    PAASEPBroadbandPipeline,
    CRSUTELBroadbandPipeline,
    # LATAM Expansion — Government contracts pipelines
    MXComprasContractsPipeline,
    ARComprarContractsPipeline,
    CLChileCompraContractsPipeline,
    UYARCEContractsPipeline,
    PESEACEContractsPipeline,
    ECSERCOPContractsPipeline,
    DODGCPContractsPipeline,
    PYDNCPContractsPipeline,
    # LATAM Expansion — Health, schools, complaints
    MXCLUESHealthPipeline,
    ARREFESHealthPipeline,
    CLDEISHealthPipeline,
    PERENIPRESSHealthPipeline,
    MXSIGEDSchoolsPipeline,
    ARPadronSchoolsPipeline,
    MXPROFECOComplaintsPipeline,
    CLSERNACComplaintsPipeline,
    # Parity — Globalized pipelines
    PeeringDBPipeline,
    QualityIndicatorsPipeline,
    LATAMProvidersPipeline,
    # Parity — NBI/poverty pipelines
    MXINEGINBIPipeline,
    ARINDECNBIPipeline,
    CLINECASENPipeline,
    PEINEIPovertyPipeline,
    UYINENBIPipeline,
    ECINECNBIPipeline,
    DOONENBIPipeline,
    PYINENBIPipeline,
    # Parity — Additional contracts (PA, CR, GT, BO)
    PAPanamaCompraContractsPipeline,
    CRSICOPContractsPipeline,
    GTGuateComprasContractsPipeline,
    BOSICOESContractsPipeline,
    # Parity — Additional health (UY, EC, DO)
    UYASSEHealthPipeline,
    ECMSPHealthPipeline,
    DOSENASAHealthPipeline,
    # Parity — Additional schools (CL, PE, UY, EC)
    CLMINEDUCSchoolsPipeline,
    PEEscaleSchoolsPipeline,
    UYANEPSchoolsPipeline,
    ECMINEDUCSchoolsPipeline,
    # Parity — Additional complaints (AR, PE)
    ARConsumidorComplaintsPipeline,
    PEOSIPTELComplaintsPipeline,
)


def _run_pipeline(pipeline_cls):
    """Run a single pipeline, catching all errors."""
    name = pipeline_cls.__name__
    try:
        p = pipeline_cls()
        result = p.run(force=False)
        logger.info(f"{name}: {result.get('status', 'unknown')}")
        return result.get("status") == "success"
    except Exception as e:
        logger.error(f"{name}: FAILED — {e}")
        return False


def _recompute_derived_data():
    """Recompute opportunity scores, quality indicators, and refresh views.

    Enhanced with new data sources: backhaul presence, school connectivity,
    health facility connectivity, employment indicators, quality seals,
    and safety indicators feed into the scoring formula.
    """
    import psycopg2
    from python.pipeline.config import DatabaseConfig
    db = DatabaseConfig()

    logger.info("Recomputing derived data (opportunity scores, quality indicators)...")
    conn = psycopg2.connect(db.url)
    cur = conn.cursor()

    try:
        # Refresh materialized view
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_market_summary")
        conn.commit()
        logger.info("Refreshed mv_market_summary")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Could not refresh mv_market_summary: {e}")

    try:
        # Recompute opportunity scores with enhanced formula
        cur.execute("SELECT MAX(year_month) FROM broadband_subscribers")
        latest_ym = cur.fetchone()[0]
        if latest_ym:
            cur.execute("""
                SELECT bs.l2_id, a2.code
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON bs.l2_id = a2.id
                WHERE bs.year_month = %s
                GROUP BY bs.l2_id, a2.code
            """, (latest_ym,))
            muni_rows = cur.fetchall()
            logger.info(f"Recomputing opportunity scores for {len(muni_rows)} municipalities...")

            for l2_id, muni_code in muni_rows:
                # Base scores from market data
                cur.execute("""
                    SELECT
                        ms.l2_id,
                        LEAST(100, GREATEST(0, (1.0 - COALESCE(ms.broadband_penetration_pct, 50) / 100.0) * 100)) AS demand_base,
                        LEAST(100, GREATEST(0, CASE WHEN ms.provider_count <= 2 THEN 90
                            WHEN ms.provider_count <= 5 THEN 70
                            WHEN ms.provider_count <= 10 THEN 40 ELSE 20 END)) AS competition_base,
                        LEAST(100, GREATEST(0, (1.0 - COALESCE(ms.fiber_share_pct, 50) / 100.0) * 100)) AS infra_base
                    FROM mv_market_summary ms WHERE ms.l2_id = %s
                """, (l2_id,))
                base = cur.fetchone()
                if not base:
                    continue

                demand_score = float(base[1])
                competition_score = float(base[2])
                infrastructure_score = float(base[3])
                growth_score = 50.0
                social_score = 50.0

                # Enhancement: backhaul presence (no backhaul = +30 infrastructure)
                cur.execute("""
                    SELECT has_fiber_backhaul FROM backhaul_presence
                    WHERE l2_id = %s ORDER BY year DESC LIMIT 1
                """, (l2_id,))
                bh = cur.fetchone()
                if bh and not bh[0]:
                    infrastructure_score = min(100, infrastructure_score + 30)

                # Enhancement: schools without internet boost demand
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline,
                           COUNT(*) AS total
                    FROM schools WHERE l2_id = %s
                """, (l2_id,))
                sc = cur.fetchone()
                if sc and sc[1] > 0:
                    offline_pct = (sc[0] / sc[1]) * 100
                    demand_score = min(100, demand_score + offline_pct * 0.2)
                    social_score = min(100, social_score + offline_pct * 0.3)

                # Enhancement: health facilities without internet
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline,
                           COUNT(*) AS total
                    FROM health_facilities WHERE l2_id = %s
                """, (l2_id,))
                hf = cur.fetchone()
                if hf and hf[1] > 0:
                    offline_pct = (hf[0] / hf[1]) * 100
                    social_score = min(100, social_score + offline_pct * 0.2)

                # Enhancement: employment net hires (growing economy = opportunity)
                cur.execute("""
                    SELECT net_hires FROM employment_indicators
                    WHERE l2_id = %s ORDER BY year DESC, month DESC LIMIT 1
                """, (l2_id,))
                emp = cur.fetchone()
                if emp and emp[0]:
                    if emp[0] > 0:
                        growth_score = min(100, growth_score + 20)
                    elif emp[0] < -100:
                        growth_score = max(0, growth_score - 10)

                # Enhancement: quality seals (poor incumbents = opportunity)
                cur.execute("""
                    SELECT AVG(overall_score) FROM quality_seals WHERE l2_id = %s
                """, (l2_id,))
                qs = cur.fetchone()
                if qs and qs[0]:
                    avg_quality = float(qs[0])
                    if avg_quality < 50:  # Poor quality incumbents
                        competition_score = min(100, competition_score + 15)

                # Enhancement: safety (safer = easier deployment)
                cur.execute("""
                    SELECT risk_score FROM safety_indicators
                    WHERE l2_id = %s ORDER BY year DESC LIMIT 1
                """, (l2_id,))
                sf = cur.fetchone()
                if sf and sf[0]:
                    risk = float(sf[0])
                    social_score = min(100, social_score + (100 - risk) * 0.2)

                # Enhancement: building density (dense underserved = high ROI)
                cur.execute("""
                    SELECT density_per_km2, residential_addresses
                    FROM building_density WHERE l2_id = %s
                    ORDER BY year DESC LIMIT 1
                """, (l2_id,))
                bd = cur.fetchone()
                density_boost = False
                building_density_km2 = 0.0
                if bd and bd[0]:
                    building_density_km2 = float(bd[0])
                    # Dense area with low penetration = high ROI deployment
                    if building_density_km2 > 500 and demand_score > 50:
                        demand_score = min(100, demand_score + 15)
                        density_boost = True

                # Enhancement: municipal planning (permitting ease)
                cur.execute("""
                    SELECT has_plano_diretor, has_building_code
                    FROM municipal_planning WHERE l2_id = %s
                    ORDER BY munic_year DESC LIMIT 1
                """, (l2_id,))
                mp = cur.fetchone()
                has_plano_diretor = False
                planning_boost = False
                if mp:
                    has_plano_diretor = bool(mp[0])
                    if mp[0] and mp[1]:  # has both plano diretor and building code
                        infrastructure_score = min(100, infrastructure_score + 10)
                        planning_boost = True
                    elif not mp[0]:  # no plano diretor = permitting risk
                        infrastructure_score = max(0, infrastructure_score - 5)

                # Enhancement: government contract activity (investment signal)
                cur.execute("""
                    SELECT COUNT(*) FROM government_contracts
                    WHERE l2_id = %s AND published_date > NOW() - INTERVAL '12 months'
                """, (l2_id,))
                gc = cur.fetchone()
                contract_activity = int(gc[0]) if gc else 0
                if contract_activity > 0:
                    growth_score = min(100, growth_score + 10)

                # Compute overall with new weights including social_score
                overall = round(
                    demand_score * 0.25 +
                    competition_score * 0.20 +
                    infrastructure_score * 0.20 +
                    growth_score * 0.15 +
                    social_score * 0.20
                , 1)

                details = {
                    "social_score": round(social_score, 1),
                    "backhaul_boost": bh is not None and not bh[0] if bh else False,
                    "school_gap": sc[0] if sc else 0,
                    "health_gap": hf[0] if hf else 0,
                    "density_boost": density_boost,
                    "planning_boost": planning_boost,
                    "contract_activity": contract_activity,
                    "building_density_km2": round(building_density_km2, 1),
                    "has_plano_diretor": has_plano_diretor,
                }

                import json
                cur.execute("""
                    UPDATE opportunity_scores SET
                        computed_at = NOW(),
                        demand_score = %s,
                        competition_score = %s,
                        infrastructure_score = %s,
                        growth_score = %s,
                        composite_score = %s,
                        features = COALESCE(features, '{}'::jsonb) || %s::jsonb
                    WHERE geographic_id = %s
                """, (demand_score, competition_score,
                      infrastructure_score, growth_score, overall,
                      json.dumps(details), muni_code))

            conn.commit()
            logger.info(f"Updated enhanced opportunity scores for {len(muni_rows)} municipalities")

    except Exception as e:
        conn.rollback()
        logger.warning(f"Could not recompute opportunity scores: {e}")

    # ── Competitive analysis: HHI, leader, growth trend, threat level ──
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(year_month) FROM broadband_subscribers")
        latest_ym = cur.fetchone()[0]
        if latest_ym:
            # Get previous month for growth trend
            ym_parts = latest_ym.split('-')
            prev_year, prev_month = int(ym_parts[0]), int(ym_parts[1])
            if prev_month == 1:
                prev_year -= 1
                prev_month = 12
            else:
                prev_month -= 1
            prev_ym = f"{prev_year}-{prev_month:02d}"

            # Get all municipalities with broadband data
            cur.execute("""
                SELECT DISTINCT l2_id FROM broadband_subscribers
                WHERE year_month = %s AND l2_id IS NOT NULL
            """, (latest_ym,))
            ca_muni_ids = [r[0] for r in cur.fetchall()]
            logger.info(f"Computing competitive analysis for {len(ca_muni_ids)} municipalities...")

            import json as json_mod
            for l2_id in ca_muni_ids:
                # Market shares for HHI
                cur.execute("""
                    SELECT provider_id, SUM(subscribers) AS subs
                    FROM broadband_subscribers
                    WHERE l2_id = %s AND year_month = %s
                    GROUP BY provider_id
                    ORDER BY subs DESC
                """, (l2_id, latest_ym))
                shares = cur.fetchall()
                if not shares:
                    continue

                total_subs = sum(s[1] for s in shares)
                if total_subs == 0:
                    continue

                # HHI = sum of squared market shares (in percentage points)
                hhi = sum(((s[1] / total_subs) * 100) ** 2 for s in shares)
                leader_id = shares[0][0]
                leader_share = (shares[0][1] / total_subs) * 100

                # Provider details JSON
                provider_details = []
                for pid, subs in shares[:10]:
                    cur.execute("SELECT name FROM providers WHERE id = %s", (pid,))
                    pname = cur.fetchone()
                    provider_details.append({
                        "provider_id": pid,
                        "name": pname[0] if pname else f"Provider {pid}",
                        "subscribers": subs,
                        "market_share_pct": round((subs / total_subs) * 100, 1),
                    })

                # Growth trend: compare with previous month
                cur.execute("""
                    SELECT SUM(subscribers) FROM broadband_subscribers
                    WHERE l2_id = %s AND year_month = %s
                """, (l2_id, prev_ym))
                prev = cur.fetchone()
                prev_total = prev[0] if prev and prev[0] else 0
                if prev_total > 0:
                    growth_pct = ((total_subs - prev_total) / prev_total) * 100
                    if growth_pct > 2:
                        growth_trend = "growing"
                    elif growth_pct < -2:
                        growth_trend = "declining"
                    else:
                        growth_trend = "stable"
                else:
                    growth_trend = "new"

                # Threat level from HHI thresholds
                if hhi > 5000:
                    threat_level = "monopoly"
                elif hhi > 2500:
                    threat_level = "high_concentration"
                elif hhi > 1500:
                    threat_level = "moderate"
                else:
                    threat_level = "competitive"

                cur.execute("""
                    INSERT INTO competitive_analysis
                        (l2_id, year_month, computed_at, hhi_index,
                         leader_provider_id, leader_market_share,
                         provider_details, growth_trend, threat_level)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (l2_id, year_month) DO UPDATE SET
                        computed_at = EXCLUDED.computed_at,
                        hhi_index = EXCLUDED.hhi_index,
                        leader_provider_id = EXCLUDED.leader_provider_id,
                        leader_market_share = EXCLUDED.leader_market_share,
                        provider_details = EXCLUDED.provider_details,
                        growth_trend = EXCLUDED.growth_trend,
                        threat_level = EXCLUDED.threat_level
                """, (l2_id, latest_ym, round(hhi, 1), leader_id,
                      round(leader_share, 1), json_mod.dumps(provider_details),
                      growth_trend, threat_level))

            conn.commit()
            logger.info(f"Updated competitive analysis for {len(ca_muni_ids)} municipalities")

    except Exception as e:
        conn.rollback()
        logger.warning(f"Could not compute competitive analysis: {e}")

    cur.close()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Schedule groups
# ═══════════════════════════════════════════════════════════════════════════

def run_daily_telecom():
    """Daily: Anatel data (providers, broadband, base stations, quality) + Colombia CRC."""
    logger.info("=== Daily telecom pipelines ===")
    broadband_updated = False
    for cls in [AnatelProvidersPipeline, AnatelBroadbandPipeline,
                AnatelBaseStationsPipeline, AnatelQualityPipeline]:
        success = _run_pipeline(cls)
        if cls == AnatelBroadbandPipeline and success:
            broadband_updated = True

    # Colombia: CRC/MinTIC broadband
    for cls in [CRCProvidersPipeline, MinTICBroadbandPipeline]:
        success = _run_pipeline(cls)
        if cls == MinTICBroadbandPipeline and success:
            broadband_updated = True

    if broadband_updated:
        _recompute_derived_data()


def run_daily_weather():
    """Daily: Weather observations from Open-Meteo."""
    logger.info("=== Daily weather pipeline ===")
    _run_pipeline(INMETWeatherPipeline)


def run_daily_intelligence():
    """Daily: DOU regulatory acts, municipal gazettes, government contracts.

    PNCP runs last because the API is slow (~15-20 min).  DOU and Gazette
    run first so they are not blocked by PNCP timeouts.
    """
    logger.info("=== Daily intelligence pipelines ===")
    for cls in [DOUAnatelPipeline, QueridoDiarioPipeline, PNCPContractsPipeline]:
        _run_pipeline(cls)


def run_weekly_co_intelligence():
    """Weekly: Colombia SECOP II government contracts."""
    logger.info("=== Weekly CO intelligence pipelines ===")
    _run_pipeline(SECOPContractsPipeline)


def run_weekly_economic():
    """Weekly: IBGE economic data, POF, ANP fuel, ANEEL power, BNDES loans."""
    logger.info("=== Weekly economic pipelines ===")
    for cls in [IBGEPIBPipeline, IBGEProjectionsPipeline, IBGEPOFPipeline,
                ANPFuelPipeline, ANEELPowerPipeline, SNISSanitationPipeline,
                BNDESLoansPipeline]:
        _run_pipeline(cls)


def run_weekly_enrichment():
    """Weekly: CNPJ enrichment, RQUAL quality seals, FUST spending."""
    logger.info("=== Weekly enrichment pipelines ===")
    for cls in [CNPJEnrichmentPipeline, AnatelRQUALPipeline,
                TransparenciaFUSTPipeline]:
        _run_pipeline(cls)


def run_monthly_geographic():
    """Monthly: Census, SRTM terrain, MapBiomas, OSM roads + new sources + Colombia DANE."""
    logger.info("=== Monthly geographic pipelines ===")
    for cls in [IBGECensusPipeline, DANECensusPipeline, SRTMTerrainPipeline,
                MapBiomasLandCoverPipeline, OSMRoadsPipeline,
                AnatelBackhaulPipeline, DATASUSHealthPipeline,
                INEPSchoolsPipeline, IBGEMUNICPipeline,
                IBGECNEFEPipeline, CAGEDEmploymentPipeline,
                AtlasViolenciaPipeline, OoklaSpeedtestPipeline,
                # Colombia intelligence layers (monthly)
                REPSHealthPipeline, MENSchoolsPipeline,
                DANENBIPipeline]:
        _run_pipeline(cls)

    # Recompute scores after loading new data
    _recompute_derived_data()


def run_monthly_sentinel():
    """Monthly: Sentinel-2 urban growth indices and composites."""
    logger.info("=== Monthly sentinel pipeline ===")
    if SentinelGrowthPipeline is None:
        logger.warning("SentinelGrowthPipeline unavailable (missing dependencies)")
        return
    _run_pipeline(SentinelGrowthPipeline)


def run_weekly_due_diligence():
    """Weekly: Sanctions screening (CEIS/CNEP) via Portal da Transparência API."""
    logger.info("=== Weekly due diligence pipelines ===")
    for cls in [SanctionsCheckPipeline]:
        _run_pipeline(cls)


def run_monthly_due_diligence():
    """Monthly: Consumer complaints, RF ownership graph, OpenCelliD towers."""
    logger.info("=== Monthly due diligence pipelines ===")
    for cls in [ConsumerComplaintsPipeline, RFOwnershipPipeline, OpenCelliDPipeline]:
        _run_pipeline(cls)


def run_monthly_co_additional():
    """Monthly: CO EMF probes + globalized quality indicators, PeeringDB, LATAM providers."""
    logger.info("=== Monthly CO additional + globalized intelligence pipelines ===")
    for cls in [ANEEMFProbesPipeline, QualityIndicatorsPipeline, PeeringDBPipeline,
                LATAMProvidersPipeline]:
        _run_pipeline(cls)


def run_quarterly_co_centros():
    """Quarterly: MinTIC Centros Digitales (government connectivity centers)."""
    logger.info("=== Quarterly CO Centros Digitales pipeline ===")
    _run_pipeline(MinTICCentrosDigitalesPipeline)


def run_quarterly_co_complaints():
    """Quarterly: Colombia CRC telecom complaints."""
    logger.info("=== Quarterly CO complaints pipeline ===")
    _run_pipeline(CRCComplaintsPipeline)


def run_quarterly_pgfn():
    """Quarterly: PGFN federal tax debts (large 8GB+ downloads)."""
    logger.info("=== Quarterly PGFN pipeline ===")
    _run_pipeline(PGFNDividaAtivaPipeline)


# ═══════════════════════════════════════════════════════════════════════════
# LATAM Expansion — Schedule groups
# ═══════════════════════════════════════════════════════════════════════════

def run_monthly_latam_census():
    """Monthly 1st 05:00 UTC: Census refreshes for all 17 LATAM countries."""
    logger.info("=== Monthly LATAM census pipelines ===")
    for cls in [
        MXINEGICensusPipeline, ARINDECCensusPipeline, CLINECensusPipeline,
        UYINECensusPipeline, PEINEICensusPipeline, ECINECCensusPipeline,
        DOONECensusPipeline, PYINECensusPipeline, PAINECCensusPipeline,
        CRINECCensusPipeline, GTINECensusPipeline, HNINECensusPipeline,
        BOINECensusPipeline, SVCensusPipeline, VEINECensusPipeline,
        NIINIDECensusPipeline, CUONEICensusPipeline,
    ]:
        _run_pipeline(cls)


def run_monthly_latam_t1t2_broadband():
    """Monthly 2nd 05:00 UTC: Broadband data for T1+T2 countries (8 countries)."""
    logger.info("=== Monthly LATAM T1+T2 broadband pipelines ===")
    for cls in [
        MXIFTBroadbandPipeline, ARENACOMBroadbandPipeline,
        CLSUBTELBroadbandPipeline, UYURSECBroadbandPipeline,
        PEOSIPTELBroadbandPipeline, ECARCOTELBroadbandPipeline,
        DOINDOTELBroadbandPipeline, PYCONATELBroadbandPipeline,
    ]:
        _run_pipeline(cls)
    _recompute_derived_data()


def run_weekly_latam_t1_contracts():
    """Weekly Tue 05:00 UTC: Government contracts for T1 countries."""
    logger.info("=== Weekly LATAM T1 contracts pipelines ===")
    for cls in [
        MXComprasContractsPipeline, ARComprarContractsPipeline,
        CLChileCompraContractsPipeline, UYARCEContractsPipeline,
    ]:
        _run_pipeline(cls)


def run_monthly_latam_t1_social():
    """Monthly 15th 05:00 UTC: Health, schools, complaints for T1 (MX, AR, CL)."""
    logger.info("=== Monthly LATAM T1 social pipelines ===")
    for cls in [
        MXCLUESHealthPipeline, ARREFESHealthPipeline, CLDEISHealthPipeline,
        PERENIPRESSHealthPipeline,
        MXSIGEDSchoolsPipeline, ARPadronSchoolsPipeline,
        MXPROFECOComplaintsPipeline, CLSERNACComplaintsPipeline,
    ]:
        _run_pipeline(cls)


def run_quarterly_latam_t2t3():
    """Quarterly: Contracts and broadband for T2+T3 countries."""
    logger.info("=== Quarterly LATAM T2+T3 pipelines ===")
    for cls in [
        PESEACEContractsPipeline, ECSERCOPContractsPipeline,
        DODGCPContractsPipeline, PYDNCPContractsPipeline,
        PAASEPBroadbandPipeline, CRSUTELBroadbandPipeline,
    ]:
        _run_pipeline(cls)


def run_monthly_latam_nbi():
    """Monthly 3rd 05:00 UTC: NBI/poverty census demographics for 8 countries."""
    logger.info("=== Monthly LATAM NBI/poverty pipelines ===")
    for cls in [
        MXINEGINBIPipeline, ARINDECNBIPipeline, CLINECASENPipeline,
        PEINEIPovertyPipeline, UYINENBIPipeline, ECINECNBIPipeline,
        DOONENBIPipeline, PYINENBIPipeline,
    ]:
        _run_pipeline(cls)


def run_monthly_latam_t2_social():
    """Monthly 16th 05:00 UTC: Health, schools for T2 countries (UY, EC, DO, CL, PE)."""
    logger.info("=== Monthly LATAM T2 social pipelines ===")
    for cls in [
        UYASSEHealthPipeline, ECMSPHealthPipeline, DOSENASAHealthPipeline,
        CLMINEDUCSchoolsPipeline, PEEscaleSchoolsPipeline,
        UYANEPSchoolsPipeline, ECMINEDUCSchoolsPipeline,
    ]:
        _run_pipeline(cls)


def run_quarterly_latam_t3_contracts():
    """Quarterly: Contracts for T3 countries (PA, CR, GT, BO)."""
    logger.info("=== Quarterly LATAM T3 contracts pipelines ===")
    for cls in [
        PAPanamaCompraContractsPipeline, CRSICOPContractsPipeline,
        GTGuateComprasContractsPipeline, BOSICOESContractsPipeline,
    ]:
        _run_pipeline(cls)


def run_quarterly_latam_complaints():
    """Quarterly: Complaints for AR, PE."""
    logger.info("=== Quarterly LATAM complaints pipelines ===")
    for cls in [ARConsumidorComplaintsPipeline, PEOSIPTELComplaintsPipeline]:
        _run_pipeline(cls)


def run_all():
    """Run all pipeline groups."""
    run_daily_telecom()
    run_daily_weather()
    run_daily_intelligence()
    run_weekly_economic()
    run_weekly_enrichment()
    run_weekly_co_intelligence()
    run_weekly_due_diligence()
    run_monthly_geographic()
    run_monthly_due_diligence()
    run_monthly_sentinel()
    run_monthly_co_additional()
    run_quarterly_co_complaints()
    run_quarterly_co_centros()
    run_quarterly_pgfn()
    # LATAM expansion
    run_monthly_latam_census()
    run_monthly_latam_t1t2_broadband()
    run_weekly_latam_t1_contracts()
    run_monthly_latam_t1_social()
    run_quarterly_latam_t2t3()
    # Parity expansion
    run_monthly_latam_nbi()
    run_monthly_latam_t2_social()
    run_quarterly_latam_t3_contracts()
    run_quarterly_latam_complaints()


def main():
    parser = argparse.ArgumentParser(description="Pulso pipeline scheduler")
    parser.add_argument("--once", action="store_true", help="Run all pipelines once and exit")
    args = parser.parse_args()

    if args.once:
        logger.info("Running all pipelines once...")
        run_all()
        return

    scheduler = BlockingScheduler()

    # Daily at 02:00 UTC — telecom data
    scheduler.add_job(run_daily_telecom, CronTrigger(hour=2, minute=0),
                      id="daily_telecom", name="Daily Anatel pipelines")

    # Daily at 02:30 UTC — intelligence (contracts, DOU, gazettes)
    scheduler.add_job(run_daily_intelligence, CronTrigger(hour=2, minute=30),
                      id="daily_intelligence", name="Daily intelligence pipelines")

    # Daily at 03:00 UTC — weather
    scheduler.add_job(run_daily_weather, CronTrigger(hour=3, minute=0),
                      id="daily_weather", name="Daily INMET weather")

    # Weekly on Sundays at 04:00 UTC — economic
    scheduler.add_job(run_weekly_economic, CronTrigger(day_of_week="sun", hour=4, minute=0),
                      id="weekly_economic", name="Weekly economic pipelines")

    # Weekly on Sundays at 04:30 UTC — enrichment (CNPJ, RQUAL, FUST)
    scheduler.add_job(run_weekly_enrichment, CronTrigger(day_of_week="sun", hour=4, minute=30),
                      id="weekly_enrichment", name="Weekly enrichment pipelines")

    # Weekly on Tuesdays at 05:00 UTC — Colombia SECOP contracts
    scheduler.add_job(run_weekly_co_intelligence, CronTrigger(day_of_week="tue", hour=5, minute=0),
                      id="weekly_co_intelligence", name="Weekly CO SECOP contracts")

    # Monthly on 1st at 05:00 UTC — geographic + new monthly sources
    scheduler.add_job(run_monthly_geographic, CronTrigger(day=1, hour=5, minute=0),
                      id="monthly_geographic", name="Monthly geographic pipelines")

    # Monthly on 1st at 06:00 UTC — Sentinel-2 urban growth
    scheduler.add_job(run_monthly_sentinel, CronTrigger(day=1, hour=6, minute=0),
                      id="monthly_sentinel", name="Monthly Sentinel-2 urban growth")

    # Weekly on Wednesdays at 05:00 UTC — due diligence (sanctions screening)
    scheduler.add_job(run_weekly_due_diligence, CronTrigger(day_of_week="wed", hour=5, minute=0),
                      id="weekly_due_diligence", name="Weekly due diligence (sanctions)")

    # Monthly on 15th at 05:00 UTC — due diligence (complaints, ownership, OpenCelliD)
    scheduler.add_job(run_monthly_due_diligence, CronTrigger(day=15, hour=5, minute=0),
                      id="monthly_due_diligence", name="Monthly due diligence (complaints, ownership, towers)")

    # Quarterly on 1st of Jan/Apr/Jul/Oct at 07:00 UTC — PGFN tax debts
    scheduler.add_job(run_quarterly_pgfn, CronTrigger(month="1,4,7,10", day=1, hour=7, minute=0),
                      id="quarterly_pgfn", name="Quarterly PGFN federal tax debts")

    # Monthly on 2nd at 05:00 UTC — CO Phase 6 (EMF probes, quality, PeeringDB)
    scheduler.add_job(run_monthly_co_additional, CronTrigger(day=2, hour=5, minute=0),
                      id="monthly_co_additional", name="Monthly CO additional intelligence")

    # Quarterly on 15th of Feb/May/Aug/Nov at 06:00 UTC — CO CRC complaints
    scheduler.add_job(run_quarterly_co_complaints, CronTrigger(month="2,5,8,11", day=15, hour=6, minute=0),
                      id="quarterly_co_complaints", name="Quarterly CO CRC complaints")

    # Quarterly on 15th of Mar/Jun/Sep/Dec at 06:00 UTC — CO Centros Digitales
    scheduler.add_job(run_quarterly_co_centros, CronTrigger(month="3,6,9,12", day=15, hour=6, minute=0),
                      id="quarterly_co_centros", name="Quarterly CO Centros Digitales")

    # ── LATAM Expansion cron jobs ──

    # Monthly on 1st at 05:00 UTC — LATAM census refreshes (all 17 countries)
    scheduler.add_job(run_monthly_latam_census, CronTrigger(day=1, hour=5, minute=0),
                      id="monthly_latam_census", name="Monthly LATAM census (17 countries)")

    # Monthly on 2nd at 05:00 UTC — LATAM T1+T2 broadband
    scheduler.add_job(run_monthly_latam_t1t2_broadband, CronTrigger(day=2, hour=5, minute=0),
                      id="monthly_latam_broadband", name="Monthly LATAM T1+T2 broadband")

    # Weekly on Tuesdays at 05:30 UTC — LATAM T1 contracts
    scheduler.add_job(run_weekly_latam_t1_contracts, CronTrigger(day_of_week="tue", hour=5, minute=30),
                      id="weekly_latam_contracts", name="Weekly LATAM T1 contracts")

    # Monthly on 15th at 05:00 UTC — LATAM T1 health/schools/complaints
    scheduler.add_job(run_monthly_latam_t1_social, CronTrigger(day=15, hour=5, minute=0),
                      id="monthly_latam_social", name="Monthly LATAM T1 social")

    # Quarterly on 15th of Jan/Apr/Jul/Oct at 07:00 UTC — LATAM T2+T3 contracts+broadband
    scheduler.add_job(run_quarterly_latam_t2t3, CronTrigger(month="1,4,7,10", day=15, hour=7, minute=0),
                      id="quarterly_latam_t2t3", name="Quarterly LATAM T2+T3")

    # ── Parity expansion cron jobs ──

    # Monthly on 3rd at 05:00 UTC — LATAM NBI/poverty demographics (8 countries)
    scheduler.add_job(run_monthly_latam_nbi, CronTrigger(day=3, hour=5, minute=0),
                      id="monthly_latam_nbi", name="Monthly LATAM NBI/poverty (8 countries)")

    # Monthly on 16th at 05:00 UTC — LATAM T2 social (health, schools for UY, EC, DO, CL, PE)
    scheduler.add_job(run_monthly_latam_t2_social, CronTrigger(day=16, hour=5, minute=0),
                      id="monthly_latam_t2_social", name="Monthly LATAM T2 social (health, schools)")

    # Quarterly on 1st of Feb/May/Aug/Nov at 08:00 UTC — LATAM T3 contracts (PA, CR, GT, BO)
    scheduler.add_job(run_quarterly_latam_t3_contracts, CronTrigger(month="2,5,8,11", day=1, hour=8, minute=0),
                      id="quarterly_latam_t3_contracts", name="Quarterly LATAM T3 contracts")

    # Quarterly on 15th of Feb/May/Aug/Nov at 07:00 UTC — LATAM complaints (AR, PE)
    scheduler.add_job(run_quarterly_latam_complaints, CronTrigger(month="2,5,8,11", day=15, hour=7, minute=0),
                      id="quarterly_latam_complaints", name="Quarterly LATAM complaints (AR, PE)")

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    logger.info("Schedule:")
    logger.info("  Daily 02:00 UTC — Anatel telecom data")
    logger.info("  Daily 02:30 UTC — Intelligence (PNCP, DOU, Querido Diário)")
    logger.info("  Daily 03:00 UTC — INMET weather")
    logger.info("  Weekly Sun 04:00 UTC — Economic (IBGE, ANP, ANEEL, SNIS, BNDES)")
    logger.info("  Weekly Sun 04:30 UTC — Enrichment (CNPJ, RQUAL, FUST)")
    logger.info("  Weekly Tue 05:00 UTC — CO SECOP contracts")
    logger.info("  Weekly Tue 05:30 UTC — LATAM T1 contracts (MX, AR, CL, UY)")
    logger.info("  Weekly Wed 05:00 UTC — Due diligence (sanctions screening)")
    logger.info("  Monthly 1st 05:00 UTC — Geographic + LATAM census (all 19 countries)")
    logger.info("  Monthly 1st 06:00 UTC — Sentinel-2 urban growth")
    logger.info("  Monthly 2nd 05:00 UTC — LATAM T1+T2 broadband + CO additional")
    logger.info("  Monthly 15th 05:00 UTC — LATAM T1 social + due diligence")
    logger.info("  Quarterly 15th 06:00 UTC — CO CRC complaints + CO Centros Digitales")
    logger.info("  Quarterly 15th 07:00 UTC — LATAM T2+T3 contracts+broadband")
    logger.info("  Quarterly 1st 07:00 UTC — PGFN federal tax debts")
    logger.info("  Monthly 3rd 05:00 UTC — LATAM NBI/poverty (8 countries)")
    logger.info("  Monthly 16th 05:00 UTC — LATAM T2 social (health, schools)")
    logger.info("  Quarterly 1st 08:00 UTC — LATAM T3 contracts (PA, CR, GT, BO)")
    logger.info("  Quarterly 15th 07:00 UTC — LATAM complaints (AR, PE)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
