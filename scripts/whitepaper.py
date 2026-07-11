"""ENLACE RF whitepaper — investor & user grade, with flow diagrams.

Every quantitative claim is verified against the database (rf_calibration_eval,
rf_band_offsets, corpus counts pulled 2026-07-11) or the shipped product.
Regenerate: python3 scripts/whitepaper.py
Output: outputs/whitepaper/enlace-rf-whitepaper.pdf
"""

from __future__ import annotations

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ACCENT = colors.HexColor("#0D9488")
ACCENT_DARK = colors.HexColor("#0B7C72")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#737D87")
BG = colors.HexColor("#F2F1EE")
LINE = colors.HexColor("#D8D6D0")
AMBER = colors.HexColor("#B45309")

OUT = "outputs/whitepaper"
PDF = os.path.join(OUT, "enlace-rf-whitepaper.pdf")

W_PAGE, H_PAGE = A4
CONTENT_W = W_PAGE - 36 * mm

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

S = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21,
                         textColor=INK, spaceBefore=10, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                         textColor=ACCENT_DARK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.8, leading=14.6,
                           textColor=INK, spaceAfter=5, alignment=4),  # justified
    "bodyL": ParagraphStyle("bodyL", fontName="Helvetica", fontSize=9.8, leading=14.6,
                            textColor=INK, spaceAfter=5),
    "lead": ParagraphStyle("lead", fontName="Helvetica", fontSize=11.5, leading=17,
                           textColor=INK, spaceAfter=8),
    "mut": ParagraphStyle("mut", fontName="Helvetica", fontSize=8.3, leading=11.8,
                          textColor=MUTED, spaceAfter=4),
    "cap": ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=8.3, leading=11.5,
                          textColor=MUTED, spaceBefore=3, spaceAfter=10, alignment=1),
    "cellh": ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=8.8, leading=12,
                            textColor=INK),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.8, leading=12,
                           textColor=INK),
    "kpiN": ParagraphStyle("kpiN", fontName="Helvetica-Bold", fontSize=17, leading=20,
                           textColor=ACCENT_DARK, alignment=1),
    "kpiL": ParagraphStyle("kpiL", fontName="Helvetica", fontSize=7.8, leading=10.5,
                           textColor=MUTED, alignment=1),
    "toc": ParagraphStyle("toc", fontName="Helvetica", fontSize=10.5, leading=19,
                          textColor=INK),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, style="bodyL"):
    return [Paragraph(f"•&nbsp;&nbsp;{t}", S[style]) for t in items]


def table(rows, widths, header=True, align_right_from=None):
    data = []
    for i, row in enumerate(rows):
        st = S["cellh"] if (header and i == 0) else S["cell"]
        data.append([Paragraph(str(c), st) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), BG),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
        ]
    else:
        style += [("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE)]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Flow diagram flowable
# ---------------------------------------------------------------------------

class FlowDiagram(Flowable):
    """Boxes-and-arrows diagram. Coordinates in mm, origin bottom-left."""

    def __init__(self, width_mm, height_mm, nodes, edges, title=None):
        super().__init__()
        self.width = width_mm * mm
        self.height = height_mm * mm
        self.nodes = {n[0]: n for n in nodes}  # id: (id, x, y, w, h, lines, kind)
        self.edges = edges                      # (a, b, label, side)
        self.title = title

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _box(self, c, x, y, w, h, lines, kind):
        x, y, w, h = x * mm, y * mm, w * mm, h * mm
        if kind == "accent":
            c.setFillColor(ACCENT)
            c.setStrokeColor(ACCENT_DARK)
        elif kind == "store":
            c.setFillColor(BG)
            c.setStrokeColor(MUTED)
        elif kind == "warn":
            c.setFillColor(colors.HexColor("#FDF3E7"))
            c.setStrokeColor(AMBER)
        else:
            c.setFillColor(colors.white)
            c.setStrokeColor(ACCENT)
        c.setLineWidth(0.9)
        c.roundRect(x, y, w, h, 1.8 * mm, stroke=1, fill=1)
        c.setFillColor(colors.white if kind == "accent" else INK)
        n = len(lines)
        fs = 7.2
        lh = 8.6
        ty = y + h / 2 + (n - 1) * lh / 2 - fs * 0.36
        for i, ln in enumerate(lines):
            c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", fs)
            if i > 0 and kind != "accent":
                c.setFillColor(MUTED)
            c.drawCentredString(x + w / 2, ty - i * lh, ln)
            c.setFillColor(colors.white if kind == "accent" else INK)

    def _edge_pt(self, node, side):
        _, x, y, w, h, _, _ = node
        return {
            "r": (x + w, y + h / 2), "l": (x, y + h / 2),
            "t": (x + w / 2, y + h), "b": (x + w / 2, y),
        }[side]

    def _arrow(self, c, a, b, label, sides):
        (x1, y1) = self._edge_pt(self.nodes[a], sides[0])
        (x2, y2) = self._edge_pt(self.nodes[b], sides[1])
        x1, y1, x2, y2 = x1 * mm, y1 * mm, x2 * mm, y2 * mm
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.9)
        if abs(y1 - y2) < 0.1 or abs(x1 - x2) < 0.1:
            c.line(x1, y1, x2, y2)
        else:  # elbow: horizontal then vertical
            c.line(x1, y1, x2, y1)
            c.line(x2, y1, x2, y2)
        # arrowhead at (x2,y2), direction from last segment
        import math
        if abs(y1 - y2) < 0.1 or (abs(x1 - x2) >= 0.1 and abs(y1 - y2) < 0.1):
            ang = math.atan2(0, x2 - x1)
        elif abs(x1 - x2) < 0.1:
            ang = math.atan2(y2 - y1, 0)
        else:
            ang = math.atan2(y2 - y1, 0)
        s = 2.2 * mm
        c.setFillColor(MUTED)
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2 - s * math.cos(ang - 0.42), y2 - s * math.sin(ang - 0.42))
        p.lineTo(x2 - s * math.cos(ang + 0.42), y2 - s * math.sin(ang + 0.42))
        p.close()
        c.drawPath(p, stroke=0, fill=1)
        if label:
            c.setFont("Helvetica", 6.6)
            c.setFillColor(MUTED)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if abs(y1 - y2) < 0.1:
                c.drawCentredString(mx, my + 1.6 * mm, label)
            else:
                c.drawString(x2 + 1.5 * mm, (y1 + y2) / 2, label)

    def draw(self):
        c = self.canv
        if self.title:
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(MUTED)
            c.drawString(0, self.height - 3 * mm, self.title.upper())
        for e in self.edges:
            a, b, label, sides = e
            self._arrow(c, a, b, label, sides)
        for n in self.nodes.values():
            self._box(c, n[1], n[2], n[3], n[4], n[5], n[6])


