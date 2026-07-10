"""
UK Topology Router — FTTH topology generation for UK postcodes.

Exposes the Rust pulso-uk-schematic engine via endpoints:
  /generate         → full topology JSON
  /branches         → branch list with nodes
  /optical-budget   → per-node optical budget
  /bom              → BOM + cost breakdown
  /schematic.svg    → SVG schematic diagram
  /compare          → generated vs CF reference comparison
  /recalculate      → re-run optical budget after node move
  /export/geojson   → GeoJSON FeatureCollection
  /export/kml       → KML for Google Earth
  /export/bom.xlsx  → Excel BOM workbook
  /export/pdf       → PDF schematic report
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from python.api.auth.dependencies import require_auth
from python.api.services.uk_topology_service import (
    compare_with_reference,
    export_bom_xlsx,
    export_geojson,
    export_kml,
    export_schematic_pdf,
    get_topology,
    recalculate_topology,
    render_svg_schematic,
)

router = APIRouter(prefix="/api/v1/uk/topology", tags=["uk-topology"])


@router.get("/generate")
async def generate_topology(
    postcode: str = Query(..., description="UK postcode (e.g. NW9)"),
    user: dict = Depends(require_auth),
):
    """Generate full FTTH topology for a postcode."""
    return await get_topology(postcode)


@router.get("/branches")
async def get_branches(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Return branch list with nodes."""
    topo = await get_topology(postcode)
    return topo.get("branches", [])


@router.get("/optical-budget")
async def get_optical_budget(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Return per-node optical budget data."""
    topo = await get_topology(postcode)
    results = []
    for branch in topo.get("branches", []):
        for node in branch.get("nodes", []):
            ob = node.get("optical_budget", {})
            results.append({
                "building": node.get("building"),
                "branch": branch.get("name"),
                "total_loss_db": ob.get("total_loss_db"),
                "rx_power_dbm": ob.get("rx_power_dbm"),
                "margin_db": ob.get("margin_db"),
                "pass": ob.get("pass"),
            })
    return {
        "postcode": topo.get("postcode"),
        "nodes": results,
        "all_pass": all(n.get("pass", False) for n in results),
    }


@router.get("/bom")
async def get_bom(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Return BOM and cost breakdown."""
    topo = await get_topology(postcode)
    return {
        "postcode": topo.get("postcode"),
        "premises": topo.get("premises"),
        "buildings": topo.get("buildings"),
        "bom": topo.get("bom", {}),
        "cost": topo.get("cost", {}),
    }


@router.get("/schematic.svg")
async def get_schematic_svg(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Return SVG schematic of the topology."""
    topo = await get_topology(postcode)
    svg = render_svg_schematic(topo)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/compare")
async def compare_topology(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Compare generated topology against CF Project 4610 reference."""
    topo = await get_topology(postcode)
    return compare_with_reference(topo)


# ---------------------------------------------------------------------------
# Interactive editor — recalculate after node move
# ---------------------------------------------------------------------------


class RecalculateRequest(BaseModel):
    postcode: str
    node_id: str
    new_lat: float
    new_lon: float


@router.post("/recalculate")
async def recalculate(
    body: RecalculateRequest,
    user: dict = Depends(require_auth),
):
    """Recalculate distances and optical budgets after moving a node."""
    topo = await get_topology(body.postcode)
    return recalculate_topology(topo, body.node_id, body.new_lat, body.new_lon)


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.get("/export/geojson")
async def export_geojson_endpoint(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Export topology as GeoJSON FeatureCollection."""
    topo = await get_topology(postcode)
    return export_geojson(topo)


@router.get("/export/kml")
async def export_kml_endpoint(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Export topology as KML for Google Earth."""
    topo = await get_topology(postcode)
    kml = export_kml(topo)
    return Response(
        content=kml,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="topology_{postcode.replace(" ", "")}.kml"'},
    )


@router.get("/export/bom.xlsx")
async def export_bom_xlsx_endpoint(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Export BOM, cost, and optical budget as Excel workbook."""
    topo = await get_topology(postcode)
    xlsx_bytes = export_bom_xlsx(topo)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="bom_{postcode.replace(" ", "")}.xlsx"'},
    )


@router.get("/export/pdf")
async def export_pdf_endpoint(
    postcode: str = Query(..., description="UK postcode"),
    user: dict = Depends(require_auth),
):
    """Export PDF schematic report."""
    topo = await get_topology(postcode)
    pdf_bytes = export_schematic_pdf(topo)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="topology_{postcode.replace(" ", "")}.pdf"'},
    )
