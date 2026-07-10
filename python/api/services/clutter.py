"""
MapBiomas land cover → RF clutter classification.

Maps MapBiomas Collection 9 class codes (uint8) to the clutter categories
used by propagation corrections (ITU-R P.1812 representative clutter
heights, vegetation attenuation, urban/suburban/rural environment).

Class reference: https://brasil.mapbiomas.org/en/codigos-de-legenda/
(Collection 9 legend). Codes not listed fall back to "open".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClutterClass:
    key: str          # machine key: forest|urban|agriculture|water|wetland|bare|open
    label_pt: str     # UI label
    height_m: float   # representative clutter height (P.1812-style)


CLUTTER = {
    "forest": ClutterClass("forest", "Floresta", 20.0),
    "plantation": ClutterClass("plantation", "Silvicultura", 15.0),
    "urban": ClutterClass("urban", "Área urbana", 10.0),
    "agriculture": ClutterClass("agriculture", "Agropecuária", 1.0),
    "wetland": ClutterClass("wetland", "Área úmida", 2.0),
    "water": ClutterClass("water", "Água", 0.0),
    "bare": ClutterClass("bare", "Solo exposto", 0.0),
    "open": ClutterClass("open", "Campo aberto", 0.5),
}

# MapBiomas Collection 9 code -> clutter key
_MAPBIOMAS_TO_CLUTTER: dict[int, str] = {
    # Forest formations
    1: "forest", 3: "forest", 4: "forest", 5: "forest", 6: "forest", 49: "forest",
    # Forest plantation
    9: "plantation",
    # Non-forest natural
    10: "open", 11: "wetland", 12: "open", 32: "wetland", 29: "bare", 50: "open",
    13: "open",
    # Farming (pasture, crops, mosaics)
    14: "agriculture", 15: "agriculture", 18: "agriculture", 19: "agriculture",
    20: "agriculture", 21: "agriculture", 35: "agriculture", 36: "agriculture",
    39: "agriculture", 40: "agriculture", 41: "agriculture", 46: "agriculture",
    47: "agriculture", 48: "agriculture", 62: "agriculture",
    # Non-vegetated
    22: "bare", 23: "bare", 24: "urban", 25: "bare", 30: "bare",
    # Water
    26: "water", 31: "water", 33: "water",
    # Not observed
    0: "open", 27: "open",
}

_MAPBIOMAS_NAMES_PT: dict[int, str] = {
    3: "Formação florestal", 4: "Formação savânica", 5: "Mangue",
    6: "Floresta alagável", 9: "Silvicultura", 11: "Campo alagado",
    12: "Formação campestre", 15: "Pastagem", 18: "Agricultura",
    19: "Lavoura temporária", 20: "Cana", 21: "Mosaico de usos",
    23: "Praia/duna", 24: "Área urbanizada", 25: "Outra área não vegetada",
    29: "Afloramento rochoso", 30: "Mineração", 33: "Rio/lago/oceano",
    39: "Soja", 41: "Outras lavouras temporárias", 46: "Café",
    48: "Outras lavouras perenes", 49: "Restinga arbórea", 0: "Sem dados",
}


def classify(code: int) -> ClutterClass:
    """Clutter class for a MapBiomas code (unknown codes -> open)."""
    return CLUTTER[_MAPBIOMAS_TO_CLUTTER.get(int(code), "open")]


def class_name_pt(code: int) -> str:
    """Human-readable MapBiomas class name (falls back to the code)."""
    return _MAPBIOMAS_NAMES_PT.get(int(code), f"Classe {int(code)}")


def infer_environment(codes: list[int], radius_urban_threshold: float = 0.35) -> str:
    """Hata/TR 38.901 environment from the clutter mix around a point/path.

    >=35% urban pixels -> urban; >=10% -> suburban; else rural.
    """
    if not codes:
        return "rural"
    urban = sum(1 for c in codes if _MAPBIOMAS_TO_CLUTTER.get(int(c)) == "urban")
    frac = urban / len(codes)
    if frac >= radius_urban_threshold:
        return "urban"
    if frac >= 0.10:
        return "suburban"
    return "rural"


def summarize_path(codes: list[int], step_m: float) -> dict:
    """Clutter composition and vegetation depth along a profile."""
    if not codes:
        return {"fractions": {}, "vegetation_depth_m": 0.0, "environment": "rural"}
    counts: dict[str, int] = {}
    for c in codes:
        key = _MAPBIOMAS_TO_CLUTTER.get(int(c), "open")
        counts[key] = counts.get(key, 0) + 1
    n = len(codes)
    veg = counts.get("forest", 0) + counts.get("plantation", 0)
    return {
        "fractions": {k: round(v / n, 3) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])},
        "vegetation_depth_m": round(veg * step_m, 1),
        "environment": infer_environment(codes),
    }
