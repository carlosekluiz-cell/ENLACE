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
)


def _run_pipeline(pipeline_cls):
    """Run a single pipeline, catching all errors."""
    name = pipeline_cls.__name__
    try:
        p = pipeline_cls()
        result = p.run(force=False)
        logger.info(f"{name}: {result.get('status', 'unknown')}")
    except Exception as e:
        logger.error(f"{name}: FAILED — {e}")


# Schedule groups
def run_daily_telecom():
    """Daily: Anatel data (providers, broadband, base stations, quality)."""
    logger.info("=== Daily telecom pipelines ===")
    for cls in [AnatelProvidersPipeline, AnatelBroadbandPipeline,
                AnatelBaseStationsPipeline, AnatelQualityPipeline]:
        _run_pipeline(cls)


def run_daily_weather():
    """Daily: Weather observations."""
    logger.info("=== Daily weather pipeline ===")
    _run_pipeline(INMETWeatherPipeline)


def run_weekly_economic():
    """Weekly: IBGE economic data, POF, ANP fuel, ANEEL power."""
    logger.info("=== Weekly economic pipelines ===")
    for cls in [IBGEPIBPipeline, IBGEProjectionsPipeline, IBGEPOFPipeline,
                ANPFuelPipeline, ANEELPowerPipeline, SNISSanitationPipeline]:
        _run_pipeline(cls)


def run_monthly_geographic():
    """Monthly: Census, SRTM terrain, MapBiomas, OSM roads."""
    logger.info("=== Monthly geographic pipelines ===")
    for cls in [IBGECensusPipeline, SRTMTerrainPipeline,
                MapBiomasLandCoverPipeline, OSMRoadsPipeline]:
        _run_pipeline(cls)


def run_monthly_sentinel():
    """Monthly: Sentinel-2 urban growth indices and composites."""
    logger.info("=== Monthly sentinel pipeline ===")
    _run_pipeline(SentinelGrowthPipeline)


def run_all():
    """Run all pipeline groups."""
    run_daily_telecom()
    run_daily_weather()
    run_weekly_economic()
    run_monthly_geographic()
    run_monthly_sentinel()


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

    # Daily at 03:00 UTC — weather
    scheduler.add_job(run_daily_weather, CronTrigger(hour=3, minute=0),
                      id="daily_weather", name="Daily INMET weather")

    # Weekly on Sundays at 04:00 UTC — economic
    scheduler.add_job(run_weekly_economic, CronTrigger(day_of_week="sun", hour=4, minute=0),
                      id="weekly_economic", name="Weekly economic pipelines")

    # Monthly on 1st at 05:00 UTC — geographic
    scheduler.add_job(run_monthly_geographic, CronTrigger(day=1, hour=5, minute=0),
                      id="monthly_geographic", name="Monthly geographic pipelines")

    # Monthly on 1st at 06:00 UTC — Sentinel-2 urban growth
    scheduler.add_job(run_monthly_sentinel, CronTrigger(day=1, hour=6, minute=0),
                      id="monthly_sentinel", name="Monthly Sentinel-2 urban growth")

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    logger.info("Schedule:")
    logger.info("  Daily 02:00 UTC — Anatel telecom data")
    logger.info("  Daily 03:00 UTC — INMET weather")
    logger.info("  Weekly Sun 04:00 UTC — Economic (IBGE, ANP, ANEEL, SNIS)")
    logger.info("  Monthly 1st 05:00 UTC — Geographic (Census, SRTM, MapBiomas, OSM)")
    logger.info("  Monthly 1st 06:00 UTC — Sentinel-2 urban growth")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
