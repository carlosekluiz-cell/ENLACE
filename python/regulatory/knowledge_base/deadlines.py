"""Track regulatory deadlines and generate countdown alerts.

Aggregates deadlines from the regulation database and any supplementary
milestones (e.g. interim reporting dates) into a single timeline that
can be queried for urgency and upcoming actions.

Urgency thresholds:
    - critical:  <= 180 days remaining
    - warning:   <= 365 days remaining
    - info:      > 365 days remaining
    - overdue:   deadline has passed
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from python.regulatory.knowledge_base.regulations import REGULATIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Urgency thresholds (days until deadline)
# ---------------------------------------------------------------------------
URGENCY_CRITICAL_DAYS = 180
URGENCY_WARNING_DAYS = 365


# ---------------------------------------------------------------------------
# Core helper functions — defined first so they are available to Deadline
# __post_init__ when module-level constants are constructed below.
# ---------------------------------------------------------------------------

def days_until(deadline_date: date) -> int:
    """Calculate the number of days from today to a deadline.

    Args:
        deadline_date: The target deadline date.

    Returns:
        Positive integer if the deadline is in the future,
        zero if the deadline is today,
        negative integer if the deadline has passed.
    """
    delta = deadline_date - date.today()
    return delta.days


def get_urgency(deadline_date: date) -> str:
    """Determine the urgency level for a given deadline date.

    Args:
        deadline_date: The target deadline date.

    Returns:
        One of 'overdue', 'critical', 'warning', or 'info'.
    """
    remaining = days_until(deadline_date)
    if remaining < 0:
        return "overdue"
    elif remaining <= URGENCY_CRITICAL_DAYS:
        return "critical"
    elif remaining <= URGENCY_WARNING_DAYS:
        return "warning"
    else:
        return "info"


# ---------------------------------------------------------------------------
# Deadline dataclass
# ---------------------------------------------------------------------------

@dataclass
class Deadline:
    """A regulatory deadline with urgency classification.

    Attributes:
        regulation_id: Short ID linking to the parent Regulation.
        name: Human-readable label for the deadline.
        deadline_date: The date by which compliance is required.
        description: What must be done by this date.
        urgency: Computed urgency level ('overdue', 'critical', 'warning', 'info').
        days_remaining: Number of days from today to the deadline.
        milestone: Whether this is an interim milestone (True) or the final deadline (False).
    """
    regulation_id: str
    name: str
    deadline_date: date
    description: str
    urgency: str = ""
    days_remaining: int = 0
    milestone: bool = False

    def __post_init__(self):
        """Compute urgency and days_remaining if not already set."""
        if not self.urgency:
            self.urgency = get_urgency(self.deadline_date)
        self.days_remaining = days_until(self.deadline_date)


# ---------------------------------------------------------------------------
# Supplementary milestones that sit between regulation effective date and
# final deadline.  These are interim compliance steps.
# ---------------------------------------------------------------------------
_SUPPLEMENTARY_DEADLINES: list[Deadline] = [
    Deadline(
        regulation_id="norma4",
        name="Norma no. 4 — Sistema de faturamento ICMS",
        deadline_date=date(2026, 7, 1),
        description=(
            "Billing systems must be adapted to calculate and display ICMS "
            "on customer invoices. Nota fiscal eletronica (NF-e) integration "
            "must be operational."
        ),
        milestone=True,
    ),
    Deadline(
        regulation_id="norma4",
        name="Norma no. 4 — Registro Anatel SCM",
        deadline_date=date(2026, 10, 1),
        description=(
            "ISPs must complete SCM registration with Anatel, including "
            "submission of technical documentation, network topology, and "
            "coverage area declarations."
        ),
        milestone=True,
    ),
    Deadline(
        regulation_id="norma4",
        name="Norma no. 4 — Prazo final de conformidade",
        deadline_date=date(2027, 1, 1),
        description=(
            "Full compliance deadline for SVA-to-SCM transition. All ISPs "
            "must be operating under SCM classification with ICMS collection, "
            "Anatel licensing, and quality reporting in place."
        ),
        milestone=False,
    ),
    Deadline(
        regulation_id="res717",
        name="Relatório trimestral IDA — Q1",
        deadline_date=date(2026, 4, 15),
        description=(
            "Submit Q1 quarterly quality report (IDA metrics) to Anatel "
            "via the SIQ system. Applies to ISPs with >5,000 subscribers."
        ),
        milestone=True,
    ),
    Deadline(
        regulation_id="res717",
        name="Relatório trimestral IDA — Q2",
        deadline_date=date(2026, 7, 15),
        description=(
            "Submit Q2 quarterly quality report (IDA metrics) to Anatel "
            "via the SIQ system."
        ),
        milestone=True,
    ),
    Deadline(
        regulation_id="res717",
        name="Relatório trimestral IDA — Q3",
        deadline_date=date(2026, 10, 15),
        description=(
            "Submit Q3 quarterly quality report (IDA metrics) to Anatel "
            "via the SIQ system."
        ),
        milestone=True,
    ),
    Deadline(
        regulation_id="res717",
        name="Relatório trimestral IDA — Q4",
        deadline_date=date(2027, 1, 15),
        description=(
            "Submit Q4 quarterly quality report (IDA metrics) to Anatel "
            "via the SIQ system."
        ),
        milestone=True,
    ),
]


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def get_all_deadlines() -> list[Deadline]:
    """Get all tracked deadlines, including regulation final deadlines
    and supplementary milestones.

    Returns:
        List of Deadline objects sorted by deadline_date (earliest first).
    """
    all_deadlines = list(_SUPPLEMENTARY_DEADLINES)

    # Add final deadlines from the regulation database for any regulation
    # that has a deadline set and is not already covered by supplementary entries
    supplementary_finals = {
        d.regulation_id
        for d in _SUPPLEMENTARY_DEADLINES
        if not d.milestone
    }
    for reg in REGULATIONS:
        if reg.deadline is not None and reg.id not in supplementary_finals:
            all_deadlines.append(
                Deadline(
                    regulation_id=reg.id,
                    name=f"{reg.name} — Prazo final",
                    deadline_date=reg.deadline,
                    description=f"Final compliance deadline for {reg.full_name}",
                    milestone=False,
                )
            )

    # Recompute urgency and sort
    for d in all_deadlines:
        d.urgency = get_urgency(d.deadline_date)
        d.days_remaining = days_until(d.deadline_date)

    all_deadlines.sort(key=lambda d: d.deadline_date)
    logger.debug("Total tracked deadlines: %d", len(all_deadlines))
    return all_deadlines


def get_upcoming_deadlines(within_days: int = 365) -> list[Deadline]:
    """Get deadlines that fall within the specified number of days.

    Args:
        within_days: Number of days to look ahead (default 365).

    Returns:
        List of Deadline objects within the window, sorted by date.
    """
    today = date.today()
    cutoff = today + timedelta(days=within_days)

    all_dl = get_all_deadlines()
    upcoming = [
        d for d in all_dl
        if today <= d.deadline_date <= cutoff
    ]

    logger.info(
        "Found %d upcoming deadlines in the next %d days",
        len(upcoming),
        within_days,
    )
    return upcoming


def get_overdue_deadlines() -> list[Deadline]:
    """Get all deadlines that have already passed.

    Returns:
        List of overdue Deadline objects, sorted by most recently passed first.
    """
    all_dl = get_all_deadlines()
    overdue = [d for d in all_dl if d.urgency == "overdue"]
    overdue.sort(key=lambda d: d.deadline_date, reverse=True)
    return overdue


def get_deadlines_by_regulation(regulation_id: str) -> list[Deadline]:
    """Get all deadlines (milestones + final) for a specific regulation.

    Args:
        regulation_id: Short regulation ID (e.g. 'norma4').

    Returns:
        List of Deadline objects for that regulation, sorted by date.
    """
    all_dl = get_all_deadlines()
    return [d for d in all_dl if d.regulation_id == regulation_id]


def get_critical_deadlines() -> list[Deadline]:
    """Get all deadlines classified as 'critical' or 'overdue'.

    Returns:
        List of critical/overdue Deadline objects, sorted by date.
    """
    all_dl = get_all_deadlines()
    return [d for d in all_dl if d.urgency in ("critical", "overdue")]


def format_deadline_summary(deadline: Deadline) -> str:
    """Format a deadline as a human-readable summary string.

    Args:
        deadline: The Deadline object to format.

    Returns:
        Formatted string like:
            "[CRITICAL] Norma no. 4 — Prazo final: 297 days remaining (2027-01-01)"
    """
    urgency_label = deadline.urgency.upper()
    if deadline.days_remaining < 0:
        remaining_str = f"{abs(deadline.days_remaining)} days overdue"
    elif deadline.days_remaining == 0:
        remaining_str = "TODAY"
    elif deadline.days_remaining == 1:
        remaining_str = "1 day remaining"
    else:
        remaining_str = f"{deadline.days_remaining} days remaining"

    return (
        f"[{urgency_label}] {deadline.name}: "
        f"{remaining_str} ({deadline.deadline_date.isoformat()})"
    )


def generate_deadline_report() -> str:
    """Generate a full text report of all tracked deadlines.

    Returns:
        Multi-line string with all deadlines grouped by urgency.
    """
    all_dl = get_all_deadlines()
    groups = {"overdue": [], "critical": [], "warning": [], "info": []}
    for d in all_dl:
        groups.get(d.urgency, groups["info"]).append(d)

    lines = ["Regulatory Deadline Report", "=" * 40, ""]

    for urgency in ["overdue", "critical", "warning", "info"]:
        deadlines = groups[urgency]
        if not deadlines:
            continue
        lines.append(f"--- {urgency.upper()} ({len(deadlines)}) ---")
        for d in deadlines:
            lines.append(f"  {format_deadline_summary(d)}")
            lines.append(f"    {d.description}")
            lines.append("")

    report = "\n".join(lines)
    logger.info("Generated deadline report with %d entries", len(all_dl))
    return report
