"""Generate per-client prospectus PDFs — one for each of the 9 client profiles.

Every quantitative claim here is verified: held-out RMSE from
rf_calibration_eval, corpus sizes from the ingest tables, features from the
live product at app.enlace.network. Do not add numbers that are not in
docs/propagation-methodology.md.

Usage: python3 scripts/prospectus.py   (writes outputs/prospectus/*.pdf)
"""

from __future__ import annotations

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ACCENT = colors.HexColor("#0D9488")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#737D87")
BG = colors.HexColor("#F2F1EE")

OUT_DIR = "outputs/prospectus"

# ---------------------------------------------------------------------------
# Shared, verified facts
# ---------------------------------------------------------------------------

VALIDATION_ROWS = [
    ["Fatia (held-out)", "Pontos de teste", "RMSE antes", "RMSE calibrado"],
    ["Urbano (estações atribuídas)", "257.446", "25,8 dB", "7,0 dB"],
    ["Suburbano", "13.625", "26,1 dB", "7,6 dB"],
    ["Rural", "35.621", "25,6 dB", "8,3 dB"],
    ["Urbano (tier cego por proximidade)", "359.914", "28,6 dB", "8,3 dB"],
]

DATA_LAYERS = (
    "SRTM GL1 30 m (terreno) · Copernicus GLO-30 (superfície/DSM) · "
    "ANADEM v1 (solo exposto) · MapBiomas C9 (uso do solo) · "
    "Google Open Buildings 2.5D (altura de edifícios, 0,5 m)"
)

PHYSICS = (
    "Hata/COST-231 e 3GPP TR 38.901 com piso FSPL · difração multi-obstáculo "
    "Deygout (ITU-R P.526) · chuva regional ITU-R P.837 · perda de entrada em "
    "edifícios ITU-R P.2109 · zona de Fresnel · cobertura P50/P90 com "
    "incerteza (sigma) calibrada"
)

METHOD_NOTE = (
    "Como validamos: previsão de campo elétrico comparada a 3,55 milhões de "
    "medições RNI da Anatel (2005–2025), cruzadas com o registro de "
    "licenciamento SMP (112 mil estações, atualizado diariamente). Correções "
    "ajustadas em 80% dos dados; todos os números acima vêm dos 20% nunca "
    "vistos pelo ajuste. Metodologia pública em enlace.network/validation."
)

DISCLAIMER = (
    "Estudos de radiofrequência para fins de licenciamento ou responsabilidade "
    "técnica devem ser assinados por engenheiro habilitado (Lei 5.194/66). O "
    "Enlace fornece a ferramenta de cálculo e os dados; a responsabilidade "
    "técnica do projeto permanece com o profissional. Pagamento online em "
    "breve — ativação por contato: contato@enlace.network."
)

PRICING = {
    "teste": "Teste — R$ 0 (5 estudos/mês, para conhecer a plataforma)",
    "wisp": "WISP — R$ 149/mês (estudos ilimitados, exportação PDF/KMZ/GeoJSON, presets de equipamentos)",
    "provedor": "Provedor — R$ 499/mês (setoriais, P50/P90, 5 usuários, API, relatórios com sua marca)",
    "enterprise": "Enterprise — sob consulta (API ilimitada, lote, due diligence, white-label, SLA)",
}

# ---------------------------------------------------------------------------
# The 9 profiles
# ---------------------------------------------------------------------------

