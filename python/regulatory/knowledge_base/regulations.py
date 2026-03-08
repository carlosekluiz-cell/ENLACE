"""Brazilian telecom regulatory database.

Structured knowledge base of key regulations affecting ISPs in Brazil.
Each regulation is modeled as a dataclass with compliance requirements,
deadlines, penalties, and impact classification.

Key regulations:
    1. Norma no. 4 (SVA to SCM reclassification) - deadline Jan 2027
    2. Resolution 614/2013 (Regulamento do SCM) - licensing and quality
    3. Resolution 632/2014 (Regulamento de Direitos dos Consumidores) - consumer rights
    4. Resolution 717/2019 (Regulamento de Qualidade) - IDA quality metrics
    5. LGPD (Lei 13.709/2018) - data protection
    6. Resolution 694/2018 (Cybersecurity) - security obligations

Sources:
    - Anatel regulatory portal (gov.br/anatel)
    - Official Gazette (Diário Oficial da União)
    - Abrint regulatory bulletins
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RegulatoryStatus(Enum):
    """Current status of a regulation."""
    ACTIVE = "active"
    PENDING = "pending"
    PROPOSED = "proposed"
    SUPERSEDED = "superseded"


class Impact(Enum):
    """Expected impact level on ISP operations."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Regulation:
    """A Brazilian telecom regulation with compliance details.

    Attributes:
        id: Short identifier used throughout the system (e.g. 'norma4').
        name: Human-readable short name.
        full_name: Official legal name / number.
        description: Summary of what the regulation requires.
        effective_date: Date the regulation became/becomes effective.
        deadline: Compliance deadline, or None if already in effect.
        status: Current regulatory status.
        impact: Expected impact on ISP operations.
        affected_services: List of service types affected (e.g. 'SCM', 'SMP').
        affected_size: Which ISPs are affected by subscriber count.
        compliance_requirements: List of specific compliance actions needed.
        penalties: List of possible penalties for non-compliance.
        source_url: Link to official regulation text.
    """
    id: str
    name: str
    full_name: str
    description: str
    effective_date: date
    deadline: Optional[date]
    status: RegulatoryStatus
    impact: Impact
    affected_services: list[str] = field(default_factory=list)
    affected_size: str = "all"
    compliance_requirements: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    source_url: str = ""


