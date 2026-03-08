"""ISP regulatory profile analyzer.

Cross-references ISP characteristics (state, size, services, revenue)
against all applicable regulations to produce a comprehensive compliance
dashboard.  This is the main entry point for regulatory compliance
assessment.

Compliance checks performed:
    1. Norma no. 4 readiness (SVA -> SCM transition + ICMS impact)
    2. Licensing status (5,000-subscriber threshold)
    3. Quality standard compliance (Res. 717/2019 IDA metrics)
    4. Consumer protection requirements (Res. 632/2014)
    5. LGPD data protection compliance
    6. Cybersecurity requirements (Res. 740/2020)
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from python.regulatory.knowledge_base.regulations import (
    REGULATIONS,
    get_regulation,
    get_regulations_by_size,
    RegulatoryStatus,
)
from python.regulatory.knowledge_base.deadlines import (
    days_until,
    get_deadlines_by_regulation,
    get_urgency,
)
from python.regulatory.analyzer.norma4 import (
    NORMA4_DEADLINE,
    calculate_impact as norma4_calculate_impact,
)
from python.regulatory.analyzer.licensing import (
    LICENSING_THRESHOLD,
    check_licensing,
)
from python.regulatory.analyzer.quality import (
    QUALITY_THRESHOLDS,
    QUALITY_REPORTING_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class ComplianceCheck:
    """Result of a single regulatory compliance check.

    Attributes:
        regulation_id: Short ID of the regulation checked.
        regulation_name: Human-readable regulation name.
        status: Compliance status ('compliant', 'at_risk', 'non_compliant', 'unknown').
        description: Summary of the compliance finding.
        action_items: Specific actions needed for compliance.
        deadline: Nearest applicable deadline, or None.
        estimated_cost_brl: Estimated cost of compliance in BRL, or None.
        priority: Priority ranking (1 = highest).
        urgency: Urgency level ('critical', 'warning', 'info').
    """
    regulation_id: str
    regulation_name: str
    status: str
    description: str
    action_items: list[str] = field(default_factory=list)
    deadline: Optional[date] = None
    estimated_cost_brl: Optional[float] = None
    priority: int = 99
    urgency: str = "info"


@dataclass
class ComplianceProfile:
    """Complete compliance profile for an ISP.

    Attributes:
        provider_id: Internal provider identifier, or None.
        provider_name: ISP name.
        state_codes: Brazilian UF codes where the ISP operates.
        subscriber_count: Total number of subscribers.
        checks: List of compliance checks performed.
        overall_score: Compliance score from 0 to 100 (100 = fully compliant).
        critical_issues: Count of non-compliant / at-risk items with critical urgency.
        warnings: Count of warning-level issues.
        estimated_total_cost_brl: Sum of all estimated compliance costs.
        summary: Human-readable compliance summary.
    """
    provider_id: Optional[int] = None
    provider_name: str = ""
    state_codes: list[str] = field(default_factory=list)
    subscriber_count: int = 0
    checks: list[ComplianceCheck] = field(default_factory=list)
    overall_score: float = 0.0
    critical_issues: int = 0
    warnings: int = 0
    estimated_total_cost_brl: float = 0.0
    summary: str = ""


def analyze_profile(
    provider_name: str,
    state_codes: list[str],
    subscriber_count: int,
    services: list[str],
    current_classification: str = "SVA",
    monthly_revenue_brl: Optional[float] = None,
    provider_id: Optional[int] = None,
    quality_metrics: Optional[dict[str, float]] = None,
    has_dpo: bool = False,
    has_cybersecurity_policy: bool = False,
) -> ComplianceProfile:
    """Analyze ISP compliance profile against all applicable regulations.

    This is the main entry point for regulatory compliance assessment.
    It runs all applicable checks and produces a comprehensive profile.

    Args:
        provider_name: ISP name.
        state_codes: List of UF codes where the ISP operates.
        subscriber_count: Total number of active subscribers.
        services: List of service types (e.g. ['SCM', 'broadband']).
        current_classification: Current service classification ('SVA' or 'SCM').
        monthly_revenue_brl: Total monthly broadband revenue in BRL.
        provider_id: Optional internal provider identifier.
        quality_metrics: Optional dict of quality metric values for assessment.
        has_dpo: Whether the ISP has appointed a Data Protection Officer.
        has_cybersecurity_policy: Whether the ISP has a cybersecurity policy.

    Returns:
        ComplianceProfile with all checks, scores, and recommendations.
    """
    logger.info(
        "Analyzing compliance profile for '%s' (%d subs, states=%s, classification=%s)",
        provider_name,
        subscriber_count,
        state_codes,
        current_classification,
    )

    checks: list[ComplianceCheck] = []

    # --- Check 1: Norma no. 4 readiness ---
    norma4_check = _check_norma4(
        state_codes=state_codes,
        subscriber_count=subscriber_count,
        current_classification=current_classification,
        monthly_revenue_brl=monthly_revenue_brl,
    )
    checks.append(norma4_check)

    # --- Check 2: Licensing threshold ---
    licensing_check = _check_licensing(
        subscriber_count=subscriber_count,
        services=services,
        monthly_revenue_brl=monthly_revenue_brl,
    )
    checks.append(licensing_check)

    # --- Check 3: Quality standards ---
    quality_check = _check_quality(
        subscriber_count=subscriber_count,
        quality_metrics=quality_metrics,
    )
    checks.append(quality_check)

    # --- Check 4: Consumer protection ---
    consumer_check = _check_consumer_protection(
        subscriber_count=subscriber_count,
        current_classification=current_classification,
    )
    checks.append(consumer_check)

    # --- Check 5: LGPD data protection ---
    lgpd_check = _check_lgpd(
        subscriber_count=subscriber_count,
        has_dpo=has_dpo,
    )
    checks.append(lgpd_check)

    # --- Check 6: Cybersecurity ---
    cyber_check = _check_cybersecurity(
        subscriber_count=subscriber_count,
        has_cybersecurity_policy=has_cybersecurity_policy,
    )
    checks.append(cyber_check)

    # Sort checks by priority (lowest number = highest priority)
    checks.sort(key=lambda c: c.priority)

    # Compute aggregate metrics
    critical_count = sum(
        1 for c in checks
        if c.status in ("non_compliant", "at_risk") and c.urgency == "critical"
    )
    warning_count = sum(
        1 for c in checks
        if c.status == "at_risk" and c.urgency == "warning"
    )
    total_cost = sum(c.estimated_cost_brl or 0 for c in checks)
    overall_score = _compute_overall_score(checks)

    # Generate summary
    summary = _generate_summary(
        provider_name=provider_name,
        checks=checks,
        overall_score=overall_score,
        critical_count=critical_count,
        warning_count=warning_count,
    )

    profile = ComplianceProfile(
        provider_id=provider_id,
        provider_name=provider_name,
        state_codes=state_codes,
        subscriber_count=subscriber_count,
        checks=checks,
        overall_score=overall_score,
        critical_issues=critical_count,
        warnings=warning_count,
        estimated_total_cost_brl=round(total_cost, 2),
        summary=summary,
    )

    logger.info(
        "Compliance profile for '%s': score=%.1f, critical=%d, warnings=%d, "
        "estimated cost=R$%.2f",
        provider_name,
        overall_score,
        critical_count,
        warning_count,
        total_cost,
    )
    return profile


# ---------------------------------------------------------------------------
# Individual compliance checks
# ---------------------------------------------------------------------------

def _check_norma4(
    state_codes: list[str],
    subscriber_count: int,
    current_classification: str,
    monthly_revenue_brl: Optional[float],
) -> ComplianceCheck:
    """Check Norma no. 4 SVA->SCM transition readiness."""

    remaining_days = days_until(NORMA4_DEADLINE)
    urgency = get_urgency(NORMA4_DEADLINE)

    if current_classification.upper() == "SCM":
        return ComplianceCheck(
            regulation_id="norma4",
            regulation_name="Norma no. 4 — SVA para SCM",
            status="compliant",
            description=(
                "ISP is already classified as SCM. Norma no. 4 transition "
                "requirements are satisfied."
            ),
            action_items=["Verify ICMS collection is operational across all states"],
            deadline=NORMA4_DEADLINE,
            estimated_cost_brl=0.0,
            priority=2,
            urgency="info",
        )

    # SVA -> needs transition
    action_items = [
        "Begin SCM registration process with Anatel",
        "Adapt billing systems for ICMS calculation",
        "Update customer contracts for SCM classification",
        "Implement ICMS nota fiscal eletronica integration",
        "Prepare quarterly quality reports (IDA format)",
    ]

    # Estimate cost
    estimated_cost = 0.0
    if monthly_revenue_brl and state_codes:
        # ICMS impact for first year
        for code in state_codes:
            try:
                impact = norma4_calculate_impact(
                    code,
                    monthly_revenue_brl / len(state_codes),
                    subscriber_count // len(state_codes),
                    current_classification,
                )
                estimated_cost += impact.additional_annual_tax_brl
            except ValueError:
                logger.warning("Could not calculate Norma4 impact for state %s", code)

    # Add system adaptation costs
    system_adaptation_cost = 50_000  # Billing, reporting systems
    estimated_cost += system_adaptation_cost

    if remaining_days <= 0:
        status = "non_compliant"
        description = (
            f"OVERDUE: Norma no. 4 deadline has passed ({abs(remaining_days)} days ago). "
            f"Immediate action required to transition from SVA to SCM."
        )
    elif remaining_days <= 180:
        status = "at_risk"
        description = (
            f"CRITICAL: Only {remaining_days} days remaining until Norma no. 4 deadline. "
            f"ISP is still classified as SVA and must transition to SCM."
        )
    else:
        status = "at_risk"
        description = (
            f"{remaining_days} days remaining until Norma no. 4 deadline "
            f"({NORMA4_DEADLINE.isoformat()}). ISP must transition from SVA to SCM. "
            f"Estimated annual ICMS impact across {len(state_codes)} state(s)."
        )

    return ComplianceCheck(
        regulation_id="norma4",
        regulation_name="Norma no. 4 — SVA para SCM",
        status=status,
        description=description,
        action_items=action_items,
        deadline=NORMA4_DEADLINE,
        estimated_cost_brl=round(estimated_cost, 2),
        priority=1,  # Highest priority
        urgency=urgency,
    )


def _check_licensing(
    subscriber_count: int,
    services: list[str],
    monthly_revenue_brl: Optional[float],
) -> ComplianceCheck:
    """Check licensing threshold requirements."""

    lic_status = check_licensing(
        subscriber_count=subscriber_count,
        services=services,
        monthly_revenue_brl=monthly_revenue_brl,
    )

    if lic_status.above_threshold:
        return ComplianceCheck(
            regulation_id="res614",
            regulation_name="Resolução 614 — Licenciamento SCM",
            status="at_risk",
            description=(
                f"ISP has {subscriber_count:,} subscribers, exceeding the "
                f"{LICENSING_THRESHOLD:,} threshold. Autorização de SCM required."
            ),
            action_items=[
                "Apply for Autorização de SCM at Anatel",
                "Prepare technical and financial documentation",
                "Budget for annual TFF (Taxa de Fiscalização de Funcionamento)",
            ] + lic_status.requirements[:3],
            deadline=None,  # No specific deadline, but ongoing obligation
            estimated_cost_brl=lic_status.estimated_licensing_cost_brl + lic_status.estimated_annual_cost_brl,
            priority=2,
            urgency="critical" if lic_status.urgency == "immediate" else "warning",
        )
    elif lic_status.urgency == "approaching":
        return ComplianceCheck(
            regulation_id="res614",
            regulation_name="Resolução 614 — Licenciamento SCM",
            status="at_risk",
            description=(
                f"ISP is at {lic_status.pct_of_threshold:.0f}% of the "
                f"{LICENSING_THRESHOLD:,} subscriber threshold "
                f"({lic_status.subscribers_until_threshold:,} remaining). "
                f"Prepare for Autorização requirements."
            ),
            action_items=[
                "Begin preparing Autorização documentation proactively",
                f"Budget R${lic_status.estimated_licensing_cost_brl:,.0f} for licensing costs",
                "Monitor subscriber growth rate",
            ],
            deadline=None,
            estimated_cost_brl=0.0,  # No cost yet until threshold is crossed
            priority=4,
            urgency="warning",
        )
    else:
        return ComplianceCheck(
            regulation_id="res614",
            regulation_name="Resolução 614 — Licenciamento SCM",
            status="compliant",
            description=(
                f"ISP has {subscriber_count:,} subscribers, well below the "
                f"{LICENSING_THRESHOLD:,} threshold. Comunicação Prévia suffices."
            ),
            action_items=["Maintain current Comunicação Prévia registration"],
            deadline=None,
            estimated_cost_brl=0.0,
            priority=8,
            urgency="info",
        )


def _check_quality(
    subscriber_count: int,
    quality_metrics: Optional[dict[str, float]],
) -> ComplianceCheck:
    """Check quality standard compliance (Res. 717/2019)."""

    requires_reporting = subscriber_count >= QUALITY_REPORTING_THRESHOLD

    if quality_metrics is None:
        # No quality data provided — status unknown
        if requires_reporting:
            return ComplianceCheck(
                regulation_id="res717",
                regulation_name="Resolução 717 — Qualidade do SCM",
                status="unknown",
                description=(
                    f"ISP has {subscriber_count:,} subscribers (above {QUALITY_REPORTING_THRESHOLD:,} "
                    f"threshold) and is required to submit quarterly quality reports. "
                    f"No quality metrics were provided for assessment."
                ),
                action_items=[
                    "Implement quality measurement systems (speed, latency, availability)",
                    "Register in Anatel SIQ system for quarterly reporting",
                    "Establish internal quality monitoring dashboards",
                ],
                deadline=None,
                estimated_cost_brl=25_000,  # Quality monitoring systems
                priority=3,
                urgency="warning",
            )
        else:
            return ComplianceCheck(
                regulation_id="res717",
                regulation_name="Resolução 717 — Qualidade do SCM",
                status="compliant",
                description=(
                    f"ISP has {subscriber_count:,} subscribers (below "
                    f"{QUALITY_REPORTING_THRESHOLD:,} threshold). Quarterly quality "
                    f"reporting is not mandatory but recommended."
                ),
                action_items=["Consider voluntary quality monitoring"],
                deadline=None,
                estimated_cost_brl=0.0,
                priority=7,
                urgency="info",
            )

    # Assess provided quality metrics
    violations = []
    warnings = []
    for metric_key, threshold in QUALITY_THRESHOLDS.items():
        measured = quality_metrics.get(metric_key)
        if measured is None:
            continue
        if measured < threshold:
            violations.append(f"{metric_key}: {measured:.1f} (min: {threshold:.1f})")
        elif measured < threshold + 5:
            warnings.append(f"{metric_key}: {measured:.1f} (min: {threshold:.1f})")

    if violations:
        return ComplianceCheck(
            regulation_id="res717",
            regulation_name="Resolução 717 — Qualidade do SCM",
            status="non_compliant",
            description=(
                f"Quality metrics below Anatel thresholds: {'; '.join(violations)}"
            ),
            action_items=[
                "Investigate and remediate quality violations immediately",
                "Submit improvement plan to Anatel if required",
                "Increase network monitoring and capacity",
            ],
            deadline=None,
            estimated_cost_brl=50_000,  # Network improvements estimate
            priority=3,
            urgency="critical" if requires_reporting else "warning",
        )
    elif warnings:
        return ComplianceCheck(
            regulation_id="res717",
            regulation_name="Resolução 717 — Qualidade do SCM",
            status="at_risk",
            description=(
                f"Quality metrics near Anatel thresholds: {'; '.join(warnings)}"
            ),
            action_items=[
                "Monitor quality metrics closely",
                "Plan capacity upgrades to maintain headroom above thresholds",
            ],
            deadline=None,
            estimated_cost_brl=15_000,
            priority=5,
            urgency="warning",
        )
    else:
        return ComplianceCheck(
            regulation_id="res717",
            regulation_name="Resolução 717 — Qualidade do SCM",
            status="compliant",
            description="All measured quality metrics meet or exceed Anatel thresholds.",
            action_items=["Continue monitoring and maintain quality levels"],
            deadline=None,
            estimated_cost_brl=0.0,
            priority=7,
            urgency="info",
        )


def _check_consumer_protection(
    subscriber_count: int,
    current_classification: str,
) -> ComplianceCheck:
    """Check consumer protection requirements (Res. 632/2014)."""

    if current_classification.upper() == "SVA":
        return ComplianceCheck(
            regulation_id="res632",
            regulation_name="Resolução 632 — Proteção do Consumidor",
            status="at_risk",
            description=(
                "Under SVA classification, Res. 632 consumer protection rules "
                "were not mandatory. After Norma no. 4 reclassification to SCM, "
                "full compliance with consumer protection regulations is required."
            ),
            action_items=[
                "Implement complaint handling system with protocol numbers",
                "Create transparent pricing and contract terms",
                "Establish customer service SLAs (5 business days for Anatel complaints)",
                "Offer at least 3 plan tiers including entry-level option",
                "Implement 30-day advance notice for contract changes",
                "Set up cancellation process without undue obstacles",
            ],
            deadline=NORMA4_DEADLINE,
            estimated_cost_brl=20_000,
            priority=4,
            urgency="warning",
        )
    else:
        # Already SCM — check should be ongoing
        return ComplianceCheck(
            regulation_id="res632",
            regulation_name="Resolução 632 — Proteção do Consumidor",
            status="compliant",
            description=(
                "ISP is classified as SCM and subject to Res. 632 consumer "
                "protection rules. Ongoing compliance monitoring recommended."
            ),
            action_items=[
                "Regularly audit complaint resolution SLAs",
                "Review contract transparency quarterly",
            ],
            deadline=None,
            estimated_cost_brl=0.0,
            priority=6,
            urgency="info",
        )


def _check_lgpd(
    subscriber_count: int,
    has_dpo: bool,
) -> ComplianceCheck:
    """Check LGPD data protection compliance."""

    action_items = []
    issues = []

    if not has_dpo:
        issues.append("No DPO (Encarregado de Proteção de Dados) appointed")
        action_items.append("Appoint a Data Protection Officer (DPO/Encarregado)")

    # All ISPs must comply with LGPD
    base_actions = [
        "Implement subscriber consent management system",
        "Maintain Records of Processing Activities (ROPA)",
        "Establish data breach notification procedures (72h to ANPD)",
        "Implement data subject rights request handling",
        "Conduct Data Protection Impact Assessment (DPIA/RIPD)",
    ]

    if issues:
        return ComplianceCheck(
            regulation_id="lgpd",
            regulation_name="LGPD — Proteção de Dados Pessoais",
            status="at_risk",
            description=(
                f"LGPD compliance gaps identified: {'; '.join(issues)}. "
                f"With {subscriber_count:,} subscribers' personal data, "
                f"LGPD compliance is essential."
            ),
            action_items=action_items + base_actions,
            deadline=None,  # LGPD is already in effect
            estimated_cost_brl=30_000,  # DPO + systems
            priority=4,
            urgency="warning",
        )
    else:
        return ComplianceCheck(
            regulation_id="lgpd",
            regulation_name="LGPD — Proteção de Dados Pessoais",
            status="compliant",
            description=(
                "DPO is appointed. Verify ongoing LGPD compliance including "
                "consent management, ROPA, and breach notification procedures."
            ),
            action_items=["Conduct annual LGPD compliance audit"],
            deadline=None,
            estimated_cost_brl=0.0,
            priority=6,
            urgency="info",
        )


def _check_cybersecurity(
    subscriber_count: int,
    has_cybersecurity_policy: bool,
) -> ComplianceCheck:
    """Check cybersecurity requirements (Res. 740/2020)."""

    action_items = []
    issues = []

    if not has_cybersecurity_policy:
        issues.append("No cybersecurity policy (Norma de Segurança Cibernética) in place")
        action_items.append(
            "Develop and implement a Cybersecurity Policy per Res. 740/2020"
        )

    base_actions = [
        "Implement security incident response procedures",
        "Establish Anatel incident notification process (24h for critical incidents)",
        "Conduct periodic vulnerability assessments",
        "Maintain security logs and audit trails (1-year retention)",
        "Designate a cybersecurity officer",
    ]

    if issues:
        return ComplianceCheck(
            regulation_id="res740",
            regulation_name="Resolução 740 — Segurança Cibernética",
            status="at_risk",
            description=(
                f"Cybersecurity compliance gaps: {'; '.join(issues)}. "
                f"Res. 740/2020 requires all telecom providers to maintain "
                f"cybersecurity policies and incident response procedures."
            ),
            action_items=action_items + base_actions,
            deadline=None,
            estimated_cost_brl=40_000,  # Policy development + security tools
            priority=5,
            urgency="warning",
        )
    else:
        return ComplianceCheck(
            regulation_id="res740",
            regulation_name="Resolução 740 — Segurança Cibernética",
            status="compliant",
            description=(
                "Cybersecurity policy is in place. Verify ongoing compliance "
                "including incident response readiness and vulnerability management."
            ),
            action_items=["Conduct annual cybersecurity policy review and testing"],
            deadline=None,
            estimated_cost_brl=0.0,
            priority=7,
            urgency="info",
        )


# ---------------------------------------------------------------------------
# Scoring and summary
# ---------------------------------------------------------------------------

def _compute_overall_score(checks: list[ComplianceCheck]) -> float:
    """Compute an overall compliance score from 0 to 100.

    Scoring:
        - compliant: 100 points
        - at_risk: 50 points
        - non_compliant: 0 points
        - unknown: 30 points

    Weighted by priority (higher priority = more weight).

    Args:
        checks: List of ComplianceCheck objects.

    Returns:
        Overall score from 0 to 100.
    """
    if not checks:
        return 0.0

    status_scores = {
        "compliant": 100,
        "at_risk": 50,
        "non_compliant": 0,
        "unknown": 30,
    }

    # Weight by inverse priority (priority 1 = weight 10, priority 10 = weight 1)
    total_weight = 0.0
    weighted_sum = 0.0

    for check in checks:
        weight = max(1, 11 - check.priority)
        score = status_scores.get(check.status, 30)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight <= 0:
        return 0.0

    return round(weighted_sum / total_weight, 1)


def _generate_summary(
    provider_name: str,
    checks: list[ComplianceCheck],
    overall_score: float,
    critical_count: int,
    warning_count: int,
) -> str:
    """Generate a human-readable compliance summary.

    Args:
        provider_name: ISP name.
        checks: List of ComplianceCheck objects.
        overall_score: Computed overall score.
        critical_count: Number of critical issues.
        warning_count: Number of warnings.

    Returns:
        Multi-line summary string.
    """
    total = len(checks)
    compliant = sum(1 for c in checks if c.status == "compliant")
    at_risk = sum(1 for c in checks if c.status == "at_risk")
    non_compliant = sum(1 for c in checks if c.status == "non_compliant")
    unknown = sum(1 for c in checks if c.status == "unknown")

    lines = [
        f"Compliance Profile: {provider_name}",
        f"Overall Score: {overall_score:.0f}/100",
        f"Checks: {total} total — {compliant} compliant, {at_risk} at risk, "
        f"{non_compliant} non-compliant, {unknown} unknown",
    ]

    if critical_count > 0:
        lines.append(f"CRITICAL ISSUES: {critical_count} — immediate action required")

    if warning_count > 0:
        lines.append(f"Warnings: {warning_count} — attention needed")

    # List non-compliant and at-risk items
    urgent_checks = [
        c for c in checks if c.status in ("non_compliant", "at_risk")
    ]
    if urgent_checks:
        lines.append("")
        lines.append("Priority actions:")
        for i, check in enumerate(urgent_checks, 1):
            status_label = "NON-COMPLIANT" if check.status == "non_compliant" else "AT RISK"
            lines.append(f"  {i}. [{status_label}] {check.regulation_name}")
            if check.action_items:
                lines.append(f"     -> {check.action_items[0]}")
            if check.deadline:
                lines.append(f"     Deadline: {check.deadline.isoformat()}")

    return "\n".join(lines)