PROFILES = [
    {
        "slug": "01-micro-wisp",
        "title": "Micro-WISPs e provedores de bairro",
        "subtitle": "Para quem sobe na torre e precisa acertar de primeira",
        "pains": [
            ("Cada instalação errada custa caro", "Uma visita técnica desperdiçada ou um cliente sem sinal consome a margem do mês."),
            ("Ferramentas profissionais custam milhares de dólares", "Softwares tradicionais de planejamento RF são precificados para operadoras, não para o provedor de bairro."),
            ("Planejar 'no olho' não escala", "Crescer para o próximo bairro exige saber onde o sinal chega antes de investir em POP e torre."),
        ],
        "solutions": [
            ("Clique no mapa, veja o alcance", "Estudo de enlace ou cobertura para qualquer coordenada do Brasil em segundos, no navegador — sem instalar nada."),
            ("Presets dos rádios que você já usa", "Ubiquiti, Cambium, Mimosa, Intelbras — potência, ganho e sensibilidade já preenchidos."),
            ("Terreno e edifícios de verdade", "Elevação 30 m + altura de prédios 0,5 m: o modelo enxerga o morro e o prédio que bloqueiam seu link."),
            ("PDF pronto para o cliente", "Exporte o estudo com um clique e anexe na proposta."),
        ],
        "tier": ["teste", "wisp"],
        "hook": (
            "Erro medido de 7 dB em área urbana — validado contra milhões de "
            "medições reais da Anatel, não contra promessa de fabricante."
        ),
    },
    {
        "slug": "02-integrador-fwa",
        "title": "Integradores e revendas FWA",
        "subtitle": "Feche mais projetos com estudo técnico na proposta",
        "pains": [
            ("Proposta sem estudo perde para proposta com estudo", "O cliente corporativo quer ver a viabilidade antes de assinar."),
            ("Site survey presencial para cada lead não fecha a conta", "Deslocar equipe para pré-venda em leads frios custa mais do que a comissão."),
            ("Cada fabricante tem sua própria calculadora otimista", "Link planner de fabricante assume mundo plano e sem obstáculo."),
        ],
        "solutions": [
            ("Viabilidade remota em minutos", "Endereço do cliente → estudo de enlace com Fresnel, difração e chuva regional — antes da visita."),
            ("Neutro de fabricante", "Um único modelo físico calibrado para comparar Ubiquiti, Cambium, Mimosa e Intelbras nas mesmas condições."),
            ("KMZ/GeoJSON para o time de campo", "O instalador abre no Google Earth exatamente o que foi vendido."),
            ("Margem de enlace honesta", "Disponibilidade com chuva P.837 da região do cliente — não a média mundial."),
        ],
        "tier": ["wisp", "provedor"],
        "hook": (
            "O estudo que acompanha sua proposta usa o mesmo motor validado "
            "contra 3,55 milhões de medições de campo da Anatel."
        ),
    },
    {
        "slug": "03-consultoria-rf",
        "title": "Consultorias de RF e engenharia",
        "subtitle": "Benchmark publicado, metodologia auditável, marca sua",
        "pains": [
            ("Defender o estudo perante o cliente exige lastro", "“Confia no software” não sustenta um laudo questionado."),
            ("Licenças de ferramentas legadas custam caro por engenheiro", "E rodam em desktop, travando o trabalho em equipe."),
            ("Dados de terreno/clutter atualizados dão trabalho", "Montar pipeline de SRTM, DSM, uso do solo e edifícios consome semanas de projeto."),
        ],
        "solutions": [
            ("Acurácia medida e publicada", "RMSE held-out por ambiente, com N declarado — cite o benchmark no seu laudo."),
            ("Cinco camadas de dados nacionais prontas", DATA_LAYERS),
            ("API para automação", "Rode lotes de estudos e integre ao seu fluxo de relatórios."),
            ("Relatórios white-label", "PDF com a marca da sua consultoria, disclaimer de responsabilidade técnica incluído."),
        ],
        "tier": ["provedor", "enterprise"],
        "hook": (
            "Único planejador nacional com erro medido publicamente: 7,0 dB "
            "urbano em avaliação out-of-sample reproduzível."
        ),
    },
    {
        "slug": "04-isp-regional",
        "title": "ISPs regionais e altnets em expansão",
        "subtitle": "Decida a próxima cidade com física, não com achismo",
        "pains": [
            ("Expansão FWA/híbrida exige priorizar cidades", "Escolher errado imobiliza capex em POPs que não performam."),
            ("Times de projeto sobrecarregados", "Engenharia vira gargalo quando cada estudo leva meio dia em ferramenta desktop."),
            ("Cobertura prometida × cobertura entregue", "Vender plano onde o sinal não chega gera churn e reclamação no Procon."),
        ],
        "solutions": [
            ("Cobertura P50/P90 por setor", "Azimute, meia-potência e downtilt — com incerteza calibrada, não mapa binário."),
            ("Ambiente inferido automaticamente", "MapBiomas classifica urbano/suburbano/rural ponto a ponto — a correção certa em cada pixel."),
            ("Multiusuário + projetos salvos", "5 usuários no plano Provedor; estudos versionados e compartilhados."),
            ("API 1.000 chamadas/mês", "Alimente seu BI de expansão com estudos em lote."),
        ],
        "tier": ["provedor"],
        "hook": (
            "P90 calibrado significa: no plano conservador, 9 em cada 10 "
            "pontos previstos cobertos realmente têm sinal."
        ),
    },
    {
        "slug": "05-fundo-ma",
        "title": "Fundos de investimento e M&A de ISPs",
        "subtitle": "Due diligence de cobertura em dias, não meses",
        "pains": [
            ("O ativo declara cobertura que ninguém verificou", "Base de assinantes e mapa comercial raramente batem com a física."),
            ("Drive test em cada praça-alvo é caro e lento", "Semanas de campo por alvo inviabilizam pipeline de aquisições."),
            ("Comparar alvos exige régua única", "Cada ISP entrega mapa em formato e critério diferente."),
        ],
        "solutions": [
            ("Verificação independente da cobertura declarada", "Reprocessamos as torres do alvo no nosso motor calibrado e comparamos com o mapa comercial."),
            ("Régua única entre alvos", "Mesmo modelo, mesmos dados, mesmo critério P50/P90 para todo o pipeline."),
            ("Processamento em lote via API", "Centenas de sites por alvo, resultados em planilha/GeoJSON para o data room."),
            ("Números defensáveis no IC", "Erro do modelo medido e publicado — anexe o benchmark ao memo de investimento."),
        ],
        "tier": ["enterprise"],
        "hook": (
            "Erro conhecido de 7–8 dB validado em 3,55 milhões de medições: "
            "a diferença entre estimativa e opinião."
        ),
    },
    {
        "slug": "06-torres",
        "title": "Empresas de torres (towercos)",
        "subtitle": "Precifique cada vertical pelo alcance que ela entrega",
        "pains": [
            ("Duas torres iguais não valem o mesmo", "O valor de uma vertical depende do que ela cobre — terreno, clutter e altura decidem."),
            ("Prospecção de inquilinos sem argumento técnico", "“Alugue nossa torre” convence menos que “desta torre você cobre X km² do seu alvo”."),
            ("Avaliar portfólio inteiro é projeto de meses", "Estudo manual por site não escala para centenas de ativos."),
        ],
        "solutions": [
            ("Footprint por torre, em lote", "Cobertura calibrada de cada vertical do portfólio — km², população de referência, P50/P90."),
            ("Argumento de venda por inquilino-alvo", "Simule o equipamento do prospect na sua torre e mostre o alcance dele."),
            ("Ranking objetivo de ativos", "Ordene o portfólio por capacidade de cobertura para priorizar comercialização."),
            ("Dados nacionais sem mobilização", "Qualquer coordenada do Brasil, sem visita de campo."),
        ],
        "tier": ["enterprise"],
        "hook": (
            "O mesmo motor que erra só 7 dB em área urbana transforma altura "
            "de torre em km² — o ativo vira número."
        ),
    },
    {
        "slug": "07-bancos-bndes",
        "title": "Bancos, BNDES e financiadores de infraestrutura",
        "subtitle": "O plano de cobertura do tomador, verificado por física",
        "pains": [
            ("Projetos de conectividade chegam com mapas otimistas", "O financiador não tem instrumento próprio para checar a promessa técnica."),
            ("Acompanhar execução exige medir cobertura entregue", "Milestone de “cidade coberta” precisa de critério verificável."),
            ("Risco técnico mal precificado vira inadimplência", "Rede que não performa não gera a receita que paga o financiamento."),
        ],
        "solutions": [
            ("Parecer independente sobre o plano de RF", "Reprocessamos o projeto do tomador e apontamos onde a física diverge da promessa."),
            ("Critério auditável de milestone", "Cobertura P90 calibrada como régua contratual de desembolso."),
            ("Metodologia pública e versionada", "Relatórios citam método, dados e erro medido — auditáveis por terceiros."),
            ("Escala nacional imediata", "Qualquer município brasileiro, sem depender de dados do próprio tomador."),
        ],
        "tier": ["enterprise"],
        "hook": (
            "Avaliação técnica com erro declarado (7–8 dB held-out) e "
            "metodologia 100% reproduzível de dados públicos."
        ),
    },
    {
        "slug": "08-governo-anatel",
        "title": "Governo, reguladores e políticas públicas",
        "subtitle": "Cobertura declarada × cobertura física, em escala nacional",
        "pains": [
            ("Mapas de cobertura declarados pelas operadoras", "Verificação independente em escala é cara com drive test."),
            ("Políticas de universalização precisam de diagnóstico", "Onde exatamente falta sinal, e quanto custaria cobrir?"),
            ("Editais e obrigações exigem linha de base técnica", "Sem referência física, a fiscalização discute mapa contra mapa."),
        ],
        "solutions": [
            ("Modelo calibrado com os dados da própria Anatel", "3,55 milhões de medições RNI + registro SMP — o modelo aprende do acervo público."),
            ("Verificação em lote por município/UF", "Cobertura física estimada de qualquer conjunto de estações licenciadas."),
            ("Diagnóstico de vazios de cobertura", "Cruzamento com MapBiomas e edifícios para localizar população sem sinal plausível."),
            ("Transparência total", "Metodologia, erro e scripts públicos — defensável em contraditório."),
        ],
        "tier": ["enterprise"],
        "hook": (
            "Construído sobre dados abertos do próprio regulador — e devolve "
            "ao regulador uma capacidade de verificação que hoje não existe."
        ),
    },
    {
        "slug": "09-operadoras",
        "title": "Operadoras móveis e carriers",
        "subtitle": "Um segundo par de olhos, calibrado no seu país",
        "pains": [
            ("Ferramentas globais, calibração genérica", "Modelos tunados para Europa/EUA erram o clutter tropical e a morfologia urbana brasileira."),
            ("Drive test cobre uma fração da rede", "Calibração contínua exige mais pontos do que qualquer campanha entrega."),
            ("Densificação 5G é sensível a edifício", "FR1 em área densa precisa de modelo que enxergue prédio por prédio."),
        ],
        "solutions": [
            ("Calibração brasileira de fábrica", "Correções por ambiente ajustadas em milhões de medições nacionais — offsets por banda medidos (700 MHz a 2,5 GHz)."),
            ("Edifícios 2.5D em escala nacional", "Google Open Buildings 0,5 m integrado ao perfil de enlace e à cobertura."),
            ("Benchmark independente do seu planejador atual", "Compare as previsões da sua ferramenta com um modelo de erro conhecido."),
            ("API e processamento em lote", "Integração ao seu pipeline de planejamento e otimização."),
        ],
        "tier": ["enterprise"],
        "hook": (
            "Offsets por banda medidos de estações reais: 700 MHz propaga "
            "~10 dB além de 2,5 GHz após correção de distância — medido, não assumido."
        ),
    },
]

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

