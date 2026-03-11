"""Match rural deployments to Brazilian government funding programs.

Tracks major federal programs that fund or subsidize rural telecom
infrastructure deployments. Provides eligibility scoring and guidance
for application.

Programs tracked:
- FUST (Universal Telecom Service Fund)
- Norte Conectado (Amazon fiber backbone)
- New PAC Connectivity (4G/5G expansion)
- 5G Auction Obligations (operator coverage obligations)
- WiFi Brasil / GESAC (community internet points)
- BNDES ProConectividade (development bank credit lines)

Sources:
    - MCom (Ministry of Communications) program documentation
    - Anatel auction obligation terms
    - BNDES financing guidelines
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brazilian state-to-region mapping (for geographic eligibility)
# ---------------------------------------------------------------------------
LEGAL_AMAZON_STATES = {
    "AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO",
}

NORTHEAST_STATES = {
    "AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE",
}

NORTH_STATES = {
    "AC", "AM", "AP", "PA", "RO", "RR", "TO",
}


@dataclass
class FundingProgram:
    """Describes a government funding program for rural telecom.

    Attributes:
        id: Short identifier for the program.
        name: Common name / acronym.
        full_name: Official full name in Portuguese.
        description: Brief English description.
        eligibility_criteria: Human-readable eligibility conditions.
        max_funding_brl: Maximum funding amount, or None if unlimited/varies.
        funding_type: Type of funding (grant, credit, partnership).
        application_url: URL for more information or application.
        deadline: Application deadline, or None if ongoing.
        notes: Additional context.
    """

    id: str
    name: str
    full_name: str
    description: str
    eligibility_criteria: list[str]
    max_funding_brl: float | None
    funding_type: str  # "grant", "credit", "partnership"
    application_url: str
    deadline: str | None
    notes: str


# ---------------------------------------------------------------------------
# Funding programs database
# ---------------------------------------------------------------------------
FUNDING_PROGRAMS: list[FundingProgram] = [
    FundingProgram(
        id="fust",
        name="FUST",
        full_name="Fundo de Universalização dos Serviços de Telecomunicações",
        description="Fundo universal de telecomunicações para áreas não atendidas",
        eligibility_criteria=[
            "Município com menos de 30.000 habitantes",
            "Área não atendida (sem banda larga > 10 Mbps)",
            "Provedor com licença SCM",
        ],
        max_funding_brl=5_000_000,
        funding_type="credit",
        application_url="https://gov.br/mcom/fust",
        deadline=None,
        notes="Linhas de crédito BNDES disponíveis. Taxas abaixo do mercado. Prazo de até 10 anos.",
    ),
    FundingProgram(
        id="norte_conectado",
        name="Norte Conectado",
        full_name="Programa Norte Conectado",
        description="Programa de backbone de fibra para a região amazônica",
        eligibility_criteria=[
            "Localização na Amazônia Legal",
            "Comunidade ao longo das rotas aprovadas de backbone de fibra",
        ],
        max_funding_brl=None,
        funding_type="partnership",
        application_url="https://gov.br/mcom/norte-conectado",
        deadline=None,
        notes="Backbone público (governo), última milha privada. Mais de 12.000 km de fibra ao longo dos rios.",
    ),
    FundingProgram(
        id="new_pac",
        name="Novo PAC Conectividade",
        full_name="Novo PAC — Eixo Inclusão Digital",
        description="Expansão 4G/5G para municípios não atendidos",
        eligibility_criteria=[
            "Município sem cobertura 4G",
            "Na lista de municípios-alvo do Novo PAC",
        ],
        max_funding_brl=10_000_000,
        funding_type="partnership",
        application_url="https://gov.br/planalto/novo-pac",
        deadline=None,
        notes="4G para mais de 6.800 vilas, 5G para todos os municípios. Operadoras em parceria com o governo.",
    ),
    FundingProgram(
        id="5g_obligations",
        name="Obrigações do Leilão 5G",
        full_name="Obrigações do Leilão 5G",
        description="Obrigações de cobertura do leilão de espectro 5G",
        eligibility_criteria=[
            "Comunidade na área de obrigação de operadora",
            "Parceria com operadora detentora da obrigação (Claro, Vivo, TIM, etc.)",
        ],
        max_funding_brl=None,
        funding_type="partnership",
        application_url="https://anatel.gov.br/leilao5g",
        deadline="2028-12-31",
        notes=(
            "Operadoras devem cobrir áreas não atendidas específicas até 2028. "
            "Parceria com operadora detentora para infraestrutura compartilhada."
        ),
    ),
    FundingProgram(
        id="wifi_brasil",
        name="WiFi Brasil / GESAC",
        full_name="Programa WiFi Brasil (antigo GESAC)",
        description="Pontos de WiFi comunitário gratuito via satélite",
        eligibility_criteria=[
            "Instituição pública (escola, unidade de saúde, centro comunitário)",
            "Município sem banda larga",
            "Localizado em área prioritária (rural, indígena, quilombola)",
        ],
        max_funding_brl=None,
        funding_type="grant",
        application_url="https://gov.br/mcom/wifi-brasil",
        deadline=None,
        notes=(
            "Governo fornece terminal satelital + AP WiFi. "
            "Usa satélite SGDC da Telebras. Gratuito para instituições elegíveis."
        ),
    ),
    FundingProgram(
        id="bndes_proconectividade",
        name="BNDES ProConectividade",
        full_name="BNDES ProConectividade",
        description="Linha de crédito do banco de desenvolvimento para infraestrutura de ISP",
        eligibility_criteria=[
            "ISP registrado (SCM ou Comunicação Prévia)",
            "CNPJ válido com histórico de crédito positivo",
            "Projeto em município não atendido (< 60.000 habitantes)",
        ],
        max_funding_brl=20_000_000,
        funding_type="credit",
        application_url="https://bndes.gov.br/proconectividade",
        deadline=None,
        notes=(
            "Taxa de juros: TLP + 1,3% a 1,8%. Financiamento de até 80%. "
            "Prazo de 12 anos com 2 anos de carência."
        ),
    ),
]


@dataclass
class FundingMatch:
    """Result of matching a deployment to a funding program.

    Attributes:
        program: The matched funding program.
        eligibility_score: Score from 0-100 indicating match quality.
        eligible_criteria: Criteria that the deployment meets.
        ineligible_criteria: Criteria that are not met or uncertain.
        estimated_funding_brl: Estimated funding amount, or None if variable.
        required_documents: Documents needed for application.
        notes: Match-specific guidance.
    """

    program: FundingProgram
    eligibility_score: float  # 0-100
    eligible_criteria: list[str]
    ineligible_criteria: list[str]
    estimated_funding_brl: float | None
    required_documents: list[str]
    notes: str


def _check_fust_eligibility(
    municipality_population: int,
    state_code: str,
    technology: str,
    capex_brl: float,
) -> FundingMatch:
    """Check FUST eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "fust")
    eligible: list[str] = []
    ineligible: list[str] = []

    # Population check
    if municipality_population < 30_000:
        eligible.append("Municipality < 30,000 inhabitants")
    else:
        ineligible.append(
            f"Municipality has {municipality_population:,} inhabitants (limit: 30,000)"
        )

    # Underserved area (assumed true for rural deployments)
    eligible.append("Underserved area (rural deployment)")

    # SCM license (assumed — note requirement)
    eligible.append("SCM licensed provider (verify current status)")

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    estimated_funding = min(capex_brl * 0.80, program.max_funding_brl or capex_brl)

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=round(estimated_funding, 2),
        required_documents=[
            "CNPJ and SCM authorization/comunicação prévia",
            "Technical project documentation",
            "Financial statements (last 3 years)",
            "Coverage area map and population data",
            "Business plan with subscriber projections",
        ],
        notes=(
            f"FUST credit via BNDES. Estimated financing: R${estimated_funding:,.0f} "
            f"(up to 80% of CAPEX R${capex_brl:,.0f})."
        ),
    )


