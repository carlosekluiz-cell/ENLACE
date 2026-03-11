"""PDF report generator for ENLACE platform.

Generates 4 types of reports:
1. Market Analysis Report -- municipality market overview
2. Expansion Opportunity Report -- opportunity scoring + financial viability
3. Compliance Report -- regulatory compliance status
4. Rural Feasibility Report -- rural connectivity design + funding

Uses HTML templates rendered to PDF via WeasyPrint.  When WeasyPrint is
unavailable the raw HTML bytes are returned instead (the caller can
choose a fallback content type).

All reports query live data from PostgreSQL and output in Portuguese.
"""

import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime

import psycopg2

from python.ml.config import DB_CONFIG

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
/* Pulso Network Report Stylesheet */
@page {
    size: A4;
    margin: 20mm 15mm 25mm 15mm;
    @bottom-center {
        content: "Pulso Network — Página " counter(page) " de " counter(pages);
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
        <div class="subtitle">Pulso Network — Inteligência para Decisões em Telecomunicações</div>
        <div class="meta">
            Tipo: {meta.report_type} | Gerado em: {meta.generated_at:%Y-%m-%d %H:%M UTC}
            | Por: {meta.generated_by} | Versão: {meta.version}
        </div>
    </div>
    """


def _html_footer(meta: ReportMetadata) -> str:
    """Render the report footer block."""
    return f"""
    <div class="footer">
        Gerado pela Pulso Network v{meta.version} em {meta.generated_at:%Y-%m-%d %H:%M UTC}.
        Este relatório é apenas para fins informativos. Fontes: Anatel, IBGE, BNDES, MCom.
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

def _get_db_connection():
    """Get a psycopg2 connection using shared DB config."""
    return psycopg2.connect(**DB_CONFIG)


def generate_market_report(
    municipality_id: int,
    provider_id: int | None = None,
) -> tuple[bytes, str]:
    """Generate a market analysis report with real database data.

    Queries mv_market_summary, broadband_subscribers, providers, and
    opportunity_scores to produce a comprehensive Portuguese-language
    market report.

    Args:
        municipality_id: IBGE municipality code (e.g. 4108403).
        provider_id: Optional provider ID for provider-specific analysis.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    conn = _get_db_connection()
    try:
        cur = conn.cursor()

        # 1. Market summary
        cur.execute("""
            SELECT municipality_name, state_abbrev, municipality_code,
                   total_subscribers, fiber_subscribers, provider_count,
                   total_households, total_population,
                   broadband_penetration_pct, fiber_share_pct, year_month
            FROM mv_market_summary
            WHERE municipality_code = %s
            ORDER BY year_month DESC LIMIT 1
        """, (str(municipality_id),))
        mkt = cur.fetchone()

        if not mkt:
            # Fallback: try by l2_id
            cur.execute("""
                SELECT municipality_name, state_abbrev, municipality_code,
                       total_subscribers, fiber_subscribers, provider_count,
                       total_households, total_population,
                       broadband_penetration_pct, fiber_share_pct, year_month
                FROM mv_market_summary
                WHERE l2_id = %s
                ORDER BY year_month DESC LIMIT 1
            """, (municipality_id,))
            mkt = cur.fetchone()

        if not mkt:
            meta = ReportMetadata(
                report_type="Análise de Mercado",
                title=f"Análise de Mercado — Município {municipality_id}",
                generated_at=datetime.utcnow(),
                generated_by="Pulso Network",
            )
            html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}
<h2>Erro</h2>
<div class="warning">Nenhum dado encontrado para o município {municipality_id}.</div>
{_html_footer(meta)}
</body></html>"""
            return _render_to_bytes(html)

        (muni_name, state, muni_code, total_subs, fiber_subs, prov_count,
         households, population, penetration, fiber_share, year_month) = mkt

        meta = ReportMetadata(
            report_type="Análise de Mercado",
            title=f"Análise de Mercado — {muni_name} ({state})",
            generated_at=datetime.utcnow(),
            generated_by="Pulso Network",
        )

        # 2. Provider breakdown (top 20)
        cur.execute("""
            SELECT p.name, p.national_id, bs.technology,
                   SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs
            JOIN providers p ON p.id = bs.provider_id
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            WHERE a2.code = %s AND bs.year_month = %s
            GROUP BY p.name, p.national_id, bs.technology
            ORDER BY subs DESC
            LIMIT 20
        """, (str(municipality_id), str(year_month)))
        providers = cur.fetchall()

        # 3. Technology distribution
        cur.execute("""
            SELECT bs.technology, SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            WHERE a2.code = %s AND bs.year_month = %s
            GROUP BY bs.technology
            ORDER BY subs DESC
        """, (str(municipality_id), str(year_month)))
        tech_dist = cur.fetchall()

        # 4. Growth trend (last 6 months)
        #    Detect incomplete months by comparing provider count vs previous
        cur.execute("""
            WITH monthly AS (
                SELECT bs.year_month,
                       SUM(bs.subscribers) AS subs,
                       COUNT(DISTINCT bs.provider_id) AS n_providers
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON a2.id = bs.l2_id
                WHERE a2.code = %s
                GROUP BY bs.year_month
                ORDER BY bs.year_month DESC
                LIMIT 7
            )
            SELECT year_month, subs, n_providers FROM monthly
            ORDER BY year_month DESC
        """, (str(municipality_id),))
        growth_raw = cur.fetchall()

        # Flag if latest month has fewer providers than previous (incomplete data)
        data_incomplete_warning = ""
        if len(growth_raw) >= 2:
            latest_providers = growth_raw[0][2]
            prev_providers = growth_raw[1][2]
            if latest_providers < prev_providers * 0.85:
                missing = prev_providers - latest_providers
                data_incomplete_warning = (
                    f'<div class="warning">'
                    f'<strong>Aviso:</strong> O mês {growth_raw[0][0]} possui dados incompletos '
                    f'({latest_providers} provedores reportaram vs {prev_providers} no mês anterior). '
                    f'{missing} provedor(es) ainda não reportaram. '
                    f'A queda aparente de assinantes pode não refletir a realidade.</div>'
                )

        growth_data = [(r[0], r[1]) for r in growth_raw[:6]]

        # 5. HHI calculation
        total_for_hhi = sum(p[3] for p in providers) if providers else 1
        hhi = sum((p[3] / total_for_hhi * 100) ** 2 for p in providers) if providers else 0

        # 6. Opportunity score
        cur.execute("""
            SELECT composite_score, demand_score, competition_score,
                   infrastructure_score, growth_score, confidence
            FROM opportunity_scores
            WHERE geographic_id = %s
            ORDER BY computed_at DESC LIMIT 1
        """, (str(municipality_id),))
        opp = cur.fetchone()

        cur.close()
    finally:
        conn.close()

    # --- Build provider table rows ---
    provider_rows = ""
    for p_name, p_cnpj, p_tech, p_subs in providers:
        share = (p_subs / total_subs * 100) if total_subs else 0
        tech_label = {"fiber": "Fibra", "wireless": "Radio", "other": "Outros",
                      "cable": "Cabo", "dsl": "DSL", "satellite": "Satélite"}.get(
                          p_tech, p_tech or "—")
        provider_rows += f"""
        <tr>
            <td>{p_name}</td>
            <td>{p_cnpj or '—'}</td>
            <td>{p_subs:,}</td>
            <td>{share:.1f}%</td>
            <td>{tech_label}</td>
        </tr>"""

    # --- Build technology distribution ---
    tech_rows = ""
    tech_bar_items = []
    for t_tech, t_subs in tech_dist:
        t_share = (t_subs / total_subs * 100) if total_subs else 0
        t_label = {"fiber": "Fibra Óptica", "wireless": "Radio/FWA",
                   "other": "Outros", "cable": "Cabo Coaxial",
                   "dsl": "DSL/xDSL", "satellite": "Satélite"}.get(
                       t_tech, t_tech or "Outros")
        tech_rows += f"""
        <tr><td>{t_label}</td><td>{t_subs:,}</td><td>{t_share:.1f}%</td></tr>"""
        tech_bar_items.append((t_label, t_subs))

    # --- Growth trend ---
    growth_rows = ""
    for g_month, g_subs in reversed(growth_data):
        growth_rows += f"<tr><td>{g_month}</td><td>{g_subs:,}</td></tr>"

    growth_change = ""
    if len(growth_data) >= 2:
        newest, oldest = growth_data[0][1], growth_data[-1][1]
        if oldest > 0:
            pct_change = (newest - oldest) / oldest * 100
            months = len(growth_data)
            direction = "crescimento" if pct_change >= 0 else "queda"
            growth_change = f"""
            <div class="summary-box">
                <strong>Tendência:</strong> {direction} de {abs(pct_change):.1f}%
                nos últimos {months} meses ({oldest:,} → {newest:,} assinantes).
            </div>"""

    # --- HHI interpretation ---
    if hhi < 1500:
        hhi_label = "Competitivo"
        hhi_class = "summary-box"
    elif hhi < 2500:
        hhi_label = "Moderadamente Concentrado"
        hhi_class = "recommendation"
    else:
        hhi_label = "Altamente Concentrado"
        hhi_class = "warning"

    # --- Opportunity score section ---
    opp_section = ""
    if opp:
        comp_score, demand, competition, infra, growth, confidence = opp
        opp_section = f"""
        <h2>Score de Oportunidade</h2>
        <div class="metric-row">
            <div class="metric-card">
                <div class="value">{comp_score:.0f}</div>
                <div class="label">Score Geral</div>
            </div>
            <div class="metric-card">
                <div class="value">{demand:.0f}</div>
                <div class="label">Demanda</div>
            </div>
            <div class="metric-card">
                <div class="value">{competition:.0f}</div>
                <div class="label">Competição</div>
            </div>
            <div class="metric-card">
                <div class="value">{infra:.0f}</div>
                <div class="label">Infraestrutura</div>
            </div>
            <div class="metric-card">
                <div class="value">{growth:.0f}</div>
                <div class="label">Crescimento</div>
            </div>
        </div>
        <p style="font-size: 8pt; color: #888;">Confiança: {confidence:.0f}% | Fonte: modelo Pulso v1.0</p>
        """

    # --- Provider-specific section ---
    provider_section = ""
    if provider_id is not None:
        conn2 = _get_db_connection()
        try:
            cur2 = conn2.cursor()
            cur2.execute("""
                SELECT p.name, bs.technology, SUM(bs.subscribers) AS subs
                FROM broadband_subscribers bs
                JOIN providers p ON p.id = bs.provider_id
                JOIN admin_level_2 a2 ON a2.id = bs.l2_id
                WHERE a2.code = %s AND bs.provider_id = %s AND bs.year_month = %s
                GROUP BY p.name, bs.technology
                ORDER BY subs DESC
            """, (str(municipality_id), provider_id, str(year_month)))
            prov_data = cur2.fetchall()
            cur2.close()
        finally:
            conn2.close()

        if prov_data:
            prov_name = prov_data[0][0]
            prov_total = sum(r[2] for r in prov_data)
            prov_share = (prov_total / total_subs * 100) if total_subs else 0
            prov_tech_rows = ""
            for _, tech, subs in prov_data:
                prov_tech_rows += f"<tr><td>{tech}</td><td>{subs:,}</td></tr>"

            provider_section = f"""
            <h2>Análise do Provedor: {prov_name}</h2>
            <table>
                <tr><th>Métrica</th><th>Valor</th></tr>
                <tr><td>Assinantes</td><td>{prov_total:,}</td></tr>
                <tr><td>Market Share</td><td>{prov_share:.1f}%</td></tr>
            </table>
            <h3>Distribuição por Tecnologia</h3>
            <table>
                <tr><th>Tecnologia</th><th>Assinantes</th></tr>
                {prov_tech_rows}
            </table>
            """

    # --- Recommendations ---
    recommendations = ""
    if penetration and penetration < 40:
        recommendations += """
        <div class="recommendation">
            <strong>Oportunidade de Crescimento:</strong> Penetração de banda larga abaixo de 40%
            indica mercado com demanda não atendida significativa. Municípios neste patamar
            apresentam forte potencial para expansão de rede.
        </div>"""
    if hhi > 2500:
        recommendations += """
        <div class="recommendation">
            <strong>Estratégia Competitiva:</strong> Mercado altamente concentrado (HHI &gt; 2.500).
            Novos entrantes podem competir com tecnologia de fibra e diferenciação em qualidade
            de serviço.
        </div>"""
    if fiber_share and fiber_share > 80:
        recommendations += f"""
        <div class="summary-box">
            <strong>Maturidade de Fibra:</strong> Com {fiber_share:.0f}% de participação de fibra,
            este município está em estágio avançado de migração tecnológica. Foco em retenção
            e upsell de planos premium.
        </div>"""
    if not recommendations:
        recommendations = """
        <div class="recommendation">
            <strong>Análise:</strong> Mercado com indicadores equilibrados. Avalie scores de
            oportunidade específicos para identificar nichos de crescimento.
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Resumo Executivo</h2>
<div class="summary-box">
    Análise de mercado para <strong>{muni_name} ({state})</strong> — Código IBGE {muni_code}.
    População: <strong>{population:,}</strong> | Domicílios: <strong>{households:,}</strong>.
    O município possui <strong>{total_subs:,}</strong> assinantes de banda larga distribuidos
    entre <strong>{prov_count}</strong> provedores, com penetração de <strong>{penetration:.1f}%</strong>
    e {fiber_share:.0f}% de participação de fibra óptica.
    Dados referentes a <strong>{year_month}</strong> (Anatel/IBGE).
</div>

<h2>Visão Geral do Mercado</h2>
<div class="metric-row">
    <div class="metric-card">
        <div class="value">{total_subs:,}</div>
        <div class="label">Assinantes</div>
    </div>
    <div class="metric-card">
        <div class="value">{prov_count}</div>
        <div class="label">Provedores</div>
    </div>
    <div class="metric-card">
        <div class="value">{penetration:.1f}%</div>
        <div class="label">Penetração</div>
    </div>
    <div class="metric-card">
        <div class="value">{fiber_share:.0f}%</div>
        <div class="label">Fibra</div>
    </div>
</div>
<table>
    <tr><th>Métrica</th><th>Valor</th><th>Descrição</th></tr>
    <tr><td>Município</td><td>{muni_name} ({state})</td><td>Código IBGE: {muni_code}</td></tr>
    <tr><td>População</td><td>{population:,}</td><td>Estimativa IBGE</td></tr>
    <tr><td>Domicílios</td><td>{households:,}</td><td>IBGE Censo</td></tr>
    <tr><td>Total de Assinantes</td><td>{total_subs:,}</td><td>Banda larga fixa (último mês)</td></tr>
    <tr><td>Assinantes Fibra</td><td>{fiber_subs:,}</td><td>FTTH/FTTB</td></tr>
    <tr><td>Provedores Ativos</td><td>{prov_count}</td><td>ISPs com assinantes ativos</td></tr>
    <tr><td>Penetração</td><td>{penetration:.1f}%</td><td>Assinantes / domicílios</td></tr>
    <tr><td>Participação Fibra</td><td>{fiber_share:.0f}%</td><td>Fibra / total</td></tr>
</table>

<h2>Paisagem Competitiva</h2>
<div class="{hhi_class}">
    <strong>Índice HHI: {hhi:,.0f}</strong> — Mercado <strong>{hhi_label}</strong>.
</div>
<table>
    <tr><th>Provedor</th><th>CNPJ</th><th>Assinantes</th><th>Market Share</th><th>Tecnologia</th></tr>
    {provider_rows}
</table>

<h2>Distribuição por Tecnologia</h2>
{_build_bar_chart(tech_bar_items)}
<table>
    <tr><th>Tecnologia</th><th>Assinantes</th><th>Participação</th></tr>
    {tech_rows}
</table>

<h2>Evolução de Assinantes</h2>
{data_incomplete_warning}
{growth_change}
<table>
    <tr><th>Mês</th><th>Assinantes</th></tr>
    {growth_rows}
</table>

{opp_section}

{provider_section}

<h2>Recomendações</h2>
{recommendations}

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)


# ---------------------------------------------------------------------------
# Report: Expansion Opportunity
# ---------------------------------------------------------------------------

def generate_expansion_report(municipality_id: int) -> tuple[bytes, str]:
    """Generate an expansion opportunity report with real data.

    Args:
        municipality_id: IBGE municipality code.

    Returns:
        Tuple of (content_bytes, media_type).
    """
    conn = _get_db_connection()
    try:
        cur = conn.cursor()

        # Market summary
        cur.execute("""
            SELECT municipality_name, state_abbrev, municipality_code,
                   total_subscribers, fiber_subscribers, provider_count,
                   total_households, total_population,
                   broadband_penetration_pct, fiber_share_pct, year_month
            FROM mv_market_summary
            WHERE municipality_code = %s
            ORDER BY year_month DESC LIMIT 1
        """, (str(municipality_id),))
        mkt = cur.fetchone()

        # Opportunity score
        cur.execute("""
            SELECT composite_score, demand_score, competition_score,
                   infrastructure_score, growth_score, confidence
            FROM opportunity_scores
            WHERE geographic_id = %s
            ORDER BY computed_at DESC LIMIT 1
        """, (str(municipality_id),))
        opp = cur.fetchone()

        # Top providers for competitive context
        year_month = mkt[10] if mkt else None
        providers = []
        if year_month:
            cur.execute("""
                SELECT p.name, bs.technology, SUM(bs.subscribers) AS subs
                FROM broadband_subscribers bs
                JOIN providers p ON p.id = bs.provider_id
                JOIN admin_level_2 a2 ON a2.id = bs.l2_id
                WHERE a2.code = %s AND bs.year_month = %s
                GROUP BY p.name, bs.technology
                ORDER BY subs DESC LIMIT 10
            """, (str(municipality_id), str(year_month)))
            providers = cur.fetchall()

        # Growth trend with incomplete data detection
        cur.execute("""
            WITH monthly AS (
                SELECT bs.year_month,
                       SUM(bs.subscribers) AS subs,
                       COUNT(DISTINCT bs.provider_id) AS n_providers
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON a2.id = bs.l2_id
                WHERE a2.code = %s
                GROUP BY bs.year_month
                ORDER BY bs.year_month DESC
                LIMIT 7
            )
            SELECT year_month, subs, n_providers FROM monthly
            ORDER BY year_month DESC
        """, (str(municipality_id),))
        growth_raw = cur.fetchall()

        exp_data_warning = ""
        if len(growth_raw) >= 2:
            latest_p = growth_raw[0][2]
            prev_p = growth_raw[1][2]
            if latest_p < prev_p * 0.85:
                missing = prev_p - latest_p
                exp_data_warning = (
                    f'<div class="warning">'
                    f'<strong>Aviso:</strong> O mês {growth_raw[0][0]} possui dados incompletos '
                    f'({latest_p} provedores vs {prev_p} anterior). '
                    f'{missing} provedor(es) ainda não reportaram.</div>'
                )

        growth_data = [(r[0], r[1]) for r in growth_raw[:6]]

        cur.close()
    finally:
        conn.close()

    muni_name = mkt[0] if mkt else f"Município {municipality_id}"
    state = mkt[1] if mkt else ""
    total_subs = mkt[3] if mkt else 0
    fiber_subs = mkt[4] if mkt else 0
    prov_count = mkt[5] if mkt else 0
    households = mkt[6] if mkt else 0
    population = mkt[7] if mkt else 0
    penetration = mkt[8] if mkt else 0
    fiber_share = mkt[9] if mkt else 0

    meta = ReportMetadata(
        report_type="Plano de Expansão",
        title=f"Plano de Expansão — {muni_name} ({state})",
        generated_at=datetime.utcnow(),
        generated_by="Pulso Network",
    )

    # Opportunity scores section
    opp_section = ""
    if opp:
        comp, demand, competition, infra, growth, confidence = opp
        opp_section = f"""
        <h2>Score de Oportunidade</h2>
        <div class="metric-row">
            <div class="metric-card">
                <div class="value">{comp:.0f}</div>
                <div class="label">Score Geral</div>
            </div>
            <div class="metric-card">
                <div class="value">{demand:.0f}</div>
                <div class="label">Demanda</div>
            </div>
            <div class="metric-card">
                <div class="value">{competition:.0f}</div>
                <div class="label">Competição</div>
            </div>
            <div class="metric-card">
                <div class="value">{infra:.0f}</div>
                <div class="label">Infraestrutura</div>
            </div>
            <div class="metric-card">
                <div class="value">{growth:.0f}</div>
                <div class="label">Crescimento</div>
            </div>
        </div>
        <table>
            <tr><th>Sub-Score</th><th>Peso</th><th>Pontuação</th><th>Descrição</th></tr>
            <tr><td>Demanda</td><td>30%</td><td>{demand:.0f}</td><td>Demanda não atendida baseada no gap de penetração</td></tr>
            <tr><td>Competição</td><td>25%</td><td>{competition:.0f}</td><td>Concentração de mercado e barreiras de entrada</td></tr>
            <tr><td>Infraestrutura</td><td>20%</td><td>{infra:.0f}</td><td>Proximidade de infraestrutura existente</td></tr>
            <tr><td>Crescimento</td><td>25%</td><td>{growth:.0f}</td><td>Trajetória de crescimento de assinantes</td></tr>
            <tr><td><strong>Composto</strong></td><td>100%</td><td><strong>{comp:.0f}</strong></td><td>Score ponderado final</td></tr>
        </table>
        <p style="font-size: 8pt; color: #888;">Confiança: {confidence:.0f}%</p>
        """
    else:
        opp_section = """
        <h2>Score de Oportunidade</h2>
        <div class="recommendation">Score de oportunidade não disponível para este município.</div>
        """

    # Gap analysis
    gap_subs = max(0, (households or 0) - (total_subs or 0))
    gap_pct = 100 - (penetration or 0)

    # Provider table
    prov_rows = ""
    for p_name, p_tech, p_subs in providers:
        share = (p_subs / total_subs * 100) if total_subs else 0
        prov_rows += f"<tr><td>{p_name}</td><td>{p_subs:,}</td><td>{share:.1f}%</td><td>{p_tech}</td></tr>"

    # Growth trend
    growth_rows = ""
    for g_month, g_subs in reversed(growth_data):
        growth_rows += f"<tr><td>{g_month}</td><td>{g_subs:,}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Resumo Executivo</h2>
<div class="summary-box">
    Avaliação de oportunidade de expansão para <strong>{muni_name} ({state})</strong>.
    População: <strong>{population:,}</strong> | Domicílios: <strong>{households:,}</strong> |
    Assinantes atuais: <strong>{total_subs:,}</strong> | Penetração: <strong>{penetration:.1f}%</strong>.
    <br><strong>Gap estimado: {gap_subs:,} domicílios sem banda larga ({gap_pct:.1f}% do mercado)</strong>.
</div>

{opp_section}

<h2>Análise de Gap de Mercado</h2>
<div class="metric-row">
    <div class="metric-card">
        <div class="value">{gap_subs:,}</div>
        <div class="label">Domicílios sem BL</div>
    </div>
    <div class="metric-card">
        <div class="value">{gap_pct:.0f}%</div>
        <div class="label">Gap de Penetração</div>
    </div>
    <div class="metric-card">
        <div class="value">{fiber_share:.0f}%</div>
        <div class="label">Fibra Atual</div>
    </div>
    <div class="metric-card">
        <div class="value">{prov_count}</div>
        <div class="label">Concorrentes</div>
    </div>
</div>

<h2>Contexto Competitivo (Top 10)</h2>
<table>
    <tr><th>Provedor</th><th>Assinantes</th><th>Market Share</th><th>Tecnologia</th></tr>
    {prov_rows}
</table>

<h2>Evolução de Assinantes</h2>
{exp_data_warning}
<table>
    <tr><th>Mês</th><th>Assinantes</th></tr>
    {growth_rows}
</table>

<h2>Recomendações</h2>
<div class="recommendation">
    <strong>Estratégia de Entrada:</strong> Para municípios com score acima de 70,
    implantação de fibra em fases focando bairros de alta densidade primeiro
    tipicamente gera o retorno mais rápido.
</div>
<div class="recommendation">
    <strong>Financiamento:</strong> Explore linhas de crédito BNDES ProConectividade
    (até 80% de financiamento a TLP + 1,3-1,8%) para municípios com menos de 60.000 habitantes.
</div>
{"" if population and population > 60000 else '''
<div class="summary-box">
    <strong>Elegibilidade FUST:</strong> Município potencialmente elegível para recursos
    do Fundo de Universalização dos Serviços de Telecomunicações.
</div>
'''}

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
        report_type="Conformidade Regulatória",
        title=f"Relatório de Conformidade — {provider_name}",
        generated_at=datetime.utcnow(),
        generated_by="Pulso Network",
    )

    states_str = ", ".join(state_codes) if state_codes else "N/A"
    revenue_str = _format_brl(revenue) if revenue else "Não informado"

    # Determine licensing status
    if subscriber_count > 5000:
        license_status = "Autorização formal SCM da Anatel OBRIGATÓRIA"
        license_class = "warning"
    elif subscriber_count > 4000:
        license_status = "Aproximando-se do limite de 5.000 — prepare o processo de autorização"
        license_class = "recommendation"
    else:
        license_status = "Abaixo do limite de 5.000 — Comunicação Prévia e suficiente"
        license_class = "summary-box"

    # Norma no. 4 assessment
    norma4_note = ""
    if revenue and revenue > 0:
        norma4_note = f"""
        <h3>Impacto Norma no. 4</h3>
        <div class="summary-box">
            Receita mensal: {revenue_str}. A reclassificação pela Norma no. 4 de SVA para SCM
            implica em tributação de ICMS. Consulte análise detalhada por estado para
            avaliar o impacto específico.
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
<html lang="pt-BR">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Resumo Executivo</h2>
<div class="summary-box">
    Avaliação de conformidade regulatória para <strong>{provider_name}</strong>
    operando em <strong>{states_str}</strong> com <strong>{subscriber_count:,}</strong>
    assinantes. Este relatório avalia requisitos de licenciamento, implicações
    fiscais da Norma no. 4, obrigações de qualidade e prazos regulatórios.
</div>

<h2>Perfil do Provedor</h2>
<table>
    <tr><th>Campo</th><th>Valor</th></tr>
    <tr><td>Nome do Provedor</td><td>{provider_name}</td></tr>
    <tr><td>Estados</td><td>{states_str}</td></tr>
    <tr><td>Assinantes</td><td>{subscriber_count:,}</td></tr>
    <tr><td>Receita Mensal</td><td>{revenue_str}</td></tr>
</table>

<h2>Status de Licenciamento</h2>
<div class="{license_class}">
    <strong>Status:</strong> {license_status}
</div>
<table>
    <tr><th>Limite</th><th>Requisito</th><th>Sua Posição</th></tr>
    <tr>
        <td>5.000 assinantes</td>
        <td>Autorização formal SCM da Anatel</td>
        <td>{subscriber_count:,} assinantes</td>
    </tr>
    <tr>
        <td>50.000 assinantes</td>
        <td>Obrigações de reporte de qualidade para grandes provedores</td>
        <td>{subscriber_count:,} assinantes</td>
    </tr>
</table>

{norma4_note}

<h2>Conformidade por Estado</h2>
<table>
    <tr><th>Estado</th><th>Alíquota ICMS</th><th>Status</th><th>Ações Necessárias</th></tr>
    {state_rows}
</table>

<h2>Obrigações de Qualidade</h2>
<table>
    <tr><th>Métrica</th><th>Mínimo Anatel</th><th>Descrição</th></tr>
    <tr><td>Velocidade Download (% contratado)</td><td>80%</td><td>Velocidade média mensal</td></tr>
    <tr><td>Velocidade Upload (% contratado)</td><td>80%</td><td>Velocidade média mensal</td></tr>
    <tr><td>Latência</td><td>80%</td><td>Conformidade de latência</td></tr>
    <tr><td>Disponibilidade de Rede</td><td>99%</td><td>Uptime mensal</td></tr>
    <tr><td>Score IDA</td><td>6.0</td><td>Índice de Desempenho da Anatel</td></tr>
</table>

<h2>Recomendações</h2>
<div class="recommendation">
    <strong>Licenciamento:</strong> ISPs próximos de 5.000 assinantes devem iniciar o
    processo de autorização formal SCM 6-12 meses antes. Custo estimado:
    R$15.000-30.000 incluindo honorários jurídicos e consultoria.
</div>
<div class="recommendation">
    <strong>Planejamento Tributário:</strong> Revise opções de reestruturação da Norma no. 4
    (holding, cisão) para otimizar o impacto do ICMS antes da reclassificação.
</div>
<div class="recommendation">
    <strong>Qualidade:</strong> Implemente monitoramento automatizado de qualidade com
    limiares IDA da Anatel como linhas de base para alertas.
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
        report_type="Viabilidade Rural",
        title=f"Estudo de Viabilidade Rural — ({community_lat:.4f}, {community_lon:.4f})",
        generated_at=datetime.utcnow(),
        generated_by="Pulso Network",
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
    power_label = "Rede elétrica disponível" if grid_power else "Sem rede elétrica (solar necessário)"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_html_header(meta)}

<h2>Resumo Executivo</h2>
<div class="summary-box">
    Estudo de viabilidade rural para comunidade nas coordenadas
    ({community_lat:.4f}, {community_lon:.4f}) com população de
    <strong>{population:,}</strong> cobrindo <strong>{area_km2:.1f} km&sup2;</strong>.
    Energia: <strong>{power_label}</strong>.
    Este relatório inclui projeto de rede, lista de equipamentos, estimativas
    de custo, análise de demanda e elegibilidade para programas de financiamento.
</div>

<h2>Perfil da Comunidade</h2>
<table>
    <tr><th>Parâmetro</th><th>Valor</th></tr>
    <tr><td>Localização</td><td>({community_lat:.4f}, {community_lon:.4f})</td></tr>
    <tr><td>População</td><td>{population:,}</td></tr>
    <tr><td>Área</td><td>{area_km2:.1f} km&sup2;</td></tr>
    <tr><td>Energia</td><td>{power_label}</td></tr>
</table>

{design_section}

{demand_section}

{solar_section}

<h2>Programas de Financiamento</h2>
<div class="summary-box">
    Programas governamentais potencialmente elegíveis para financiamento
    de infraestrutura de telecomunicações em áreas rurais.
</div>
<table>
    <tr><th>Programa</th><th>Tipo</th><th>Valor Máximo</th><th>Descrição</th></tr>
    <tr><td>FUST</td><td>Crédito</td><td>R$5.000.000</td><td>Fundo de universalização para municípios &lt; 30 mil hab.</td></tr>
    <tr><td>Norte Conectado</td><td>Parceria</td><td>Variável</td><td>Backbone de fibra na Amazônia Legal</td></tr>
    <tr><td>Novo PAC</td><td>Parceria</td><td>R$10.000.000</td><td>Expansão 4G/5G para áreas não atendidas</td></tr>
    <tr><td>BNDES ProConectividade</td><td>Crédito</td><td>R$20.000.000</td><td>Financiamento de infraestrutura para ISPs</td></tr>
</table>

<h2>Recomendações</h2>
<div class="recommendation">
    <strong>Próximos Passos:</strong>
    <ol>
        <li>Validar localização e população da comunidade com dados IBGE</li>
        <li>Realizar visita técnica para visada de backhaul e posicionamento de torre</li>
        <li>Verificar elegibilidade para programas de financiamento com código do município</li>
        <li>Preparar documentação técnica para pedidos de financiamento</li>
        <li>Obter licenças ambientais se localização Amazônica/ribeirinha</li>
    </ol>
</div>

{_html_footer(meta)}
</body>
</html>"""

    return _render_to_bytes(html)
