"""
UK Topology Service — Subprocess wrapper for the Rust pulso-uk-schematic
binary, SVG schematic renderer, CF comparison helper, and export generators
(GeoJSON, KML, XLSX, PDF).
"""

import asyncio
import io
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUST_BINARY = os.getenv(
    "PULSO_UK_SCHEMATIC_BIN",
    str(Path(__file__).resolve().parents[3] / "rust" / "target" / "release" / "pulso-uk-schematic"),
)

CSV_DATA_PATH = os.getenv(
    "PULSO_UK_CSV_PATH",
    str(Path(__file__).resolve().parents[3] / "data" / "grahame_park_epc.csv"),
)

DEMO_POSTCODES = {"NW9 5U", "NW9 5R", "NW9 5T", "NW9"}

# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


async def generate_topology(postcode: str, use_v2: bool = True) -> dict:
    """
    Call the Rust binary and parse the JSON schematic from stdout.
    The binary prints "JSON SCHEMATIC:" followed by the JSON block.
    """
    cmd = [RUST_BINARY, CSV_DATA_PATH, postcode]
    if use_v2:
        cmd.append("--v2")

    logger.info("Running: %s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except FileNotFoundError:
        raise HTTPException(
            503,
            f"Rust binary not found at {RUST_BINARY}. Build with: cargo build --release -p pulso-uk-schematic",
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Topology generation timed out")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        logger.error("pulso-uk-schematic failed (rc=%d): %s", proc.returncode, err)
        raise HTTPException(500, f"Topology engine error: {err[:500]}")

    output = stdout.decode(errors="replace")

    # Parse JSON between markers
    marker = "JSON SCHEMATIC:"
    idx = output.find(marker)
    if idx == -1:
        # Try parsing entire stdout as JSON (fallback)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            raise HTTPException(500, "No JSON output from topology engine")

    json_str = output[idx + len(marker):].strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON: %s", exc)
        raise HTTPException(500, "Invalid JSON from topology engine")


async def get_topology(postcode: str) -> dict:
    """
    Public entry point — validates postcode is in demo coverage.
    """
    normalized = postcode.strip().upper()
    if normalized not in DEMO_POSTCODES:
        raise HTTPException(404, f"Postcode '{postcode}' not in demo coverage. Try: NW9")
    return await generate_topology(normalized, use_v2=True)


# ---------------------------------------------------------------------------
# SVG schematic renderer
# ---------------------------------------------------------------------------

# Colour palette
_CLR_SPLITTER_32 = "#22c55e"  # green
_CLR_SPLITTER_64 = "#3b82f6"  # blue
_CLR_PBO = "#f97316"          # orange
_CLR_NONE = "#9ca3af"         # grey
_CLR_AUX = "#ef4444"          # red
_CLR_CABLE = "#6b7280"        # dark grey


def _node_colour(splitter: str) -> str:
    if "32" in splitter:
        return _CLR_SPLITTER_32
    if "64" in splitter:
        return _CLR_SPLITTER_64
    if splitter.upper() == "PBO":
        return _CLR_PBO
    return _CLR_NONE


def render_svg_schematic(topology: dict) -> str:
    """
    Generate an SVG showing the topology tree:
    - AUX node at top
    - Branches as vertical chains
    - Nodes with building name, splitter type, dwelling count
    - Cable segments with fibre count labels
    """
    branches = topology.get("branches", [])
    if not branches:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50"><text x="10" y="30" font-size="14">No branches</text></svg>'

    col_width = 220
    row_height = 80
    top_margin = 60
    left_margin = 40

    max_nodes = max((len(b.get("nodes", [])) for b in branches), default=0)
    total_width = left_margin + col_width * len(branches) + 40
    total_height = top_margin + row_height * (max_nodes + 1) + 40

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" '
        f'style="background:#1a1a2e; font-family:Inter,system-ui,sans-serif;">'
    )

    # Styles
    lines.append('<defs><style>')
    lines.append('.node-rect { rx: 6; ry: 6; stroke-width: 1.5; }')
    lines.append('.label { fill: #e2e8f0; font-size: 11px; }')
    lines.append('.sub-label { fill: #94a3b8; font-size: 9px; }')
    lines.append('.cable-line { stroke-width: 2; stroke-dasharray: 4 2; }')
    lines.append('.cable-label { fill: #94a3b8; font-size: 8px; }')
    lines.append('</style></defs>')

    # AUX node at top center
    aux_x = total_width / 2
    aux_y = 30
    lines.append(
        f'<rect x="{aux_x - 40}" y="{aux_y - 15}" width="80" height="30" '
        f'fill="{_CLR_AUX}" class="node-rect" stroke="{_CLR_AUX}" opacity="0.9"/>'
    )
    lines.append(
        f'<text x="{aux_x}" y="{aux_y + 5}" text-anchor="middle" class="label" '
        f'fill="white" font-weight="bold">AUX-1</text>'
    )

    postcode = topology.get("postcode", "")
    lines.append(
        f'<text x="{aux_x}" y="{aux_y + 18}" text-anchor="middle" class="sub-label">{postcode}</text>'
    )

    for bi, branch in enumerate(branches):
        cx = left_margin + bi * col_width + col_width / 2
        nodes = branch.get("nodes", [])
        branch_name = branch.get("name", f"Branch {bi + 1}")

        # Line from AUX to first node
        first_y = top_margin + row_height
        lines.append(
            f'<line x1="{aux_x}" y1="{aux_y + 15}" x2="{cx}" y2="{first_y - 20}" '
            f'stroke="{_CLR_CABLE}" class="cable-line"/>'
        )

        # Branch label
        lines.append(
            f'<text x="{cx}" y="{top_margin + 20}" text-anchor="middle" '
            f'class="sub-label" font-weight="bold">{branch_name}</text>'
        )

        for ni, node in enumerate(nodes):
            ny = top_margin + row_height * (ni + 1)
            building = node.get("building", "?")
            splitter = node.get("splitter", "none")
            dwellings = node.get("dwelling_count", 0)
            cable = node.get("cable_type", "")
            dist = node.get("distance_from_previous_m", 0)
            colour = _node_colour(splitter)

            # Cable line to previous node
            if ni > 0:
                prev_y = top_margin + row_height * ni
                lines.append(
                    f'<line x1="{cx}" y1="{prev_y + 20}" x2="{cx}" y2="{ny - 20}" '
                    f'stroke="{_CLR_CABLE}" class="cable-line"/>'
                )
                mid_y = (prev_y + 20 + ny - 20) / 2
                lines.append(
                    f'<text x="{cx + 15}" y="{mid_y}" class="cable-label">'
                    f'{cable} {dist:.0f}m</text>'
                )

            # Node rectangle
            rect_w = 180
            rect_h = 44
            lines.append(
                f'<rect x="{cx - rect_w / 2}" y="{ny - rect_h / 2}" '
                f'width="{rect_w}" height="{rect_h}" '
                f'fill="#1e293b" stroke="{colour}" class="node-rect"/>'
            )

            # Building name
            lines.append(
                f'<text x="{cx}" y="{ny - 4}" text-anchor="middle" '
                f'class="label" font-weight="bold">{building}</text>'
            )

            # Splitter + dwellings
            lines.append(
                f'<text x="{cx}" y="{ny + 12}" text-anchor="middle" class="sub-label">'
                f'{splitter} | {dwellings} units</text>'
            )

    # Legend
    legend_y = total_height - 20
    items = [
        (_CLR_SPLITTER_32, "32-way"),
        (_CLR_SPLITTER_64, "64-way"),
        (_CLR_PBO, "PBO"),
        (_CLR_AUX, "AUX"),
    ]
    lx = 20
    for colour, label in items:
        lines.append(f'<rect x="{lx}" y="{legend_y - 8}" width="12" height="12" fill="{colour}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{legend_y + 2}" class="sub-label">{label}</text>')
        lx += 80

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CF comparison
# ---------------------------------------------------------------------------

# Real Community Fibre Project 4610 reference
CF_REFERENCE = {
    "buildings": [
        {"name": "Napier", "splitter": "64-way", "dwellings": 42, "joint_id": "J2100"},
        {"name": "Norris", "splitter": "64-way", "dwellings": 47, "joint_id": "J2101"},
        {"name": "Orde", "splitter": "32-way", "dwellings": 18, "joint_id": "J2102"},
        {"name": "Roe", "splitter": "32-way", "dwellings": 19, "joint_id": "J2103"},
        {"name": "Slatter", "splitter": "32-way", "dwellings": 22, "joint_id": "J2104"},
        {"name": "Tedder", "splitter": "64-way", "dwellings": 46, "joint_id": "J2105"},
        {"name": "Sassoon", "splitter": "64-way", "dwellings": 16, "joint_id": "J2106"},
        {"name": "Saimet", "splitter": "PBO", "dwellings": 18, "feeder": "Sassoon"},
        {"name": "Sopwith", "splitter": "64-way", "dwellings": 16, "joint_id": "J2108"},
        {"name": "Spitfire", "splitter": "PBO", "dwellings": 18, "feeder": "Sopwith"},
        {"name": "Rapide", "splitter": "32-way", "dwellings": 24, "joint_id": "J2110"},
        {"name": "Ratier", "splitter": "32-way", "dwellings": 24, "joint_id": "J2111"},
        {"name": "Wilshire", "splitter": "32-way", "dwellings": 20, "joint_id": "J2112"},
        {"name": "Whittle", "splitter": "PBO", "dwellings": 24, "feeder": "Tedder"},
        {"name": "Wheeler", "splitter": "32-way", "dwellings": 24, "joint_id": "J2114"},
    ],
    "cables": [
        {"id": "FC2100", "from": "AUX", "to": "Napier", "length_m": 189, "spec": "144F"},
        {"id": "FC2101", "from": "Napier", "to": "Norris", "length_m": 78, "spec": "144F"},
        {"id": "FC2102", "from": "Norris", "to": "Orde", "length_m": 65, "spec": "48F"},
        {"id": "FC2103", "from": "Orde", "to": "Roe", "length_m": 42, "spec": "24F"},
        {"id": "FC2104", "from": "Roe", "to": "Slatter", "length_m": 53, "spec": "24F"},
        {"id": "FC2105", "from": "AUX", "to": "Tedder", "length_m": 210, "spec": "144F"},
        {"id": "FC2106", "from": "Tedder", "to": "Sassoon", "length_m": 92, "spec": "48F"},
        {"id": "FC2107", "from": "Sassoon", "to": "Saimet", "length_m": 34, "spec": "12F"},
        {"id": "FC2108", "from": "Tedder", "to": "Sopwith", "length_m": 85, "spec": "48F"},
        {"id": "FC2109", "from": "Sopwith", "to": "Spitfire", "length_m": 38, "spec": "12F"},
        {"id": "FC2110", "from": "Tedder", "to": "Whittle", "length_m": 110, "spec": "12F"},
        {"id": "FC2111", "from": "AUX", "to": "Wheeler", "length_m": 175, "spec": "144F"},
        {"id": "FC2112", "from": "Wheeler", "to": "Rapide", "length_m": 68, "spec": "48F"},
        {"id": "FC2113", "from": "Rapide", "to": "Ratier", "length_m": 55, "spec": "24F"},
        {"id": "FC2114", "from": "Ratier", "to": "Wilshire", "length_m": 47, "spec": "24F"},
        {"id": "FC2115", "from": "Norris", "to": "Slatter", "length_m": 60, "spec": "48F"},
    ],
    "branches": ["Wheeler Chain", "Slatter Chain", "Norris Chain"],
}


def compare_with_reference(generated: dict) -> dict:
    """
    Compare generated topology against CF Project 4610 reference.
    Returns per-building match details and overall score.
    """
    all_nodes = []
    for branch in generated.get("branches", []):
        for node in branch.get("nodes", []):
            all_nodes.append(node)

    building_results = []
    matches = 0
    total = len(CF_REFERENCE["buildings"])

    for ref in CF_REFERENCE["buildings"]:
        ref_name = ref["name"]
        gen_node = next(
            (n for n in all_nodes if n.get("building", "").lower() == ref_name.lower()),
            None,
        )
        gen_splitter = gen_node.get("splitter", "NOT FOUND") if gen_node else "NOT FOUND"
        is_match = gen_splitter.lower() == ref["splitter"].lower()
        if is_match:
            matches += 1

        building_results.append({
            "name": ref_name,
            "generated_splitter": gen_splitter,
            "reference_splitter": ref["splitter"],
            "match": is_match,
        })

    # PBO detection
    pbo_targets = ["Saimet", "Spitfire", "Whittle"]
    pbo_found = sum(
        1 for name in pbo_targets
        if any(
            n.get("building", "").lower() == name.lower()
            and n.get("splitter", "").upper() == "PBO"
            for n in all_nodes
        )
    )

    return {
        "buildings": building_results,
        "overall_match_pct": round(matches / total * 100, 1) if total else 0,
        "pbo_detection": {
            "found": pbo_found,
            "expected": len(pbo_targets),
        },
        "reference_source": "CF Project 4610 — Grahame Park",
    }


# ---------------------------------------------------------------------------
# Optical budget recalculation (for interactive editor)
# ---------------------------------------------------------------------------

_FIBRE_ATTENUATION_DB_KM = 0.35
_SPLICE_LOSS_DB = 0.1
_CONNECTOR_LOSS_DB = 0.5
_CONNECTOR_PAIRS = 3
_BUILDING_ENTRY_LOSS_DB = 2.0
_SYSTEM_MARGIN_DB = 3.0
_OLT_TX_DBM = 5.0
_ONT_SENSITIVITY_DBM = -28.0

_SPLITTER_LOSS = {"32-way": 17.0, "64-way": 20.0, "PBO": 17.0, "none": 0.0}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def recalculate_topology(topology: dict, node_id: str, new_lat: float, new_lon: float) -> dict:
    """Recalculate distances and optical budgets after moving a node."""
    topo = json.loads(json.dumps(topology))  # deep copy
    aux = topo.get("aux_joint", {})
    aux_lat = aux.get("lat", 0)
    aux_lon = aux.get("lon", 0)

    for branch in topo.get("branches", []):
        prev_lat, prev_lon = aux_lat, aux_lon
        cum_dist = 0.0
        splice_count = 0
        for node in branch.get("nodes", []):
            if node.get("building", "") == node_id:
                node["lat"] = new_lat
                node["lon"] = new_lon

            d = _haversine(prev_lat, prev_lon, node["lat"], node["lon"])
            node["distance_from_previous_m"] = round(d, 1)
            cum_dist += d
            node["distance_from_aux_m"] = round(cum_dist, 1)
            splice_count += 1

            # Recalculate optical budget
            fibre_loss = (cum_dist / 1000) * _FIBRE_ATTENUATION_DB_KM
            splice_loss = splice_count * _SPLICE_LOSS_DB
            connector_loss = _CONNECTOR_PAIRS * _CONNECTOR_LOSS_DB
            splitter = node.get("splitter", "none")
            splitter_loss = _SPLITTER_LOSS.get(splitter, 0.0)
            total_loss = fibre_loss + splice_loss + connector_loss + splitter_loss + _BUILDING_ENTRY_LOSS_DB + _SYSTEM_MARGIN_DB
            rx_power = _OLT_TX_DBM - total_loss
            margin = rx_power - _ONT_SENSITIVITY_DBM
            node["optical_budget"] = {
                "total_loss_db": round(total_loss, 3),
                "rx_power_dbm": round(rx_power, 3),
                "margin_db": round(margin, 3),
                "pass": margin >= 0,
            }

            prev_lat, prev_lon = node["lat"], node["lon"]

    return topo


# ---------------------------------------------------------------------------
# Export: GeoJSON
# ---------------------------------------------------------------------------

def export_geojson(topology: dict) -> dict:
    """Convert topology to GeoJSON FeatureCollection."""
    features = []
    aux = topology.get("aux_joint", {})

    # AUX point
    if aux:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [aux["lon"], aux["lat"]]},
            "properties": {"type": "AUX_JOINT", "id": "AUX-1"},
        })

    for branch in topology.get("branches", []):
        prev_lon = aux.get("lon", 0)
        prev_lat = aux.get("lat", 0)
        prev_name = "AUX"

        for node in branch.get("nodes", []):
            # Splitter point
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [node["lon"], node["lat"]]},
                "properties": {
                    "type": "SPLITTER",
                    "building": node.get("building"),
                    "splitter_type": node.get("splitter"),
                    "dwelling_count": node.get("dwelling_count"),
                    "cable_type": node.get("cable_type"),
                    "rx_power_dbm": node.get("optical_budget", {}).get("rx_power_dbm"),
                    "margin_db": node.get("optical_budget", {}).get("margin_db"),
                    "branch": branch.get("name"),
                },
            })

            # Cable line
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[prev_lon, prev_lat], [node["lon"], node["lat"]]],
                },
                "properties": {
                    "type": "CABLE",
                    "cable_type": node.get("cable_type"),
                    "length_m": node.get("distance_from_previous_m"),
                    "from": prev_name,
                    "to": node.get("building"),
                    "branch": branch.get("name"),
                },
            })

            prev_lon, prev_lat = node["lon"], node["lat"]
            prev_name = node.get("building", "?")

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Export: KML
# ---------------------------------------------------------------------------

