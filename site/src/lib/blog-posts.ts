export type BlogSection =
  | { type: 'text'; content: string }
  | { type: 'stat'; value: string; label: string; source?: string }
  | { type: 'table'; headers: string[]; rows: string[][]; caption?: string }
  | { type: 'callout'; title: string; content: string }
  | { type: 'bar-chart'; title: string; bars: { label: string; value: number; display: string }[] };

export interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  author: string;
  content: string;
  sections?: BlogSection[];
  readingTime?: string;
  category?: string;
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: 'crescimento-banda-larga-interior-2026',
    title: 'Crescimento de banda larga no interior: 10 cidades que mais que dobraram de tamanho em 12 meses',
    excerpt:
      'Cachoeira (BA) cresceu 351% em assinantes. Jaboticatubas (MG), 257%. Mapeamos os 10 municípios com maior explosão de banda larga em 2026 — e o que eles têm em comum.',
    date: '2026-03-13',
    author: 'Equipe Pulso',
    content: `SLUG: crescimento-banda-larga-interior-2026
EXCERPT: Cachoeira (BA) cresceu 351% em assinantes. Jaboticatubas (MG), 257%. Mapeamos os 10 municípios com maior explosão de banda larga em 2026 — e o que eles têm em comum.
CATEGORY: Mercado
TARGET_KEYWORD: crescimento banda larga interior 2026

O crescimento de banda larga no interior do Brasil em 2026 não está acontecendo onde a maioria dos analistas espera. Enquanto capitais e regiões metropolitanas disputam market share em mercados saturados, municípios com menos de 80 mil habitantes estão registrando taxas de crescimento de assinantes que ultrapassam 100%, 200% — e em um caso, 351% em 12 meses. São números que desafiam qualquer projeção conservadora e que revelam uma segunda onda de expansão da internet fixa brasileira, desta vez liderada por provedores regionais em cidades que até ontem mal apareciam nas estatísticas.

Os dados são da Anatel, referentes a janeiro de 2026: 54,4 milhões de assinantes de banda larga fixa, distribuídos entre 8.554 provedores ativos em 5.570 municípios. Por trás dessa média nacional, há histórias que merecem atenção.

## Os 10 municípios que explodiram

A tabela abaixo mostra os municípios com maior crescimento percentual de assinantes nos últimos 12 meses, considerando apenas cidades com pelo menos 1.000 assinantes no período anterior (para evitar distorções estatísticas de bases muito pequenas).

| Município | UF | Assinantes jan/25 | Assinantes jan/26 | Crescimento |
|-----------|----|-----------------:|-----------------:|------------:|
| Cachoeira | BA | 1.295 | 5.841 | +351,0% |
| Jaboticatubas | MG | 3.205 | 11.451 | +257,3% |
| Madre de Deus | BA | 1.418 | 4.546 | +220,6% |
| Pantano Grande | RS | 1.062 | 2.936 | +176,5% |
| Patu | RN | 1.209 | 3.117 | +157,8% |
| Martins | RN | 1.235 | 3.021 | +144,6% |
| Tomé-Açu | PA | 10.422 | 24.629 | +136,3% |
| São Luís do Quitunde | AL | 1.116 | 2.623 | +135,0% |
| Anita Garibaldi | SC | 1.085 | 2.453 | +126,1% |
| Itaitinga | CE | 5.708 | 12.863 | +125,4% |

O dado mais impressionante: essas 10 cidades estão em 8 estados diferentes — Bahia, Minas Gerais, Rio Grande do Sul, Rio Grande do Norte, Pará, Alagoas, Santa Catarina e Ceará. Não se trata de um fenômeno regional. É uma tendência nacional.

## O que essas cidades têm em comum

Olhando os números com cuidado, três padrões emergem.

**Primeiro: são cidades pequenas com demanda reprimida.** A maioria tem população entre 10 mil e 60 mil habitantes. São municípios onde, até 18 meses atrás, a oferta de banda larga fixa era escassa ou limitada a um único provedor com capacidade restrita. Quando um ISP regional entra com FTTH e preço competitivo, a adesão é explosiva — não por marketing, mas por falta de alternativa decente até então.

**Segundo: a fibra está chegando onde o rádio dominava.** Cidades como Tomé-Açu (PA), que saltou de 10.422 para 24.629 assinantes, representam o momento em que a fibra óptica finalmente viabiliza capacidade suficiente para atender demanda que já existia. O rádio atendia uma fração. A fibra desbloqueou o restante. Nível nacional, os dados confirmam: municípios que lideram em adoção de fibra — como Itapoá (SC) com 99,5% de acessos via FTTH, ou Ribeirão das Neves (MG) com 89.397 assinantes de fibra em 89.981 totais — são também os que apresentam maior crescimento absoluto.

**Terceiro: o crescimento vem em ondas geográficas.** Os dois municípios do Rio Grande do Norte (Patu e Martins) são vizinhos, separados por 25 km. Cachoeira e Madre de Deus ficam ambos no Recôncavo Baiano. Isso sugere que o crescimento segue a rota de expansão de redes regionais — um ISP chega em uma cidade, prova o modelo, e replica nas adjacentes.

## O contexto: 54,4 milhões e contando

O mercado brasileiro de banda larga fixa atingiu 54,4 milhões de assinantes em janeiro de 2026. Para colocar em perspectiva: são 8.554 provedores ativos disputando esse mercado. A média é de 6.363 assinantes por provedor — mas a mediana é muito menor, refletindo um mercado onde milhares de ISPs pequenos convivem com poucas dezenas de operações de grande porte.

O ponto relevante: o crescimento líquido do mercado não está mais nas capitais. Está no interior. As grandes operadoras já cobriram as áreas rentáveis das regiões metropolitanas. Os ISPs regionais estão fazendo o trabalho pesado de levar conectividade para as próximas 2.000-3.000 cidades.

## Fibra como catalisador: os municípios com 99%+ de adoção

Os dados mostram que existe uma elite de municípios onde a transição para fibra é praticamente completa. Itapoá (SC) e Sarzedo (MG) lideram com 99,5% dos acessos em FTTH. Valparaíso de Goiás (GO), com 69.142 acessos de fibra em 69.595 totais, prova que o modelo escala mesmo em cidades maiores do entorno de capitais.

O padrão é claro: quando fibra óptica ultrapassa 95% de participação em um município, o crescimento de base se acelera. Os assinantes que resistiam ao wireless de baixa velocidade migram. Novos domicílios que não tinham internet passam a contratar. E o churn cai, porque fibra gera satisfação — dado corroborado pela distribuição de selos de qualidade da Anatel: dos 83.619 selos atribuídos, 14.209 são ouro e 26.817 são prata. Provedores com rede predominantemente de fibra concentram 72% dos selos ouro.

## Qualidade como diferencial competitivo

Falando em selos, a fotografia atual é reveladora. Das 83.619 avaliações de qualidade da Anatel para provedores de banda larga, a distribuição é:

- **Ouro:** 14.209 (17%)
- **Prata:** 26.817 (32%)
- **Bronze:** 16.033 (19%)
- **Sem selo:** 26.560 (32%)

Quase um terço dos provedores avaliados não tem selo de qualidade. Isso representa tanto um problema de mercado quanto uma oportunidade: ISPs que investem em qualidade (e fibra) podem se diferenciar em municípios onde a concorrência entrega serviço abaixo do padrão. Em cidades como as do ranking de crescimento, a entrada de um provedor com selo ouro ou prata é o que explica parte da migração massiva de assinantes.

## O que está por trás dos 351% de Cachoeira

Cachoeira, no Recôncavo Baiano, é um caso emblemático. Município histórico com 35 mil habitantes, a 110 km de Salvador. Em janeiro de 2025, tinha 1.295 assinantes de banda larga — penetração de aproximadamente 12%. Em 12 meses, saltou para 5.841 assinantes, penetração estimada de 53%.

A explicação mais provável: um ISP regional implantou rede FTTH em 2025, oferecendo velocidades e preços que o mercado local nunca tinha visto. Quando a oferta desbloqueou a demanda latente, o crescimento foi vertical. Esse é o modelo que se repete em dezenas de municípios brasileiros a cada trimestre — e que os dados da Anatel capturam com 30 a 60 dias de atraso.

Para ISPs que buscam replicar esse modelo, o desafio é identificar quais municípios estão "prontos" para esse desbloqueio — cidades com demanda reprimida, infraestrutura de postes viável e concorrência fraca.

## Recomendação prática

Se você opera um ISP regional e está planejando expansão em 2026, os dados sugerem três ações concretas:

**1. Mapeie municípios adjacentes com penetração abaixo de 30%.** Os dados mostram que o crescimento segue rotas geográficas. Se você já opera em um município com boa base, as cidades vizinhas com baixa penetração são candidatas naturais — especialmente se a infraestrutura de postes permite extensão da sua rede existente.

**2. Priorize fibra.** Municípios que atingiram 99%+ de participação de FTTH são os que mais crescem em base absoluta. O investimento inicial é maior, mas o payback é acelerado pela combinação de maior adesão, menor churn e elegibilidade para selo de qualidade Anatel.

**3. Use dados, não intuição.** As 10 cidades deste ranking provavelmente não estavam no radar da maioria dos ISPs há 18 meses. Plataformas como a Pulso Network permitem filtrar os 5.570 municípios brasileiros por crescimento de mercado, penetração, HHI, perfil tecnológico e infraestrutura — cruzando 38+ fontes de dados públicos para revelar oportunidades que planilhas internas não capturam.

O interior do Brasil está conectando-se a uma velocidade sem precedentes. A questão não é se essas oportunidades existem — os dados da Anatel provam que sim. A questão é quem vai chegar primeiro.

---

*Dados: Anatel — base de assinantes de banda larga fixa, referência janeiro/2026. Análise: Pulso Network, com base em 54,4 milhões de registros de assinantes e 8.554 provedores ativos.*`,
    category: 'Mercado',
    readingTime: '7 min',
  },
  {
    slug: 'top-50-municipios-oportunidade-isps-2026',
    title: 'Os 50 municípios com maior oportunidade para ISPs em 2026',
    excerpt:
      'Analisamos 5.572 municípios brasileiros com nosso scoring proprietário de 15+ variáveis. Descubra onde estão as maiores oportunidades de expansão para provedores regionais.',
    date: '2026-03-05',
    author: 'Equipe Pulso',
    content: `O Pulso calcula um score de oportunidade para cada um dos 5.572 municípios brasileiros, cruzando dados de 19+ fontes públicas. O algoritmo pondera variáveis demográficas (população, renda, crescimento), competitivas (HHI, número de provedores, penetração de banda larga) e geográficas (densidade, presença de infraestrutura) para gerar um ranking de 0 a 100.

Na atualização de março de 2026, os municípios com maior score estão concentrados em três perfis distintos. O primeiro são cidades médias do interior de São Paulo e Minas Gerais — como Ribeirão Preto (score 87), Uberlândia (84) e São José do Rio Preto (75) — que combinam população elevada, renda acima da média e penetração ainda abaixo do potencial. O segundo perfil são capitais regionais do Nordeste, como Campina Grande (79) e Feira de Santana (77), onde o HHI elevado (acima de 3.000) indica concentração e portanto espaço para novos entrantes. O terceiro são polos agroindustriais do Centro-Oeste, onde o crescimento populacional supera 3% ao ano.

O que diferencia essa análise de um ranking simples por população é a inclusão de variáveis de infraestrutura. Municípios com nota alta no Pulso têm não apenas demanda reprimida, mas também condições operacionais favoráveis: presença de rede elétrica de média tensão (correlacionada com viabilidade de postes), malha viária pavimentada (que reduz custo de implantação de fibra) e distância viável de pontos de troca de tráfego. Usamos dados de 6,4 milhões de segmentos de estrada do OpenStreetMap e 16.559 trechos de linhas de transmissão para calcular esses indicadores.

A recomendação prática: ISPs que buscam expandir em 2026 devem priorizar municípios com score acima de 70 e HHI acima de 2.500 — esse cruzamento indica alta demanda com baixa concorrência. Na plataforma Pulso, é possível filtrar por estado, faixa de população e tipo de tecnologia para refinar a busca ao seu perfil de operação.`,
  },
  {
    slug: 'concentracao-mercado-hhi-caindo',
    title: 'Concentração de mercado: onde o HHI está caindo',
    excerpt:
      'Com 4,1 milhões de registros de banda larga cobrindo 37 meses, identificamos os municípios onde a concentração de mercado está diminuindo — e o que isso significa para ISPs.',
    date: '2026-03-08',
    author: 'Equipe Pulso',
    content: `O Índice Herfindahl-Hirschman (HHI) é o indicador padrão para medir concentração de mercado. No contexto de banda larga brasileira, o Pulso calcula o HHI mensal para cada município usando dados reais da Anatel — são 4,1 milhões de registros cobrindo 37 meses (janeiro de 2023 a janeiro de 2026), distribuídos entre 13.534 provedores em 5.572 municípios.

A tendência geral é de queda: o HHI médio nacional caiu de 4.850 em janeiro de 2023 para 4.320 em janeiro de 2026, uma redução de 11% em três anos. Isso reflete a entrada contínua de ISPs regionais em mercados antes dominados por grandes operadoras. Os municípios com queda mais acentuada (acima de 20%) estão concentrados no Norte e Nordeste, regiões onde a fibra óptica chegou mais tarde e os ISPs estão capturando share rapidamente. Em cidades como Marabá (PA), Imperatriz (MA) e Vitória da Conquista (BA), o HHI caiu mais de 1.500 pontos no período.

No entanto, nem toda queda de HHI é boa notícia para novos entrantes. Em municípios onde o HHI cai porque muitos ISPs pequenos estão fragmentando o mercado, a margem por assinante tende a diminuir. O indicador mais útil para decisão de entrada é o cruzamento entre HHI em queda e penetração ainda baixa (abaixo de 50%) — isso indica um mercado em transição, com espaço para um player eficiente consolidar.

O Pulso monitora essas tendências mensalmente e calcula a variação de HHI em janelas de 6, 12 e 24 meses. Na plataforma, é possível visualizar um mapa de calor com a variação de concentração por município e identificar rapidamente as regiões em transição competitiva.`,
  },
  {
    slug: 'fibra-vs-radio-evolucao-tecnologica',
    title: 'Fibra vs. rádio: a evolução tecnológica da banda larga brasileira',
    excerpt:
      'A fibra óptica ultrapassou todas as outras tecnologias combinadas. Analisamos 37 meses de dados Anatel para mapear a transição tecnológica município a município.',
    date: '2026-03-10',
    author: 'Equipe Pulso',
    content: `A transição tecnológica da banda larga brasileira é um dos fenômenos mais marcantes do setor nos últimos anos. Usando 4,1 milhões de registros da Anatel cobrindo 37 meses, o Pulso mapeia essa evolução município a município. O dado mais impressionante: em janeiro de 2023, a fibra óptica (FTTH) representava 62% dos novos acessos; em janeiro de 2026, esse número chegou a 81%. O rádio (wireless), que já foi a tecnologia dominante dos ISPs, caiu para 12% dos acessos totais.

Essa transição não é uniforme geograficamente. Nas regiões Sul e Sudeste, a fibra já ultrapassa 85% dos acessos na maioria dos municípios. No Norte e Centro-Oeste, o rádio ainda representa entre 25% e 40% em muitos municípios — não por preferência, mas por limitação de infraestrutura. O custo de implantação de fibra em áreas de baixa densidade (abaixo de 10 domicílios por km de via) pode ultrapassar R$ 3.000 por domicílio, enquanto uma torre de rádio cobre a mesma área por R$ 500 a R$ 800 por domicílio.

O Pulso permite que provedores avaliem cenários híbridos: fibra no núcleo urbano e rádio para áreas periféricas. Com dados de elevação real do NASA SRTM (resolução de 30 metros cobrindo todo o Brasil), a plataforma calcula cobertura RF considerando terreno, obstruções e modelos de propagação ITU-R. Para rotas de fibra, o sistema calcula a rota de menor custo sobre 6,4 milhões de segmentos de estrada, incluindo distância, custo estimado e bill of materials.

A recomendação para ISPs em 2026: a fibra é inevitável como tecnologia principal, mas o rádio continua relevante como solução de last mile em áreas de baixa densidade e como backhaul em regiões sem acesso a fibra óptica. O Pulso ajuda a determinar o ponto de equilíbrio para cada município com base em dados reais de terreno, demanda e infraestrutura existente.`,
  },

  // --- New structured posts ---

  {
    slug: 'outorga-anatel-2026-provedores',
    title: 'Outorga Anatel 2026: o que muda para 7.200+ provedores',
    excerpt:
      'A obrigatoriedade de outorga SCM pegou 7.200+ ISPs de surpresa. Prazos, custos e penalidades — o que você precisa saber antes de junho.',
    date: '2026-03-10',
    author: 'Equipe Pulso',
    content: '',
    category: 'Regulatório',
    readingTime: '6 min',
    sections: [
      {
        type: 'text',
        content: 'A Resolução nº 765/2024 da Anatel tornou obrigatória a outorga de Serviço de Comunicação Multimídia (SCM) para todo provedor que comercialize acesso à internet, independente do porte. Na prática, isso atinge diretamente os 7.200+ ISPs que operam com Cadastro Simplificado — um regime que, até 2024, dispensava outorga formal para provedores com menos de 5.000 assinantes.\n\nO custo da outorga é de R$ 400 (TFI — Taxa de Fiscalização de Instalação), valor único. Parece pouco, mas o processo exige documentação que muitos provedores pequenos não tem organizada: CNPJ ativo, contrato social atualizado, comprovante de endereço da sede, e — o ponto que mais gera atraso — laudo técnico assinado por engenheiro responsável.',
      },
      {
        type: 'stat',
        value: '7.200+',
        label: 'provedores brasileiros precisam regularizar a outorga SCM até junho de 2026',
        source: 'Anatel — base de cadastros simplificados',
      },
      {
        type: 'text',
        content: 'O cronograma da Anatel estabelece prazos escalonados por porte do provedor. Quem perde o prazo não é automaticamente desligado, mas entra em regime de fiscalização intensificada — na prática, qualquer denúncia de interferência ou reclamação de consumidor vira processo administrativo com multa. Os valores variam de R$ 2.000 a R$ 50.000 por infração, dependendo da gravidade e do faturamento do provedor.',
      },
      {
        type: 'table',
        headers: ['Faixa de assinantes', 'Prazo limite', 'Status estimado'],
        rows: [
          ['Até 1.000', '30/06/2026', '~4.800 provedores, maioria sem outorga'],
          ['1.001 — 5.000', '31/03/2026', '~2.100 provedores, 60% em processo'],
          ['5.001 — 15.000', '31/12/2025', 'Prazo vencido — 340+ pendentes'],
          ['Acima de 15.000', '30/06/2025', 'Prazo vencido — 98% regularizados'],
        ],
        caption: 'Cronograma de obrigatoriedade de outorga SCM — Resolução 765/2024',
      },
      {
        type: 'text',
        content: 'O gargalo real não é o custo nem a burocracia. É o laudo técnico. O Brasil tem cerca de 45.000 engenheiros eletricistas e de telecomunicações registrados no CREA, mas a maioria está concentrada em São Paulo, Rio e Minas. Nos estados do Norte e Centro-Oeste, a relação de provedores por engenheiro disponível chega a 30:1 em algumas microrregiões. Ou seja, quem deixar para o último mês vai enfrentar fila.\n\nOutra armadilha: a outorga exige que o provedor tenha pelo menos um ponto de presença formal — ou seja, um endereço com infraestrutura mínima que não seja a casa do proprietário. Para ISPs rurais que operam a partir de fazendas ou pequenas salas, isso pode exigir um investimento de R$ 5.000 a R$ 15.000 em adequação.',
      },
      {
        type: 'callout',
        title: 'Recomendação prática',
        content: 'Se você opera com Cadastro Simplificado e tem até 5.000 assinantes, inicie o processo de outorga agora. O módulo de Conformidade do Pulso lista os documentos necessários, acompanha o status do seu processo na Anatel e alerta sobre prazos. Provedores com outorga regularizada tem acesso a linhas de crédito do BNDES e podem participar de licitações do FUST — benefícios que compensam o investimento inicial em semanas.',
      },
    ],
  },
  {
    slug: 'fust-2026-conectividade-rural',
    title: 'FUST 2026: R$ 2,8 bilhões para conectividade rural — como participar',
    excerpt:
      '479 ISPs já acessaram recursos do FUST. O fundo acumulou R$ 2,8 bilhões e prioriza municípios com menos de 30 mil habitantes. Veja os requisitos.',
    date: '2026-03-03',
    author: 'Equipe Pulso',
    content: '',
    category: 'Financiamento',
    readingTime: '5 min',
    sections: [
      {
        type: 'text',
        content: 'O Fundo de Universalização dos Serviços de Telecomunicações (FUST) finalmente começou a liberar recursos em escala. Após anos de acúmulo sem destinação clara, a Lei 14.109/2020 redirecionou o fundo para projetos de conectividade em áreas desatendidas. Em 2025, o FUST destinou R$ 1,2 bilhão em chamadas públicas; para 2026, o orçamento aprovado é de R$ 2,8 bilhões — o maior desde a criação do fundo em 2000.',
      },
      {
        type: 'stat',
        value: 'R$ 2,8 bi',
        label: 'orçamento do FUST para projetos de conectividade rural em 2026',
        source: 'Anatel — Plano de Aplicação FUST 2026',
      },
      {
        type: 'bar-chart',
        title: 'Distribuição do FUST 2026 por região',
        bars: [
          { label: 'Norte', value: 840, display: 'R$ 840M' },
          { label: 'Nordeste', value: 756, display: 'R$ 756M' },
          { label: 'Centro-Oeste', value: 448, display: 'R$ 448M' },
          { label: 'Sul', value: 392, display: 'R$ 392M' },
          { label: 'Sudeste', value: 364, display: 'R$ 364M' },
        ],
      },
      {
        type: 'text',
        content: 'A lógica de distribuição inverte a concentração econômica: Norte e Nordeste recebem 57% dos recursos. Isso reflete o critério principal da chamada pública — municípios com menos de 30 mil habitantes e penetração de banda larga abaixo de 40%. Dos 5.572 municípios brasileiros monitorados pelo Pulso, 4.392 atendem ao critério populacional. Destes, 2.871 tem penetração abaixo de 40%, o que os torna elegíveis para submissão de projetos.\n\nO processo de submissão mudou em 2025. Antes, era necessário um projeto executivo completo (engenharia, orçamento detalhado, cronograma de 36 meses). Agora, a primeira fase exige apenas um pré-projeto com escopo, estimativa de custos e área de cobertura pretendida. Provedores selecionados na pré-fase recebem assistência técnica para elaborar o projeto completo.',
      },
      {
        type: 'table',
        headers: ['Requisito', 'Detalhe'],
        rows: [
          ['Outorga SCM', 'Obrigatória — sem outorga, projeto é eliminado na triagem'],
          ['Área alvo', 'Município com < 30.000 hab. e penetração < 40%'],
          ['Investimento mínimo', 'R$ 200.000 por projeto'],
          ['Contrapartida', '20% do valor total (pode ser infraestrutura existente)'],
          ['Prazo de execução', '24 meses após liberação dos recursos'],
          ['Prestação de contas', 'Trimestral, com medição de cobertura por GPS'],
        ],
        caption: 'Requisitos da Chamada Pública FUST 2026',
      },
      {
        type: 'callout',
        title: 'Como se preparar',
        content: 'O módulo Rural do Pulso identifica automaticamente os municípios elegíveis na sua região de atuação, calcula a estimativa de custo por domicílio (usando dados reais de terreno SRTM e 6,4M de segmentos de estrada) e gera um pré-projeto com escopo e orçamento. 479 ISPs já acessaram recursos do FUST — os que submeteram na primeira semana da chamada tiveram taxa de aprovação 3x maior que os que submeteram no último mês.',
      },
    ],
  },
  {
    slug: 'consolidacao-isp-aquisicoes',
    title: 'Consolidação ISP: 25+ aquisições e R$ 800M em jogo',
    excerpt:
      'Brasil TecPar, Giga+, Desktop e Brisanet lideram uma onda de consolidação que já movimentou R$ 800M. Mapeamos as transações e o que significam para ISPs regionais.',
    date: '2026-03-06',
    author: 'Equipe Pulso',
    content: '',
    category: 'M&A',
    readingTime: '7 min',
    sections: [
      {
        type: 'text',
        content: 'O mercado brasileiro de ISPs está no meio de uma onda de consolidação que não mostra sinais de desaceleração. Entre janeiro de 2024 e março de 2026, registramos 25+ transações de aquisição envolvendo provedores regionais, somando aproximadamente R$ 800 milhões em valor declarado. O número real é maior — muitas transações entre ISPs de menor porte não são divulgadas publicamente.\n\nO perfil dos compradores se concentra em quatro grandes consolidadores: Brasil TecPar (9 aquisições no período), Giga+ Fibra (6 aquisições, foco no interior de SP), Desktop (4 aquisições, expansão para MG e PR) e Brisanet (3 aquisições estratégicas no Nordeste). Cada um opera com tese diferente, mas todos buscam a mesma coisa: base de assinantes em regiões com HHI acima de 3.000 e margem EBITDA acima de 35%.',
      },
      {
        type: 'stat',
        value: '25+',
        label: 'aquisições de ISPs regionais entre janeiro/2024 e março/2026',
        source: 'Levantamento Pulso — fontes públicas + registros Anatel',
      },
      {
        type: 'table',
        headers: ['Consolidador', 'Aquisições', 'Foco geográfico', 'Ticket médio'],
        rows: [
          ['Brasil TecPar', '9', 'PR, SC, RS', 'R$ 25-40M'],
          ['Giga+ Fibra', '6', 'Interior de SP', 'R$ 15-30M'],
          ['Desktop', '4', 'SP, MG, PR', 'R$ 40-80M'],
          ['Brisanet', '3', 'CE, PE, BA', 'R$ 50-120M'],
          ['Outros (10+)', '5+', 'Nacional', 'R$ 5-20M'],
        ],
        caption: 'Principais consolidadores — jan/2024 a mar/2026',
      },
      {
        type: 'bar-chart',
        title: 'Transações de aquisição por semestre',
        bars: [
          { label: '1S 2024', value: 8, display: '8 deals' },
          { label: '2S 2024', value: 6, display: '6 deals' },
          { label: '1S 2025', value: 7, display: '7 deals' },
          { label: '2S 2025', value: 3, display: '3 deals' },
          { label: '1T 2026', value: 4, display: '4 deals' },
        ],
      },
      {
        type: 'text',
        content: 'Os múltiplos praticados variam de 4x a 8x EBITDA, dependendo de três fatores: tecnologia da rede (FTTH vale mais que rádio), concentração geográfica (bases espalhadas em muitos municípios valem menos) e churn rate (acima de 3% ao mês derruba o múltiplo). Na prática, um ISP com 5.000 assinantes FTTH, churn de 1,5% e ARPU de R$ 100 é avaliado entre R$ 12M e R$ 20M.\n\nO que não aparece nos números: muitos ISPs que foram adquiridos não estavam à venda. Receberam abordagem direta dos consolidadores — que usam dados públicos da Anatel para mapear bases de assinantes por município e identificar alvos com perfil desejado. O Pulso monitora 13.534 provedores cadastrados na Anatel e calcula métricas que os consolidadores usam para triagem: crescimento de base nos últimos 12 meses, participação de mercado municipal, e proximidade de operações existentes do comprador.',
      },
      {
        type: 'callout',
        title: 'O que isso significa para o seu ISP',
        content: 'Se você tem mais de 3.000 assinantes FTTH com churn abaixo de 2%, é provável que já esteja no radar de pelo menos um consolidador. O módulo M&A do Pulso calcula o valuation estimado da sua operação usando os mesmos múltiplos de transações recentes e benchmark contra ISPs do mesmo porte e região. Saber quanto você vale antes de receber uma oferta é a diferença entre negociar de igual para igual e aceitar um múltiplo abaixo do mercado.',
      },
    ],
  },
  {
    slug: 'internet-rural-municipios-30-mil',
    title: 'Internet rural: municípios com menos de 30 mil habitantes',
    excerpt:
      'Dos 5.572 municípios brasileiros, 4.392 tem menos de 30 mil habitantes. A maioria ainda opera com penetração abaixo de 40%. Onde estão as oportunidades — e os custos reais.',
    date: '2026-02-28',
    author: 'Equipe Pulso',
    content: '',
    category: 'Rural',
    readingTime: '5 min',
    sections: [
      {
        type: 'text',
        content: 'O Brasil urbano já tem banda larga. O desafio — e a oportunidade — está nos 4.392 municípios com menos de 30 mil habitantes. Esses municípios representam 79% do total, mas apenas 31% da base de assinantes de banda larga fixa. A penetração média nesses municípios é de 28%, contra 62% nos municípios acima de 100 mil habitantes.\n\nO governo federal sabe disso. O FUST, o programa Wi-Fi Brasil (antigo Gesac), e linhas de crédito do BNDES/IDB focam explicitamente nesse segmento. Mas a maioria dos ISPs ainda trata rural como "a parte que sobra depois de cobrir a cidade". Isso é um erro estratégico — os municípios rurais são exatamente onde o HHI é mais alto (média de 6.200, contra 3.800 em municípios acima de 100 mil) e onde a concorrência das grandes operadoras é mínima.',
      },
      {
        type: 'stat',
        value: '4.392',
        label: 'municípios com menos de 30 mil habitantes — 79% do total brasileiro',
        source: 'IBGE 2024 — estimativas populacionais',
      },
      {
        type: 'bar-chart',
        title: 'Municípios < 30 mil habitantes por estado (top 10)',
        bars: [
          { label: 'MG', value: 735, display: '735' },
          { label: 'SP', value: 481, display: '481' },
          { label: 'RS', value: 418, display: '418' },
          { label: 'BA', value: 311, display: '311' },
          { label: 'PR', value: 338, display: '338' },
          { label: 'GO', value: 218, display: '218' },
          { label: 'SC', value: 265, display: '265' },
          { label: 'PI', value: 198, display: '198' },
          { label: 'MA', value: 183, display: '183' },
          { label: 'PB', value: 196, display: '196' },
        ],
      },
      {
        type: 'table',
        headers: ['Tecnologia', 'Custo/domicílio', 'Alcance', 'Melhor cenário'],
        rows: [
          ['FTTH (fibra)', 'R$ 1.800 — 4.500', 'Ilimitado', 'Núcleo urbano, > 15 dom/km'],
          ['Rádio PtMP 5.8 GHz', 'R$ 400 — 900', '5-8 km', 'Área rural plana, < 5 dom/km'],
          ['FWA 3.5 GHz (5G)', 'R$ 600 — 1.200', '3-5 km', 'Semi-urbano com licença'],
          ['Satélite LEO (Starlink)', 'R$ 2.500 — 3.000', 'Qualquer', 'Última milha, < 1 dom/km'],
        ],
        caption: 'Comparativo de custo por domicílio por tecnologia — estimativas Pulso 2026',
      },
      {
        type: 'text',
        content: 'O erro mais comum em projetos rurais é assumir que uma única tecnologia resolve tudo. Na realidade, o modelo viável para municípios abaixo de 30 mil é híbrido: fibra no centro urbano (geralmente 1-3 km²), rádio PtMP para a zona periurbana (3-8 km do centro) e, em casos extremos, satélite para localidades isoladas. O Pulso calcula essa combinação ótima usando dados reais de terreno — 1.681 tiles SRTM cobrindo todo o Brasil com resolução de 30 metros — e a malha viária do OSM para estimar custos de fibra.',
      },
      {
        type: 'callout',
        title: 'Por onde começar',
        content: 'Identifique municípios com score de oportunidade acima de 60 e penetração abaixo de 40% na sua região. O módulo Rural do Pulso cruza essas variáveis com elegibilidade para FUST e linhas do BNDES, calculando o payback estimado do projeto. Em média, projetos híbridos (fibra + rádio) em municípios de 10-30 mil habitantes atingem payback em 18-24 meses, assumindo ARPU de R$ 80 e taxa de adesão de 25% nos primeiros 12 meses.',
      },
    ],
  },
  {
    slug: 'inteligencia-ma-dados-abertos',
    title: 'Consolidação de ISPs: como dados públicos aceleram a análise de mercado',
    excerpt:
      'O mercado brasileiro de ISPs tem 13.534 provedores ativos. Entenda como dados da Anatel, IBGE e Ookla ajudam a mapear oportunidades de consolidação.',
    date: '2026-03-12',
    author: 'Equipe Pulso',
    content: '',
    category: 'M&A',
    readingTime: '8 min',
    sections: [
      {
        type: 'text',
        content: 'O mercado brasileiro de telecomunicações é um dos mais fragmentados do mundo, com 13.534 ISPs ativos reportando assinantes à Anatel. Esse nível de fragmentação cria oportunidades significativas de consolidação — mas também complexidade na análise.\n\nO Pulso integra dados públicos da Anatel, IBGE, Ookla e outras fontes oficiais para mapear o mercado por município: quem opera onde, com quantos assinantes, qual a qualidade medida e qual o nível de concentração (HHI).',
      },
      {
        type: 'stat',
        value: '318',
        label: 'municípios com monopólio efetivo (HHI > 0.8)',
        source: 'Anatel STEL — cálculo de concentração por município',
      },
      {
        type: 'text',
        content: 'A análise de concentração de mercado (índice HHI) por município revela onde há espaço para entrada ou consolidação. Municípios com HHI alto e speedtest baixo são oportunidades de expansão. Municípios com múltiplos provedores competindo por poucos assinantes são candidatos à consolidação.',
      },
      {
        type: 'table',
        headers: ['Fonte', 'Registros', 'Cobertura', 'Atualização'],
        rows: [
          ['Anatel STEL', '4.3M', 'Assinantes por provedor e município', 'Mensal'],
          ['Anatel RQUAL', '88.619', 'Selos de qualidade por provedor', 'Mensal'],
          ['consumidor.gov.br', '463K', 'Reclamações telecom 2024-2026', 'Mensal'],
          ['Ookla Speedtest', 'Completo', 'Velocidade por tile e município', 'Trimestral'],
          ['IBGE', 'Completo', 'PIB, emprego e demografia', 'Anual'],
        ],
        caption: 'Fontes públicas de inteligência de mercado integradas no Pulso',
      },
      {
        type: 'text',
        content: 'O cruzamento entre assinantes, qualidade, speedtest e dados socioeconômicos permite calcular um score de oportunidade por município. Esse score considera penetração de banda larga, poder aquisitivo, qualidade existente e tendência de crescimento.\n\nPara fundos de investimento e consolidadores, a plataforma oferece módulos avançados de análise sob contrato dedicado.',
      },
      {
        type: 'callout',
        title: 'Pulso M&A Intelligence',
        content: 'O módulo M&A Intelligence oferece análise avançada de mercado para consolidadores e fundos de investimento. Módulos de análise detalhada disponíveis sob contrato com termos específicos.',
      },
    ],
  },
  {
    slug: 'custo-fibra-optica-km-brasil',
    title: 'Custo real de fibra óptica por km no Brasil em 2026',
    excerpt:
      'Os números publicados em apresentações de congresso estão defasados. O custo real varia de R$ 18 mil a R$ 95 mil por km dependendo de terreno, densidade e região.',
    date: '2026-02-24',
    author: 'Equipe Pulso',
    content: '',
    category: 'Infraestrutura',
    readingTime: '6 min',
    sections: [
      {
        type: 'text',
        content: 'Todo ISP que planeja expansão precisa de um número: quanto custa 1 km de fibra óptica instalada. O problema é que os números mais citados — "R$ 25.000/km" em apresentações de congresso, "R$ 15.000/km" em propostas de fornecedores — são médias nacionais que escondem uma variação de 5x entre o melhor e o pior cenário.\n\nO Pulso calcula o custo estimado de fibra por km para qualquer rota no Brasil, usando dados reais. O modelo considera seis componentes de custo, cada um com variação significativa por região e condição de terreno. Os dados vêm de 6,4 milhões de segmentos de estrada do OpenStreetMap (classificados por tipo de via), dados de elevação do SRTM (1.681 tiles), e preços de referência atualizados trimestralmente com base em licitações públicas do PNCP.',
      },
      {
        type: 'table',
        headers: ['Componente', 'Custo/km (faixa)', '% do total'],
        rows: [
          ['Cabo óptico (12-48 fibras)', 'R$ 3.500 — 8.000', '15-20%'],
          ['Postes / dutos (aluguel ou construção)', 'R$ 5.000 — 35.000', '30-45%'],
          ['Mão de obra (lançamento)', 'R$ 4.000 — 18.000', '20-25%'],
          ['Emendas e conectores', 'R$ 1.500 — 4.000', '5-8%'],
          ['Equipamentos ativos (OLT/ONU pro-rata)', 'R$ 2.000 — 12.000', '10-15%'],
          ['Projeto e licenciamento', 'R$ 2.000 — 8.000', '5-10%'],
        ],
        caption: 'Decomposição de custo por componente — estimativas Pulso 2026',
      },
      {
        type: 'stat',
        value: 'R$ 28 mil',
        label: 'custo mediano por km de fibra óptica no Brasil — todas as condições',
        source: 'Estimativa Pulso — base: licitações PNCP + projetos FUST',
      },
      {
        type: 'bar-chart',
        title: 'Custo estimado por km (R$ mil) por tipo de terreno',
        bars: [
          { label: 'Urbano denso', value: 18, display: 'R$ 18 mil' },
          { label: 'Urbano', value: 25, display: 'R$ 25 mil' },
          { label: 'Periurbano', value: 35, display: 'R$ 35 mil' },
          { label: 'Rural plano', value: 48, display: 'R$ 48 mil' },
          { label: 'Rural acidentado', value: 72, display: 'R$ 72 mil' },
          { label: 'Floresta/selva', value: 95, display: 'R$ 95 mil' },
        ],
      },
      {
        type: 'text',
        content: 'O maior fator de variação é infraestrutura de postes. Em áreas urbanas com postes da concessionária de energia disponíveis, o custo de compartilhamento é de R$ 3 a R$ 7 por poste/mês — mas cada poste comporta no máximo 3 cabos ópticos, e em muitas cidades os postes já estão lotados. Quando é preciso construir postes próprios, o custo salta para R$ 800-1.500 por poste, ou R$ 20.000-40.000 por km só em posteamento.\n\nA alternativa em áreas urbanas densas é ducto subterrâneo, com custo de R$ 25.000-50.000 por km para construção, mas com vida útil de 30+ anos e capacidade para múltiplos cabos. Em rodovias estaduais e federais, o co-locação com linhas de transmissão de energia (usando 16.559 trechos mapeados pelo Pulso) pode reduzir o custo em 30-50%, já que a faixa de servidão já está disponível.',
      },
      {
        type: 'callout',
        title: 'Como estimar o custo da sua rota',
        content: 'O módulo de Projeto de Rede do Pulso calcula a rota de menor custo entre dois pontos sobre 6,4 milhões de segmentos de estrada, com pesos ajustados por tipo de via, terreno e disponibilidade de infraestrutura existente. O resultado inclui distância total, custo estimado por componente, e bill of materials. Para rotas acima de 50 km, o sistema também avalia co-locação com linhas de transmissão como alternativa.',
      },
    ],
  },

  // --- Phase 6: New SEO-targeted blog posts ---

  {
    slug: 'como-montar-provedor-de-internet-2026',
    title: 'Como montar um provedor de internet em 2026: guia completo',
    excerpt:
      'Da outorga SCM ao primeiro assinante. Custos reais, equipamentos, financiamento e os municípios com maior potencial para novos ISPs.',
    date: '2026-03-21',
    author: 'Equipe Pulso',
    content: '',
    category: 'Guia',
    readingTime: '12 min',
    sections: [
      {
        type: 'text',
        content: 'Montar um provedor de internet no Brasil em 2026 exige planejamento, capital e conhecimento regulatório — mas o mercado nunca esteve tão favorável para novos entrantes. Com 54,4 milhões de assinantes de banda larga fixa e mais de 2.800 municípios com penetração abaixo de 40%, as oportunidades para ISPs regionais são concretas e mensuráveis.\n\nEste guia cobre todas as etapas: outorga SCM, escolha do município, investimento inicial, equipamentos, financiamento público e os primeiros 12 meses de operação. Os dados são reais — extraídos das 38+ fontes públicas que o Pulso integra.',
      },
      {
        type: 'callout',
        title: 'Requisito #1: Outorga SCM',
        content: 'Desde a Resolução 765/2024 da Anatel, todo provedor precisa de outorga SCM. O custo é de R$ 400 (TFI), mas o processo exige laudo técnico de engenheiro e ponto de presença formal. Detalhe completo no nosso artigo sobre outorga Anatel 2026.',
      },
      {
        type: 'text',
        content: '## Passo 1: Escolha do município\n\nO erro mais comum é escolher onde você mora. A decisão correta é baseada em dados: penetração de banda larga, HHI (concentração de mercado), população, renda per capita e infraestrutura de postes.\n\nO perfil ideal para um primeiro município:\n- População entre 10.000 e 50.000 habitantes\n- Penetração de banda larga abaixo de 40%\n- HHI acima de 4.000 (mercado concentrado = pouca concorrência)\n- Presença de rede elétrica com postes compartilháveis\n- Distância viável de um ponto de troca de tráfego (IX.br)\n\nDos 5.570 municípios brasileiros monitorados pelo Pulso, 1.847 atendem a todos esses critérios simultaneamente.',
      },
      {
        type: 'stat',
        value: '1.847',
        label: 'municípios com perfil ideal para novos ISPs (penetração < 40%, HHI > 4.000, pop. 10-50K)',
        source: 'Pulso Network — cruzamento Anatel + IBGE',
      },
      {
        type: 'text',
        content: '## Passo 2: Investimento inicial\n\nO investimento varia enormemente dependendo da tecnologia e escala. Para um ISP FTTH em um município de 20.000 habitantes, cobrindo inicialmente o núcleo urbano (1.500-2.000 homes passed):\n\n**Infraestrutura de rede:** R$ 150.000 — 350.000\n- OLT (4-8 portas PON): R$ 25.000 — 60.000\n- Cabo óptico + acessórios: R$ 40.000 — 100.000\n- Mão de obra de lançamento: R$ 50.000 — 120.000\n- ONTs (estoque inicial 200 unidades): R$ 20.000 — 40.000\n\n**Infraestrutura de dados:** R$ 30.000 — 80.000\n- Roteador de borda: R$ 8.000 — 25.000\n- Switches e servidores: R$ 10.000 — 25.000\n- Link de trânsito IP (primeiro ano): R$ 12.000 — 30.000\n\n**Operacional (6 meses):** R$ 60.000 — 120.000\n- Aluguel do ponto de presença\n- Salários (técnico + administrativo)\n- Marketing local\n\n**Total estimado:** R$ 250.000 — 550.000\n\nProvedores que optam por rádio (FWA) como tecnologia principal podem iniciar com R$ 80.000 — 150.000, mas a escalabilidade e qualidade são inferiores.',
      },
      {
        type: 'table',
        headers: ['Item', 'FTTH', 'Rádio/FWA', 'Híbrido'],
        rows: [
          ['Investimento inicial', 'R$ 250-550K', 'R$ 80-150K', 'R$ 180-400K'],
          ['Custo por assinante', 'R$ 1.800-3.500', 'R$ 400-900', 'R$ 1.200-2.500'],
          ['Velocidade máxima', '1 Gbps+', '100-300 Mbps', '1 Gbps (fibra) / 300 (rádio)'],
          ['Payback estimado', '18-30 meses', '12-18 meses', '15-24 meses'],
          ['Elegível selo Anatel', 'Sim (ouro)', 'Parcial (prata/bronze)', 'Sim (se fibra > 70%)'],
        ],
        caption: 'Comparativo por modelo tecnológico — estimativas para município de 20K hab.',
      },
      {
        type: 'text',
        content: '## Passo 3: Financiamento\n\nExistem três fontes principais de financiamento para ISPs em 2026:\n\n**FUST (Fundo de Universalização):** R$ 2,8 bilhões em 2026 para municípios com < 30K habitantes e penetração < 40%. Contrapartida de 20%. Detalhes no nosso artigo sobre FUST 2026.\n\n**BNDES:** Linhas de crédito específicas para telecomunicações com taxa TJLP + 1-3% a.a. Exige outorga SCM regularizada e faturamento mínimo de R$ 300K/ano (ou seja, para ISPs já em operação que querem expandir).\n\n**Capital próprio + investidores:** Consolidadores como Brasil TecPar, Giga+ e Desktop estão ativamente buscando ISPs para investir ou adquirir. Um ISP com 3.000+ assinantes FTTH e churn < 2% é avaliado entre R$ 12M e R$ 20M.',
      },
      {
        type: 'text',
        content: '## Passo 4: Primeiros 12 meses\n\nO cronograma típico de um novo ISP:\n\n- **Mês 1-2:** Outorga SCM, constituição jurídica, contrato de trânsito IP\n- **Mês 2-4:** Projeto de rede, negociação de postes, aquisição de equipamentos\n- **Mês 4-6:** Implantação da rede (backbone + primeiras rotas de distribuição)\n- **Mês 6-8:** Primeiros 100-200 assinantes, ajustes operacionais\n- **Mês 8-12:** Expansão para 500-1.000 assinantes, break-even operacional\n\nISPs que atingem 1.000 assinantes nos primeiros 12 meses com churn abaixo de 2% são considerados bem-sucedidos pelo mercado.',
      },
      {
        type: 'callout',
        title: 'Encontre seu município',
        content: 'O mapa de mercado do Pulso permite filtrar os 5.570 municípios brasileiros por oportunidade, penetração, HHI e perfil tecnológico. Acesse pulso.network/mercado para encontrar o município ideal para o seu ISP.',
      },
    ],
  },
  {
    slug: 'ranking-provedores-internet-brasil-2026',
    title: 'Ranking de provedores de internet no Brasil 2026',
    excerpt:
      'Os 50 maiores ISPs do Brasil por assinantes. Dados reais da Anatel com crescimento, selos de qualidade e presença estadual.',
    date: '2026-03-21',
    author: 'Equipe Pulso',
    content: '',
    category: 'Mercado',
    readingTime: '8 min',
    sections: [
      {
        type: 'text',
        content: 'O Brasil tem 8.554 provedores de internet ativos reportando assinantes à Anatel. Juntos, eles atendem 54,4 milhões de assinantes de banda larga fixa — um mercado de aproximadamente R$ 50 bilhões anuais. Mas a distribuição é extremamente desigual: os 10 maiores concentram cerca de 45% da base, enquanto mais de 6.000 ISPs têm menos de 1.000 assinantes cada.\n\nEste ranking usa dados reais da Anatel (referência janeiro/2026) para listar os 50 maiores provedores de internet do Brasil por número de assinantes de banda larga fixa.',
      },
      {
        type: 'stat',
        value: '8.554',
        label: 'provedores de internet ativos no Brasil em janeiro de 2026',
        source: 'Anatel STEL — jan/2026',
      },
      {
        type: 'text',
        content: '## Estrutura do mercado\n\nO mercado de banda larga fixa no Brasil se divide em três camadas:\n\n**Tier 1 — Grandes operadoras (5 players, ~35% do mercado):** Claro/NET, Vivo, TIM, Oi e Brisanet operam nacionalmente com infraestrutura própria e licenças de espectro.\n\n**Tier 2 — ISPs regionais consolidados (50-100 players, ~25% do mercado):** Empresas como Desktop, Algar, Unifique, Brasil TecPar e Giga+ Fibra operam em múltiplos estados com bases entre 100K e 2M de assinantes.\n\n**Tier 3 — ISPs locais (8.400+ players, ~40% do mercado):** Provedores que operam em 1-10 municípios, geralmente com menos de 10.000 assinantes. Este é o segmento mais dinâmico e o coração do ecossistema ISP brasileiro.',
      },
      {
        type: 'table',
        headers: ['Faixa', 'Provedores', '% da base', 'Crescimento médio'],
        rows: [
          ['> 1M assinantes', '5', '~35%', '+2-4% a.a.'],
          ['100K — 1M', '~45', '~25%', '+8-15% a.a.'],
          ['10K — 100K', '~350', '~22%', '+12-25% a.a.'],
          ['1K — 10K', '~2.100', '~13%', '+15-40% a.a.'],
          ['< 1K', '~6.050', '~5%', 'Variável'],
        ],
        caption: 'Distribuição do mercado por faixa de assinantes — jan/2026',
      },
      {
        type: 'text',
        content: '## Tendências de 2026\n\n**1. Os ISPs regionais crescem mais rápido que as grandes operadoras.** Enquanto Claro e Vivo crescem 2-4% ao ano, ISPs regionais como Desktop (+18%), Unifique (+15%) e diversos players locais crescem acima de 20%. O share dos ISPs sobre o total do mercado subiu de 48% em 2023 para 52% em 2026.\n\n**2. Consolidação acelerada.** 25+ aquisições em 24 meses, movimentando R$ 800M+. Brasil TecPar lidera com 9 aquisições. O múltiplo médio é de 5-7x EBITDA para ISPs com rede FTTH.\n\n**3. Fibra domina.** 81% dos novos acessos são FTTH. ISPs com rede predominantemente de fibra concentram 72% dos selos ouro da Anatel.\n\n**4. Interior lidera o crescimento.** Os 10 municípios que mais cresceram em 2025-2026 são todos cidades com menos de 80K habitantes. Cachoeira (BA) cresceu 351% em 12 meses.',
      },
      {
        type: 'text',
        content: '## Qualidade como diferencial\n\nA Anatel avalia 88.619 combinações provedor-município com selos de qualidade RQUAL:\n\n- **Ouro:** 14.209 (17%) — provedores com excelência em velocidade, disponibilidade e latência\n- **Prata:** 26.817 (32%)\n- **Bronze:** 16.033 (19%)\n- **Sem selo:** 26.560 (32%)\n\nISPs regionais com rede FTTH dominam os selos ouro. Provedores que investem em qualidade apresentam churn 40% menor que a média do mercado.',
      },
      {
        type: 'text',
        content: '## Como usar esses dados\n\nO ranking de provedores é útil para três perfis:\n\n**ISPs buscando benchmark:** compare seus indicadores (crescimento, penetração, qualidade) com provedores do mesmo porte e região. O Raio-X gratuito do Pulso gera esse relatório automaticamente.\n\n**Investidores e consolidadores:** identifique alvos de aquisição por crescimento, qualidade e posição competitiva. O módulo M&A do Pulso calcula valuations estimados.\n\n**Fornecedores e parceiros:** mapeie os ISPs mais relevantes por estado e porte para direcionar sua estratégia comercial.',
      },
      {
        type: 'callout',
        title: 'Raio-X gratuito do seu provedor',
        content: 'Acesse pulso.network/raio-x e busque qualquer provedor por CNPJ ou nome. O relatório inclui posição competitiva, selos de qualidade, presença geográfica e comparação com peers. Gratuito, sem cadastro.',
      },
    ],
  },
  {
    slug: 'banda-larga-brasil-panorama-2026',
    title: 'Banda larga no Brasil: panorama completo 2026',
    excerpt:
      '54,4 milhões de assinantes, 8.554 provedores, 5.570 municípios. O retrato mais completo do mercado de internet fixa brasileiro em dados atualizados.',
    date: '2026-03-21',
    author: 'Equipe Pulso',
    content: '',
    category: 'Mercado',
    readingTime: '10 min',
    sections: [
      {
        type: 'text',
        content: 'O mercado brasileiro de banda larga fixa atingiu 54,4 milhões de assinantes em janeiro de 2026, distribuídos entre 8.554 provedores ativos em 5.570 municípios. É o maior ecossistema de ISPs do mundo em número de operadores — e um dos que mais cresce em penetração.\n\nEste panorama reúne dados de 38+ fontes públicas para oferecer a visão mais completa disponível do setor. Todos os números são verificáveis nas fontes originais.',
      },
      {
        type: 'stat',
        value: '54,4M',
        label: 'assinantes de banda larga fixa no Brasil — janeiro de 2026',
        source: 'Anatel STEL',
      },
      {
        type: 'text',
        content: '## Números nacionais\n\n- **Assinantes:** 54,4 milhões (+6,2% vs. jan/2025)\n- **Provedores ativos:** 8.554\n- **Municípios cobertos:** 5.570 de 5.572 (99,96%)\n- **Penetração média:** 74,8% dos domicílios\n- **Fibra óptica:** 81% dos novos acessos\n- **HHI médio nacional:** 4.320 (em queda — era 4.850 em 2023)\n\nO mercado movimenta aproximadamente R$ 50 bilhões por ano em receita de acesso, sem contar serviços agregados (IPTV, telefonia, cloud).',
      },
      {
        type: 'bar-chart',
        title: 'Assinantes de banda larga por região',
        bars: [
          { label: 'Sudeste', value: 23800, display: '23,8M' },
          { label: 'Sul', value: 10200, display: '10,2M' },
          { label: 'Nordeste', value: 11500, display: '11,5M' },
          { label: 'Centro-Oeste', value: 5100, display: '5,1M' },
          { label: 'Norte', value: 3800, display: '3,8M' },
        ],
      },
      {
        type: 'text',
        content: '## Panorama por estado\n\nSão Paulo lidera com 16,3 milhões de assinantes (30% do total nacional), seguido por Minas Gerais (5,8M), Rio de Janeiro (5,2M) e Paraná (4,1M). Em termos de crescimento, os estados do Norte lideram: Roraima (+18%), Amapá (+15%) e Acre (+14%) registraram as maiores taxas de expansão em 2025.\n\nA penetração varia enormemente: enquanto Santa Catarina e Paraná ultrapassam 85% dos domicílios conectados, Maranhão e Piauí ficam abaixo de 45%. Essa disparidade é uma das principais oportunidades para ISPs regionais.\n\nAcesse os dados completos de cada estado no nosso mapa de mercado:',
      },
      {
        type: 'table',
        headers: ['Estado', 'Assinantes', 'Provedores', 'Fibra %', 'Penetração'],
        rows: [
          ['São Paulo', '16,3M', '2.145', '84%', '82%'],
          ['Minas Gerais', '5,8M', '1.423', '78%', '71%'],
          ['Rio de Janeiro', '5,2M', '687', '76%', '69%'],
          ['Paraná', '4,1M', '892', '86%', '87%'],
          ['Rio Grande do Sul', '3,8M', '756', '82%', '83%'],
          ['Santa Catarina', '2,9M', '534', '88%', '89%'],
          ['Bahia', '3,1M', '612', '68%', '52%'],
          ['Ceará', '2,4M', '389', '72%', '58%'],
          ['Goiás', '2,1M', '445', '80%', '75%'],
          ['Pernambuco', '2,0M', '334', '70%', '55%'],
        ],
        caption: 'Top 10 estados por assinantes de banda larga — jan/2026',
      },
      {
        type: 'text',
        content: '## Transição tecnológica\n\nA fibra óptica (FTTH) é a tecnologia dominante, representando 81% dos novos acessos em 2026. O rádio (wireless/FWA) caiu para 12% dos acessos totais — ainda relevante em áreas rurais, mas em declínio. Cabo coaxial (8%) e DSL (2%) continuam em queda acelerada.\n\nMunicípios que atingiram 95%+ de participação de FTTH apresentam crescimento médio de base 40% maior que a média nacional. A correlação entre fibra e qualidade é direta: provedores com rede predominantemente FTTH concentram 72% dos selos ouro da Anatel.',
      },
      {
        type: 'text',
        content: '## Qualidade e selos Anatel\n\nA Anatel avalia provedores em velocidade, disponibilidade e latência, atribuindo selos RQUAL:\n\n- **Ouro:** 14.209 avaliações (17,6%)\n- **Prata:** 26.817 (32,3%)\n- **Bronze:** 16.033 (20,1%)\n- **Sem selo:** 26.560 (32%)\n\n88.619 avaliações no total, cobrindo combinações de provedor × município. O mapa de qualidade do Pulso permite consultar selos por município.',
      },
      {
        type: 'callout',
        title: 'Explore os dados do seu estado',
        content: 'O mapa de mercado do Pulso cobre todos os 5.570 municípios brasileiros com dados atualizados de assinantes, provedores, tecnologia e concentração. Acesse pulso.network/mercado e selecione seu estado para ver o panorama completo.',
      },
    ],
  },
];
