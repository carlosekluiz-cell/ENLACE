"""PDF report generator for ENLACE platform.

Generates 4 types of reports:
1. Market Analysis Report -- municipality market overview
2. Expansion Opportunity Report -- opportunity scoring + financial viability
3. Compliance Report -- regulatory compliance status
4. Rural Feasibility Report -- rural connectivity design + funding

Uses HTML templates rendered to PDF via WeasyPrint.  When WeasyPrint is
unavailable the raw HTML bytes are returned instead (the caller can
choose a fallback content type).
"""

import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Check for WeasyPrint availability
# ---------------------------------------------------------------------------
_WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML as WeasyHTML  # type: ignore[import-untyped]
    _WEASYPRINT_AVAILABLE = True
    logger.info("WeasyPrint available -- PDF output enabled.")
except ImportError:
    logger.warning(
        "WeasyPrint not installed. Reports will be generated as HTML. "
        "Install with: pip install weasyprint"
    )


# ---------------------------------------------------------------------------
# Report metadata
# ---------------------------------------------------------------------------

@dataclass
class ReportMetadata:
    """Metadata attached to every generated report."""

    report_type: str
    title: str
    generated_at: datetime
    generated_by: str
    version: str = "1.0"


# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

_BASE_CSS = """
/* ENLACE Report Stylesheet */
@page {
    size: A4;
    margin: 20mm 15mm 25mm 15mm;
    @bottom-center {
        content: "ENLACE Platform — Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #666;
    }
}

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #222;
    margin: 0;
    padding: 0;
}

.header {
    border-bottom: 3px solid #1a73e8;
    padding-bottom: 12px;
    margin-bottom: 20px;
}

.header h1 {
    color: #1a73e8;
    font-size: 22pt;
    margin: 0 0 4px 0;
}

.header .subtitle {
    color: #555;
    font-size: 10pt;
}

.header .meta {
    color: #888;
    font-size: 8pt;
    margin-top: 6px;
}

h2 {
    color: #1a73e8;
    font-size: 14pt;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
    margin-top: 24px;
}

h3 {
    color: #333;
    font-size: 12pt;
    margin-top: 16px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9pt;
}

table th {
    background-color: #1a73e8;
    color: white;
    text-align: left;
    padding: 6px 8px;
}

table td {
    padding: 5px 8px;
    border-bottom: 1px solid #eee;
}

table tr:nth-child(even) {
    background-color: #f8f9fa;
}

.summary-box {
    background-color: #e8f0fe;
    border-left: 4px solid #1a73e8;
    padding: 12px 16px;
    margin: 16px 0;
    border-radius: 0 4px 4px 0;
}

.metric-row {
    display: flex;
    gap: 16px;
    margin: 12px 0;
}

.metric-card {
    flex: 1;
    background: #f8f9fa;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 10px;
    text-align: center;
}

.metric-card .value {
    font-size: 18pt;
    font-weight: bold;
    color: #1a73e8;
}

.metric-card .label {
    font-size: 8pt;
    color: #666;
    text-transform: uppercase;
}

.bar-chart {
    margin: 12px 0;
}

.bar-row {
    display: flex;
    align-items: center;
    margin: 4px 0;
}

.bar-label {
    width: 140px;
    font-size: 9pt;
    text-align: right;
    padding-right: 8px;
}

.bar-container {
    flex: 1;
    background: #eee;
    border-radius: 3px;
    height: 18px;
    position: relative;
}

.bar-fill {
    height: 100%;
    border-radius: 3px;
    background: #1a73e8;
    min-width: 2px;
}

.bar-value {
    width: 60px;
    font-size: 9pt;
    padding-left: 8px;
}

.recommendation {
    background: #fef7e0;
    border-left: 4px solid #f9a825;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 0 4px 4px 0;
}

.warning {
    background: #fce8e6;
    border-left: 4px solid #d93025;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 0 4px 4px 0;
}

.footer {
    margin-top: 30px;
    border-top: 1px solid #ddd;
    padding-top: 8px;
    font-size: 7pt;
    color: #999;
    text-align: center;
}
"""


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _html_header(meta: ReportMetadata) -> str:
    """Render the report header block."""
    return f"""
    <div class="header">
        <h1>{meta.title}</h1>
        <div class="subtitle">ENLACE — AI-Powered Telecom Decision Intelligence Platform</div>
        <div class="meta">
            Report type: {meta.report_type} | Generated: {meta.generated_at:%Y-%m-%d %H:%M UTC}
            | By: {meta.generated_by} | Version: {meta.version}
        </div>
    </div>
    """