_KML_CABLE_COLORS = {
    "12F": "ff50af4c",   # green (AABBGGRR)
    "24F": "ff07c1ff",   # amber
    "48F": "ff356bff",   # orange
    "144F": "ff4343f4",  # red
}


def export_kml(topology: dict) -> str:
    """Generate KML document for Google Earth."""
    postcode = topology.get("postcode", "Unknown")
    aux = topology.get("aux_joint", {})
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"<name>PULSO UK Topology — {postcode}</name>",
        "<description>FTTH network topology generated by PULSO</description>",
        # Styles
        '<Style id="aux"><IconStyle><color>ff00d4ff</color><scale>1.5</scale>'
        '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/star.png</href></Icon>'
        "</IconStyle></Style>",
        '<Style id="splitter-32"><IconStyle><color>ff5ec422</color><scale>1.2</scale>'
        '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>'
        "</IconStyle></Style>",
        '<Style id="splitter-64"><IconStyle><color>fff68233</color><scale>1.2</scale>'
        '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>'
        "</IconStyle></Style>",
        '<Style id="pbo"><IconStyle><color>ff1673f9</color><scale>1.0</scale>'
        '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>'
        "</IconStyle></Style>",
    ]

    # Cable styles
    for cable, color in _KML_CABLE_COLORS.items():
        w = {"12F": 2, "24F": 3, "48F": 4, "144F": 5}.get(cable, 2)
        lines.append(
            f'<Style id="cable-{cable}"><LineStyle><color>{color}</color>'
            f"<width>{w}</width></LineStyle></Style>"
        )

    # AUX placemark
    if aux:
        lines.append(
            f"<Placemark><name>AUX-1</name><styleUrl>#aux</styleUrl>"
            f"<Point><coordinates>{aux['lon']},{aux['lat']},0</coordinates></Point></Placemark>"
        )

    for branch in topology.get("branches", []):
        lines.append(f"<Folder><name>{branch.get('name', 'Branch')}</name>")
        prev_lon = aux.get("lon", 0)
        prev_lat = aux.get("lat", 0)

        for node in branch.get("nodes", []):
            spl = node.get("splitter", "none")
            style = "splitter-32" if "32" in spl else ("splitter-64" if "64" in spl else ("pbo" if spl.upper() == "PBO" else "aux"))
            building = node.get("building", "?")
            dw = node.get("dwelling_count", 0)
            lines.append(
                f"<Placemark><name>{building}</name>"
                f"<description>{spl}, {dw} dwellings</description>"
                f"<styleUrl>#{style}</styleUrl>"
                f"<Point><coordinates>{node['lon']},{node['lat']},0</coordinates></Point></Placemark>"
            )

            # Cable line
            cable = node.get("cable_type", "12F")
            cable_style = f"cable-{cable}" if cable in _KML_CABLE_COLORS else "cable-12F"
            lines.append(
                f"<Placemark><name>{cable} cable</name>"
                f"<styleUrl>#{cable_style}</styleUrl>"
                f"<LineString><coordinates>"
                f"{prev_lon},{prev_lat},0 {node['lon']},{node['lat']},0"
                f"</coordinates></LineString></Placemark>"
            )
            prev_lon, prev_lat = node["lon"], node["lat"]

        lines.append("</Folder>")

    lines.extend(["</Document>", "</kml>"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export: XLSX BOM
# ---------------------------------------------------------------------------

def export_bom_xlsx(topology: dict) -> bytes:
    """Generate Excel workbook with BOM, cost, and optical budget sheets."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1e40af", end_color="1e40af", fill_type="solid")

    def add_header(ws, headers):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

    # Sheet 1: Cable Schedule
    ws1 = wb.active
    ws1.title = "Cable Schedule"
    add_header(ws1, ["Segment", "From", "To", "Cable Type", "Length (m)", "Branch"])
    row = 2
    aux = topology.get("aux_joint", {})
    for branch in topology.get("branches", []):
        prev_name = "AUX"
        for i, node in enumerate(branch.get("nodes", [])):
            ws1.cell(row=row, column=1, value=f"FC{row - 1:04d}")
            ws1.cell(row=row, column=2, value=prev_name)
            ws1.cell(row=row, column=3, value=node.get("building", "?"))
            ws1.cell(row=row, column=4, value=node.get("cable_type", ""))
            ws1.cell(row=row, column=5, value=round(node.get("distance_from_previous_m", 0), 1))
            ws1.cell(row=row, column=6, value=branch.get("name", ""))
            prev_name = node.get("building", "?")
            row += 1

    for col in range(1, 7):
        ws1.column_dimensions[chr(64 + col)].width = 18

    # Sheet 2: Equipment Schedule
    ws2 = wb.create_sheet("Equipment")
    add_header(ws2, ["Location", "Type", "Quantity", "Unit Cost (£)", "Total (£)"])
    row = 2
    for branch in topology.get("branches", []):
        for node in branch.get("nodes", []):
            spl = node.get("splitter", "none")
            if spl == "none":
                continue
            cost = {"32-way": 85, "64-way": 120, "PBO": 45}.get(spl, 0)
            ws2.cell(row=row, column=1, value=node.get("building", ""))
            ws2.cell(row=row, column=2, value=f"Splitter {spl}")
            ws2.cell(row=row, column=3, value=1)
            ws2.cell(row=row, column=4, value=cost)
            ws2.cell(row=row, column=5, value=cost)
            row += 1

    # ONTs
    premises = topology.get("premises", 0)
    ws2.cell(row=row, column=1, value="All premises")
    ws2.cell(row=row, column=2, value="ONT")
    ws2.cell(row=row, column=3, value=premises)
    ws2.cell(row=row, column=4, value=45)
    ws2.cell(row=row, column=5, value=premises * 45)
    for col in range(1, 6):
        ws2.column_dimensions[chr(64 + col)].width = 18

    # Sheet 3: Cost Summary
    ws3 = wb.create_sheet("Cost Summary")
    add_header(ws3, ["Category", "Amount (£)"])
    cost_data = topology.get("cost", {})
    cost_rows = [
        ("Total CAPEX", cost_data.get("total_capex_gbp", 0)),
        ("CAPEX per premises", cost_data.get("capex_per_premises_gbp", 0)),
        ("Annual PIA rental", cost_data.get("annual_pia_rental_gbp", 0)),
    ]
    for i, (cat, val) in enumerate(cost_rows, 2):
        ws3.cell(row=i, column=1, value=cat)
        ws3.cell(row=i, column=2, value=round(val, 2))
    ws3.column_dimensions["A"].width = 25
    ws3.column_dimensions["B"].width = 18

    # Sheet 4: Optical Budget
    ws4 = wb.create_sheet("Optical Budget")
    add_header(ws4, ["Building", "Branch", "Splitter", "Distance (m)", "Loss (dB)", "Rx (dBm)", "Margin (dB)", "Pass"])
    row = 2
    pass_fill = PatternFill(start_color="dcfce7", end_color="dcfce7", fill_type="solid")
    fail_fill = PatternFill(start_color="fecaca", end_color="fecaca", fill_type="solid")
    for branch in topology.get("branches", []):
        for node in branch.get("nodes", []):
            ob = node.get("optical_budget", {})
            ws4.cell(row=row, column=1, value=node.get("building", ""))
            ws4.cell(row=row, column=2, value=branch.get("name", ""))
            ws4.cell(row=row, column=3, value=node.get("splitter", ""))
            ws4.cell(row=row, column=4, value=round(node.get("distance_from_aux_m", 0), 1))
            ws4.cell(row=row, column=5, value=round(ob.get("total_loss_db", 0), 2))
            ws4.cell(row=row, column=6, value=round(ob.get("rx_power_dbm", 0), 2))
            ws4.cell(row=row, column=7, value=round(ob.get("margin_db", 0), 2))
            pass_cell = ws4.cell(row=row, column=8, value="PASS" if ob.get("pass") else "FAIL")
            pass_cell.fill = pass_fill if ob.get("pass") else fail_fill
            row += 1
    for col in range(1, 9):
        ws4.column_dimensions[chr(64 + col)].width = 16

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Export: PDF schematic
# ---------------------------------------------------------------------------

def export_schematic_pdf(topology: dict) -> bytes:
    """Generate PDF report with cover, BOM, optical budget, and cost."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=22, spaceAfter=10)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, spaceBefore=16, spaceAfter=8)
    body_style = styles["BodyText"]

    story = []
    postcode = topology.get("postcode", "Unknown")
    premises = topology.get("premises", 0)
    buildings = topology.get("buildings", 0)

    # Page 1: Cover
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph("PULSO UK", title_style))
    story.append(Paragraph("FTTH Network Topology Report", styles["Heading2"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"<b>Postcode:</b> {postcode}", body_style))
    story.append(Paragraph(f"<b>Premises:</b> {premises}", body_style))
    story.append(Paragraph(f"<b>Buildings:</b> {buildings}", body_style))
    story.append(Paragraph(f"<b>Branches:</b> {len(topology.get('branches', []))}", body_style))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", body_style))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("Generated by PULSO — AI-Powered Telecom Design Platform", body_style))

    # Page 2: BOM
    story.append(Paragraph("Bill of Materials", h2_style))
    bom = topology.get("bom", {})
    bom_data = [
        ["Item", "Quantity"],
        ["32-way splitters", str(bom.get("splitter_32way", 0))],
        ["64-way splitters", str(bom.get("splitter_64way", 0))],
        ["PBO boxes", str(bom.get("pbo_count", 0))],
        ["Splice closures", str(bom.get("splice_closures", 0))],
        ["Cable segments", str(bom.get("cable_segments", 0))],
        ["12F cable", f"{bom.get('cable_12f_m', 0):.0f}m"],
        ["24F cable", f"{bom.get('cable_24f_m', 0):.0f}m"],
        ["48F cable", f"{bom.get('cable_48f_m', 0):.0f}m"],
        ["144F cable", f"{bom.get('cable_144f_m', 0):.0f}m"],
        ["Total cable", f"{bom.get('total_cable_m', 0):.0f}m"],
    ]
    t = Table(bom_data, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(t)

    # Page 3: Optical Budget
    story.append(Paragraph("Optical Budget — Per Building", h2_style))
    ob_data = [["Building", "Branch", "Splitter", "Dist (m)", "Rx (dBm)", "Margin (dB)", "Status"]]
    for branch in topology.get("branches", []):
        for node in branch.get("nodes", []):
            ob = node.get("optical_budget", {})
            ob_data.append([
                node.get("building", ""),
                branch.get("name", ""),
                node.get("splitter", ""),
                f"{node.get('distance_from_aux_m', 0):.0f}",
                f"{ob.get('rx_power_dbm', 0):.1f}",
                f"{ob.get('margin_db', 0):.1f}",
                "PASS" if ob.get("pass") else "FAIL",
            ])
    t2 = Table(ob_data, colWidths=[25 * mm, 30 * mm, 18 * mm, 18 * mm, 22 * mm, 22 * mm, 18 * mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(t2)

    # Page 4: Cost
    story.append(Paragraph("Cost Estimate", h2_style))
    cost = topology.get("cost", {})
    cost_data = [
        ["Category", "Amount (GBP)"],
        ["Total CAPEX", f"£{cost.get('total_capex_gbp', 0):,.0f}"],
        ["CAPEX per premises", f"£{cost.get('capex_per_premises_gbp', 0):,.0f}"],
        ["Annual PIA rental", f"£{cost.get('annual_pia_rental_gbp', 0):,.0f}"],
    ]
    t3 = Table(cost_data, colWidths=[120 * mm, 50 * mm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(t3)

    doc.build(story)
    return buf.getvalue()
