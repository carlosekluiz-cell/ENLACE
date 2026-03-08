"""Normalize telecom provider names for deduplication.

Brazilian provider names have many variations:
- "VIVO S.A." / "TELEFONICA BRASIL S.A." / "TELEFONICA BRASIL" -> "telefonica brasil sa vivo"
- "CLARO S.A." / "NET SERVICOS" / "EMBRATEL" -> "claro sa" (same group)
- "OI S.A." / "OI MOVEL" / "TELEMAR" -> "oi sa"
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
    "telemar": "oi sa",
    "brasil telecom": "oi sa",
    "brt": "oi sa",

    # TIM
    "tim s.a": "tim sa",
    "tim s/a": "tim sa",
    "tim celular": "tim sa",
    "tim sa": "tim sa",
    "intelig": "tim sa",
}


def normalize_provider_name(name: str) -> str:
    """Normalize a provider name for matching and deduplication."""
    # Lowercase
    normalized = name.lower().strip()
    # Remove accents
    normalized = unidecode(normalized)
    # Remove common suffixes
    for suffix in [" ltda", " eireli", " me", " epp", " s.a.", " s/a", " s.a"]:
        normalized = normalized.replace(suffix, "")
    # Remove special characters except spaces
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Check against known groups
    for pattern, canonical in PROVIDER_GROUPS.items():
        if pattern in normalized:
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