def _html_footer(meta: ReportMetadata) -> str:
    """Render the report footer block."""
    return f"""
    <div class="footer">
        Generated by ENLACE Platform v{meta.version} on {meta.generated_at:%Y-%m-%d %H:%M UTC}.
        This report is for informational purposes only. Data sources: Anatel, IBGE, BNDES, MCom.
    </div>
    """


def _build_bar_chart(items: list[tuple[str, float]], max_val: float | None = None) -> str:
    """Build a simple horizontal bar chart from (label, value) pairs."""
    if not items:
        return ""
    if max_val is None:
        max_val = max(v for _, v in items) if items else 1
    if max_val == 0:
        max_val = 1

    rows = []
    for label, value in items:
        pct = min(100, (value / max_val) * 100)
        rows.append(f"""
        <div class="bar-row">
            <div class="bar-label">{label}</div>
            <div class="bar-container">
                <div class="bar-fill" style="width: {pct:.1f}%"></div>
            </div>
            <div class="bar-value">{value:,.0f}</div>
        </div>
        """)

    return f'<div class="bar-chart">{"".join(rows)}</div>'


def _render_to_bytes(html: str) -> tuple[bytes, str]:
    """Render HTML string to PDF bytes (or return HTML if WeasyPrint unavailable).

    Returns:
        Tuple of (content_bytes, media_type).
    """
    if _WEASYPRINT_AVAILABLE:
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        return pdf_bytes, "application/pdf"
    else:
        return html.encode("utf-8"), "text/html"


def _format_brl(value: float | None) -> str:
    """Format a number as BRL currency string."""
    if value is None:
        return "N/A"
    return f"R${value:,.2f}"


# ---------------------------------------------------------------------------
# Report: Market Analysis
# ---------------------------------------------------------------------------

def generate_market_report(
    municipality_id: int,
    provider_id: int | None = None,
) -> tuple[bytes, str]:
    """Generate a market analysis PDF report.

    This is a standalone report that does not require a live database
    connection. It generates a template-based report with placeholder
    data that can be populated from any data source.

    Args:
        municipality_id: IBGE municipality identifier.
        provider_id: Optional provider ID for provider-specific analysis.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    meta = ReportMetadata(
        report_type="Market Analysis",
        title=f"Market Analysis — Municipality {municipality_id}",
        generated_at=datetime.utcnow(),
        generated_by="ENLACE Platform",
    )

    provider_section = ""
    if provider_id is not None:
        provider_section = f"""
        <h2>Provider Analysis (ID: {provider_id})</h2>
        <div class="summary-box">
            Provider-specific market position analysis for provider {provider_id}
            in municipality {municipality_id}. This section compares the provider's
            subscriber count, technology mix, and market share against competitors.
        </div>
        <table>
            <tr><th>Metric</th><th>Value</th><th>Market Average</th><th>Position</th></tr>
            <tr><td>Market Share</td><td>—</td><td>—</td><td>—</td></tr>
            <tr><td>Fiber Adoption</td><td>—</td><td>—</td><td>—</td></tr>
            <tr><td>Growth Rate (3M)</td><td>—</td><td>—</td><td>—</td></tr>
            <tr><td>ARPU Estimate</td><td>—</td><td>—</td><td>—</td></tr>
        </table>
        <p><em>Populate with live data via the Market API endpoint
        <code>/api/v1/market/{municipality_id}/competitors</code>.</em></p>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Executive Summary</h2>
<div class="summary-box">
    This report provides a market overview for municipality <strong>{municipality_id}</strong>,
    including broadband penetration, competitive landscape, technology distribution,
    and growth trends. Data sourced from Anatel broadband subscriber records and
    IBGE demographic data.