# ---------------------------------------------------------------------------
# Regulatory database
# ---------------------------------------------------------------------------
REGULATIONS: list[Regulation] = [
    Regulation(
        id="norma4",
        name="Norma no. 4",
        full_name="Norma no. 4/2024 - Reclassificação de SVA para SCM",
        description=(
            "Reclassifies fixed broadband internet from SVA (Serviço de Valor "
            "Adicionado) to SCM (Serviço de Comunicação Multimídia), subjecting "
            "ISPs to ICMS taxation, Anatel licensing, and quality reporting "
            "obligations previously not applicable under SVA."
        ),
        effective_date=date(2024, 6, 1),
        deadline=date(2027, 1, 1),
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.HIGH,
        affected_services=["SCM", "broadband", "fixed_internet"],
        affected_size="all",
        compliance_requirements=[
            "Register as SCM provider with Anatel",
            "Implement ICMS collection and reporting per state",
            "Update customer contracts to reflect SCM classification",
            "Submit quarterly quality reports (IDA) to Anatel",
            "Adapt billing systems for ICMS calculation and nota fiscal",
            "Implement consumer protection procedures per Res. 632",
            "Register in Anatel's STEL and MOSAICO systems",
        ],
        penalties=[
            "Fines up to R$50 million for non-compliance",
            "Service authorization revocation",
            "Customer complaints escalation to Anatel",
            "Prohibition from participating in public tenders",
            "Criminal liability for tax evasion (ICMS)",
        ],
        source_url="https://www.gov.br/anatel/norma-4-2024",
    ),

    Regulation(
        id="res614",
        name="Resolução 614/2013",
        full_name="Resolução no. 614/2013 - Regulamento do SCM",
        description=(
            "Establishes the regulatory framework for SCM (Serviço de "
            "Comunicação Multimídia). Defines licensing requirements, "
            "coverage obligations, and technical standards. ISPs above "
            "5,000 subscribers require an Autorização (license); below "
            "that threshold, a simplified Comunicação Prévia suffices."
        ),
        effective_date=date(2013, 5, 28),
        deadline=None,
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.HIGH,
        affected_services=["SCM"],
        affected_size="all",
        compliance_requirements=[
            "Obtain SCM Autorização (>5,000 subscribers) or file Comunicação Prévia",
            "Maintain updated registration in STEL",
            "Comply with spectrum usage regulations (if applicable)",
            "Submit annual technical and financial reports to Anatel",
            "Maintain minimum network documentation and topology records",
        ],
        penalties=[
            "Fines from R$1,000 to R$50 million based on severity",
            "Temporary or permanent suspension of authorization",
            "Equipment seizure for unlicensed operation",
        ],
        source_url="https://www.anatel.gov.br/legislacao/resolucoes/2013/614",
    ),

    Regulation(
        id="res632",
        name="Resolução 632/2014",
        full_name="Resolução no. 632/2014 - Regulamento de Direitos dos Consumidores",
        description=(
            "Consumer protection regulation for telecom services. Mandates "
            "transparency in pricing, contract terms, complaint handling "
            "procedures, and service cancellation rights. Under SCM, ISPs "
            "must maintain call centers, online portals, and respond to "
            "complaints within defined SLAs."
        ),
        effective_date=date(2014, 6, 7),
        deadline=None,
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.MEDIUM,
        affected_services=["SCM", "SMP", "STFC", "SeAC"],
        affected_size="all",
        compliance_requirements=[
            "Provide clear and complete price information before contracting",
            "Allow contract cancellation at any time without penalty (after loyalty period)",
            "Maintain complaint handling system with protocol numbers",
            "Respond to Anatel consumer complaints within 5 business days",
            "Send monthly billing summary with all charges itemized",
            "Offer at least 3 plan options including a basic/entry-level plan",
            "Notify customers 30 days before any contract changes",
        ],
        penalties=[
            "Fines per consumer complaint not addressed within SLA",
            "Anatel Cautelar (injunction) to cease violating practices",
            "Public reprimand and negative listing on Anatel portal",
            "Fines up to R$50 million for systematic violations",
        ],
        source_url="https://www.anatel.gov.br/legislacao/resolucoes/2014/632",
    ),

    Regulation(
        id="res717",
        name="Resolução 717/2019",
        full_name="Resolução no. 717/2019 - Regulamento de Qualidade dos Serviços",
        description=(
            "Quality regulation for telecom services. Establishes the IDA "
            "(Indicador de Desempenho de Atendimento) framework for measuring "
            "service quality. ISPs must meet minimum thresholds for speed "
            "delivery, latency, availability, and customer service response. "
            "Anatel publishes quarterly quality rankings."
        ),
        effective_date=date(2019, 10, 1),
        deadline=None,
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.MEDIUM,
        affected_services=["SCM", "SMP", "STFC"],
        affected_size="above_5000",
        compliance_requirements=[
            "Deliver at least 80% of contracted download speed (monthly average)",
            "Deliver at least 80% of contracted upload speed (monthly average)",
            "Maintain network availability >= 99% per month",
            "Latency <= 80ms for 95% of measurements",
            "Submit quarterly quality reports to Anatel (SIQ system)",
            "Participate in annual customer satisfaction survey (IDA Pesquisa)",
            "Achieve minimum IDA composite score of 6.0",
        ],
        penalties=[
            "Public ranking in Anatel quality portal (reputational)",
            "Mandatory improvement plans for scores below threshold",
            "Fines for repeated quality violations",
            "Prohibition from selling new plans until improvements verified",
        ],
        source_url="https://www.anatel.gov.br/legislacao/resolucoes/2019/717",
    ),

    Regulation(
        id="lgpd",
        name="LGPD",
        full_name="Lei 13.709/2018 - Lei Geral de Proteção de Dados Pessoais",
        description=(
            "Brazil's general data protection law, modeled after GDPR. "
            "Applies to all ISPs processing subscriber personal data. "
            "Requires consent management, data protection officers (DPO/Encarregado), "
            "breach notification, and data subject rights management."
        ),
        effective_date=date(2020, 9, 18),
        deadline=None,
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.MEDIUM,
        affected_services=["SCM", "SMP", "STFC", "SeAC"],
        affected_size="all",
        compliance_requirements=[
            "Appoint a DPO (Encarregado de Proteção de Dados)",
            "Implement subscriber consent management for data processing",
            "Maintain Records of Processing Activities (ROPA)",
            "Implement data breach notification process (72h to ANPD)",
            "Honor data subject rights (access, deletion, portability)",
            "Conduct Data Protection Impact Assessments (DPIA/RIPD) for high-risk processing",
            "Implement data minimization and retention policies",
        ],
        penalties=[
            "Fines up to 2% of revenue, capped at R$50 million per violation",
            "Partial or total suspension of data processing activities",
            "Public notice of violation",
            "Blocking or deletion of affected personal data",
        ],
        source_url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
    ),

    Regulation(
        id="res740",
        name="Resolução 740/2020",
        full_name="Resolução no. 740/2020 - Regulamento de Segurança Cibernética",
        description=(
            "Cybersecurity regulation for telecom providers. Requires ISPs "
            "to implement cybersecurity policies, incident response plans, "
            "and report security incidents to Anatel. Aligns with NIST and "
            "ISO 27001 frameworks."
        ),
        effective_date=date(2021, 1, 4),
        deadline=None,
        status=RegulatoryStatus.ACTIVE,
        impact=Impact.MEDIUM,
        affected_services=["SCM", "SMP", "STFC", "SeAC"],
        affected_size="all",
        compliance_requirements=[
            "Develop and maintain a Cybersecurity Policy (Norma de Segurança Cibernética)",
            "Implement incident response and notification procedures",
            "Report critical security incidents to Anatel within 24 hours",
            "Conduct periodic vulnerability assessments",
            "Maintain logs and audit trails for at least 1 year",
            "Designate a cybersecurity officer (Responsável pela Segurança Cibernética)",
        ],
        penalties=[
            "Fines for failure to report security incidents",
            "Mandatory corrective action plans",
            "Potential service suspension for critical vulnerabilities",
        ],
        source_url="https://www.anatel.gov.br/legislacao/resolucoes/2020/740",
    ),
]

