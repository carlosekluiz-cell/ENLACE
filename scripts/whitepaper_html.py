"""ENLACE RF whitepaper — designed edition (HTML → Chromium PDF).

Design system: Fraunces (display serif) · Inter (body) · IBM Plex Mono
(eyebrows/data); petrol-dark cover with radio-wave motif; hand-paginated
A4 pages; SVG flow diagrams. All numbers verified against the DB
(rf_calibration_eval / rf_band_offsets, pulled 2026-07-11).

Regenerate: python3 scripts/whitepaper_html.py
Output: outputs/whitepaper/enlace-rf-whitepaper.pdf (+ .html source)
"""

from __future__ import annotations

import base64
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "whitepaper")
HTML = os.path.join(OUT, "enlace-rf-whitepaper.html")
PDF = os.path.join(OUT, "enlace-rf-whitepaper.pdf")


def b64(path, mime):
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def font(name):
    return b64(os.path.join(ROOT, "assets", "fonts", name), "font/ttf")


def png(path):
    return b64(os.path.join(ROOT, path), "image/png")


TODAY = date.today().strftime("%d/%m/%Y")

# ---------------------------------------------------------------------------
# SVG diagram toolkit
# ---------------------------------------------------------------------------

def node(x, y, w, h, title, subs, kind="plain"):
    fills = {
        "accent": ("#0D9488", "#0B7C72", "#FFFFFF", "#CDEFEA"),
        "plain": ("#FFFFFF", "#0D9488", "#16211F", "#647672"),
        "store": ("#EEF4F2", "#8FA6A0", "#16211F", "#647672"),
        "warn": ("#FBF3E6", "#C08A3E", "#3D2E14", "#8A6A3A"),
    }
    fill, stroke, tcol, scol = fills[kind]
    lines = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>']
    n = 1 + len(subs)
    lh = 13
    total = n * lh
    ty = y + h / 2 - total / 2 + lh - 3
    lines.append(f'<text x="{x + w/2}" y="{ty}" text-anchor="middle" '
                 f'font-family="IBM Plex Mono" font-size="9.5" font-weight="500" '
                 f'letter-spacing="0.06em" fill="{tcol}">{title}</text>')
    for i, s in enumerate(subs, 1):
        lines.append(f'<text x="{x + w/2}" y="{ty + i*lh}" text-anchor="middle" '
                     f'font-family="Inter" font-size="9" fill="{scol}">{s}</text>')
    return "\n".join(lines)


def arrow(x1, y1, x2, y2, label="", elbow=False, dash=False):
    d = f'M {x1} {y1} L {x2} {y2}'
    if elbow:
        d = f'M {x1} {y1} L {x2} {y1} L {x2} {y2}'
    dash_attr = ' stroke-dasharray="4 3"' if dash else ""
    s = (f'<path d="{d}" fill="none" stroke="#8FA6A0" stroke-width="1.4"'
         f'{dash_attr} marker-end="url(#arr)"/>')
    if label:
        lx, ly = (x1 + x2) / 2, y1 - 6
        if elbow:
            lx, ly = x2 + 6, (y1 + y2) / 2 + 3
            anchor = "start"
        else:
            anchor = "middle"
        s += (f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" '
              f'font-family="IBM Plex Mono" font-size="8" fill="#647672">{label}</text>')
    return s


SVG_DEFS = """<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
 markerWidth="7" markerHeight="7" orient="auto-start-reverse">
 <path d="M 0 1 L 9 5 L 0 9 z" fill="#8FA6A0"/></marker></defs>"""


def svg(width, height, body):
    return (f'<svg viewBox="0 0 {width} {height}" '
            f'style="width:100%;height:auto;display:block">{SVG_DEFS}{body}</svg>')


def fig_arch():
    b = []
    b.append(node(0, 60, 150, 84, "5 CAMADAS DE DADOS",
                  ["SRTM · GLO-30 · ANADEM", "MapBiomas · Open Buildings", "sob demanda, cache local"], "store"))
    b.append(node(190, 60, 140, 84, "MOTOR RUST",
                  ["gRPC · física completa", "difração de terreno", "grades em milissegundos"], "accent"))
    b.append(node(370, 60, 140, 84, "API FASTAPI",
                  ["autenticação · estudos", "exportação · calibração", "app.enlace.network/api"], "accent"))
    b.append(node(190, 180, 140, 56, "POSTGRES · CALIBRAÇÃO",
                  ["3,88 M medições Anatel", "curvas de correção"], "store"))
    b.append(node(560, 34, 140, 46, "PLANNER WEB", ["deck.gl · pt-BR"]))
    b.append(node(560, 98, 140, 46, "API DE CLIENTES", ["lote · integrações"]))
    b.append(node(560, 162, 140, 46, "EXPORTAÇÃO", ["PDF · KMZ · GeoJSON"]))
    b.append(arrow(150, 102, 186, 102))
    b.append(arrow(330, 102, 366, 102, "gRPC"))
    b.append(arrow(260, 180, 260, 148, "correções", dash=True))
    b.append(arrow(510, 90, 556, 60))
    b.append(arrow(510, 102, 556, 121))
    b.append(arrow(510, 114, 556, 182))
    return svg(710, 246, "\n".join(b))


def fig_dados():
    b = []
    b.append(node(0, 40, 128, 58, "COORDENADA", ["qualquer ponto", "do Brasil"]))
    b.append(node(168, 40, 128, 58, "CACHE LOCAL?", ["tile de 1°×1°"]))
    b.append(node(336, 40, 170, 58, "DOWNLOAD ABERTO",
                  ["OpenTopography · AWS", "Google Cloud Storage"], "store"))
    b.append(node(546, 40, 150, 58, "CONVERSÃO",
                  ["GeoTIFF → .hgt / .lc", "3601² · int16 / uint8"]))
    b.append(node(336, 138, 170, 48, "PERFIL / GRADE",
                  ["curvatura k = 4/3"], "accent"))
    b.append(arrow(128, 69, 164, 69))
    b.append(arrow(296, 69, 332, 69, "não"))
    b.append(arrow(506, 69, 542, 69))
    b.append(arrow(232, 98, 232, 162, "sim", elbow=False))
    b.append(f'<path d="M 232 162 L 332 162" fill="none" stroke="#8FA6A0" stroke-width="1.4" marker-end="url(#arr)"/>')
    b.append(arrow(621, 98, 621, 162, elbow=False))
    b.append(f'<path d="M 621 162 L 510 162" fill="none" stroke="#8FA6A0" stroke-width="1.4" marker-end="url(#arr)"/>')
    return svg(710, 196, "\n".join(b))


def fig_fisica():
    b = []
    b.append(node(0, 44, 108, 64, "ENTRADA", ["torre · rádio", "freq. · alturas"]))
    b.append(node(140, 44, 122, 64, "AMBIENTE", ["MapBiomas →", "urb/sub/rural"]))
    b.append(node(294, 44, 130, 64, "PERDA-BASE",
                  ["Hata · COST-231", "TR 38.901 · piso FSPL"], "accent"))
    b.append(node(456, 44, 124, 64, "DIFRAÇÃO",
                  ["Deygout multi-", "obstáculo · P.526"], "accent"))
    b.append(node(294, 148, 130, 52, "CLIMA / EDIFÍCIO", ["chuva P.837 · P.2109"]))
    b.append(node(456, 148, 124, 52, "CORREÇÃO", ["calibrada · §6"], "warn"))
    b.append(node(614, 74, 96, 96, "SAÍDA",
                  ["P50 / P90", "sigma calibrado", "margem · Fresnel"], "accent"))
    b.append(arrow(108, 76, 136, 76))
    b.append(arrow(262, 76, 290, 76))
    b.append(arrow(424, 76, 452, 76))
    b.append(arrow(580, 76, 610, 100))
    b.append(arrow(424, 174, 610, 150, dash=True))
    b.append(arrow(580, 174, 610, 146, dash=True))
    return svg(710, 210, "\n".join(b))