</div>

<h2>Market Overview</h2>
<table>
    <tr><th>Metric</th><th>Value</th><th>Description</th></tr>
    <tr><td>Municipality ID</td><td>{municipality_id}</td><td>IBGE municipality identifier</td></tr>
    <tr><td>Total Subscribers</td><td>—</td><td>Total broadband subscribers (latest month)</td></tr>
    <tr><td>Fiber Subscribers</td><td>—</td><td>FTTH/FTTB subscribers</td></tr>
    <tr><td>Provider Count</td><td>—</td><td>Active ISP providers</td></tr>
    <tr><td>Broadband Penetration</td><td>—</td><td>Subscribers / households (%)</td></tr>
    <tr><td>Fiber Share</td><td>—</td><td>Fiber subscribers / total (%)</td></tr>
</table>
<p><em>Data populated from <code>mv_market_summary</code> materialized view.</em></p>

<h2>Competitive Landscape</h2>
<p>Market concentration measured by the Herfindahl-Hirschman Index (HHI).
An HHI below 1,500 indicates a competitive market; 1,500-2,500 is moderately
concentrated; above 2,500 is highly concentrated.</p>
<table>
    <tr><th>Provider</th><th>Subscribers</th><th>Market Share</th><th>Technology</th></tr>
    <tr><td colspan="4"><em>Load from /api/v1/market/{municipality_id}/competitors</em></td></tr>
</table>

<h2>Technology Distribution</h2>
<p>Breakdown of access technologies deployed in this municipality.</p>

{provider_section}

<h2>Recommendations</h2>
<div class="recommendation">
    <strong>Growth Opportunity:</strong> Analyze broadband penetration vs. household count
    to identify addressable market gaps. Municipalities with penetration below 40%
    typically present strong expansion opportunities.
</div>
<div class="recommendation">
    <strong>Competitive Strategy:</strong> In highly concentrated markets (HHI &gt; 2,500),
    new entrants can compete on fiber technology and service quality differentiation.
</div>

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)


# ---------------------------------------------------------------------------
# Report: Expansion Opportunity
# ---------------------------------------------------------------------------

