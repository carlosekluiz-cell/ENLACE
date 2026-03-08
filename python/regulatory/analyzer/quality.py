"""Quality standard compliance checker for SCM providers.

Validates ISP quality metrics against Anatel regulatory thresholds
defined in Resolution 717/2019 (Regulamento de Qualidade dos Serviços
de Telecomunicações).

Key quality indicators monitored:
    - Download speed compliance (% of contracted speed delivered)
    - Upload speed compliance (% of contracted speed delivered)
    - Latency compliance (% of measurements within threshold)
    - Network availability (uptime %)
    - IDA composite score (customer experience index)

ISPs with 5,000+ subscribers must submit quarterly reports via
Anatel's SIQ (Sistema de Indicadores de Qualidade) system.

Sources:
    - Resolution 717/2019 (Regulamento de Qualidade)
    - Anatel SIQ reporting guidelines
    - Abrint quality benchmark studies
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimum quality thresholds from Anatel Regulamento de Qualidade
# ---------------------------------------------------------------------------
QUALITY_THRESHOLDS: dict[str, float] = {
    "download_speed_compliance_pct": 80.0,
    "upload_speed_compliance_pct": 80.0,
    "latency_compliance_pct": 95.0,
    "availability_pct": 99.0,
    "ida_score_min": 6.0,
}

# Descriptive labels for each metric
METRIC_LABELS: dict[str, str] = {
    "download_speed_compliance_pct": "Download speed compliance",
    "upload_speed_compliance_pct": "Upload speed compliance",
    "latency_compliance_pct": "Latency compliance",
    "availability_pct": "Network availability",
    "ida_score_min": "IDA composite score",
}

# Warning zone: if metric is within this many percentage points of the
# threshold, issue a warning even if technically compliant
WARNING_MARGIN_PCT = 5.0

# Subscriber threshold for mandatory quality reporting
QUALITY_REPORTING_THRESHOLD = 5000


@dataclass
class QualityViolation:
    """A single quality threshold violation.

    Attributes:
        metric: The metric that is in violation.
        label: Human-readable label for the metric.
        measured_value: The ISP's measured value.
        threshold: The regulatory minimum.
        gap: How far below the threshold the ISP is.
        severity: 'violation' (below threshold) or 'warning' (close to threshold).
        recommendation: Suggested remediation action.
    """
    metric: str
    label: str
    measured_value: float
    threshold: float
    gap: float
    severity: str
    recommendation: str


@dataclass
class QualityStatus:
    """Quality compliance status for a single municipality or aggregate.

    Attributes:
        municipality_id: Municipality identifier (0 if aggregate/unknown).
        municipality_name: Municipality name.
        metrics: Dict of metric name to measured value.
        thresholds: Dict of metric name to regulatory threshold.
        compliant: Whether all metrics meet or exceed thresholds.
        violations: List of QualityViolation objects.
        risk_level: 'compliant', 'warning', or 'violation'.
        overall_score: Normalized quality score (0-100).
        requires_reporting: Whether the ISP must report to Anatel SIQ.
    """
    municipality_id: int = 0
    municipality_name: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    compliant: bool = True
    violations: list[QualityViolation] = field(default_factory=list)
    risk_level: str = "compliant"
    overall_score: float = 100.0
    requires_reporting: bool = False


def check_quality(
    metrics: dict[str, float],
    municipality_id: int = 0,
    municipality_name: str = "",
    subscriber_count: int = 0,
) -> QualityStatus:
    """Check quality metrics against Anatel thresholds.

    Args:
        metrics: Dictionary of metric name to measured value.
            Expected keys:
                - download_speed_compliance_pct (0-100)
                - upload_speed_compliance_pct (0-100)
                - latency_compliance_pct (0-100)
                - availability_pct (0-100)
                - ida_score_min (0-10)
        municipality_id: Optional municipality identifier.
        municipality_name: Optional municipality name.
        subscriber_count: Subscriber count in this municipality/area.

    Returns:
        QualityStatus with compliance assessment.
    """
    violations = []
    all_compliant = True
    has_warnings = False

    for metric_key, threshold in QUALITY_THRESHOLDS.items():
        measured = metrics.get(metric_key)
        if measured is None:
            # Metric not provided — cannot assess
            logger.debug(
                "Quality metric '%s' not provided for municipality %s",
                metric_key,
                municipality_name or municipality_id,
            )
            continue

        label = METRIC_LABELS.get(metric_key, metric_key)

        if measured < threshold:
            # Violation: below minimum threshold
            gap = threshold - measured
            violations.append(QualityViolation(
                metric=metric_key,
                label=label,
                measured_value=round(measured, 2),
                threshold=threshold,
                gap=round(gap, 2),
                severity="violation",
                recommendation=_get_recommendation(metric_key, measured, threshold),
            ))
            all_compliant = False

        elif measured < threshold + WARNING_MARGIN_PCT:
            # Warning zone: technically compliant but close to the line
            gap = threshold - measured  # Will be negative (above threshold)
            violations.append(QualityViolation(
                metric=metric_key,
                label=label,
                measured_value=round(measured, 2),
                threshold=threshold,
                gap=round(gap, 2),
                severity="warning",
                recommendation=_get_recommendation(metric_key, measured, threshold),
            ))
            has_warnings = True

    # Determine risk level
    if not all_compliant:
        risk_level = "violation"
    elif has_warnings:
        risk_level = "warning"
    else:
        risk_level = "compliant"

    # Compute overall quality score (0-100)
    overall_score = _compute_quality_score(metrics)

    # Reporting requirement
    requires_reporting = subscriber_count >= QUALITY_REPORTING_THRESHOLD

    status = QualityStatus(
        municipality_id=municipality_id,
        municipality_name=municipality_name,
        metrics={k: round(v, 2) for k, v in metrics.items()},
        thresholds=dict(QUALITY_THRESHOLDS),
        compliant=all_compliant,
        violations=violations,
        risk_level=risk_level,
        overall_score=round(overall_score, 1),
        requires_reporting=requires_reporting,
    )

    logger.info(
        "Quality check for %s: %s (score=%.1f, %d violations, %d warnings)",
        municipality_name or f"municipality {municipality_id}",
        risk_level,
        overall_score,
        sum(1 for v in violations if v.severity == "violation"),
        sum(1 for v in violations if v.severity == "warning"),
    )
    return status


def check_quality_multi(
    provider_metrics: list[dict],
    subscriber_count: int = 0,
) -> list[QualityStatus]:
    """Check quality across multiple municipalities for a provider.

    Args:
        provider_metrics: List of dicts, each containing:
            - municipality_id: int
            - municipality_name: str (optional)
            - metrics: dict of metric values
        subscriber_count: Total subscriber count (for reporting threshold).

    Returns:
        List of QualityStatus objects, one per municipality.
    """
    results = []
    for entry in provider_metrics:
        status = check_quality(
            metrics=entry.get("metrics", {}),
            municipality_id=entry.get("municipality_id", 0),
            municipality_name=entry.get("municipality_name", ""),
            subscriber_count=subscriber_count,
        )
        results.append(status)

    # Sort: violations first, then warnings, then compliant
    severity_order = {"violation": 0, "warning": 1, "compliant": 2}
    results.sort(key=lambda s: severity_order.get(s.risk_level, 3))

    logger.info(
        "Quality check across %d municipalities: %d violations, %d warnings, %d compliant",
        len(results),
        sum(1 for s in results if s.risk_level == "violation"),
        sum(1 for s in results if s.risk_level == "warning"),
        sum(1 for s in results if s.risk_level == "compliant"),
    )
    return results


def _compute_quality_score(metrics: dict[str, float]) -> float:
    """Compute a normalized quality score from 0 to 100.

    Each metric contributes proportionally based on how far above or
    below its threshold it is. A score of 100 means all metrics are at
    or above their thresholds.

    Args:
        metrics: Dictionary of metric values.

    Returns:
        Quality score from 0 to 100.
    """
    if not metrics:
        return 0.0

    scores = []
    weights = {
        "download_speed_compliance_pct": 0.25,
        "upload_speed_compliance_pct": 0.20,
        "latency_compliance_pct": 0.20,
        "availability_pct": 0.20,
        "ida_score_min": 0.15,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for metric_key, threshold in QUALITY_THRESHOLDS.items():
        measured = metrics.get(metric_key)
        if measured is None:
            continue

        weight = weights.get(metric_key, 0.2)
        total_weight += weight

        # For most metrics, the score is (measured / threshold) capped at 1.0
        # For IDA score, threshold is 6.0 and max is 10.0
        if metric_key == "ida_score_min":
            # Scale IDA: 0=0%, 6=threshold(~80%), 10=100%
            metric_score = min(100, (measured / 10.0) * 100)
        else:
            # For percentage metrics: 80% threshold -> 100% score at threshold
            if threshold > 0:
                ratio = measured / threshold
                metric_score = min(100, ratio * 100)
            else:
                metric_score = 100

        weighted_sum += metric_score * weight

    if total_weight <= 0:
        return 0.0

    return weighted_sum / total_weight


def _get_recommendation(
    metric_key: str,
    measured: float,
    threshold: float,
) -> str:
    """Generate a remediation recommendation for a quality metric.

    Args:
        metric_key: The metric identifier.
        measured: Measured value.
        threshold: Regulatory threshold.

    Returns:
        Recommendation string.
    """
    gap = threshold - measured

    recommendations = {
        "download_speed_compliance_pct": (
            f"Download speed compliance is {measured:.1f}% vs {threshold:.1f}% minimum. "
            f"Review network capacity planning, check for congestion points, "
            f"and verify speed provisioning profiles. "
            f"Need to improve by {gap:.1f} percentage points."
            if gap > 0 else
            f"Download speed compliance at {measured:.1f}% is within {abs(gap):.1f}pp of "
            f"the {threshold:.1f}% threshold. Monitor closely and maintain headroom."
        ),
        "upload_speed_compliance_pct": (
            f"Upload speed compliance is {measured:.1f}% vs {threshold:.1f}% minimum. "
            f"Check upstream bandwidth allocation and verify symmetric/asymmetric "
            f"plan configurations."
            if gap > 0 else
            f"Upload speed compliance at {measured:.1f}% is within {abs(gap):.1f}pp of "
            f"the {threshold:.1f}% threshold. Continue monitoring."
        ),
        "latency_compliance_pct": (
            f"Latency compliance is {measured:.1f}% vs {threshold:.1f}% minimum. "
            f"Investigate routing inefficiencies, check for bufferbloat, "
            f"review peering/transit arrangements, and verify CPE quality."
            if gap > 0 else
            f"Latency compliance at {measured:.1f}% is near the {threshold:.1f}% "
            f"threshold. Monitor and optimize routing paths."
        ),
        "availability_pct": (
            f"Network availability is {measured:.2f}% vs {threshold:.2f}% minimum. "
            f"Review redundancy architecture, implement failover mechanisms, "
            f"and investigate root causes of recent outages. "
            f"A {gap:.2f}pp gap translates to ~{gap * 0.01 * 30 * 24 * 60:.0f} "
            f"additional minutes of downtime per month."
            if gap > 0 else
            f"Availability at {measured:.2f}% is within {abs(gap):.2f}pp of the "
            f"{threshold:.2f}% threshold. Maintain redundancy and monitoring."
        ),
        "ida_score_min": (
            f"IDA score is {measured:.1f} vs {threshold:.1f} minimum. "
            f"Focus on customer service responsiveness, complaint resolution "
            f"time, and first-call resolution rate. Consider customer "
            f"experience training for support staff."
            if gap > 0 else
            f"IDA score at {measured:.1f} is close to the {threshold:.1f} minimum. "
            f"Continue improving customer experience metrics."
        ),
    }

    return recommendations.get(
        metric_key,
        f"Metric '{metric_key}' is at {measured:.1f} vs threshold {threshold:.1f}. "
        f"Review and improve."
    )


def get_quality_summary(statuses: list[QualityStatus]) -> dict:
    """Generate an aggregate quality summary across multiple municipalities.

    Args:
        statuses: List of QualityStatus objects.

    Returns:
        Dictionary with aggregate quality statistics.
    """
    if not statuses:
        return {
            "total_municipalities": 0,
            "compliant": 0,
            "warning": 0,
            "violation": 0,
            "average_score": 0.0,
            "worst_municipality": None,
            "most_common_violation": None,
        }

    compliant_count = sum(1 for s in statuses if s.risk_level == "compliant")
    warning_count = sum(1 for s in statuses if s.risk_level == "warning")
    violation_count = sum(1 for s in statuses if s.risk_level == "violation")
    avg_score = sum(s.overall_score for s in statuses) / len(statuses)

    # Find worst municipality
    worst = min(statuses, key=lambda s: s.overall_score)

    # Most common violation metric
    violation_counts: dict[str, int] = {}
    for s in statuses:
        for v in s.violations:
            if v.severity == "violation":
                violation_counts[v.metric] = violation_counts.get(v.metric, 0) + 1

    most_common = None
    if violation_counts:
        most_common_metric = max(violation_counts, key=violation_counts.get)
        most_common = {
            "metric": most_common_metric,
            "label": METRIC_LABELS.get(most_common_metric, most_common_metric),
            "count": violation_counts[most_common_metric],
        }

    return {
        "total_municipalities": len(statuses),
        "compliant": compliant_count,
        "warning": warning_count,
        "violation": violation_count,
        "compliance_rate_pct": round(compliant_count / len(statuses) * 100, 1),
        "average_score": round(avg_score, 1),
        "worst_municipality": {
            "id": worst.municipality_id,
            "name": worst.municipality_name,
            "score": worst.overall_score,
            "risk_level": worst.risk_level,
        },
        "most_common_violation": most_common,
    }