# ---------------------------------------------------------------------------
# Diagrams
# ---------------------------------------------------------------------------

def diagram_arch():
    """D1 — platform architecture."""
    nodes = [
        ("dados", 2, 26, 40, 20, ["5 CAMADAS DE DADOS", "SRTM · GLO-30 · ANADEM", "MapBiomas · Open Buildings", "(sob demanda, cache local)"], "store"),
        ("engine", 52, 26, 36, 20, ["MOTOR RUST", "gRPC :50051", "física + difração", "grades de cobertura"], "accent"),
        ("api", 98, 26, 36, 20, ["API FASTAPI", "auth JWT · estudos", "exportação · calibração", "app.enlace.network/api"], "accent"),
        ("calib", 52, 2, 36, 15, ["POSTGRES", "3,88 M medições Anatel", "curvas de correção"], "store"),
        ("web", 144, 36, 30, 12, ["PLANNER WEB", "deck.gl · pt-BR"], "plain"),
        ("apiclient", 144, 20, 30, 12, ["API CLIENTES", "lote · integração"], "plain"),
        ("pdf", 144, 4, 30, 12, ["EXPORTAÇÃO", "PDF · KMZ · GeoJSON"], "plain"),
    ]
    edges = [
        ("dados", "engine", "", ("r", "l")),
        ("engine", "api", "gRPC", ("r", "l")),
        ("calib", "api", "correções", ("t", "b")),
        ("api", "web", "", ("r", "l")),
        ("api", "apiclient", "", ("r", "l")),
        ("api", "pdf", "", ("r", "l")),
    ]
    return FlowDiagram(174, 52, nodes, edges, "Figura 1 — Arquitetura da plataforma")


def diagram_dados():
    """D2 — on-demand data pipeline."""
    nodes = [
        ("req", 2, 20, 30, 14, ["COORDENADA", "qualquer ponto", "do Brasil"], "plain"),
        ("cache", 40, 20, 30, 14, ["CACHE LOCAL?", "tile 1°×1°"], "plain"),
        ("fetch", 78, 20, 42, 14, ["DOWNLOAD ABERTO", "OpenTopography · AWS", "Google Cloud Storage"], "store"),
        ("conv", 128, 20, 30, 14, ["CONVERSÃO", "GeoTIFF → .hgt/.lc", "3601² · int16/uint8"], "plain"),
        ("perfil", 78, 2, 42, 12, ["PERFIL / GRADE", "amostragem k=4/3 (curvatura)"], "accent"),
    ]
    edges = [
        ("req", "cache", "", ("r", "l")),
        ("cache", "fetch", "não", ("r", "l")),
        ("fetch", "conv", "", ("r", "l")),
        ("cache", "perfil", "sim", ("b", "t")),
        ("conv", "perfil", "", ("b", "t")),
    ]
    return FlowDiagram(174, 40, nodes, edges,
                       "Figura 2 — Aquisição de dados sob demanda (sem espelho nacional prévio)")