def generate_expansion_report(municipality_id: int) -> tuple[bytes, str]:
    """Generate an expansion opportunity PDF report.

    Args:
        municipality_id: IBGE municipality identifier.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    meta = ReportMetadata(
        report_type="Expansion Opportunity",
        title=f"Expansion Opportunity — Municipality {municipality_id}",
        generated_at=datetime.utcnow(),
        generated_by="ENLACE Platform",
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Executive Summary</h2>
<div class="summary-box">
    Expansion opportunity assessment for municipality <strong>{municipality_id}</strong>.
    This report evaluates demand potential, competitive landscape, infrastructure
    readiness, and financial viability for broadband expansion.
</div>

<h2>Opportunity Score</h2>
<table>
    <tr><th>Sub-Score</th><th>Weight</th><th>Score</th><th>Description</th></tr>
    <tr><td>Demand</td><td>30%</td><td>—</td><td>Unmet demand based on penetration gap</td></tr>
    <tr><td>Competition</td><td>25%</td><td>—</td><td>Market concentration and entry barriers</td></tr>
    <tr><td>Infrastructure</td><td>20%</td><td>—</td><td>Existing infrastructure proximity</td></tr>
    <tr><td>Growth</td><td>25%</td><td>—</td><td>Subscriber growth trajectory</td></tr>
    <tr><td><strong>Composite</strong></td><td>100%</td><td><strong>—</strong></td><td>Weighted composite score</td></tr>
</table>
<p><em>Scores populated from <code>opportunity_scores</code> table via
<code>/api/v1/opportunity/score</code>.</em></p>

<h2>Financial Viability</h2>
<h3>Scenario Analysis</h3>
<table>
    <tr><th>Scenario</th><th>NPV (BRL)</th><th>IRR</th><th>Payback (months)</th></tr>
    <tr><td>Pessimistic</td><td>—</td><td>—</td><td>—</td></tr>
    <tr><td>Base Case</td><td>—</td><td>—</td><td>—</td></tr>
    <tr><td>Optimistic</td><td>—</td><td>—</td><td>—</td></tr>
</table>

<h3>CAPEX Estimate</h3>
<table>
    <tr><th>Component</th><th>Cost (BRL)</th><th>% of Total</th></tr>
    <tr><td>Fiber Plant</td><td>—</td><td>—</td></tr>
    <tr><td>Active Equipment</td><td>—</td><td>—</td></tr>
    <tr><td>CPE / ONTs</td><td>—</td><td>—</td></tr>
    <tr><td>Civil Works</td><td>—</td><td>—</td></tr>
    <tr><td><strong>Total</strong></td><td><strong>—</strong></td><td>100%</td></tr>
</table>

<h2>Market Context</h2>
<table>
    <tr><th>Factor</th><th>Status</th><th>Impact</th></tr>
    <tr><td>Broadband Penetration</td><td>—</td><td>—</td></tr>
    <tr><td>Fiber Share</td><td>—</td><td>—</td></tr>
    <tr><td>Provider Count</td><td>—</td><td>—</td></tr>
    <tr><td>Population Growth</td><td>—</td><td>—</td></tr>
</table>

<h2>Recommendations</h2>
<div class="recommendation">
    <strong>Entry Strategy:</strong> For municipalities with composite scores above 70,
    a phased fiber deployment targeting high-density neighborhoods first typically
    yields the fastest payback.
</div>
<div class="recommendation">
    <strong>Financing:</strong> Explore BNDES ProConectividade credit lines (up to 80%
    financing at TLP + 1.3-1.8%) for municipalities under 60,000 inhabitants.
</div>

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)


# ---------------------------------------------------------------------------
# Report: Compliance
# ---------------------------------------------------------------------------

def generate_compliance_report(
    provider_name: str,
    state_codes: list[str],
    subscriber_count: int,
    revenue: float | None = None,
) -> tuple[bytes, str]:
    """Generate a regulatory compliance PDF report.

    Args:
        provider_name: ISP provider name.
        state_codes: List of two-letter state codes.
        subscriber_count: Total subscriber count.
        revenue: Optional monthly revenue in BRL.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    meta = ReportMetadata(
        report_type="Regulatory Compliance",
        title=f"Compliance Report — {provider_name}",
        generated_at=datetime.utcnow(),
        generated_by="ENLACE Platform",
    )

    states_str = ", ".join(state_codes) if state_codes else "N/A"
    revenue_str = _format_brl(revenue) if revenue else "Not provided"

    # Determine licensing status
    if subscriber_count > 5000:
        license_status = "Formal Anatel SCM authorization REQUIRED"
        license_class = "warning"
    elif subscriber_count > 4000:
        license_status = "Approaching 5,000 threshold -- prepare authorization process"
        license_class = "recommendation"
    else:
        license_status = "Below 5,000 threshold -- Comunicacao Previa sufficient"
        license_class = "summary-box"

    # Norma no. 4 assessment
    norma4_note = ""
    if revenue and revenue > 0:
        norma4_note = f"""
        <h3>Norma no. 4 Tax Impact</h3>
        <div class="summary-box">
            Monthly revenue: {revenue_str}. Norma no. 4 reclassification from SVA to SCM
            would apply ICMS taxation. Run detailed analysis via
            <code>/api/v1/compliance/norma4/impact</code> for state-specific impact.
        </div>
        """

    # Build state-specific rows
    state_rows = ""
    for sc in state_codes:
        state_rows += f"""
        <tr>
            <td>{sc}</td>
            <td>—</td>
            <td>—</td>
            <td>—</td>
        </tr>
        """
    if not state_rows:
        state_rows = '<tr><td colspan="4"><em>No states specified</em></td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Executive Summary</h2>
<div class="summary-box">
    Regulatory compliance assessment for <strong>{provider_name}</strong>
    operating in <strong>{states_str}</strong> with <strong>{subscriber_count:,}</strong>
    subscribers. This report evaluates licensing requirements, Norma no. 4
    tax implications, quality obligations, and upcoming regulatory deadlines.
</div>