def _check_norte_conectado_eligibility(
    state_code: str,
    latitude: float | None,
    longitude: float | None,
) -> FundingMatch:
    """Check Norte Conectado eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "norte_conectado")
    eligible: list[str] = []
    ineligible: list[str] = []

    if state_code.upper() in LEGAL_AMAZON_STATES:
        eligible.append("Location in Legal Amazon")
    else:
        ineligible.append(f"State {state_code} is not in Legal Amazon")

    # Route proximity would require geospatial check; note as uncertain
    if state_code.upper() in LEGAL_AMAZON_STATES:
        eligible.append("Community along approved routes (verify with MCom route maps)")
    else:
        ineligible.append("Not on Norte Conectado route (outside Legal Amazon)")

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=None,
        required_documents=[
            "Letter of interest to MCom",
            "Community location map (KML/shapefile)",
            "Population and demand documentation",
            "Proposed last-mile deployment plan",
        ],
        notes=(
            "Norte Conectado provides public backbone fiber. ISP provides last-mile. "
            "Verify proximity to approved fiber routes with MCom."
        ),
    )


def _check_new_pac_eligibility(
    municipality_population: int,
    state_code: str,
    technology: str,
    capex_brl: float,
) -> FundingMatch:
    """Check New PAC Connectivity eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "new_pac")
    eligible: list[str] = []
    ineligible: list[str] = []

    # Technology alignment
    if technology.lower() in ("4g", "4g_700mhz", "4g_250mhz", "lte", "5g"):
        eligible.append("Technology aligns with New PAC (4G/5G expansion)")
    else:
        ineligible.append(
            f"Technology '{technology}' may not align with New PAC 4G/5G focus"
        )

    # Municipality target (would need actual target list)
    if municipality_population < 50_000:
        eligible.append("Small municipality — likely on New PAC target list (verify)")
    else:
        ineligible.append(
            f"Municipality population {municipality_population:,} — may not be priority"
        )

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    estimated_funding = min(capex_brl, program.max_funding_brl or capex_brl)

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=round(estimated_funding, 2),
        required_documents=[
            "Partnership proposal with operator",
            "Coverage area documentation",
            "Population data from IBGE",
            "Technical deployment plan",
        ],
        notes=(
            "New PAC targets 4G to 6,800+ villages. "
            "Partnership model — verify with operator and MCom."
        ),
    )