def diagram_fisica():
    """D3 — physics chain."""
    nodes = [
        ("inp", 2, 20, 26, 16, ["ENTRADA", "torre · rádio", "frequência", "alturas"], "plain"),
        ("env", 34, 20, 30, 16, ["AMBIENTE", "MapBiomas →", "urbano/suburb./rural"], "plain"),
        ("base", 70, 20, 32, 16, ["PERDA-BASE", "Hata/COST-231", "3GPP TR 38.901", "piso FSPL"], "accent"),
        ("difr", 108, 20, 32, 16, ["DIFRAÇÃO", "Deygout multi-", "obstáculo (P.526)", "DSM/DTM/solo"], "accent"),
        ("clima", 70, 2, 32, 12, ["CLIMA/EDIFÍCIO", "chuva P.837", "entrada P.2109"], "plain"),
        ("corr", 108, 2, 32, 12, ["CORREÇÃO", "calibrada por", "ambiente (§5)"], "warn"),
        ("out", 146, 12, 28, 20, ["SAÍDA", "P50 / P90", "sigma calibrado", "margem · Fresnel"], "accent"),
    ]
    edges = [
        ("inp", "env", "", ("r", "l")),
        ("env", "base", "", ("r", "l")),
        ("base", "difr", "", ("r", "l")),
        ("difr", "out", "", ("r", "l")),
        ("clima", "out", "", ("r", "l")),
        ("corr", "out", "", ("r", "l")),
    ]
    return FlowDiagram(174, 42, nodes, edges, "Figura 3 — Cadeia física do modelo")


def diagram_calib():
    """D4 — calibration loop."""
    nodes = [
        ("rni", 2, 34, 38, 14, ["ANATEL RNI", "3,88 M medições", "de campo (2005–2025)"], "store"),
        ("smp", 2, 16, 38, 14, ["REGISTRO SMP", "3,24 M setores", "112 mil estações (diário)"], "store"),
        ("pred", 50, 25, 34, 16, ["PREDIÇÃO", "composta por", "estação próxima", "(motor completo)"], "accent"),
        ("resid", 94, 25, 32, 16, ["RESÍDUOS", "3,55 M pontos", "medido − previsto", "classif. MapBiomas"], "plain"),
        ("fit", 136, 34, 38, 13, ["AJUSTE (80%)", "a + b·log10(d)", "por ambiente + banda"], "accent"),
        ("eval", 136, 14, 38, 13, ["AVALIAÇÃO (20%)", "held-out, nunca", "visto pelo ajuste"], "warn"),
        ("apply", 94, 2, 32, 11, ["APLICAÇÃO", "na API (§4)"], "accent"),
    ]
    edges = [
        ("rni", "pred", "", ("r", "l")),
        ("smp", "pred", "", ("r", "l")),
        ("pred", "resid", "", ("r", "l")),
        ("resid", "fit", "80%", ("r", "l")),
        ("resid", "eval", "20%", ("r", "l")),
        ("fit", "apply", "curvas", ("b", "t")),
    ]
    return FlowDiagram(174, 50, nodes, edges,
                       "Figura 4 — Loop de calibração e avaliação honesta (split 80/20)")


def diagram_roadmap():
    """D5 — roadmap."""
    nodes = [
        ("now", 2, 14, 40, 18, ["HOJE (no ar)", "planner público", "calibração v1/v2", "benchmark publicado"], "accent"),
        ("f1", 50, 14, 40, 18, ["FASE SEGUINTE", "correção no motor", "(requer EIRP real", "por estação)"], "plain"),
        ("f2", 98, 14, 40, 18, ["FROTA-SENSOR", "telemetria de CPEs", "calibração contínua", "(inicia com piloto)"], "plain"),
        ("f3", 146, 14, 28, 18, ["GPU + ML", "ray tracing 2.5D", "mapa nacional", "instantâneo"], "plain"),
    ]
    edges = [
        ("now", "f1", "", ("r", "l")),
        ("f1", "f2", "", ("r", "l")),
        ("f2", "f3", "", ("r", "l")),
    ]
    return FlowDiagram(174, 36, nodes, edges, "Figura 6 — Roteiro tecnológico")


def diagram_gtm():
    """D5b — client ladder."""
    nodes = [
        ("t0", 2, 2, 40, 26, ["AUTOATENDIMENTO", "micro-WISPs", "integradores FWA", "Teste R$0 → WISP R$149"], "plain"),
        ("t1", 50, 2, 40, 26, ["ASSISTIDO", "ISPs regionais", "consultorias RF", "Provedor R$499"], "plain"),
        ("t2", 98, 2, 40, 26, ["ENTERPRISE", "torres · M&A · bancos", "governo · operadoras", "sob consulta"], "accent"),
        ("cash", 146, 8, 28, 14, ["RECEITA", "recorrente +", "projetos"], "store"),
    ]
    edges = [
        ("t0", "t1", "upgrade", ("r", "l")),
        ("t1", "t2", "upgrade", ("r", "l")),
        ("t2", "cash", "", ("r", "l")),
    ]
    return FlowDiagram(174, 32, nodes, edges, "Figura 5 — Escada de clientes (9 perfis, 3 degraus)")


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------