S_TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=colors.white)
S_SUB = ParagraphStyle("s", fontName="Helvetica", fontSize=12, leading=16, textColor=colors.white)
S_H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK, spaceBefore=14, spaceAfter=6)
S_BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK)
S_MUT = ParagraphStyle("m", fontName="Helvetica", fontSize=8.5, leading=12, textColor=MUTED)
S_HOOK = ParagraphStyle("hk", fontName="Helvetica-Bold", fontSize=11.5, leading=16, textColor=ACCENT)
S_CELL_H = ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=INK)
S_CELL = ParagraphStyle("c", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)


def _cover(canvas_obj, doc, profile):
    canvas_obj.saveState()
    W, H = A4
    canvas_obj.setFillColor(ACCENT)
    canvas_obj.rect(0, H - 68 * mm, W, 68 * mm, stroke=0, fill=1)
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica-Bold", 15)
    canvas_obj.drawString(18 * mm, H - 16 * mm, "ENLACE")
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(18 * mm, H - 21 * mm, "Planejamento de RF calibrado para o Brasil · app.enlace.network")
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(MUTED)
    canvas_obj.drawString(
        18 * mm, 12 * mm,
        f"Enlace · {date.today().strftime('%d/%m/%Y')} · contato@enlace.network · enlace.network/pricing · página {doc.page}",
    )
    canvas_obj.restoreState()


