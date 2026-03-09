"""Run all data pipelines in dependency order.

IBGE Census runs first because it populates admin_level_1 (states) and
admin_level_2 (municipalities) that all other pipelines reference.
Anatel Providers runs second so broadband can map CNPJs to provider IDs.
"""
import logging
import os
import sys

# Ensure project root is on PYTHONPATH
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

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
    SRTMTerrainPipeline,
)


def run_all():
    """Execute all pipelines in dependency order."""
    pipelines = [
        # Phase 1: Geographic foundation (MUST run first)
        IBGECensusPipeline(),           # States + municipalities (all other pipelines depend on this)
        # Phase 2: Provider registry (broadband depends on this)
        AnatelProvidersPipeline(),
        # Phase 3: Core telecom data
        AnatelBroadbandPipeline(),      # Highest priority — subscriber data
        AnatelBaseStationsPipeline(),
        AnatelQualityPipeline(),
        # Phase 4: Economic & demographic
        IBGEPIBPipeline(),
        IBGEProjectionsPipeline(),
        IBGEPOFPipeline(),               # Household expenditure (POF 2017-2018)
        ANPFuelPipeline(),               # Fuel sales as economic activity proxy
        # Phase 5: Infrastructure & environment
        ANEELPowerPipeline(),
        INMETWeatherPipeline(),
        OSMRoadsPipeline(),
        SNISSanitationPipeline(),        # Sanitation infrastructure
        # Phase 6: Large file downloads (slowest)
        SRTMTerrainPipeline(),
        MapBiomasLandCoverPipeline(),
    ]

    results = {}
    passed = 0
    failed = 0

    for pipeline in pipelines:
        try:
            result = pipeline.run(force=True)
            results[pipeline.name] = result
            status = result.get("status", "unknown")
            rows = result.get("rows_inserted", 0) + result.get("rows_updated", 0)
            print(f"  OK  {pipeline.name}: {status} ({rows} rows)")
            passed += 1
        except Exception as e:
            results[pipeline.name] = {"status": "failed", "error": str(e)}
            print(f"FAIL  {pipeline.name}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed out of {len(pipelines)} pipelines")
    return results


if __name__ == "__main__":
    run_all()