def fig_calib():
    b = []
    b.append(node(0, 30, 156, 58, "ANATEL RNI",
                  ["3,88 M medições", "de campo · 2005–2025"], "store"))
    b.append(node(0, 118, 156, 58, "REGISTRO SMP",
                  ["3,24 M setores", "112 mil estações · diário"], "store"))
    b.append(node(200, 74, 138, 66, "PREDIÇÃO",
                  ["composta por estação", "próxima · motor completo"], "accent"))
    b.append(node(382, 74, 130, 66, "RESÍDUOS",
                  ["3,55 M pontos", "classif. MapBiomas"]))
    b.append(node(556, 24, 154, 56, "AJUSTE — 80%",
                  ["a + b·log₁₀(d)", "por ambiente + banda"], "accent"))
    b.append(node(556, 108, 154, 56, "AVALIAÇÃO — 20%",
                  ["held-out: nunca", "visto pelo ajuste"], "warn"))
    b.append(node(382, 178, 130, 44, "APLICAÇÃO NA API", ["a cada estudo"], "accent"))
    b.append(arrow(156, 59, 196, 96, elbow=False))
    b.append(arrow(156, 147, 196, 118, elbow=False))
    b.append(arrow(338, 107, 378, 107))
    b.append(arrow(512, 95, 552, 62, "80%"))
    b.append(arrow(512, 118, 552, 130, "20%"))
    b.append(f'<path d="M 633 80 L 633 94 L 447 94 L 447 174" fill="none" stroke="#8FA6A0" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#arr)"/>')
    b.append(f'<text x="500" y="88" font-family="IBM Plex Mono" font-size="8" fill="#647672">curvas</text>')
    return svg(710, 232, "\n".join(b))


def fig_gtm():
    b = []
    b.append(node(0, 30, 172, 90, "AUTOATENDIMENTO",
                  ["micro-WISPs", "integradores FWA", "Teste R$0 → WISP R$149"]))
    b.append(node(212, 30, 172, 90, "ASSISTIDO",
                  ["ISPs regionais", "consultorias de RF", "Provedor R$499"]))
    b.append(node(424, 30, 172, 90, "ENTERPRISE",
                  ["torres · M&A · bancos", "governo · operadoras", "sob consulta"], "accent"))
    b.append(node(636, 52, 74, 46, "RECEITA", ["MRR +", "projetos"], "store"))
    b.append(arrow(172, 75, 208, 75, "upgrade"))
    b.append(arrow(384, 75, 420, 75, "upgrade"))
    b.append(arrow(596, 75, 632, 75))
    return svg(710, 130, "\n".join(b))


def fig_roadmap():
    b = []
    steps = [
        (0, "HOJE — NO AR", ["planner público", "calibração v1/v2", "benchmark publicado"], "accent"),
        (186, "FASE SEGUINTE", ["correção no motor", "requer EIRP real", "por estação"], "plain"),
        (372, "FROTA-SENSOR", ["telemetria de CPEs", "calibração contínua", "inicia com piloto"], "plain"),
        (558, "GPU + ML", ["ray tracing 2.5D", "mapa nacional", "instantâneo"], "plain"),
    ]
    for x, t, subs, kind in steps:
        b.append(node(x, 24, 152, 78, t, subs, kind))
    for x in (152, 338, 524):
        b.append(arrow(x, 63, x + 34, 63))
    return svg(710, 112, "\n".join(b))


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def page(body, num=None, eyebrow="ENLACE · WHITEPAPER", dark=False):
    cls = "page dark" if dark else "page"
    footer = ""
    header = ""
    if num is not None:
        header = (f'<div class="runhead"><span>{eyebrow}</span>'
                  f'<span>PROPAGAÇÃO RF CALIBRADA — BRASIL</span></div>')
        footer = (f'<div class="runfoot"><span>enlace.network · '
                  f'contato@enlace.network</span><span class="pno">{num:02d}</span></div>')
    return f'<section class="{cls}">{header}{body}{footer}</section>'


def sec(n, eyebrow, title):
    return (f'<div class="sechead"><div class="secnum">{n}</div>'
            f'<div><div class="eyebrow">{eyebrow}</div>'
            f'<h2>{title}</h2></div></div>')


def figure(label, caption, svg_html):
    return (f'<figure class="panel"><figcaption class="figlabel">{label}</figcaption>'
            f'{svg_html}<figcaption class="figcap">{caption}</figcaption></figure>')