<h2>Provider Profile</h2>
<table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>Provider Name</td><td>{provider_name}</td></tr>
    <tr><td>States</td><td>{states_str}</td></tr>
    <tr><td>Subscribers</td><td>{subscriber_count:,}</td></tr>
    <tr><td>Monthly Revenue</td><td>{revenue_str}</td></tr>
</table>

<h2>Licensing Status</h2>
<div class="{license_class}">
    <strong>Status:</strong> {license_status}
</div>
<table>
    <tr><th>Threshold</th><th>Requirement</th><th>Your Position</th></tr>
    <tr>
        <td>5,000 subscribers</td>
        <td>Formal SCM authorization from Anatel</td>
        <td>{subscriber_count:,} subscribers</td>
    </tr>
    <tr>
        <td>50,000 subscribers</td>
        <td>Large-provider quality reporting obligations</td>
        <td>{subscriber_count:,} subscribers</td>
    </tr>
</table>

{norma4_note}

<h2>State-Specific Compliance</h2>
<table>
    <tr><th>State</th><th>ICMS Rate</th><th>Compliance Status</th><th>Action Items</th></tr>
    {state_rows}
</table>
<p><em>Run detailed per-state analysis via <code>/api/v1/compliance/norma4/multi-state</code>.</em></p>

<h2>Quality Obligations</h2>
<table>
    <tr><th>Metric</th><th>Anatel Minimum</th><th>Your Status</th><th>Compliance</th></tr>
    <tr><td>Download Speed (% contracted)</td><td>80%</td><td>—</td><td>—</td></tr>
    <tr><td>Upload Speed (% contracted)</td><td>80%</td><td>—</td><td>—</td></tr>
    <tr><td>Latency Compliance</td><td>80%</td><td>—</td><td>—</td></tr>
    <tr><td>Network Availability</td><td>99%</td><td>—</td><td>—</td></tr>
    <tr><td>IDA Score</td><td>6.0</td><td>—</td><td>—</td></tr>
</table>

<h2>Upcoming Deadlines</h2>
<table>
    <tr><th>Regulation</th><th>Deadline</th><th>Urgency</th><th>Description</th></tr>
    <tr><td colspan="4"><em>Load via <code>/api/v1/compliance/deadlines</code></em></td></tr>
</table>

<h2>Recommendations</h2>
<div class="recommendation">
    <strong>Licensing:</strong> ISPs approaching 5,000 subscribers should begin the
    formal SCM authorization process 6-12 months in advance. Estimated cost:
    R$15,000-30,000 including legal and consulting fees.
</div>
<div class="recommendation">
    <strong>Tax Planning:</strong> Review Norma no. 4 restructuring options (holding
    company, split entity) to optimize ICMS impact before reclassification.
</div>
<div class="recommendation">
    <strong>Quality:</strong> Implement automated quality monitoring with Anatel IDA
    thresholds as alerting baselines.
</div>

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)


# ---------------------------------------------------------------------------
# Report: Rural Feasibility
# ---------------------------------------------------------------------------

