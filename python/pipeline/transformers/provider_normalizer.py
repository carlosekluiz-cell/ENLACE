"""Normalize telecom provider names for deduplication.

Brazilian provider names have many variations:
- "VIVO S.A." / "TELEFONICA BRASIL S.A." / "TELEFONICA BRASIL" -> "telefonica brasil sa vivo"
- "CLARO S.A." / "NET SERVICOS" / "EMBRATEL" -> "claro sa" (same group)
- "OI S.A." / "OI MOVEL" / "TELEMAR" -> "oi sa"

Colombian ISPs have similar grouping needs:
- "COMCEL S.A." / "CLARO" -> "claro co"
- "COLOMBIA TELECOMUNICACIONES" / "MOVISTAR" -> "movistar co"
"""
from unidecode import unidecode
import re

# Known corporate group mappings (Anatel uses many names for same entity)
PROVIDER_GROUPS = {
    # Claro/NET/Embratel group
    "net servicos": "claro sa",
    "net serviços": "claro sa",
    "embratel": "claro sa",
    "claro nxt": "claro sa",
    "claro s.a": "claro sa",
    "claro s/a": "claro sa",
    "claro sa": "claro sa",
    "claro": "claro sa",
    "america movil": "claro sa",

    # Vivo/Telefonica group
    "telefonica brasil": "telefonica brasil sa vivo",
    "telefônica brasil": "telefonica brasil sa vivo",
    "vivo s.a": "telefonica brasil sa vivo",
    "vivo sa": "telefonica brasil sa vivo",
    "vivo s/a": "telefonica brasil sa vivo",
    "vivo": "telefonica brasil sa vivo",
    "gvt": "telefonica brasil sa vivo",
    "global village telecom": "telefonica brasil sa vivo",
    "terra networks": "telefonica brasil sa vivo",

    # Oi group
    "oi s.a": "oi sa",
    "oi s/a": "oi sa",
    "oi movel": "oi sa",
    "oi móvel": "oi sa",
    "oi sa": "oi sa",
    "oi": "oi sa",
    "telemar": "oi sa",
    "brasil telecom": "oi sa",
    "brt": "oi sa",

    # TIM
    "tim s.a": "tim sa",
    "tim s/a": "tim sa",
    "tim celular": "tim sa",
    "tim sa": "tim sa",
    "tim": "tim sa",
    "intelig": "tim sa",
}


# Colombian ISP corporate group mappings
COLOMBIA_PROVIDER_GROUPS = {
    # Claro Colombia (America Movil)
    "comcel": "claro co",
    "claro": "claro co",
    "telmex colombia": "claro co",
    "america movil": "claro co",

    # Movistar Colombia (Telefonica)
    "colombia telecomunicaciones": "movistar co",
    "movistar": "movistar co",
    "telefonica": "movistar co",

    # Tigo-UNE (Millicom)
    "tigo": "tigo une",
    "une": "tigo une",
    "tigo une": "tigo une",
    "millicom": "tigo une",
    "colombia movil": "tigo une",
    "edatel": "tigo une",

    # ETB (Empresa de Telecomunicaciones de Bogota)
    "etb": "etb",
    "empresa de telecomunicaciones de bogota": "etb",
}


def normalize_provider_name(name: str, country_code: str = "BR") -> str:
    """Normalize a provider name for matching and deduplication."""
    # Lowercase
    normalized = name.lower().strip()
    # Remove accents
    normalized = unidecode(normalized)
    # Remove common suffixes
    for suffix in [" ltda", " eireli", " me", " epp", " s.a.", " s/a", " s.a", " sas"]:
        normalized = normalized.replace(suffix, "")
    # Remove special characters except spaces
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Select the right group mapping based on country
    groups = COLOMBIA_PROVIDER_GROUPS if country_code == "CO" else PROVIDER_GROUPS

    # Check against known groups using word-boundary matching
    # to avoid false positives like "brisanet servicos" matching "net servicos"
    for pattern, canonical in groups.items():
        if re.search(r"(?:^|\s)" + re.escape(pattern) + r"(?:\s|$)", normalized):
            return canonical

    return normalized


def classify_provider(subscriber_count: int) -> str:
    """Classify provider by Anatel size categories."""
    if subscriber_count >= 50000:
        return "PGP"  # Prestadora de Grande Porte
    elif subscriber_count >= 5000:
        return "PMP"  # Prestadora de Medio Porte
    else:
        return "PPP"  # Prestadora de Pequeno Porte