def _check_5g_obligations_eligibility(
    state_code: str,
    municipality_population: int,
) -> FundingMatch:
    """Check 5G Auction Obligations eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "5g_obligations")
    eligible: list[str] = []
    ineligible: list[str] = []

    # Small/underserved municipalities are typically in obligation areas
    if municipality_population < 30_000:
        eligible.append("Small municipality — likely in operator obligation area")
    else:
        ineligible.append("Larger municipality — may already have coverage")

    # All states potentially have obligations
    eligible.append("5G obligations cover all states (verify specific operator area)")

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=None,
        required_documents=[
            "Infrastructure sharing proposal",
            "Coverage gap documentation",
            "Partnership agreement draft with operator",
        ],
        notes=(
            "Contact obligation-holding operators (Claro, Vivo, TIM) for "
            "shared infrastructure partnership. Deadline: 2028-12-31."
        ),
    )


def _check_wifi_brasil_eligibility(
    municipality_population: int,
    state_code: str,
) -> FundingMatch:
    """Check WiFi Brasil / GESAC eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "wifi_brasil")
    eligible: list[str] = []
    ineligible: list[str] = []

    if municipality_population < 50_000:
        eligible.append("Small/rural municipality — eligible for WiFi Brasil")
    else:
        ineligible.append("Larger municipality — lower priority")

    eligible.append("Requires public institution host (school, health unit, etc.)")

    # Priority for specific regions
    if state_code.upper() in LEGAL_AMAZON_STATES | NORTHEAST_STATES:
        eligible.append(f"State {state_code} is in priority region")
    else:
        eligible.append("All states eligible, but priority for North/Northeast")

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=None,
        required_documents=[
            "Host institution letter of support",
            "INEP school code or CNES health unit code",
            "Community population documentation",
        ],
        notes=(
            "WiFi Brasil provides free satellite terminal + WiFi AP "
            "for public institutions. Uses Telebras SGDC."
        ),
    )