def on_cover(c, doc):
    c.saveState()
    c.setFillColor(ACCENT)
    c.rect(0, 0, W_PAGE, H_PAGE, stroke=0, fill=1)
    c.setFillColor(ACCENT_DARK)
    c.rect(0, 0, W_PAGE, 70 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(20 * mm, H_PAGE - 24 * mm, "ENLACE")
    c.setFont("Helvetica", 9.5)
    c.drawString(20 * mm, H_PAGE - 30 * mm, "enlace.network · app.enlace.network")
    c.setFont("Helvetica-Bold", 30)
    c.drawString(20 * mm, H_PAGE - 105 * mm, "Propagação de RF calibrada")
    c.drawString(20 * mm, H_PAGE - 117 * mm, "em escala nacional")
    c.setFont("Helvetica", 13)
    c.drawString(20 * mm, H_PAGE - 132 * mm, "Whitepaper técnico e de negócio — Brasil")
    c.setFont("Helvetica", 10.5)
    y = H_PAGE - 152 * mm
    for line in [
        "O único planejador de rádio do mercado brasileiro com erro medido,",
        "publicado e reproduzível: calibrado e avaliado out-of-sample contra",
        "3,55 milhões de medições de campo do próprio regulador.",
    ]:
        c.drawString(20 * mm, y, line)
        y -= 6.2 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, 58 * mm, f"Versão 1.0 · {date.today().strftime('%d/%m/%Y')}")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, 51 * mm, "contato@enlace.network")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#BFE9E4"))
    c.drawString(20 * mm, 20 * mm,
                 "Metodologia pública: enlace.network/validation · Preços: enlace.network/pricing")
    c.restoreState()