def _later(canvas_obj, doc):
    canvas_obj.saveState()
    W, H = A4
    canvas_obj.setFillColor(ACCENT)
    canvas_obj.rect(0, H - 10 * mm, W, 10 * mm, stroke=0, fill=1)
    canvas_obj.setFillColor(colors.white)
    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.drawString(18 * mm, H - 7 * mm, "ENLACE · Propagação RF calibrada")
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(MUTED)
    canvas_obj.drawString(
        18 * mm, 12 * mm,
        f"Enlace · contato@enlace.network · app.enlace.network · página {doc.page}",
    )
    canvas_obj.restoreState()


def build_pdf(profile: dict) -> str:
    path = os.path.join(OUT_DIR, f"enlace-prospecto-{profile['slug']}.pdf")
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"Enlace — {profile['title']}",
        author="Enlace",
    )
    story = []

    # Cover header text lives in the teal band (drawn by _cover); push the
    # first page's content below the 68 mm band.
    story.append(Spacer(1, 56 * mm))
    story.append(Paragraph(profile["hook"], S_HOOK))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("O problema que resolvemos para você", S_H2))
    for head, body in profile["pains"]:
        story.append(Paragraph(f"<b>{head}.</b> {body}", S_BODY))
        story.append(Spacer(1, 2.5 * mm))

    story.append(Paragraph("Como o Enlace responde", S_H2))
    for head, body in profile["solutions"]:
        story.append(Paragraph(f"<b>{head}.</b> {body}", S_BODY))
        story.append(Spacer(1, 2.5 * mm))

    story.append(PageBreak())

    story.append(Paragraph("Acurácia medida — não prometida", S_H2))
    tbl_data = [[Paragraph(c, S_CELL_H) for c in VALIDATION_ROWS[0]]] + [
        [Paragraph(c, S_CELL) for c in row] for row in VALIDATION_ROWS[1:]
    ]
    tbl = Table(tbl_data, colWidths=[62 * mm, 32 * mm, 36 * mm, 40 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#D8D6D0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(METHOD_NOTE, S_MUT))

    story.append(Paragraph("O que há por trás", S_H2))
    story.append(Paragraph(f"<b>Dados (todo o território nacional):</b> {DATA_LAYERS}.", S_BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<b>Física:</b> {PHYSICS}.", S_BODY))

    story.append(Paragraph("Plano recomendado", S_H2))
    for tier in profile["tier"]:
        story.append(Paragraph(f"• {PRICING[tier]}", S_BODY))
        story.append(Spacer(1, 1.5 * mm))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "<b>Comece agora:</b> crie sua conta em app.enlace.network (plano Teste "
        "gratuito, sem cartão) ou escreva para contato@enlace.network. Preços "
        "completos em enlace.network/pricing.", S_BODY,
    ))
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D8D6D0")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(DISCLAIMER, S_MUT))

    def on_first(cv, dc):
        _cover(cv, dc, profile)
        # Title inside the teal band
        cv.saveState()
        W, H = A4
        cv.setFillColor(colors.white)
        cv.setFont("Helvetica-Bold", 21)
        y = H - 38 * mm
        # naive wrap for long titles
        words, line, lines = profile["title"].split(), "", []
        for w in words:
            trial = (line + " " + w).strip()
            if cv.stringWidth(trial, "Helvetica-Bold", 21) > W - 36 * mm:
                lines.append(line)
                line = w
            else:
                line = trial
        lines.append(line)
        for ln in lines:
            cv.drawString(18 * mm, y, ln)
            y -= 9 * mm
        cv.setFont("Helvetica", 12)
        cv.drawString(18 * mm, y - 1 * mm, profile["subtitle"])
        cv.restoreState()

    doc.build(story, onFirstPage=on_first, onLaterPages=_later)
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    for profile in PROFILES:
        paths.append(build_pdf(profile))
    for p in paths:
        print(p, f"{os.path.getsize(p) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
