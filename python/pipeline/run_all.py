"""Run all data pipelines in sequence."""
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
    AnatelBaseStationsPipeline,
    AnatelBroadbandPipeline,
    AnatelProvidersPipeline,
    AnatelQualityPipeline,
    IBGECensusPipeline,
    IBGEPIBPipeline,
    IBGEProjectionsPipeline,
    INMETWeatherPipeline,
    MapBiomasLandCoverPipeline,
    OSMRoadsPipeline,
    SRTMTerrainPipeline,
)


def run_all():
    """Execute all pipelines in dependency order."""
    pipelines = [
        AnatelProvidersPipeline(),
        AnatelBroadbandPipeline(),
        AnatelBaseStationsPipeline(),
        AnatelQualityPipeline(),
        IBGECensusPipeline(),
        IBGEPIBPipeline(),
        IBGEProjectionsPipeline(),
        SRTMTerrainPipeline(),
        MapBiomasLandCoverPipeline(),
        OSMRoadsPipeline(),
        ANEELPowerPipeline(),
        INMETWeatherPipeline(),
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