def on_page(c, doc):
    c.saveState()
    c.setFillColor(ACCENT)
    c.rect(0, H_PAGE - 9 * mm, W_PAGE, 9 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(18 * mm, H_PAGE - 6.3 * mm, "ENLACE · Whitepaper — Propagação RF calibrada")
    c.setFont("Helvetica", 8.5)
    c.drawRightString(W_PAGE - 18 * mm, H_PAGE - 6.3 * mm, "v1.0 · julho 2026")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(18 * mm, 11 * mm, "Enlace · contato@enlace.network · app.enlace.network")
    c.drawRightString(W_PAGE - 18 * mm, 11 * mm, f"{doc.page}")
    c.restoreState()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def kpi_row():
    kpis = [
        ("3,55 M", "medições de campo usadas na avaliação"),
        ("7,0 dB", "RMSE urbano held-out (antes: 25,8)"),
        ("100%", "do território nacional, sob demanda"),
        ("19/19", "testes e2e no produto público"),
        ("R$ 0–499", "autoatendimento + Enterprise"),
    ]
    cells = [[Paragraph(n, S["kpiN"]) for n, _ in kpis],
             [Paragraph(l, S["kpiL"]) for _, l in kpis]]
    t = Table(cells, colWidths=[CONTENT_W / 5] * 5)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, ACCENT),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def build():
    os.makedirs(OUT, exist_ok=True)
    doc = SimpleDocTemplate(
        PDF, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="ENLACE — Whitepaper: Propagação de RF calibrada em escala nacional",
        author="Enlace",
    )
    st = []

    # Page 1 is the cover (drawn by on_cover); content starts on page 2.
    st.append(PageBreak())

    # ---- TOC ------------------------------------------------------------
    st.append(P("Sumário", "h1"))
    for i, (sec, pg) in enumerate([
        ("Sumário executivo", ""),
        ("O problema: planejar rádio no Brasil é caro, lento e não auditável", ""),
        ("A plataforma: arquitetura e produto", ""),
        ("Os dados: cinco camadas nacionais, sob demanda", ""),
        ("A física: cadeia de modelos ITU-R / 3GPP", ""),
        ("A calibração: 3,55 milhões de medições do regulador", ""),
        ("Validação: números, método e limites declarados", ""),
        ("Go-to-market: nove perfis de cliente, três degraus", ""),
        ("Roteiro tecnológico e barreiras de entrada", ""),
        ("Riscos e mitigação", ""),
        ("Conclusão e contato", ""),
    ], 1):
        st.append(Paragraph(f"<b>{i}.</b>&nbsp;&nbsp;{sec}", S["toc"]))
    st.append(Spacer(1, 6 * mm))
    st.append(HRFlowable(width="100%", thickness=0.5, color=LINE))
    st.append(Spacer(1, 3 * mm))
    st.append(P("Este documento destina-se a investidores, parceiros e usuários "
                "técnicos. Todos os números quantitativos são medidos (não "
                "projetados) e reproduzíveis a partir de dados públicos; a "
                "metodologia completa está publicada em enlace.network/validation.", "mut"))
    st.append(PageBreak())

    # ---- 1. Executive summary -------------------------------------------
    st.append(P("1. Sumário executivo", "h1"))
    st.append(P("O Enlace é uma plataforma de planejamento de radiofrequência que "
                "responde, para qualquer coordenada do Brasil, a pergunta que decide "
                "investimentos de rede: <b>“se eu instalar um rádio aqui, onde o sinal "
                "chega — e com que confiança?”</b>", "lead"))
    st.append(kpi_row())
    st.append(Spacer(1, 5 * mm))
    st.append(P("Três fatos distinguem o Enlace de todo planejador de RF disponível "
                "no mercado brasileiro:"))
    st += bullets([
        "<b>Erro medido, não prometido.</b> Calibramos o modelo contra 3,55 milhões "
        "de medições de campo da Anatel e publicamos o erro em avaliação "
        "out-of-sample: RMSE de 7,0 dB em área urbana (o modelo físico puro erra "
        "25,8 dB). Nenhum concorrente publica número equivalente para o Brasil.",
        "<b>Dados nacionais completos, custo marginal próximo de zero.</b> Terreno "
        "30 m, superfície com vegetação, solo exposto, uso do solo e altura de "
        "edifícios (0,5 m) — cinco camadas abertas, buscadas sob demanda e "
        "cacheadas. Nenhum licenciamento de dados de terceiros.",
        "<b>Produto no ar e vendável hoje.</b> Planner web público "
        "(app.enlace.network) com autenticação real, estudos exportáveis em "
        "PDF/KMZ/GeoJSON, preços publicados (R$ 0 a R$ 499/mês + Enterprise) e "
        "prospectos para nove perfis de cliente.",
    ])
    st.append(P("A tese de investimento é direta: o mercado brasileiro de provedores "
                "regionais é numeroso e mal servido — as ferramentas profissionais "
                "custam milhares de dólares por licença e nenhuma é calibrada para o "
                "território brasileiro. O Enlace entrega acurácia auditável a preço de "
                "SaaS nacional, e a base de calibração (que melhora com cada nova "
                "medição) forma uma barreira de entrada cumulativa.", "body"))

    # ---- 2. Problema -----------------------------------------------------
    st.append(P("2. O problema", "h1"))
    st.append(P("Toda rede sem fio começa com uma previsão de propagação. Errar essa "
                "previsão custa caro em qualquer escala:"))
    st += bullets([
        "<b>Para o pequeno provedor</b>, uma instalação que “não fecha o link” é uma "
        "visita técnica perdida e um cliente frustrado — margens que o provedor de "
        "bairro não tem.",
        "<b>Para o ISP regional</b>, escolher a cidade errada para expansão FWA "
        "imobiliza capex em POPs de baixa performance e gera churn onde a cobertura "
        "prometida não se confirma.",
        "<b>Para o investidor e o financiador</b>, o mapa de cobertura declarado por "
        "um ativo em due diligence raramente foi verificado por física independente.",
        "<b>Para o regulador</b>, fiscalizar obrigações de cobertura em escala exige "
        "instrumento técnico que hoje não existe fora de campanhas de drive test.",
    ])
    st.append(P("As ferramentas estabelecidas atendem mal a esse mercado: são "
                "licenciadas por milhares de dólares por engenheiro, rodam em "
                "desktop, exigem que o usuário providencie os próprios dados de "
                "terreno e clutter — e, criticamente, <b>não declaram o erro de suas "
                "previsões no Brasil</b>. A previsão sem barra de erro é opinião com "
                "gráfico.", "body"))

    # ---- 3. Plataforma ---------------------------------------------------
    st.append(P("3. A plataforma", "h1"))
    st.append(diagram_arch())
    st.append(P("Figura 1: as cinco camadas de dados alimentam um motor de cálculo em "
                "Rust (perfis, difração e grades de cobertura em milissegundos), "
                "exposto por uma API FastAPI que serve o planner web, integrações via "
                "API e a exportação de estudos. O banco de calibração alimenta as "
                "correções aplicadas a cada estudo.", "cap"))
    st.append(P("O produto no ar", "h2"))
    st.append(P("Em app.enlace.network, o usuário cria conta, clica em qualquer ponto "
                "do mapa e obtém: perfil de terreno com zona de Fresnel e difração; "
                "orçamento de enlace com chuva regional (ITU-R P.837) e perda de "
                "entrada em edifícios (P.2109); cobertura setorial P50/P90 com "
                "incerteza calibrada; presets dos rádios mais vendidos (Ubiquiti, "
                "Cambium, Mimosa, Intelbras); busca por endereço; projetos salvos; e "
                "exportação em PDF, KMZ e GeoJSON. A qualidade é verificada por 19 "
                "testes de navegador de ponta a ponta contra a URL pública e 497 "
                "testes de unidade/integração.", "body"))
    img_w = CONTENT_W
    img_h = img_w * 900 / 1440
    st.append(Image("outputs/e2e_1_enlace.png", width=img_w, height=img_h))
    st.append(P("O planner em produção: estudo de enlace ponto-a-ponto sobre modelo "
                "de superfície (DSM), com Fresnel, margem e disponibilidade.", "cap"))
    st.append(Image("outputs/e2e_2_coverage.png", width=img_w, height=img_h))
    st.append(P("Cobertura calibrada: grade de 14 mil pontos com sombra de terreno, "
                "ambiente inferido por uso do solo e P50/P90.", "cap"))

    # ---- 4. Dados ---------------------------------------------------------
    st.append(P("4. Os dados: cinco camadas nacionais, sob demanda", "h1"))
    st.append(P("A plataforma não depende de licenciamento de dados de terceiros. "
                "Cinco camadas abertas cobrem 100% do território:"))
    st.append(table([
        ["Camada", "Fonte", "Resolução", "Papel no modelo"],
        ["Terreno (DTM)", "SRTM GL1 (NASA)", "30 m", "elevação básica, difração"],
        ["Superfície (DSM)", "Copernicus GLO-30 (ESA)", "30 m", "vegetação + construções no perfil"],
        ["Solo exposto", "ANADEM v1 (INPE/UFRGS)", "30 m", "altura real acima do solo"],
        ["Uso do solo", "MapBiomas C9", "30 m", "classificação urbano/suburbano/rural"],
        ["Edifícios 2.5D", "Google Open Buildings", "0,5 m", "altura de prédios no enlace"],
    ], [30 * mm, 48 * mm, 22 * mm, 74 * mm]))
    st.append(Spacer(1, 4 * mm))
    st.append(diagram_dados())
    st.append(P("Figura 2: nenhum espelho nacional é necessário — o tile de 1°×1° é "
                "baixado na primeira consulta àquela região e cacheado. O custo de "
                "infraestrutura cresce com o uso, não com o território.", "cap"))

    # ---- 5. Física ---------------------------------------------------------
    st.append(P("5. A física: cadeia de modelos ITU-R / 3GPP", "h1"))
    st.append(diagram_fisica())
    st.append(P("Figura 3: perda-base despachada por ambiente com piso de espaço "
                "livre; difração de múltiplos obstáculos por Deygout sobre o perfil "
                "real; efeitos de clima e edifício; correção calibrada; saída "
                "probabilística.", "cap"))
    st += bullets([
        "<b>Perda-base por ambiente:</b> Hata/COST-231 e 3GPP TR 38.901 (RMa/UMa), "
        "com o espaço livre como piso físico — o modelo nunca prevê sinal melhor "
        "que o vácuo.",
        "<b>Difração de terreno:</b> método de Deygout com gume de faca ITU-R P.526 "
        "sobre até 200 amostras de perfil, em qualquer das três superfícies "
        "(terreno, superfície, solo).",
        "<b>Clima e edifício:</b> atenuação por chuva com intensidade R0,01 regional "
        "(ITU-R P.837, grade própria por coordenada) e perda de entrada em "
        "edifícios (P.2109) para recepção indoor.",
        "<b>Saída probabilística:</b> cada ponto carrega um sigma de sombreamento; a "
        "cobertura é reportada em P50 (mediana) e P90 (conservadora) — 9 em 10 "
        "pontos previstos cobertos no P90 devem ter sinal de fato.",
    ])

    # ---- 6. Calibração -----------------------------------------------------
    st.append(P("6. A calibração: o que nos separa de todos os outros", "h1"))
    st.append(P("Modelos físicos genéricos erram de forma sistemática: superestimam "
                "sinal perto da torre (o feixe da antena passa por cima do medidor) e "
                "subestimam efeitos locais de clutter tropical. A resposta do Enlace "
                "é medir esse erro no maior acervo de medições de campo do país — o "
                "do próprio regulador — e corrigi-lo.", "body"))
    st.append(diagram_calib())
    st.append(P("Figura 4: medições RNI georreferenciadas são confrontadas com a "
                "predição do motor para as estações licenciadas próximas (registro "
                "SMP, atualizado diariamente). Os resíduos são classificados por "
                "ambiente via MapBiomas; 80% ajustam curvas de correção por ambiente "
                "e banda; os 20% restantes — nunca vistos pelo ajuste — produzem os "
                "números da Tabela 2.", "cap"))
    st.append(P("Dois níveis de rigor", "h2"))
    st += bullets([
        "<b>Tier 1 (atribuído):</b> 1,72 milhão de resíduos onde a medição é "
        "vinculada a estações licenciadas identificadas — o cenário de maior "
        "confiança na atribuição.",
        "<b>Tier 2 (cego, por proximidade):</b> o restante do acervo, previsto às "
        "cegas pela composição das estações próximas — teste mais duro, mais "
        "próximo do uso real. O erro urbano cai de 28,6 para 8,3 dB.",
    ])

    # ---- 7. Validação -------------------------------------------------------
    st.append(P("7. Validação: números, método e limites", "h1"))
    st.append(P("Tabela 2 — Erro held-out do modelo calibrado (20% nunca vistos pelo ajuste)", "h2"))
    st.append(table([
        ["Fatia", "N (teste)", "RMSE físico puro", "RMSE calibrado"],
        ["Urbano — atribuído (tier 1)", "257.446", "25,8 dB", "<b>7,0 dB</b>"],
        ["Suburbano — atribuído", "13.625", "26,1 dB", "<b>7,6 dB</b>"],
        ["Rural — atribuído", "35.621", "25,6 dB", "<b>8,3 dB</b>"],
        ["Urbano — cego por proximidade (tier 2)", "359.914", "28,6 dB", "<b>8,3 dB</b>"],
        ["Suburbano — cego (tier 2)", "1.588", "25,8 dB", "<b>8,5 dB</b>"],
        ["Rural — cego (tier 2)", "3.452", "24,8 dB", "<b>8,8 dB</b>"],
    ], [66 * mm, 26 * mm, 40 * mm, 42 * mm]))
    st.append(Spacer(1, 4 * mm))
    st.append(P("Tabela 3 — Offsets por banda, medidos de estações de banda única", "h2"))
    st.append(table([
        ["Banda", "700 MHz", "850 MHz", "900 MHz", "1800 MHz", "2100 MHz", "2500 MHz"],
        ["Offset medido", "+11,8 dB", "+6,4 dB", "+11,2 dB", "+3,0 dB", "+8,0 dB", "+1,5 dB"],
        ["N estações-medição", "547", "7.420", "1.046", "3.687", "5.128", "9.976"],
    ], [34 * mm, 23 * mm, 23 * mm, 23 * mm, 24 * mm, 24 * mm, 23 * mm]))
    st.append(P("A estrutura é fisicamente coerente: bandas baixas propagam além do "
                "modelo genérico (700 MHz supera 2,5 GHz em ~10 dB após correção de "
                "distância), caminhos sobre água perdem ~4 dB menos que sobre terra, "
                "e o viés de −26 dB sob a torre decaindo a ~0 dB em 1,5–2 km é a "
                "assinatura do downtilt das antenas setoriais — aprendida dos dados, "
                "não assumida. A variante ciente de banda atinge 8,0 dB no subconjunto "
                "held-out de banda única.", "body"))
    st.append(P("O que declaramos como limite (e por quê)", "h2"))
    st += bullets([
        "<b>EIRP típico por banda, não por estação:</b> o registro público SMP não "
        "traz potência/altura por setor; usamos EIRP típico por banda. As correções "
        "absorvem o erro médio dessa hipótese; o desvio estação-a-estação permanece "
        "no sigma. A exportação técnica do Mosaico ou telemetria de piloto removerá "
        "essa hipótese (§9).",
        "<b>Medições RNI são banda larga:</b> o medidor integra todas as emissoras "
        "co-localizadas; a atribuição por proximidade é probabilística — por isso "
        "reportamos o tier 2 cego separadamente, e ele sustenta 8,3 dB urbano.",
        "<b>Correções hoje aplicadas na API</b> (não dentro do motor Rust) — decisão "
        "deliberada até desembaraçar EIRP de propagação (§9).",
    ])
    st.append(P("Metodologia completa, scripts e artefato de validação são públicos: "
                "enlace.network/validation. Qualquer terceiro com acesso aos dados "
                "abertos da Anatel reproduz a Tabela 2.", "mut"))

    # ---- 8. GTM -------------------------------------------------------------
    st.append(P("8. Go-to-market: nove perfis, três degraus", "h1"))
    st.append(diagram_gtm())
    st.append(P("Figura 5: o mesmo motor serve do provedor de bairro (autoatendimento "
                "R$ 149/mês) à operadora nacional (Enterprise) — o custo de servir um "
                "estudo adicional é próximo de zero.", "cap"))
    st.append(table([
        ["Perfil", "Dor central", "Produto", "Plano"],
        ["Micro-WISPs", "instalação errada consome a margem", "estudo por clique + presets", "Teste/WISP"],
        ["Integradores FWA", "proposta sem estudo perde", "viabilidade remota + KMZ", "WISP/Provedor"],
        ["Consultorias RF", "laudo precisa de lastro", "benchmark citável + white-label", "Provedor/Ent."],
        ["ISPs regionais", "priorizar expansão", "cobertura P90 setorial + API", "Provedor"],
        ["Fundos / M&A", "cobertura declarada não auditada", "due diligence em lote", "Enterprise"],
        ["Towercos", "precificar verticais", "footprint por torre em lote", "Enterprise"],
        ["Bancos / BNDES", "risco técnico mal precificado", "parecer independente, milestone P90", "Enterprise"],
        ["Governo / regulador", "fiscalizar em escala", "verificação física por município", "Enterprise"],
        ["Operadoras", "calibração genérica global", "segundo par de olhos calibrado BR", "Enterprise"],
    ], [32 * mm, 52 * mm, 58 * mm, 32 * mm]))
    st.append(Spacer(1, 3 * mm))
    st.append(P("Preços publicados (enlace.network/pricing): Teste R$ 0 (5 "
                "estudos/mês) · WISP R$ 149/mês · Provedor R$ 499/mês · Enterprise "
                "sob consulta. Pagamento online em implantação; ativação por contato. "
                "Prospectos individuais por perfil: enlace.network/prospectos/.", "body"))

    # ---- 9. Roadmap -----------------------------------------------------------
    st.append(P("9. Roteiro tecnológico e barreiras de entrada", "h1"))
    st.append(diagram_roadmap())
    st.append(P("Figura 6: cada fase aprofunda a vantagem de dados — o ativo que um "
                "concorrente não copia baixando os mesmos rasters públicos.", "cap"))
    st += bullets([
        "<b>Correção dentro do motor:</b> aplicar as curvas por ambiente/banda no "
        "cálculo da grade (hoje na API). Destravado por potências reais por estação "
        "(exportação técnica Mosaico) ou telemetria de piloto.",
        "<b>Frota como sensor:</b> agente leve nos CPEs dos ISPs clientes reporta "
        "nível de sinal georreferenciado → calibração contínua e hiperlocal. Cada "
        "cliente novo melhora o modelo que serve todos os clientes — efeito de rede "
        "técnico, não apenas comercial.",
        "<b>GPU ray tracing + ML:</b> traçado de raios sobre os edifícios 2.5D para "
        "área densa e um surrogate neural para mapas nacionais instantâneos.",
    ])
    st.append(P("Por que é difícil copiar", "h2"))
    st.append(P("Os rasters são públicos; a barreira não está neles. Está em (i) 3,55 "
                "milhões de resíduos processados, classificados e auditados — meses de "
                "engenharia de dados contra fontes com peculiaridades não documentadas; "
                "(ii) no pipeline diário contra o registro de licenciamento; (iii) no "
                "benchmark publicado que obriga qualquer entrante a competir em acurácia "
                "declarada, não em marketing; e (iv), com a frota-sensor, em dados "
                "proprietários que nenhum acervo público contém.", "body"))

    # ---- 10. Riscos -------------------------------------------------------------
    st.append(P("10. Riscos e mitigação", "h1"))
    st.append(table([
        ["Risco", "Mitigação"],
        ["Hipótese de EIRP típico distorce correções por banda",
         "declarada e quantificada (§7); exportação Mosaico ou telemetria de piloto elimina"],
        ["Dependência de fontes abertas (SRTM, GLO-30, MapBiomas…)",
         "cinco fontes independentes, cache local; nenhuma tem histórico de fechamento"],
        ["Concorrente global adiciona calibração Brasil",
         "nossa vantagem é o loop (dados → correção → benchmark público) e o custo BR; a frota-sensor amplia"],
        ["Adoção lenta do autoatendimento",
         "escada de 9 perfis: Enterprise (due diligence, torres, bancos) monetiza cedo com tíquetes maiores"],
        ["Responsabilidade técnica de estudos (Lei 5.194/66)",
         "posicionamento como ferramenta de cálculo; laudo permanece com engenheiro habilitado; disclaimer em toda exportação"],
    ], [72 * mm, 102 * mm]))

    # ---- 11. Conclusão -----------------------------------------------------------
    st.append(P("11. Conclusão", "h1"))
    st.append(P("O Enlace já é o que os concorrentes teriam de anunciar como roadmap: "
                "um planejador nacional com física completa, dados de edifício a 0,5 m, "
                "erro medido e publicado, produto público com preços e um funil de "
                "vendas por perfil. A pergunta aberta não é técnica — é de velocidade "
                "de distribuição.", "lead"))
    st += bullets([
        "<b>Usuários:</b> crie a conta gratuita em app.enlace.network — 5 estudos/mês, sem cartão.",
        "<b>Investidores e parceiros Enterprise:</b> contato@enlace.network.",
        "<b>Verificação independente:</b> enlace.network/validation (metodologia e números reproduzíveis).",
    ])
    st.append(Spacer(1, 4 * mm))
    st.append(HRFlowable(width="100%", thickness=0.5, color=LINE))
    st.append(Spacer(1, 2 * mm))
    st.append(P("Estudos de radiofrequência para fins de licenciamento ou com responsabilidade "
                "técnica devem ser assinados por engenheiro habilitado (Lei 5.194/66). Este "
                "documento não constitui oferta de valores mobiliários. Números de validação "
                "referem-se à avaliação held-out descrita na §7, computada em julho/2026; o "
                "erro em cenários individuais pode variar e é reportado por estudo via sigma.", "mut"))

    doc.build(st, onFirstPage=on_cover, onLaterPages=on_page)
    return PDF


if __name__ == "__main__":
    # Cover consumes page 1: emit a PageBreak-free build where the first
    # story element lands on page 2.
    path = build()
    print(path, f"{os.path.getsize(path)/1024:.0f} KB")