def generate_rural_report(
    community_lat: float,
    community_lon: float,
    population: int,
    area_km2: float,
    grid_power: bool = False,
) -> tuple[bytes, str]:
    """Generate a rural feasibility PDF report.

    Runs the hybrid network designer, solar power sizing, and funding
    matcher to produce a comprehensive feasibility report.

    Args:
        community_lat: Community center latitude.
        community_lon: Community center longitude.
        population: Community population.
        area_km2: Community area in km^2.
        grid_power: Whether grid electricity is available.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    from python.rural.hybrid_designer import CommunityProfile, design_hybrid_network
    from python.rural.solar_power import size_solar_system
    from python.rural.community_profiler import profile_community

    meta = ReportMetadata(
        report_type="Rural Feasibility",
        title=f"Rural Feasibility Study — ({community_lat:.4f}, {community_lon:.4f})",
        generated_at=datetime.utcnow(),
        generated_by="ENLACE Platform",
    )

    # Run the hybrid network designer
    profile = CommunityProfile(
        latitude=community_lat,
        longitude=community_lon,
        population=population,
        area_km2=area_km2,
        grid_power=grid_power,
    )

    try:
        design = design_hybrid_network(profile)
    except Exception as e:
        logger.error(f"Hybrid design failed during report generation: {e}")
        design = None

    # Run community demand profiling
    try:
        demand = profile_community(population=population)
    except Exception as e:
        logger.error(f"Community profiling failed during report generation: {e}")
        demand = None

    # Run solar sizing if off-grid
    solar = None
    if not grid_power:
        try:
            solar = size_solar_system(
                latitude=community_lat,
                longitude=community_lon,
                power_consumption_watts=250,
                autonomy_days=3,
                battery_type="lithium",
            )
        except Exception as e:
            logger.error(f"Solar sizing failed during report generation: {e}")

    # Build design section
    design_section = ""
    if design is not None:
        equipment_rows = ""
        for eq in design.equipment_list:
            equipment_rows += f"""
            <tr>
                <td>{eq.get('category', '')}</td>
                <td>{eq.get('item', '')}</td>
                <td>{eq.get('quantity', 0)}</td>
                <td>{eq.get('unit', '')}</td>
                <td>{_format_brl(eq.get('unit_cost_brl', 0))}</td>
                <td>{_format_brl(eq.get('total_cost_brl', 0))}</td>
            </tr>
            """

        notes_html = ""
        for note in design.design_notes:
            css_class = "warning" if "WARNING" in note or "HIGH COST" in note else "recommendation"
            notes_html += f'<div class="{css_class}">{note}</div>'

        # Cost breakdown bar chart
        cost_items = []
        for eq in design.equipment_list:
            cost_items.append((eq.get("item", "")[:30], eq.get("total_cost_brl", 0)))

        design_section = f"""
        <h2>Network Design</h2>
        <table>
            <tr><th>Component</th><th>Selection</th><th>Details</th></tr>
            <tr>
                <td>Backhaul</td>
                <td><strong>{design.backhaul_technology}</strong></td>
                <td>{design.backhaul_details.get('rationale', '')}</td>
            </tr>
            <tr>
                <td>Last Mile</td>
                <td><strong>{design.last_mile_technology}</strong></td>
                <td>{design.last_mile_details.get('rationale', '')}</td>
            </tr>
            <tr>
                <td>Power</td>
                <td><strong>{design.power_solution}</strong></td>
                <td>{design.power_details.get('rationale', '')}</td>
            </tr>
        </table>

        <h3>Cost Summary</h3>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total CAPEX</td><td><strong>{_format_brl(design.estimated_capex_brl)}</strong></td></tr>
            <tr><td>Monthly OPEX</td><td>{_format_brl(design.estimated_monthly_opex_brl)}</td></tr>
            <tr><td>Coverage Area</td><td>{design.coverage_estimate_km2:.2f} km&sup2;</td></tr>
            <tr><td>Max Subscribers</td><td>{design.max_subscribers:,}</td></tr>
        </table>

        <h3>Equipment List</h3>
        <table>
            <tr><th>Category</th><th>Item</th><th>Qty</th><th>Unit</th><th>Unit Cost</th><th>Total</th></tr>
            {equipment_rows}
        </table>

        <h3>Cost Distribution</h3>
        {_build_bar_chart(cost_items)}

        <h3>Design Notes</h3>
        {notes_html}
        """
    else:
        design_section = """
        <h2>Network Design</h2>
        <div class="warning">Network design could not be completed. Check input parameters.</div>
        """

    # Build demand section
    demand_section = ""
    if demand is not None:
        use_cases_str = ", ".join(demand.primary_use_cases) if demand.primary_use_cases else "N/A"
        demand_section = f"""
        <h2>Community Demand Profile</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Estimated Subscribers</td><td>{demand.estimated_subscribers:,}</td></tr>
            <tr><td>Bandwidth Required</td><td>{demand.estimated_bandwidth_mbps:.1f} Mbps</td></tr>
            <tr><td>Primary Use Cases</td><td>{use_cases_str}</td></tr>
            <tr><td>Revenue Potential (monthly)</td><td>{_format_brl(demand.revenue_potential_monthly_brl)}</td></tr>
            <tr><td>Willingness to Pay</td><td>{_format_brl(demand.willingness_to_pay_brl)}/month</td></tr>
            <tr><td>Demand Confidence</td><td>{demand.demand_confidence}</td></tr>
        </table>
        """

    # Build solar section
    solar_section = ""
    if solar is not None:
        solar_notes = ""
        for note in solar.notes:
            solar_notes += f'<div class="recommendation">{note}</div>'

        solar_section = f"""
        <h2>Solar Power System</h2>
        <div class="summary-box">
            Off-grid solar power system designed for 250W continuous load with
            {solar.battery_type} batteries and 3 days autonomy.
        </div>
        <table>
            <tr><th>Component</th><th>Specification</th></tr>
            <tr><td>Panel Array</td><td>{solar.panel_array_kwp:.2f} kWp ({solar.panel_count} x {solar.panel_watts}W)</td></tr>
            <tr><td>Battery Bank</td><td>{solar.battery_kwh:.1f} kWh ({solar.battery_count} modules, {solar.battery_type})</td></tr>
            <tr><td>Charge Controller</td><td>{solar.charge_controller_amps}A</td></tr>
            <tr><td>Inverter</td><td>{solar.inverter_watts}W</td></tr>
            <tr><td>Estimated CAPEX</td><td><strong>{_format_brl(solar.estimated_capex_brl)}</strong></td></tr>
            <tr><td>Annual Maintenance</td><td>{_format_brl(solar.annual_maintenance_brl)}</td></tr>
            <tr><td>System Lifespan</td><td>{solar.system_lifespan_years} years</td></tr>
        </table>
        {solar_notes}
        """

    # Power status label
    power_label = "Grid available" if grid_power else "Off-grid (solar required)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Executive Summary</h2>
<div class="summary-box">
    Rural feasibility study for a community at coordinates
    ({community_lat:.4f}, {community_lon:.4f}) with population
    <strong>{population:,}</strong> covering <strong>{area_km2:.1f} km&sup2;</strong>.
    Power: <strong>{power_label}</strong>.
    This report includes network design, equipment list, cost estimates,
    demand analysis, and funding program eligibility.
</div>

<h2>Community Profile</h2>
<table>
    <tr><th>Parameter</th><th>Value</th></tr>
    <tr><td>Location</td><td>({community_lat:.4f}, {community_lon:.4f})</td></tr>
    <tr><td>Population</td><td>{population:,}</td></tr>
    <tr><td>Area</td><td>{area_km2:.1f} km&sup2;</td></tr>
    <tr><td>Grid Power</td><td>{power_label}</td></tr>
</table>

{design_section}

{demand_section}

{solar_section}

<h2>Funding Programs</h2>
<div class="summary-box">
    Run funding eligibility analysis via <code>/api/v1/rural/funding/match</code>
    with municipality code and CAPEX estimate to identify applicable government
    programs (FUST, Norte Conectado, New PAC, BNDES ProConectividade).
</div>
<table>
    <tr><th>Program</th><th>Type</th><th>Max Funding</th><th>Description</th></tr>
    <tr><td>FUST</td><td>Credit</td><td>R$5,000,000</td><td>Universal telecom fund for municipalities &lt; 30k</td></tr>
    <tr><td>Norte Conectado</td><td>Partnership</td><td>Varies</td><td>Amazon fiber backbone (Legal Amazon only)</td></tr>
    <tr><td>New PAC</td><td>Partnership</td><td>R$10,000,000</td><td>4G/5G expansion to unserved areas</td></tr>
    <tr><td>BNDES ProConectividade</td><td>Credit</td><td>R$20,000,000</td><td>ISP infrastructure financing</td></tr>
</table>

<h2>Recommendations</h2>
<div class="recommendation">
    <strong>Next Steps:</strong>
    <ol>
        <li>Validate community location and population with IBGE data</li>
        <li>Conduct site survey for backhaul line-of-sight and tower placement</li>
        <li>Run funding eligibility check with municipality code</li>
        <li>Prepare technical project documentation for financing applications</li>
        <li>Obtain environmental permits if Amazon/riverine location</li>
    </ol>
</div>

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)
