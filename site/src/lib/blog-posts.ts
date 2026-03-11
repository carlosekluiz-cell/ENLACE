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
    slug: 'top-50-municípios-oportunidade-isps-2026',
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
    slug: 'concentração-mercado-hhi-caindo',
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
    slug: 'fibra-vs-rádio-evolução-tecnologica',
    title: 'Fibra vs. rádio: a evolução tecnológica da banda larga brasileira',
    excerpt:
      'A fibra óptica ultrapassou todas as outras tecnologias combinadas. Analisamos 37 meses de dados Anatel para mapear a transição tecnológica município a município.',
    date: '2026-03-10',
    author: 'Equipe Pulso',
    content: `A transição tecnológica da banda larga brasileira é um dos fenômenos mais marcantes do setor nos últimos anos. Usando 4,1 milhões de registros da Anatel cobrindo 37 meses, o Pulso mapeia essa evolução município a município. O dado mais impressionante: em janeiro de 2023, a fibra óptica (FTTH) representava 62% dos novos acessos; em janeiro de 2026, esse número chegou a 81%. O rádio (wireless), que já foi a tecnologia dominante dos ISPs, caiu para 12% dos acessos totais.

Essa transição não é uniforme geograficamente. Nas regiões Sul e Sudeste, a fibra já ultrapassa 85% dos acessos na maioria dos municípios. No Norte e Centro-Oeste, o rádio ainda representa entre 25% e 40% em muitos municípios — não por preferência, mas por limitação de infraestrutura. O custo de implantação de fibra em áreas de baixa densidade (abaixo de 10 domicílios por km de via) pode ultrapassar R$ 3.000 por domicílio, enquanto uma torre de rádio cobre a mesma área por R$ 500 a R$ 800 por domicílio.

O Rust RF Engine do Pulso permite que provedores avaliem cenários híbridos: fibra no núcleo urbano e rádio para áreas periféricas. Com dados de elevação real do NASA SRTM (1.681 tiles cobrindo todo o Brasil, resolução de 30 metros), o motor calcula cobertura RF considerando terreno, obstruções e modelos de propagação ITU-R. Para rotas de fibra, o algoritmo Dijkstra opera sobre 6,4 milhões de segmentos de estrada, calculando distância, custo estimado e bill of materials.

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
        content: 'O módulo de Projeto RF do Pulso calcula a rota de menor custo entre dois pontos usando Dijkstra sobre 6,4 milhões de segmentos de estrada, com pesos ajustados por tipo de via, terreno (SRTM 30m) e disponibilidade de infraestrutura existente. O resultado inclui distância total, custo estimado por componente, e bill of materials. Para rotas acima de 50 km, o sistema também avalia co-locação com linhas de transmissão como alternativa.',
      },
    ],
  },
];