def tbl(headers, rows, hl_col=None, widths=None):
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = []
        for i, c in enumerate(r):
            klass = ' class="hl"' if hl_col is not None and i == hl_col else ""
            tds.append(f"<td{klass}>{c}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    colgroup = ""
    if widths:
        colgroup = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in widths) + "</colgroup>"
    return f'<table>{colgroup}<thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def build_html():
    f_fra400 = font("fraunces-400.ttf")
    f_fra600 = font("fraunces-600.ttf")
    f_int400 = font("inter-400.ttf")
    f_int600 = font("inter-600.ttf")
    f_mon400 = font("plexmono-400.ttf")
    f_mon500 = font("plexmono-500.ttf")
    shot1 = png("outputs/e2e_1_enlace.png")
    shot2 = png("outputs/e2e_2_coverage.png")

    # ---------- cover ----------
    waves = "".join(
        f'<circle cx="880" cy="360" r="{r}" fill="none" stroke="#2DD4BF" '
        f'stroke-opacity="{op}" stroke-width="1.1"/>'
        for r, op in [(90, .55), (150, .42), (215, .30), (285, .21), (360, .14),
                      (440, .09), (525, .055), (615, .03)]
    )
    cover = f"""
    <div class="coverwrap">
      <svg class="covermotif" viewBox="0 0 900 700" preserveAspectRatio="xMaxYMid slice">
        {waves}
        <circle cx="880" cy="360" r="5" fill="#2DD4BF"/>
      </svg>
      <div class="coverhead">
        <div class="brand">ENLACE</div>
        <div class="brandsub">enlace.network · app.enlace.network</div>
      </div>
      <div class="covermain">
        <div class="eyebrow" style="color:#5FC9BC">WHITEPAPER · TÉCNICO E DE NEGÓCIO · BRASIL</div>
        <h1>Propagação de RF<br/>calibrada em<br/>escala nacional</h1>
        <p class="coverlead">Enlaces ponto-a-ponto, FWA, 4G e 5G: o único planejador de
        redes sem fio do mercado brasileiro com erro medido, publicado e
        reproduzível — calibrado e avaliado out-of-sample contra 3,55&nbsp;milhões
        de medições de campo do próprio regulador.</p>
      </div>
      <div class="coverkpis">
        <div><b>3,55 M</b><span>medições de campo na avaliação</span></div>
        <div><b>7,0 dB</b><span>RMSE urbano held-out · antes 25,8</span></div>
        <div><b>100%</b><span>do território, sob demanda</span></div>
        <div><b>19/19</b><span>testes e2e no produto público</span></div>
      </div>
      <div class="coverfoot">
        <span>Versão 1.1 — {TODAY}</span>
        <span>contato@enlace.network</span>
        <span>metodologia: enlace.network/validation</span>
      </div>
    </div>"""

    # ---------- p2: sumário executivo ----------
    p2 = f"""
    {sec("01", "SUMÁRIO EXECUTIVO", "A pergunta que decide redes")}
    <p class="lead">Do enlace do WISP ao setor 5G: o Enlace responde, para qualquer
    coordenada do Brasil, a pergunta que decide qualquer investimento em rede sem
    fio: <em>“se eu transmitir daqui, onde o sinal chega — e com que
    confiança?”</em></p>
    <div class="threefacts">
      <div class="fact"><div class="factnum">I</div>
        <h3>Erro medido, não prometido</h3>
        <p>Calibramos o modelo contra 3,55 milhões de medições de campo da Anatel e
        publicamos o erro em avaliação out-of-sample: <b>RMSE de 7,0 dB em área
        urbana</b> — o modelo físico puro erra 25,8 dB. Nenhum concorrente publica
        número equivalente para o Brasil.</p></div>
      <div class="fact"><div class="factnum">II</div>
        <h3>Dados nacionais completos, custo marginal ≈ zero</h3>
        <p>Terreno 30 m, superfície com vegetação, solo exposto, uso do solo e altura
        de edifícios a 0,5 m — cinco camadas abertas, buscadas sob demanda e
        cacheadas. <b>Nenhum licenciamento de dados de terceiros.</b></p></div>
      <div class="fact"><div class="factnum">III</div>
        <h3>Produto no ar, vendável hoje</h3>
        <p>Planner web público com autenticação real, estudos exportáveis em
        PDF/KMZ/GeoJSON, <b>preços publicados</b> (R$ 0 a R$ 499/mês + Enterprise) e
        prospectos para nove perfis de cliente.</p></div>
    </div>
    <div class="pull">
      <p>A tese é direta: o mercado de provedores regionais brasileiros é numeroso e
      mal servido — as ferramentas profissionais custam milhares de dólares por
      licença e nenhuma é calibrada para o território. O Enlace entrega acurácia
      auditável a preço de SaaS nacional, e a base de calibração — que melhora com
      cada nova medição — forma uma <b>barreira de entrada cumulativa</b>.</p>
    </div>
    <div class="toc">
      <div class="eyebrow">NESTE DOCUMENTO</div>
      <ol>
        <li><span>O problema</span><i></i><b>03</b></li>
        <li><span>A plataforma e o produto</span><i></i><b>04</b></li>
        <li><span>Os dados: cinco camadas nacionais</span><i></i><b>06</b></li>
        <li><span>A física: conceitos e equações</span><i></i><b>07</b></li>
        <li><span>A calibração: loop e metodologia</span><i></i><b>09</b></li>
        <li><span>Anatomia do erro</span><i></i><b>11</b></li>
        <li><span>Validação: números, método, limites</span><i></i><b>12</b></li>
        <li><span>Exemplo aplicado (números reais)</span><i></i><b>13</b></li>
        <li><span>Go-to-market: nove perfis</span><i></i><b>14</b></li>
        <li><span>Roteiro e barreiras · riscos</span><i></i><b>15</b></li>
        <li><span>Referências e glossário</span><i></i><b>16</b></li>
      </ol>
    </div>"""

    # ---------- p3: problema ----------
    p3 = f"""
    {sec("02", "O PROBLEMA", "Planejar rede sem fio no Brasil é caro, lento e não auditável")}
    <p>Toda rede sem fio começa com uma previsão de propagação. Errar essa previsão
    custa caro em qualquer escala:</p>
    <div class="grid2">
      <div class="card"><div class="eyebrow">PROVEDOR DE BAIRRO</div>
        <p>Uma instalação que “não fecha o link” é uma visita técnica perdida e um
        cliente frustrado — margens que o micro-provedor não tem.</p></div>
      <div class="card"><div class="eyebrow">ISP REGIONAL</div>
        <p>Escolher a cidade errada para a expansão FWA imobiliza capex em POPs de
        baixa performance e gera churn onde a cobertura prometida não se
        confirma.</p></div>
      <div class="card"><div class="eyebrow">INVESTIDOR · FINANCIADOR</div>
        <p>O mapa de cobertura declarado por um ativo em due diligence raramente foi
        verificado por física independente.</p></div>
      <div class="card"><div class="eyebrow">REGULADOR</div>
        <p>Fiscalizar obrigações de cobertura em escala exige um instrumento técnico
        que hoje não existe fora de campanhas de drive test.</p></div>
    </div>
    <div class="pull amber">
      <p>As ferramentas estabelecidas atendem mal a este mercado: são licenciadas por
      milhares de dólares por engenheiro, rodam em desktop, exigem que o usuário
      providencie os próprios dados de terreno e clutter — e, criticamente,
      <b>não declaram o erro de suas previsões no Brasil</b>.</p>
      <p class="punch">A previsão sem barra de erro é opinião com gráfico.</p>
    </div>
    <h3 class="sub">O que este documento cobre — e onde ele se encaixa</h3>
    <div class="grid2">
      <div class="card teal"><div class="eyebrow">ESTE WHITEPAPER — REDES SEM FIO</div>
        <p>Enlaces ponto-a-ponto (5,8 GHz e licenciados), FWA, cobertura celular
        4G e <b>5G</b> (TR 38.901, o modelo de canal padronizado do 5G, vale de
        0,5 a 100 GHz). Fibra não tem problema de propagação — luz em vidro chega
        ou o cabo foi rompido; planejar fibra é problema de topologia e custo, e
        vive em outro produto da plataforma. <b>ISP de fibra? Este produto continua
        sendo seu:</b> backhaul sem fio entre POPs, FWA de borda para vender antes
        de o civil chegar, e alcance rural onde a fibra não fecha conta.</p></div>
      <div class="card"><div class="eyebrow">O RESTO DA PLATAFORMA ENLACE</div>
        <p><b>FTTH / fibra:</b> motor de conversão de rede completa (topologia,
        BOM, exportações), em produção no piloto do Reino Unido — adaptação ao
        cadastro brasileiro está no roteiro. <b>Telemetria de frota:</b> agente
        leve em CPEs, hoje servindo auditoria em api.enlace.network.
        <b>Inteligência de mercado:</b> módulos de fibra, backhaul e concorrência
        para ISPs. Cada um terá seu próprio material.</p></div>
    </div>"""

    # ---------- p4: plataforma ----------
    p4 = f"""
    {sec("03", "A PLATAFORMA", "Da coordenada ao estudo, em segundos")}
    {figure("FIGURA 1 — ARQUITETURA DA PLATAFORMA",
            "As cinco camadas de dados alimentam um motor de cálculo em Rust — perfis, difração e grades de cobertura em milissegundos — exposto por uma API que serve o planner web, integrações e exportação. O banco de calibração alimenta as correções aplicadas a cada estudo.",
            fig_arch())}
    <h3 class="sub">O produto no ar</h3>
    <p>Em <b>app.enlace.network</b>, o usuário cria conta, clica em qualquer ponto do
    mapa e obtém: perfil de terreno com zona de Fresnel e difração; orçamento de
    enlace com chuva regional (ITU-R P.837) e perda de entrada em edifícios
    (P.2109); e cobertura setorial P50/P90 com incerteza calibrada — tudo no
    navegador, sem instalar nada.</p>
    <figure class="shot"><img src="{shot1}" alt="Estudo de enlace"/>
      <figcaption class="figcap">Estudo de enlace ponto-a-ponto sobre modelo de
      superfície (DSM): Fresnel, difração, margem e disponibilidade com chuva
      regional.</figcaption></figure>"""

    # ---------- p5: screenshots ----------
    p5 = f"""
    {sec("03", "A PLATAFORMA", "O planner em produção")}
    <figure class="shot"><img src="{shot2}" alt="Cobertura calibrada"/>
      <figcaption class="figcap">Cobertura calibrada: grade de 14 mil pontos com
      sombra de terreno, ambiente inferido por uso do solo e P50/P90.</figcaption>
    </figure>
    <div class="grid3">
      <div class="card"><div class="eyebrow">EQUIPAMENTOS</div>
        <p>Presets de Ubiquiti, Cambium, Mimosa e Intelbras — potência, ganho e
        sensibilidade preenchidos.</p></div>
      <div class="card"><div class="eyebrow">SETORIAIS + P90</div>
        <p>Azimute, meia-potência e downtilt; cobertura mediana e conservadora com
        sigma calibrado.</p></div>
      <div class="card"><div class="eyebrow">FLUXO COMPLETO</div>
        <p>Busca por endereço, projetos salvos e exportação em PDF, KMZ e
        GeoJSON.</p></div>
    </div>
    <p class="mut">Qualidade verificada por 19 testes de navegador de ponta a ponta
    contra a URL pública e 497 testes de unidade e integração.</p>"""

    # ---------- p6: dados ----------
    p6 = f"""
    {sec("04", "OS DADOS", "Cinco camadas nacionais, sob demanda")}
    <p>A plataforma não depende de licenciamento de dados de terceiros. Cinco camadas
    abertas cobrem 100% do território:</p>
    {tbl(["Camada", "Fonte", "Resolução", "Papel no modelo"], [
        ["Terreno (DTM)", "SRTM GL1 — NASA", "30 m", "elevação básica, difração"],
        ["Superfície (DSM)", "Copernicus GLO-30 — ESA", "30 m", "vegetação e construções no perfil"],
        ["Solo exposto", "ANADEM v1 — INPE/UFRGS", "30 m", "altura real acima do solo"],
        ["Uso do solo", "MapBiomas C9", "30 m", "classificação urbano / suburbano / rural"],
        ["Edifícios 2.5D", "Google Open Buildings", "0,5 m", "altura de prédios no enlace"],
    ], widths=["17%", "26%", "13%", "44%"])}
    {figure("FIGURA 2 — AQUISIÇÃO SOB DEMANDA",
            "Nenhum espelho nacional é necessário: o tile de 1°×1° é baixado na primeira consulta àquela região e cacheado. O custo de infraestrutura cresce com o uso — não com o território.",
            fig_dados())}"""

    # ---------- p7: física ----------
    p7 = f"""
    {sec("05", "A FÍSICA", "Cadeia de modelos ITU-R / 3GPP")}
    {figure("FIGURA 3 — CADEIA FÍSICA DO MODELO",
            "Perda-base despachada por ambiente com piso de espaço livre; difração de múltiplos obstáculos sobre o perfil real; efeitos de clima e edifício; correção calibrada; saída probabilística.",
            fig_fisica())}
    <div class="grid2">
      <div class="card"><div class="eyebrow">PERDA-BASE POR AMBIENTE</div>
        <p>Hata/COST-231 e 3GPP TR 38.901 (RMa/UMa) — o modelo de canal oficial do
        5G — com o espaço livre como piso físico: o modelo nunca prevê sinal
        melhor que o vácuo.</p></div>
      <div class="card"><div class="eyebrow">DIFRAÇÃO DE TERRENO</div>
        <p>Método de Deygout com gume de faca ITU-R P.526 sobre até 200 amostras de
        perfil, em qualquer das três superfícies.</p></div>
      <div class="card"><div class="eyebrow">CLIMA E EDIFÍCIO</div>
        <p>Atenuação por chuva com intensidade R<sub>0,01</sub> regional (ITU-R
        P.837, grade própria) e perda de entrada em edifícios (P.2109) para recepção
        indoor.</p></div>
      <div class="card"><div class="eyebrow">SAÍDA PROBABILÍSTICA</div>
        <p>Cada ponto carrega um sigma de sombreamento; a cobertura sai em P50
        (mediana) e P90 (conservadora) — no P90, 9 em 10 pontos previstos cobertos
        devem ter sinal de fato.</p></div>
    </div>
    <div class="pull">
      <p><b>E o 5G em 3,5 GHz (n78)?</b> Suportado pela física — TR 38.901 cobre a
      banda, e os edifícios 2.5D importam ainda mais nela. Honestidade de escopo:
      as correções calibradas foram medidas nas bandas 700–2500 MHz; em 3,5 GHz
      aplicamos a física com o sigma declarado, e a telemetria de piloto (§11)
      trará a calibração medida também para essa banda.</p>
    </div>"""

    # ---------- p8: calibração ----------
    p8 = f"""
    {sec("06", "A CALIBRAÇÃO", "O que nos separa de todos os outros")}
    <p>Modelos físicos genéricos erram de forma sistemática: superestimam sinal perto
    da torre — o feixe da antena passa por cima do medidor — e subestimam efeitos de
    clutter tropical. A resposta do Enlace é medir esse erro no maior acervo de
    medições de campo do país, o do próprio regulador, e corrigi-lo.</p>
    {figure("FIGURA 4 — LOOP DE CALIBRAÇÃO · SPLIT 80/20",
            "Medições RNI georreferenciadas são confrontadas com a predição do motor para as estações licenciadas próximas (registro SMP, atualizado diariamente). Os resíduos, classificados por ambiente via MapBiomas, ajustam curvas de correção em 80% dos dados; os 20% restantes — nunca vistos pelo ajuste — produzem os números da Tabela 2.",
            fig_calib())}
    <div class="grid2">
      <div class="card teal"><div class="eyebrow">TIER 1 — ATRIBUÍDO</div>
        <p><b>1,72 milhão de resíduos</b> onde a medição é vinculada a estações
        licenciadas identificadas — o cenário de maior confiança na
        atribuição.</p></div>
      <div class="card teal"><div class="eyebrow">TIER 2 — CEGO, POR PROXIMIDADE</div>
        <p>O restante do acervo, previsto às cegas pela composição das estações
        próximas — o teste mais duro, mais próximo do uso real. <b>O erro urbano cai
        de 28,6 para 8,3 dB.</b></p></div>
    </div>"""

    # ---------- p9: validação ----------
    p9 = f"""
    {sec("08", "VALIDAÇÃO", "Números, método e limites declarados")}
    <div class="eyebrow tbl-label">TABELA 2 — ERRO HELD-OUT DO MODELO CALIBRADO (20% NUNCA VISTOS PELO AJUSTE)</div>
    {tbl(["Fatia", "N teste", "RMSE físico puro", "RMSE calibrado"], [
        ["Urbano — atribuído (tier 1)", "257.446", "25,8 dB", "7,0 dB"],
        ["Suburbano — atribuído", "13.625", "26,1 dB", "7,6 dB"],
        ["Rural — atribuído", "35.621", "25,6 dB", "8,3 dB"],
        ["Urbano — cego por proximidade (tier 2)", "359.914", "28,6 dB", "8,3 dB"],
        ["Suburbano — cego (tier 2)", "1.588", "25,8 dB", "8,5 dB"],
        ["Rural — cego (tier 2)", "3.452", "24,8 dB", "8,8 dB"],
    ], hl_col=3, widths=["44%", "16%", "21%", "19%"])}
    <div class="eyebrow tbl-label">TABELA 3 — OFFSETS POR BANDA, MEDIDOS DE ESTAÇÕES DE BANDA ÚNICA</div>
    {tbl(["", "700 MHz", "850 MHz", "900 MHz", "1800 MHz", "2100 MHz", "2500 MHz"], [
        ["Offset medido", "+11,8 dB", "+6,4 dB", "+11,2 dB", "+3,0 dB", "+8,0 dB", "+1,5 dB"],
        ["N medições", "547", "7.420", "1.046", "3.687", "5.128", "9.976"],
    ], widths=["22%", "13%", "13%", "13%", "13%", "13%", "13%"])}
    <p>A estrutura é fisicamente coerente: bandas baixas propagam além do modelo
    genérico — 700 MHz supera 2,5 GHz em ~10 dB após correção de distância; caminhos
    sobre água perdem ~4 dB menos que sobre terra; e o viés de −26 dB sob a torre,
    decaindo a ≈0 dB em 1,5–2 km, é a assinatura do downtilt das antenas setoriais —
    <b>aprendida dos dados, não assumida</b>.</p>
    <div class="limits">
      <div class="eyebrow amberink">O QUE DECLARAMOS COMO LIMITE — E POR QUÊ</div>
      <ul>
        <li><b>EIRP típico por banda, não por estação:</b> o registro público SMP não
        traz potência/altura por setor. As correções absorvem o erro médio dessa
        hipótese; o desvio estação-a-estação permanece no sigma. A exportação técnica
        do Mosaico ou a telemetria de piloto removerá a hipótese (§11).</li>
        <li><b>Medições RNI são banda larga:</b> o medidor integra as emissoras
        co-localizadas; a atribuição é probabilística — por isso o tier 2 cego é
        reportado em separado, e sustenta 8,3 dB urbano.</li>
        <li><b>Correções aplicadas hoje na API</b>, não dentro do motor Rust —
        a curva ĉ(d) por ambiente já é aplicada ponto a ponto (§6); levá-la para dentro do motor Rust aguarda o desembaraço EIRP × propagação (§11).</li>
      </ul>
    </div>
    <p class="mut">Metodologia completa, scripts e artefato de validação são públicos
    — enlace.network/validation. Qualquer terceiro com acesso aos dados abertos da
    Anatel reproduz a Tabela 2.</p>"""

    # ---------- p10: gtm ----------
    p10 = f"""
    {sec("10", "GO-TO-MARKET", "Nove perfis, três degraus, um motor")}
    {figure("FIGURA 5 — ESCADA DE CLIENTES",
            "O mesmo motor serve do provedor de bairro (autoatendimento a R$ 149/mês) à operadora nacional (Enterprise) — o custo de servir um estudo adicional é próximo de zero.",
            fig_gtm())}
    {tbl(["Perfil", "Dor central", "Produto", "Plano"], [
        ["Micro-WISPs", "instalação errada consome a margem", "estudo por clique + presets", "Teste / WISP"],
        ["Integradores FWA", "proposta sem estudo perde", "viabilidade remota + KMZ", "WISP / Provedor"],
        ["Consultorias RF", "laudo precisa de lastro", "benchmark citável + white-label", "Provedor / Ent."],
        ["ISPs regionais (fibra + FWA)", "priorizar expansão · backhaul", "backhaul + cobertura P90 + API", "Provedor"],
        ["Fundos / M&A", "cobertura declarada não auditada", "due diligence em lote", "Enterprise"],
        ["Towercos", "precificar verticais", "footprint por torre em lote", "Enterprise"],
        ["Bancos / BNDES", "risco técnico mal precificado", "parecer independente · milestone P90", "Enterprise"],
        ["Governo / regulador", "fiscalizar em escala", "verificação física por município", "Enterprise"],
        ["Operadoras", "calibração genérica global", "segundo par de olhos, calibrado BR", "Enterprise"],
    ], widths=["18%", "30%", "34%", "18%"])}
    <div class="chips">
      <span class="chip">TESTE — R$ 0 · 5 estudos/mês</span>
      <span class="chip hot">WISP — R$ 149/mês</span>
      <span class="chip">PROVEDOR — R$ 499/mês</span>
      <span class="chip">ENTERPRISE — sob consulta</span>
    </div>
    <p class="mut">Preços publicados em enlace.network/pricing · pagamento online em
    implantação; ativação por contato · prospectos individuais por perfil em
    enlace.network/prospectos/.</p>"""

    # ---------- p11: roadmap + riscos ----------
    p11 = f"""
    {sec("11", "ROTEIRO E BARREIRAS", "Cada fase aprofunda a vantagem de dados")}
    {figure("FIGURA 6 — ROTEIRO TECNOLÓGICO",
            "Correção dentro do motor (destravada por potências reais por estação); frota como sensor — cada CPE de cliente reporta sinal georreferenciado, e cada cliente novo melhora o modelo que serve todos; GPU ray tracing sobre os edifícios 2.5D e um surrogate neural para mapas nacionais instantâneos. Em paralelo: o motor de topologia FTTH do piloto britânico, adaptado ao cadastro brasileiro.",
            fig_roadmap())}
    <div class="pull">
      <p><b>Por que é difícil copiar.</b> Os rasters são públicos; a barreira não
      está neles. Está nos 3,55 milhões de resíduos processados, classificados e
      auditados — meses de engenharia contra fontes com peculiaridades não
      documentadas; no pipeline diário contra o registro de licenciamento; no
      benchmark publicado, que obriga qualquer entrante a competir em <b>acurácia
      declarada</b>, não em marketing; e, com a frota-sensor, em dados proprietários
      que nenhum acervo público contém.</p>
    </div>
    <div class="eyebrow tbl-label">RISCOS E MITIGAÇÃO</div>
    {tbl(["Risco", "Mitigação"], [
        ["Hipótese de EIRP típico distorce correções por banda",
         "declarada e quantificada (§7); exportação Mosaico ou telemetria de piloto elimina"],
        ["Dependência de fontes abertas (SRTM, GLO-30, MapBiomas…)",
         "cinco fontes independentes, cache local; nenhuma tem histórico de fechamento"],
        ["Concorrente global adiciona calibração Brasil",
         "a vantagem é o loop dados → correção → benchmark público; a frota-sensor amplia"],
        ["Adoção lenta do autoatendimento",
         "a escada monetiza cedo no Enterprise (due diligence, torres, bancos) com tíquetes maiores"],
        ["Responsabilidade técnica (Lei 5.194/66)",
         "ferramenta de cálculo; o laudo permanece com engenheiro habilitado; disclaimer em toda exportação"],
    ], widths=["42%", "58%"])}"""

    # ---------- p12: back cover ----------
    p12 = f"""
    <div class="backwrap">
      <div class="eyebrow" style="color:#5FC9BC">CONCLUSÃO</div>
      <h1 class="backtitle">O que os concorrentes<br/>anunciariam como roadmap,<br/>já está no ar.</h1>
      <p class="coverlead">Um planejador nacional com física completa, dados de
      edifício a 0,5 m, erro medido e publicado, produto público com preços e um
      funil de vendas por perfil. A pergunta aberta não é técnica — é de velocidade
      de distribuição.</p>
      <div class="backctas">
        <div><div class="eyebrow" style="color:#5FC9BC">USUÁRIOS</div>
          <p>Conta gratuita em <b>app.enlace.network</b> — 5 estudos/mês, sem cartão.</p></div>
        <div><div class="eyebrow" style="color:#5FC9BC">INVESTIDORES · ENTERPRISE</div>
          <p><b>contato@enlace.network</b></p></div>
        <div><div class="eyebrow" style="color:#5FC9BC">VERIFICAÇÃO INDEPENDENTE</div>
          <p><b>enlace.network/validation</b> — metodologia e números reproduzíveis.</p></div>
      </div>
      <div class="backdisc">Estudos de radiofrequência para fins de licenciamento ou
      com responsabilidade técnica devem ser assinados por engenheiro habilitado
      (Lei 5.194/66). Este documento não constitui oferta de valores mobiliários.
      Números de validação referem-se à avaliação held-out (§7), computada em
      julho/2026; o erro em cenários individuais varia e é reportado por estudo via
      sigma. · ENLACE · v1.1 · {TODAY}</div>
    </div>"""

    # ---------- p8: equations ----------
    p_eq = f"""
    {sec("05", "A FÍSICA — EM EQUAÇÕES", "O que o motor calcula, exatamente")}
    <p>Cada estágio da Figura 3 é uma expressão fechada, avaliada por ponto da
    grade. O piso físico é o espaço livre:</p>
    <div class="panel">
      <div class="eqrow"><div class="eq"><i>L</i><sub>FSPL</sub> = 32,45 + 20&thinsp;log<sub>10</sub><i>f</i><sub>MHz</sub> + 20&thinsp;log<sub>10</sub><i>d</i><sub>km</sub></div><div class="eqname">espaço livre</div></div>
      <div class="eqrow"><div class="eq"><i>L</i><sub>Hata,urb</sub> = 69,55 + 26,16&thinsp;log<sub>10</sub><i>f</i> − 13,82&thinsp;log<sub>10</sub><i>h</i><sub>b</sub> − <i>a</i>(<i>h</i><sub>m</sub>) + (44,9 − 6,55&thinsp;log<sub>10</sub><i>h</i><sub>b</sub>)&thinsp;log<sub>10</sub><i>d</i></div><div class="eqname">150–2000 MHz</div></div>
      <div class="eqrow"><div class="eq"><i>L</i> = max(&thinsp;<i>L</i><sub>modelo</sub>, <i>L</i><sub>FSPL</sub>&thinsp;) + <i>J</i>(<i>v</i>) + <i>A</i><sub>chuva</sub> + <i>L</i><sub>BEL</sub> − <i>ĉ</i>(<i>d</i>, amb)</div><div class="eqname">cadeia completa</div></div>
    </div>
    <p>Acima de 2 GHz o despacho troca Hata pelo 3GPP TR 38.901 — UMa para
    urbano/suburbano, RMa para rural — o modelo de canal padronizado do 5G.
    A difração usa o parâmetro de Fresnel-Kirchhoff <i>v</i> de cada obstáculo do
    perfil real (Deygout: obstáculo principal, depois recursão nos
    sub-caminhos):</p>
    <div class="panel">
      <div class="eqrow"><div class="eq"><i>v</i> = <i>h</i>&thinsp;√(&thinsp;2/λ · (1/<i>d</i><sub>1</sub> + 1/<i>d</i><sub>2</sub>)&thinsp;)</div><div class="eqname">parâmetro de difração</div></div>
      <div class="eqrow"><div class="eq"><i>J</i>(<i>v</i>) = 6,9 + 20&thinsp;log<sub>10</sub>(&thinsp;√((<i>v</i>−0,1)² + 1) + <i>v</i> − 0,1&thinsp;)</div><div class="eqname">ITU-R P.526, v &gt; −0,78</div></div>
      <div class="eqrow"><div class="eq"><i>r</i><sub>1</sub> = √(&thinsp;λ&thinsp;<i>d</i><sub>1</sub><i>d</i><sub>2</sub> / (<i>d</i><sub>1</sub>+<i>d</i><sub>2</sub>)&thinsp;) &nbsp;&nbsp;·&nbsp;&nbsp; Δ<i>h</i><sub>bulge</sub> = <i>d</i><sub>1</sub><i>d</i><sub>2</sub> / (2&thinsp;<i>k</i>&thinsp;<i>R</i><sub>e</sub>), <i>k</i> = 4/3</div><div class="eqname">fresnel · curvatura</div></div>
    </div>
    <p>Cada ponto carrega um desvio-padrão de sombreamento σ, herdado do modelo
    despachado, e a cobertura conservadora aplica a margem log-normal:</p>
    <div class="panel">
      <div class="eqrow"><div class="eq">P90: coberto se &nbsp;<i>P</i><sub>rx</sub> − 1,282&thinsp;σ ≥ limiar</div><div class="eqname">z de 90%</div></div>
    </div>
    {tbl(["Modelo despachado", "Faixa", "Ambiente", "σ (dB)"], [
        ["Okumura-Hata / COST-231", "150–2000 MHz", "urbano", "8,0"],
        ["Okumura-Hata / COST-231", "150–2000 MHz", "suburbano / rural", "7,0 / 6,0"],
        ["3GPP TR 38.901 UMa", "&gt; 2 GHz", "urbano · suburbano", "4,0 LOS / 6,0 NLOS"],
        ["3GPP TR 38.901 RMa", "&gt; 2 GHz", "rural", "4,0 LOS / 8,0 NLOS"],
        ["Piso FSPL", "fora das faixas", "todos", "5,5"],
    ], widths=["34%", "20%", "26%", "20%"])}
    <p class="mut">Valores de σ conforme implementados no motor
    (rust/crates/pulso-propagation). O σ reportado por estudo é a média da
    grade — 5,97 dB no exemplo da §11.</p>"""

    # ---------- p10: methodology detail ----------
    p_meth = f"""
    {sec("06", "A CALIBRAÇÃO — METODOLOGIA", "Do volt por metro ao decibel de erro")}
    <p>As medições RNI da Anatel reportam campo elétrico (V/m). A comparação com o
    motor acontece no domínio do campo: para cada medição, compomos a densidade de
    potência prevista das estações licenciadas próximas e convertemos:</p>
    <div class="panel">
      <div class="eqrow"><div class="eq"><i>S</i> = Σ<sub>estações</sub>&thinsp;EIRP<sub>banda</sub> · ⌈portadoras/3⌉ / (4π<i>d</i>²) &nbsp;&nbsp;·&nbsp;&nbsp; <i>E</i><sub>prev</sub> = √(377&thinsp;<i>S</i>)</div><div class="eqname">composição near-station</div></div>
      <div class="eqrow"><div class="eq"><i>r</i> = 20&thinsp;log<sub>10</sub>(&thinsp;<i>E</i><sub>med</sub> / <i>E</i><sub>prev</sub>&thinsp;)</div><div class="eqname">resíduo em dB</div></div>
      <div class="eqrow"><div class="eq"><i>ĉ</i>(<i>d</i>, amb) = <i>a</i><sub>amb</sub> + <i>b</i><sub>amb</sub>&thinsp;log<sub>10</sub><i>d</i><sub>m</sub>, &nbsp;<i>d</i> restrito a [100, 2500] m</div><div class="eqname">curva de correção</div></div>
    </div>
    <p><b>Hipótese de EIRP declarada:</b> o registro público não traz potência por
    setor; usamos EIRP típico por banda — 60 dBm (700/850/900 MHz), 61 dBm
    (1800/2100), 62 dBm (2300/2500), 65 dBm (3500) por grupo de 3 portadoras. As
    curvas absorvem o erro médio da hipótese; o desvio estação-a-estação fica no σ.</p>
    <p><b>Split honesto:</b> a partição 80/20 é determinística por
    <span style="font-family:'IBM Plex Mono';font-size:8pt">measurement_id mod 5</span> —
    reproduzível por qualquer auditor, sem re-sorteio favorável. As curvas abaixo
    foram ajustadas só nos 80%:</p>
    <div class="eyebrow tbl-label">TABELA 4 — CURVAS DE CORREÇÃO AJUSTADAS (TREINO 80%)</div>
    {tbl(["Modelo", "Ambiente", "a (dB)", "b (dB/década)", "N treino"], [
        ["composite_v1", "urbano", "−60,5", "+19,2", "1.030.358"],
        ["composite_v1", "suburbano", "−59,8", "+18,2", "54.852"],
        ["composite_v1", "rural", "−58,5", "+17,6", "141.054"],
        ["composite_v2_prox (cego)", "urbano", "−65,3", "+18,9", "1.440.112"],
        ["composite_v2_prox (cego)", "rural", "−61,5", "+19,2", "14.030"],
    ], hl_col=3, widths=["27%", "19%", "15%", "21%", "18%"])}
    <p>A inclinação convergente de <b>+18–19 dB/década em todos os ambientes e nos
    dois tiers</b> é o resultado mais importante da tabela: não é ruído de ajuste,
    é física — a assinatura do padrão vertical das antenas setoriais, que o modelo
    de perda de percurso não conhece. O motor aplica <i>ĉ</i>(<i>d</i>) ponto a
    ponto, resolvida pela distância real de cada pixel à torre.</p>"""

    # ---------- p11: error anatomy ----------
    p_anat = f"""
    {sec("07", "ANATOMIA DO ERRO", "O que 3,55 milhões de resíduos revelam")}
    <div class="eyebrow tbl-label">TABELA 5 — VIÉS BRUTO POR DISTÂNCIA (TIER 1, ANTES DA CORREÇÃO)</div>
    {tbl(["Anel de distância", "N", "Viés médio", "Desvio"], [
        ["0 – 500 m", "1.661.203", "−24,4 dB", "± 9,7"],
        ["500 – 1000 m", "29.968", "−6,7 dB", "± 7,7"],
        ["1000 – 1500 m", "14.645", "−2,1 dB", "± 7,5"],
        ["1500 – 2000 m", "9.411", "+0,9 dB", "± 7,4"],
    ], hl_col=2, widths=["30%", "22%", "26%", "22%"])}
    <p>A leitura: <b>sob a torre o modelo superestima em 24 dB</b> — o medidor está
    abaixo do feixe principal da antena — e o viés praticamente zera entre 1,5 e
    2 km, onde o feixe encontra o solo. É exatamente o decaimento que a curva
    log-distância da Tabela 4 captura, e a razão pela qual uma correção plana por
    ambiente seria errada: puniria a borda da célula pelo pecado do centro.</p>
    <div class="eyebrow tbl-label">TABELA 6 — RESÍDUO BRUTO POR CLASSE DE COBERTURA DO SOLO (MAPBIOMAS)</div>
    {tbl(["Classe", "N", "Viés médio", "Desvio"], [
        ["Urbano", "1.427.976", "−23,8 dB", "± 10,0"],
        ["Agricultura", "209.385", "−23,5 dB", "± 11,3"],
        ["Floresta", "42.179", "−23,0 dB", "± 12,3"],
        ["Solo exposto", "17.519", "−22,4 dB", "± 11,1"],
        ["Campo aberto", "11.166", "−24,3 dB", "± 11,7"],
        ["Água", "2.153", "−19,2 dB", "± 12,1"],
    ], hl_col=3, widths=["30%", "22%", "26%", "22%"])}
    <p>Duas assinaturas físicas: <b>caminhos sobre água perdem ~4,6 dB menos</b>
    que os urbanos (reflexão especular, sem clutter), e <b>floresta tem o maior
    espalhamento</b> (± 12,3 dB) — dossel é o clutter mais heterogêneo. Nenhum
    desses padrões foi programado; todos emergiram dos dados e são coerentes com a
    literatura de propagação, o que valida a cadeia de atribuição.</p>"""

    # ---------- p13: worked example ----------
    p_ex = f"""
    {sec("09", "EXEMPLO APLICADO", "Dois estudos reais, números reais")}
    <h3 class="sub">Cobertura 5G n78 — São Paulo, centro</h3>
    <p>Torre em −23,550, −46,630 (região da Sé), 30 m de altura, 3.500 MHz,
    raio de 2 km — executado contra a API pública em produção:</p>
    {tbl(["Parâmetro / resultado", "Valor", "Origem"], [
        ["Ambiente inferido", "urbano", "MapBiomas na área da grade"],
        ["Pontos de grade", "14.000", "motor Rust, sombra de terreno DSM"],
        ["Correção aplicada", "ĉ(d) = −60,5 + 19,2 log₁₀d", "curva urbana da Tabela 4"],
        ["σ médio da grade", "5,97 dB", "TR 38.901 UMa (LOS/NLOS por ponto)"],
        ["Cobertura P50 (mediana)", "57,0%", "limiar −95 dBm, pós-correção"],
        ["Cobertura P90 (conservadora)", "20,4%", "margem de 1,282 σ"],
    ], hl_col=1, widths=["36%", "34%", "30%"])}
    <p>A distância entre P50 e P90 é a incerteza dita em voz alta: quem vende
    cobertura pelo P50 e entrega pelo P90 gera churn; o Enlace mostra os dois.</p>
    <h3 class="sub">Enlace ponto-a-ponto — 7,8 km sobre DSM</h3>
    <p>Do conjunto de testes de ponta a ponta que roda contra o produto público
    (5,8 GHz, perfil com vegetação e edifícios):</p>
    {tbl(["Resultado", "Valor"], [
        ["Linha de visada", "livre (LOS)"],
        ["Zona de Fresnel", "≥ 60% desobstruída"],
        ["Potência recebida", "−50,6 dBm"],
        ["Margem de enlace", "19,4 dB"],
        ["Disponibilidade com chuva", "99,990% (R₀,₀₁ = 64,4 mm/h, ITU-R P.837 local)"],
    ], hl_col=1, widths=["42%", "58%"])}
    <p class="mut">Ambos os estudos são reproduzíveis por qualquer conta em
    app.enlace.network — nenhum número desta página vem de simulação privada.</p>"""

    # ---------- p16: references ----------
    p_ref = f"""
    {sec("", "REFERÊNCIAS E GLOSSÁRIO", "Fontes normativas e de dados")}
    <div class="grid2">
      <div>
        <div class="eyebrow tbl-label">MODELOS E NORMAS</div>
        <ol class="refs">
          <li>M. Hata, “Empirical Formula for Propagation Loss in Land Mobile Radio Services”, IEEE Trans. Veh. Technol., 1980.</li>
          <li>COST Action 231, Final Report, cap. 4 (COST-Hata), 1999.</li>
          <li>3GPP TR 38.901, “Study on channel model for frequencies from 0.5 to 100 GHz”.</li>
          <li>ITU-R P.526-15, “Propagation by diffraction”.</li>
          <li>J. Deygout, “Multiple Knife-Edge Diffraction of Microwaves”, IEEE Trans. Antennas Propag., 1966.</li>
          <li>ITU-R P.837-7, “Characteristics of precipitation for propagation modelling”.</li>
          <li>ITU-R P.2109-2, “Prediction of building entry loss”.</li>
        </ol>
        <div class="eyebrow tbl-label">DADOS</div>
        <ol class="refs" start="8">
          <li>NASA SRTM GL1 (30 m), via OpenTopography.</li>
          <li>Copernicus GLO-30 DSM, ESA/Airbus.</li>
          <li>ANADEM v1 — modelo de terreno nu para o Brasil, UFRGS.</li>
          <li>MapBiomas, Coleção 9, cobertura do solo 2023.</li>
          <li>Google Open Buildings 2.5D (altura, 0,5 m).</li>
          <li>Anatel — dados abertos: medições RNI; licenciamento SMP (Mosaico).</li>
        </ol>
      </div>
      <div>
        <div class="eyebrow tbl-label">GLOSSÁRIO MÍNIMO</div>
        <ol class="refs glos">
          <li><b>EIRP</b> — potência isotrópica efetivamente irradiada: transmissor + ganho de antena.</li>
          <li><b>RMSE</b> — raiz do erro quadrático médio; a régua de acurácia deste documento.</li>
          <li><b>Held-out</b> — dados nunca vistos pelo ajuste; a única avaliação que conta.</li>
          <li><b>P50 / P90</b> — cobertura mediana / conservadora (90% de confiança por ponto).</li>
          <li><b>σ (sigma)</b> — desvio-padrão do sombreamento log-normal, por ponto.</li>
          <li><b>Zona de Fresnel</b> — elipsoide em torno da linha de visada que precisa estar livre.</li>
          <li><b>Clutter</b> — o que há sobre o terreno: prédios, dossel, cultura agrícola.</li>
          <li><b>FWA</b> — acesso fixo sem fio: última milha por rádio.</li>
          <li><b>DTM / DSM</b> — modelo de terreno (solo) / de superfície (com prédios e vegetação).</li>
          <li><b>RNI</b> — medições de radiação não-ionizante da Anatel; nosso conjunto de verdade.</li>
        </ol>
        <div class="pull" style="margin-top:5mm">
          <p>Reprodutibilidade: os scripts de ingestão, benchmark e ajuste
          (<span style="font-family:'IBM Plex Mono';font-size:7.6pt">ingest_rni.py ·
          benchmark_v1.sql · classify_residuals.py · fit_corrections.sql</span>)
          acompanham o repositório do Enlace; os dados de entrada são 100%
          públicos.</p>
        </div>
      </div>
    </div>"""

    pages = [
        page(cover, dark=True),
        page(p2, 2),
        page(p3, 3),
        page(p4, 4),
        page(p5, 5),
        page(p6, 6),
        page(p7, 7),
        page(p_eq, 8),
        page(p8, 9),
        page(p_meth, 10),
        page(p_anat, 11),
        page(p9, 12),
        page(p_ex, 13),
        page(p10, 14),
        page(p11, 15),
        page(p_ref, 16),
        page(p12, dark=True),
    ]

    css = f"""
    @font-face {{ font-family: Fraunces; src: url({f_fra400}); font-weight: 400; }}
    @font-face {{ font-family: Fraunces; src: url({f_fra600}); font-weight: 600; }}
    @font-face {{ font-family: Inter; src: url({f_int400}); font-weight: 400; }}
    @font-face {{ font-family: Inter; src: url({f_int600}); font-weight: 600; }}
    @font-face {{ font-family: 'IBM Plex Mono'; src: url({f_mon400}); font-weight: 400; }}
    @font-face {{ font-family: 'IBM Plex Mono'; src: url({f_mon500}); font-weight: 500; }}

    :root {{
      --petrol: #04211F; --petrol-2: #0A3833; --teal: #0D9488; --teal-d: #0B7C72;
      --teal-b: #2DD4BF; --ink: #16211F; --stone: #5C6B67; --wash: #F1F5F3;
      --hair: #DCE4E1; --amber: #A85E1B; --amber-bg: #FBF4E8;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ background: #fff; }}
    body {{ font-family: Inter, sans-serif; color: var(--ink);
           -webkit-print-color-adjust: exact; print-color-adjust: exact; }}

    @page {{ size: A4; margin: 0; }}
    .page {{ width: 210mm; height: 297mm; position: relative; overflow: hidden;
            padding: 15mm 17mm 16mm; page-break-after: always; background: #fff; }}
    .page.dark {{ background: var(--petrol); color: #E9F2F0; padding: 0; }}

    .runhead {{ display: flex; justify-content: space-between; align-items: baseline;
               border-bottom: 1px solid var(--hair); padding-bottom: 2.4mm;
               margin-bottom: 7mm; font-family: 'IBM Plex Mono'; font-weight: 500;
               font-size: 6.4pt; letter-spacing: .18em; color: var(--stone); }}
    .runfoot {{ position: absolute; left: 17mm; right: 17mm; bottom: 8mm;
               display: flex; justify-content: space-between; align-items: baseline;
               border-top: 1px solid var(--hair); padding-top: 2.2mm;
               font-family: 'IBM Plex Mono'; font-size: 6.4pt; letter-spacing: .08em;
               color: var(--stone); }}
    .runfoot .pno {{ font-weight: 500; color: var(--teal-d); }}

    .eyebrow {{ font-family: 'IBM Plex Mono'; font-weight: 500; font-size: 6.8pt;
               letter-spacing: .2em; color: var(--teal-d); text-transform: uppercase; }}
    .sechead {{ display: flex; gap: 6mm; align-items: flex-start; margin-bottom: 6mm; }}
    .secnum {{ font-family: Fraunces; font-weight: 600; font-size: 30pt; line-height: 1;
              color: var(--teal); opacity: .32; min-width: 14mm; }}
    h2 {{ font-family: Fraunces; font-weight: 600; font-size: 17.5pt; line-height: 1.18;
         margin-top: 1.2mm; text-wrap: balance; }}
    h3.sub {{ font-family: Fraunces; font-weight: 600; font-size: 12.5pt;
             margin: 6mm 0 2.4mm; }}
    p {{ font-size: 9pt; line-height: 1.58; margin-bottom: 3.2mm; }}
    p.lead {{ font-size: 11.5pt; line-height: 1.55; margin-bottom: 6mm; }}
    p.lead em {{ font-family: Fraunces; font-style: italic; color: var(--teal-d); }}
    p.mut, .figcap {{ font-size: 7.6pt; color: var(--stone); line-height: 1.5; }}
    b {{ font-weight: 600; }}

    .threefacts {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4.5mm;
                  margin-bottom: 6mm; }}
    .fact {{ border-top: 2px solid var(--teal); padding-top: 3mm; }}
    .fact .factnum {{ font-family: Fraunces; font-weight: 600; font-size: 13pt;
                     color: var(--teal); margin-bottom: 1.6mm; }}
    .fact h3 {{ font-family: Fraunces; font-weight: 600; font-size: 11pt;
               line-height: 1.25; margin-bottom: 2mm; text-wrap: balance; }}
    .fact p {{ font-size: 8.2pt; line-height: 1.55; }}

    .pull {{ background: var(--wash); border-left: 3px solid var(--teal);
            border-radius: 0 3mm 3mm 0; padding: 4.5mm 6mm; margin: 5mm 0; }}
    .pull p {{ font-size: 9.4pt; margin-bottom: 2mm; }}
    .pull p:last-child {{ margin-bottom: 0; }}
    .pull.amber {{ background: var(--amber-bg); border-left-color: var(--amber); }}
    .punch {{ font-family: Fraunces; font-weight: 600; font-size: 13.5pt;
             color: var(--amber); }}

    .toc {{ margin-top: 7mm; border-top: 1px solid var(--hair); padding-top: 4mm; }}
    .toc ol {{ list-style: none; columns: 2; column-gap: 12mm; margin-top: 3mm; }}
    .toc li {{ display: flex; align-items: baseline; gap: 2mm; font-size: 8.8pt;
              padding: 1.5mm 0; break-inside: avoid; }}
    .toc li i {{ flex: 1; border-bottom: 1px dotted var(--hair); }}
    .toc li b {{ font-family: 'IBM Plex Mono'; font-size: 8pt; color: var(--teal-d); }}

    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin: 4mm 0; }}
    .grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; margin: 4mm 0; }}
    .card {{ border: 1px solid var(--hair); border-radius: 2.5mm; padding: 4mm 4.5mm; }}
    .card .eyebrow {{ margin-bottom: 2mm; }}
    .card p {{ font-size: 8.4pt; margin: 0; }}
    .card.teal {{ background: var(--wash); border-color: #C4DAD4; }}

    .panel {{ background: var(--wash); border: 1px solid var(--hair);
             border-radius: 3mm; padding: 4.5mm 5mm 3.5mm; margin: 4mm 0 5mm; }}
    .figlabel {{ font-family: 'IBM Plex Mono'; font-weight: 500; font-size: 6.8pt;
                letter-spacing: .18em; color: var(--teal-d); margin-bottom: 3mm; }}
    .figcap {{ margin-top: 2.6mm; }}

    table {{ width: 100%; border-collapse: collapse; margin: 2mm 0 5mm;
            font-size: 8.2pt; }}
    th {{ font-family: 'IBM Plex Mono'; font-weight: 500; font-size: 6.6pt;
         letter-spacing: .12em; text-transform: uppercase; color: var(--stone);
         text-align: left; padding: 2mm 2.5mm; border-bottom: 1.5px solid var(--teal); }}
    td {{ padding: 2.2mm 2.5mm; border-bottom: 1px solid var(--hair);
         line-height: 1.4; font-variant-numeric: tabular-nums; }}
    td.hl {{ font-family: 'IBM Plex Mono'; font-weight: 500; color: var(--teal-d);
            font-size: 8.6pt; }}
    .tbl-label {{ margin: 4mm 0 1mm; }}

    .limits {{ background: var(--amber-bg); border: 1px solid #E8D5B5;
              border-radius: 2.5mm; padding: 4mm 5mm; margin: 3mm 0; }}
    .limits .amberink {{ color: var(--amber); margin-bottom: 2mm; }}
    .limits ul {{ list-style: none; }}
    .limits li {{ font-size: 8.2pt; line-height: 1.5; padding-left: 4mm;
                 position: relative; margin-bottom: 1.8mm; }}
    .limits li::before {{ content: "—"; position: absolute; left: 0;
                         color: var(--amber); }}

    .eq {{ font-family: Fraunces, serif; font-size: 10.5pt; text-align: center;
          padding: 3mm 0 3.4mm; color: var(--ink); }}
    .eq i {{ font-style: italic; }}
    .eq .op {{ color: var(--stone); padding: 0 .5mm; }}
    .eqrow {{ display: grid; grid-template-columns: 1fr auto; align-items: center;
             border-bottom: 1px solid var(--hair); }}
    .eqrow:last-child {{ border-bottom: none; }}
    .eqrow .eqname {{ font-family: 'IBM Plex Mono'; font-weight: 500;
                     font-size: 6.6pt; letter-spacing: .14em; color: var(--stone);
                     text-transform: uppercase; }}
    .chips {{ display: flex; gap: 3mm; margin: 1mm 0 3mm; flex-wrap: wrap; }}
    .chip {{ font-family: 'IBM Plex Mono'; font-weight: 500; font-size: 7.2pt;
            letter-spacing: .06em; border: 1px solid var(--hair);
            border-radius: 10mm; padding: 1.6mm 4mm; color: var(--ink); }}
    .chip.hot {{ background: var(--teal); border-color: var(--teal-d); color: #fff; }}

    ol.refs {{ list-style: none; counter-reset: ref; margin: 1mm 0 4mm; }}
    ol.refs li {{ counter-increment: ref; font-size: 7.8pt; line-height: 1.5;
                 padding-left: 6mm; position: relative; margin-bottom: 1.6mm; }}
    ol.refs li::before {{ content: "[" counter(ref) "]";
                         font-family: 'IBM Plex Mono'; font-size: 6.8pt;
                         color: var(--teal-d); position: absolute; left: 0; top: .2mm; }}
    ol.refs.glos li::before {{ content: "—"; }}
    .shot {{ margin: 0 0 6mm; }}
    .shot img {{ width: 100%; display: block; border-radius: 2.5mm;
                border: 1px solid var(--hair);
                box-shadow: 0 2mm 6mm rgba(4, 33, 31, .10); }}
    .shot .figcap {{ margin-top: 2.2mm; }}

    /* -------- cover / back -------- */
    .coverwrap, .backwrap {{ position: absolute; inset: 0; padding: 16mm 18mm;
                            display: flex; flex-direction: column; }}
    .covermotif {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .coverhead {{ position: relative; display: flex; justify-content: space-between;
                 align-items: baseline; }}
    .brand {{ font-family: 'IBM Plex Mono'; font-weight: 500; font-size: 13pt;
             letter-spacing: .34em; }}
    .brandsub {{ font-family: 'IBM Plex Mono'; font-size: 7pt; letter-spacing: .1em;
                color: #5FC9BC; }}
    .covermain {{ position: relative; margin-top: 44mm; }}
    .covermain h1 {{ font-family: Fraunces; font-weight: 600; font-size: 33pt;
                    line-height: 1.12; margin: 5mm 0 7mm; }}
    .coverlead {{ font-size: 10.5pt; line-height: 1.65; max-width: 125mm;
                 color: #C7DCD8; }}
    .coverkpis {{ position: relative; margin-top: auto; display: grid;
                 grid-template-columns: repeat(4, 1fr); gap: 4mm;
                 border-top: 1px solid rgba(45, 212, 191, .25); padding-top: 5mm; }}
    .coverkpis b {{ display: block; font-family: Fraunces; font-weight: 600;
                   font-size: 17pt; color: #2DD4BF; margin-bottom: 1mm; }}
    .coverkpis span {{ font-size: 6.8pt; line-height: 1.45; color: #9DBEB9;
                      display: block; }}
    .coverfoot {{ position: relative; display: flex; gap: 8mm; margin-top: 7mm;
                 font-family: 'IBM Plex Mono'; font-size: 6.6pt; letter-spacing: .08em;
                 color: #6FA39C; }}

    .backwrap {{ justify-content: center; gap: 6mm; }}
    .backtitle {{ font-family: Fraunces; font-weight: 600; font-size: 24pt;
                 line-height: 1.2; }}
    .backctas {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6mm;
                border-top: 1px solid rgba(45,212,191,.25); padding-top: 5mm;
                margin-top: 4mm; }}
    .backctas p {{ font-size: 8.6pt; color: #C7DCD8; margin-top: 1.6mm; }}
    .backdisc {{ margin-top: 14mm; font-size: 6.6pt; line-height: 1.6;
                color: #6FA39C; max-width: 150mm; }}
    """

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>ENLACE — Whitepaper: Propagação de RF calibrada</title>
<style>{css}</style></head><body>{''.join(pages)}</body></html>"""


def render_pdf():
    from playwright.sync_api import sync_playwright

    os.makedirs(OUT, exist_ok=True)
    html = build_html()
    with open(HTML, "w") as f:
        f.write(html)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        pg = browser.new_page()
        pg.goto("file://" + HTML, wait_until="networkidle")
        pg.pdf(path=PDF, format="A4", print_background=True,
               prefer_css_page_size=True)
        browser.close()
    print(PDF, f"{os.path.getsize(PDF)/1024:.0f} KB")


if __name__ == "__main__":
    render_pdf()