# Build lookup index
_REGULATION_INDEX: dict[str, Regulation] = {r.id: r for r in REGULATIONS}


def get_regulation(regulation_id: str) -> Optional[Regulation]:
    """Look up a regulation by its short ID.

    Args:
        regulation_id: Regulation identifier (e.g. 'norma4', 'res614').

    Returns:
        The Regulation object, or None if not found.
    """
    reg = _REGULATION_INDEX.get(regulation_id)
    if reg is None:
        logger.warning("Regulation not found: %s", regulation_id)
    return reg


def get_active_regulations() -> list[Regulation]:
    """Get all regulations with ACTIVE status.

    Returns:
        List of active Regulation objects.
    """
    active = [r for r in REGULATIONS if r.status == RegulatoryStatus.ACTIVE]
    logger.debug("Found %d active regulations", len(active))
    return active


def get_regulations_by_service(service: str) -> list[Regulation]:
    """Get regulations that affect a specific service type.

    Args:
        service: Service type identifier (e.g. 'SCM', 'broadband', 'SMP').

    Returns:
        List of Regulation objects that list the service in affected_services.
    """
    normalized = service.strip().upper()
    # Also check lowercase for non-acronym services like 'broadband'
    matching = [
        r for r in REGULATIONS
        if normalized in [s.upper() for s in r.affected_services]
        or service.lower() in [s.lower() for s in r.affected_services]
    ]
    logger.debug(
        "Found %d regulations affecting service '%s'",
        len(matching),
        service,
    )
    return matching


def get_regulations_by_impact(impact: Impact) -> list[Regulation]:
    """Get regulations filtered by impact level.

    Args:
        impact: Impact level to filter by.

    Returns:
        List of matching Regulation objects.
    """
    return [r for r in REGULATIONS if r.impact == impact]


def get_upcoming_deadlines(days_ahead: int = 365) -> list[Regulation]:
    """Get regulations with upcoming deadlines within the specified window.

    Args:
        days_ahead: Number of days ahead to look for deadlines (default 365).

    Returns:
        List of Regulation objects with deadlines within the window,
        sorted by deadline date (earliest first).
    """
    today = date.today()
    cutoff = date.fromordinal(today.toordinal() + days_ahead)

    upcoming = [
        r for r in REGULATIONS
        if r.deadline is not None and today <= r.deadline <= cutoff
    ]
    upcoming.sort(key=lambda r: r.deadline)

    logger.info(
        "Found %d regulations with deadlines in the next %d days",
        len(upcoming),
        days_ahead,
    )
    return upcoming


def get_regulations_by_size(subscriber_count: int) -> list[Regulation]:
    """Get regulations applicable to an ISP of a given size.

    Args:
        subscriber_count: Number of subscribers the ISP serves.

    Returns:
        List of applicable Regulation objects.
    """
    applicable = []
    for reg in REGULATIONS:
        if reg.affected_size == "all":
            applicable.append(reg)
        elif reg.affected_size == "above_5000" and subscriber_count >= 5000:
            applicable.append(reg)
        elif reg.affected_size == "small" and subscriber_count < 5000:
            applicable.append(reg)
        elif reg.affected_size == "large" and subscriber_count >= 5000:
            applicable.append(reg)

    logger.debug(
        "Found %d regulations applicable to ISP with %d subscribers",
        len(applicable),
        subscriber_count,
    )
    return applicable


def search_regulations(query: str) -> list[Regulation]:
    """Search regulations by keyword across name, description, and requirements.

    Args:
        query: Search term (case-insensitive).

    Returns:
        List of matching Regulation objects.
    """
    q = query.lower()
    results = []
    for reg in REGULATIONS:
        searchable = " ".join([
            reg.name.lower(),
            reg.full_name.lower(),
            reg.description.lower(),
            " ".join(r.lower() for r in reg.compliance_requirements),
        ])
        if q in searchable:
            results.append(reg)
    return results