def _check_bndes_eligibility(
    municipality_population: int,
    capex_brl: float,
) -> FundingMatch:
    """Check BNDES ProConectividade eligibility."""
    program = next(p for p in FUNDING_PROGRAMS if p.id == "bndes_proconectividade")
    eligible: list[str] = []
    ineligible: list[str] = []

    if municipality_population < 60_000:
        eligible.append("Municipality < 60,000 inhabitants")
    else:
        ineligible.append(
            f"Municipality has {municipality_population:,} inhabitants (limit: 60,000)"
        )

    eligible.append("Registered ISP with valid CNPJ (verify)")
    eligible.append("Positive credit history required (verify)")

    score = len(eligible) / (len(eligible) + len(ineligible)) * 100

    estimated_funding = min(
        capex_brl * 0.80,
        program.max_funding_brl or capex_brl,
    )

    return FundingMatch(
        program=program,
        eligibility_score=round(score, 1),
        eligible_criteria=eligible,
        ineligible_criteria=ineligible,
        estimated_funding_brl=round(estimated_funding, 2),
        required_documents=[
            "CNPJ and company registration",
            "Financial statements (last 3 years)",
            "Technical project documentation",
            "Business plan with cash flow projections",
            "Environmental licenses (if applicable)",
            "Tax compliance certificates (CND)",
        ],
        notes=(
            f"BNDES credit line. Interest: TLP + 1.3-1.8%. "
            f"Up to 80% financing (R${estimated_funding:,.0f} of R${capex_brl:,.0f}). "
            "12 year repayment, 2 year grace period."
        ),
    )


def match_funding(
    municipality_code: str,
    municipality_population: int,
    state_code: str,
    technology: str,
    capex_brl: float,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[FundingMatch]:
    """Match a deployment to available funding programs.

    Evaluates all tracked funding programs and returns matches sorted
    by eligibility score (highest first).

    Args:
        municipality_code: IBGE municipality code.
        municipality_population: Municipality population.
        state_code: Two-letter state code (e.g. "AM", "PA", "SP").
        technology: Deployment technology (e.g. "4g_700mhz", "fiber", "satellite").
        capex_brl: Estimated total CAPEX in BRL.
        latitude: Optional latitude for geographic checks.
        longitude: Optional longitude for geographic checks.

    Returns:
        List of FundingMatch sorted by eligibility_score descending.
    """
    if municipality_population < 0:
        logger.warning("Municipality population is negative, defaulting to 0.")
        municipality_population = 0

    if capex_brl < 0:
        logger.warning("CAPEX is negative, defaulting to 0.")
        capex_brl = 0

    matches: list[FundingMatch] = []

    # Check each program
    matches.append(
        _check_fust_eligibility(municipality_population, state_code, technology, capex_brl)
    )
    matches.append(
        _check_norte_conectado_eligibility(state_code, latitude, longitude)
    )
    matches.append(
        _check_new_pac_eligibility(municipality_population, state_code, technology, capex_brl)
    )
    matches.append(
        _check_5g_obligations_eligibility(state_code, municipality_population)
    )
    matches.append(
        _check_wifi_brasil_eligibility(municipality_population, state_code)
    )
    matches.append(
        _check_bndes_eligibility(municipality_population, capex_brl)
    )

    # Sort by eligibility score descending
    matches.sort(key=lambda m: m.eligibility_score, reverse=True)

    logger.info(
        "Funding match for municipality %s (%s, pop %d): %d programs evaluated, "
        "top match: %s (%.0f%%)",
        municipality_code,
        state_code,
        municipality_population,
        len(matches),
        matches[0].program.name if matches else "none",
        matches[0].eligibility_score if matches else 0,
    )

    return matches


def get_all_programs() -> list[FundingProgram]:
    """List all tracked funding programs.

    Returns:
        List of all FundingProgram entries.
    """
    return list(FUNDING_PROGRAMS)
