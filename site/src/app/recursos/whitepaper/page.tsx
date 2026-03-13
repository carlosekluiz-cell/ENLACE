import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Whitepaper',
  description: 'Plataforma de inteligência decisional para telecomunicações no Brasil. Arquitetura de dados, pipelines, metodologia e modelo de negócio.',
  alternates: { canonical: 'https://pulso.network/recursos/whitepaper' },
};

const marketIndicators = [
  { indicator: 'Receita anual do setor de telecom', value: '~R$250 bilhões' },
  { indicator: 'ISPs registrados na Anatel', value: '13.534' },
  { indicator: 'Municípios brasileiros', value: '5.572' },
  { indicator: 'Assinantes de banda larga (na base)', value: '4.284.635 registros' },
  { indicator: 'Torres de estações base mapeadas', value: '37.325' },
  { indicator: 'Segmentos de rodovias', value: '6.457.585 (3,73M km)' },
];

const painPoints = [
  {
    title: 'Expansão às cegas',
    description: 'Decisões de CAPEX de R$1-5M baseadas em dados incompletos ou desatualizados. Um investimento mal direcionado pode comprometer a saúde financeira de um ISP regional por anos.',
  },
  {
    title: 'Complexidade regulatória',
    description: 'A transição SVA-para-SCM (Norma no. 4), exigências de qualidade RQual/IQS da Anatel, e prazos de licenciamento criam risco de multas de R$50K-500K para ISPs não preparados.',
  },
  {
    title: 'Consolidação acelerada',
    description: 'O mercado brasileiro de ISPs está em plena onda de M&A, com provedores maiores adquirindo regionais. Tanto compradores quanto vendedores operam sem ferramentas adequadas de avaliação.',
  },
  {
    title: 'Conectividade rural',
    description: '25+ milhões de brasileiros em áreas rurais ainda não têm acesso adequado à internet, representando uma oportunidade massiva — mas que exige planejamento técnico especializado.',
  },
  {
    title: 'Fragmentação de dados',
    description: 'Dados da Anatel, IBGE, INMET, CNES, INEP, PNCP, BNDES e dezenas de outras fontes existem em silos, formatos incompatíveis e com atualizações irregulares.',
  },
];

const pipelineGroups = [
  {
    name: 'Telecom',
    schedule: 'Diário 02:00 UTC',
    count: 4,
    pipelines: [
      { name: 'anatel_providers', records: '13.534', table: 'providers' },
      { name: 'anatel_broadband', records: '4.284.635', table: 'broadband_subscribers' },
      { name: 'anatel_base_stations', records: '37.325', table: 'base_stations' },
      { name: 'anatel_quality', records: '6.111.347', table: 'quality_indicators' },
    ],
    source: 'Anatel open data (CKAN/dados.gov.br)',
    format: 'CSV (semicolon-delimited, ISO-8859-1 → UTF-8)',
    normalization: 'Tecnologia mapeada (Fibra Óptica → fiber, Cabo Coaxial → cable, etc.)',
    validation: 'CNPJ unicidade, código IBGE foreign key match, scores dentro de limites físicos',
    postProcessing: 'Auto-refresh materialized view mv_market_summary + recompute opportunity_scores',
    detail: 'O pipeline de broadband é o mais crítico: 4,3M registros abrangendo 37 meses (2023-2026). A combinação year_month + provider + município cria a camada de inteligência de mercado que alimenta rankings de oportunidade, análise competitiva (HHI), e tendências de crescimento.',
  },
  {
    name: 'Intelligence',
    schedule: 'Diário 02:30 UTC',
    count: 3,
    pipelines: [
      { name: 'pncp_contracts', records: 'Variável', table: 'government_contracts' },
      { name: 'dou_anatel', records: 'Variável', table: 'regulatory_acts' },
      { name: 'querido_diario', records: 'Variável', table: 'gazette_mentions' },
    ],
    source: 'PNCP (REST JSON paginado), DOU, Querido Diário (Open Knowledge Brasil)',
    format: 'REST JSON (PNCP), scraping estruturado (DOU, Querido Diário)',
    normalization: 'Filtro por keywords telecom via regex autoritativo',
    validation: 'Município match, data de publicação, modalidade de contratação',
    postProcessing: 'Enriquecimento de growth_score (+10 para municípios com contratos gov. recentes)',
    detail: 'Três fontes complementares: PNCP para contratos governamentais, DOU para atos regulatórios da Anatel, e Querido Diário para menções em gazetas municipais — juntos fornecem visão 360° do ambiente regulatório-institucional.',
  },
  {
    name: 'Clima',
    schedule: 'Diário 03:00 UTC',
    count: 1,
    pipelines: [
      { name: 'inmet_weather', records: '61.061 obs / 671 estações', table: 'weather_observations' },
    ],
    source: 'Open-Meteo (dados originais INMET)',
    format: 'REST JSON',
    normalization: 'Coordenadas validadas, janela de 90 dias',
    validation: 'Limites físicos: temperatura −50 a +60°C, vento 0-100 m/s, precipitação ≥ 0',
    postProcessing: 'Alimenta modelagem de atenuação por chuva (ITU-R P.838) no motor RF',
    detail: 'Dados climáticos são essenciais para link budget realista — chuva intensa pode atenuar sinais wireless em até 10 dB em frequências acima de 10 GHz.',
  },
  {
    name: 'Econômico',
    schedule: 'Semanal (Domingos 04:00 UTC)',
    count: 7,
    pipelines: [
      { name: 'ibge_pib', records: 'Variável', table: 'municipal_gdp' },
      { name: 'ibge_projections', records: 'Variável', table: 'population_projections' },
      { name: 'ibge_pof', records: 'Variável', table: 'household_expenditure' },
      { name: 'anp_fuel', records: 'Variável', table: 'fuel_prices' },
      { name: 'aneel_power', records: '16.559', table: 'power_lines' },
      { name: 'snis_sanitation', records: 'Variável', table: 'sanitation_indicators' },
      { name: 'bndes_loans', records: 'Variável', table: 'bndes_loans' },
    ],
    source: 'IBGE (SIDRA), ANP, ANEEL/OSM, SNIS, BNDES Transparência',
    format: 'REST JSON (IBGE, ANP), CSV (ANEEL), HTML/JSON (SNIS, BNDES)',
    normalization: 'Código IBGE como chave, valores monetários em BRL, índices normalizados 0-100',
    validation: 'Código IBGE match, valores positivos, geometria válida (power_lines)',
    postProcessing: 'Power lines (16.559 segmentos, 256K km) alimentam análise de co-locação de fibra — potencial de redução de custo de 30-50%',
    detail: 'PIB, projeções populacionais e gastos familiares (POF) com telecomunicações compõem o perfil econômico municipal. BNDES revela financiamentos ativos no setor.',
  },
  {
    name: 'Geográfico',
    schedule: 'Mensal (dia 1, 05:00 UTC)',
    count: 12,
    pipelines: [
      { name: 'ibge_census', records: '5.570', table: 'ibge_population' },
      { name: 'srtm_terrain', records: '1.681 tiles / 40,6 GB', table: 'srtm_tiles' },
      { name: 'mapbiomas_landcover', records: 'Variável', table: 'land_cover' },
      { name: 'osm_roads', records: '6.457.585', table: 'road_segments' },
      { name: 'anatel_backhaul', records: 'Variável', table: 'backhaul_presence' },
      { name: 'datasus_health', records: 'Variável', table: 'health_facilities' },
      { name: 'inep_schools', records: 'Variável', table: 'schools' },
      { name: 'ibge_munic', records: 'Variável', table: 'municipal_planning' },
      { name: 'ibge_cnefe', records: 'Variável', table: 'building_density' },
      { name: 'caged_employment', records: 'Variável', table: 'employment_indicators' },
      { name: 'atlas_violencia', records: 'Variável', table: 'safety_indicators' },
      { name: 'sentinel_growth', records: '87+', table: 'sentinel_urban_indices' },
    ],
    source: 'IBGE, NASA/USGS, MapBiomas, OSM/Geofabrik, Anatel, DATASUS/CNES, INEP, CAGED, IPEA, ESA/Sentinel-2',
    format: 'GeoTIFF (SRTM), PBF/SHP (OSM), CSV/JSON, Cloud-Optimized GeoTIFF (Sentinel-2)',
    normalization: 'Coordenadas SRID 4326, SHA256 checksums (SRTM), highway_class enum (OSM)',
    validation: 'Coordenadas dentro do Brasil, checksum integridade, resolução 30m/10m',
    postProcessing: 'Instituições-âncora sem internet → demand_score e social_score. Backhaul ausente → +30 infrastructure_score',
    detail: 'Maior grupo. SRTM fornece terreno real (elevações verificadas: Manaus 36-86m, Curitiba 905-945m, Salvador 9-71m, SP 726-852m). OSM fornece 6,4M segmentos para roteamento de fibra. DATASUS e INEP identificam instituições sem conectividade.',
  },
  {
    name: 'Computados',
    schedule: 'Automático (pós-ingestão)',
    count: 5,
    pipelines: [
      { name: 'opportunity_scores', records: '5.570', table: 'opportunity_scores' },
      { name: 'competitive_analysis', records: '~5.570', table: 'competitive_analysis' },
      { name: 'market_summary_refresh', records: 'View', table: 'mv_market_summary' },
      { name: 'quality_derivation', records: '6.111.347', table: 'quality_indicators' },
      { name: 'station_attribution', records: '37.325', table: 'base_stations' },
    ],
    source: 'Algoritmos proprietários sobre dados de nível A1/A2/A3',
    format: 'SQL + Python (computação in-database)',
    normalization: 'Composite scores normalizados 0-100, HHI padronizado DOJ/FTC',
    validation: 'Scores 0-100, HHI ≥ 0, market shares somam 100% por município',
    postProcessing: 'REFRESH MATERIALIZED VIEW CONCURRENTLY para mv_market_summary',
    detail: 'Onde dados brutos se tornam inteligência acionável. O opportunity score combina 5 dimensões com 8 fatores de enriquecimento. O HHI usa thresholds DOJ/FTC (>2500 = alta concentração).',
  },
];

const enrichmentFactors = [
  { factor: 'Backhaul ausente', effect: 'infrastructure += 30', source: 'Anatel backhaul' },
  { factor: 'Escolas sem internet', effect: 'demand += (offline% × 0,2), social += (offline% × 0,3)', source: 'INEP Censo Escolar' },
  { factor: 'Saúde sem internet', effect: 'social += (offline% × 0,2)', source: 'DATASUS CNES' },
  { factor: 'Emprego positivo (net hires > 0)', effect: 'growth += 20', source: 'CAGED' },
  { factor: 'Qualidade incumbente baixa', effect: 'competition += 15', source: 'Anatel RQual/IQS' },
  { factor: 'Área segura', effect: 'social += (100 − risk) × 0,2', source: 'Atlas da Violência' },
  { factor: 'Densidade alta + demanda alta', effect: 'demand += 15', source: 'IBGE CNEFE' },
  { factor: 'Plano diretor + código de obras', effect: 'infrastructure += 10', source: 'IBGE MUNIC' },
];

const trustLevels = [
  {
    level: 'A1',
    name: 'Governamental',
    color: 'var(--success)',
    sources: 'Anatel, IBGE, INMET, DATASUS, INEP, PNCP, BNDES, CAGED, SNIS, ANP, IPEA/FBSP, DOU',
    criteria: 'Fonte governamental, metodologia pública, reporte obrigatório, auditável',
    tables: 25,
  },
  {
    level: 'A2',
    name: 'Científica',
    color: 'var(--accent)',
    sources: 'SRTM/NASA (30m), Sentinel-2/ESA (10m), MapBiomas (>85% acurácia)',
    criteria: 'Instituição científica, resolução conhecida, peer-reviewed, reproduzível',
    tables: 5,
  },
  {
    level: 'A3',
    name: 'Aberta',
    color: 'var(--accent)',
    sources: 'OpenStreetMap, Open-Meteo, PeeringDB, IX.br, OpenCelliD, Ookla, Microsoft Buildings',
    criteria: 'Comunidade ativa, validação cruzada, licença aberta, complemento Geofabrik',
    tables: 8,
  },
  {
    level: 'B1',
    name: 'Computada',
    color: 'var(--text-secondary)',
    sources: 'Opportunity scores, competitive analysis, base station attribution, quality derivation, Pulso Score, Credit Score ISP, Starlink threat index, weather risk, spatial analytics',
    criteria: 'Fórmula documentada, inputs de nível A, atualização automática pós-ingestão',
    tables: 8,
  },
];

const validationSteps = [
  { step: 'Contagem de registros', detail: 'Compara com última ingestão — alerta se variação > 20%' },
  { step: 'Integridade referencial', detail: 'Foreign keys verificadas (l2_id → admin_level_2, provider_id → providers)' },
  { step: 'Limites físicos', detail: 'Coordenadas dentro do Brasil, temperaturas −50 a +60°C, scores 0-100' },
  { step: 'Duplicatas', detail: 'UPSERT (ON CONFLICT DO UPDATE) — sem registros duplicados' },
  { step: 'Freshness', detail: 'Alertas se fonte não atualizar dentro do prazo (diário/semanal/mensal)' },
];

const rustModules = [
  { module: 'pulso-propagation', loc: '3.511', description: '8 modelos de propagação de rádio-frequência conforme padrões ITU-R' },
  { module: 'pulso-optimizer', loc: '1.786', description: 'Otimização de posicionamento de torres via simulated annealing' },
  { module: 'pulso-terrain', loc: '981', description: 'Processamento de terreno SRTM 30m com detecção de obstrução' },
  { module: 'pulso-raster', loc: '779', description: 'Geração de mapas de cobertura com 349K pontos de cálculo' },
  { module: 'pulso-service', loc: '600+', description: 'Servidor gRPC+TLS de alta performance (porta 50051)' },
  { module: 'pulso-tiles', loc: '347', description: 'Gerador de tiles XYZ para visualização de cobertura no mapa' },
];

const competitiveMatrix = [
  { capability: 'Inteligência de mercado por município', pulso: true, teleco: 'Parcial', anatel: 'Parcial', mckinsey: 'Sob demanda', ookla: false },
  { capability: 'Projeto RF com terreno real (30m)', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Conformidade regulatória automatizada', pulso: true, teleco: 'Parcial', anatel: false, mckinsey: 'Sob demanda', ookla: false },
  { capability: 'Avaliação M&A de ISPs (3 métodos)', pulso: true, teleco: false, anatel: false, mckinsey: 'Sob demanda', ookla: false },
  { capability: 'Monitoramento satelital (Sentinel-2)', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Planejamento rural com energia solar', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Roteamento de fibra com BOM completo', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Base integrada com 28M+ registros', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: '38 pipelines automatizados', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Motor de cálculo Rust (sub-segundo)', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Peering + IX.br analytics', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Score de crédito ISP + Pulso Score', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Análise de risco climático (ITU-R)', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Raio-X gratuito do provedor', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
  { capability: 'Inteligência de gazetas municipais', pulso: true, teleco: false, anatel: false, mckinsey: false, ookla: false },
];

const valuationMetrics = [
  { metric: 'Linhas de código (total)', value: '86.627' },
  { metric: 'Arquivos', value: '340+' },
  { metric: 'Esforço de desenvolvimento', value: '306 person-months' },
  { metric: 'Tamanho da equipe estimada', value: '14 profissionais' },
  { metric: 'Prazo de reprodução', value: '22-28 meses' },
  { metric: 'Custo de reprodução (Cost Approach)', value: 'R$16.400.000' },
  { metric: 'Valor justo (Fair Value)', value: 'R$16,4M' },
];

const tiers = [
  { name: 'Gratuito', price: 'R$0/mês', audience: 'ISPs exploradores', modules: 'Mapa, Raio-X do Provedor (resumo), dados de penetração' },
  { name: 'Starter', price: 'R$99/mês', audience: 'Análises pontuais', modules: '3 relatórios/mês, dados históricos, Diário Oficial, regulatório' },
  { name: 'Provedor', price: 'R$1.500/mês', audience: 'ISPs 1K-10K subs', modules: 'Market, Expansion, Competition, Compliance, Health, 10 relatórios/mês' },
  { name: 'Profissional', price: 'R$5.000/mês', audience: 'ISPs 10K-100K subs', modules: 'Todos os 24 módulos + API REST + 50 relatórios/mês' },
  { name: 'Empresa', price: 'Sob consulta', audience: 'Operadoras, fundos', modules: 'Tudo + API ilimitada, white-label, SLA dedicado, SSO/SAML' },
];

const revenueProjections = [
  { metric: 'Assinantes Starter', y1: '200', y2: '600', y3: '1500' },
  { metric: 'Assinantes Provedor', y1: '50', y2: '150', y3: '400' },
  { metric: 'Assinantes Profissional', y1: '10', y2: '40', y3: '100' },
  { metric: 'Contratos Empresa', y1: '2', y2: '5', y3: '10' },
  { metric: 'ARR (Receita Anual Recorrente)', y1: 'R$2,1M', y2: 'R$7,3M', y3: 'R$18,6M' },
];

function CellValue({ value }: { value: boolean | string }) {
  if (value === true) return <span style={{ color: 'var(--success)' }}>&#10003;</span>;
  if (value === false) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{value}</span>;
}

/* ── Styled infographic components ──────────────────────────── */

function FlowArrow() {
  return (
    <div className="flex items-center justify-center py-2 md:py-0 md:px-2" style={{ color: 'var(--accent)' }}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="hidden md:block">
        <path d="M5 12h14M13 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="md:hidden">
        <path d="M12 5v14M5 13l7 7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  );
}

function FlowStage({ label, sublabel, items, accent }: { label: string; sublabel: string; items: string[]; accent?: boolean }) {
  return (
    <div
      className="flex-1 p-5 min-w-0"
      style={{
        background: accent ? 'var(--accent-subtle)' : 'var(--bg-primary)',
        border: accent ? '2px solid var(--accent)' : '1px solid var(--border)',
      }}
    >
      <div className="font-mono text-lg font-bold mb-1" style={{ color: accent ? 'var(--accent)' : 'var(--text-primary)' }}>
        {label}
      </div>
      <div className="text-xs font-mono mb-3" style={{ color: 'var(--text-muted)' }}>{sublabel}</div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div key={item} className="text-xs leading-snug" style={{ color: 'var(--text-secondary)' }}>{item}</div>
        ))}
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function WhitepaperPage() {
  return (
    <>
      {/* 1. Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Whitepaper
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Plataforma de inteligência decisional.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Para telecomunicações no Brasil.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Versão 2.0 — Março 2026
          </p>
        </div>
      </Section>

      {/* 2. Sumário Executivo — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Sumário Executivo
        </div>
        <div className="max-w-3xl">
          <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            O Brasil abriga o quinto maior mercado de telecomunicações do mundo, com mais de 13.534 provedores de internet
            atendendo 5.572 municípios em um território de 8,5 milhões de km². A plataforma Pulso Network resolve
            a fragmentação de dados do setor com uma solução integrada: 38 pipelines automatizados ingerem dados de 30+ fontes
            governamentais e científicas, normalizam formatos incompatíveis, validam integridade referencial, e transformam
            28 milhões de registros brutos em inteligência acionável — rankings de oportunidade, análise competitiva,
            projetos RF com terreno real, avaliação de M&A, scores de crédito ISP, análise de peering, risco climático e inteligência regulatória.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
            {[
              { value: '28M+', label: 'Registros de produção' },
              { value: '30+', label: 'Fontes integradas' },
              { value: '38', label: 'Pipelines automatizados' },
              { value: '9.000+', label: 'LOC Rust (motor RF)' },
              { value: 'R$16,4M', label: 'Custo de reprodução' },
              { value: '0', label: 'Concorrentes equivalentes' },
            ].map((stat) => (
              <div
                key={stat.label}
                className="p-5"
                style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}
              >
                <div className="font-mono text-xl font-bold" style={{ color: 'var(--accent)' }}>{stat.value}</div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* 3. Oportunidade de Mercado — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Oportunidade de Mercado
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          O mercado brasileiro de telecomunicações
        </h2>

        <div className="overflow-x-auto mb-12" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Indicador</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {marketIndicators.map((row) => (
                <tr key={row.indicator} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.indicator}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--accent)' }}>{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="text-lg font-semibold mb-6" style={{ color: 'var(--text-primary)' }}>Dor do mercado</h3>
        <div className="max-w-3xl space-y-6">
          {painPoints.map((point, i) => (
            <div key={point.title} className="flex gap-4">
              <div className="shrink-0 font-mono text-sm font-bold mt-0.5" style={{ color: 'var(--accent)' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div>
                <h4 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{point.title}</h4>
                <p className="mt-1 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{point.description}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 4. Arquitetura de Dados — Surface (INFOGRAPHIC) */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Arquitetura de Dados
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          De dados brutos a decisões acionáveis
        </h2>
        <p className="text-sm leading-relaxed mb-10 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          A plataforma não agrega dados — ela transforma. Cada registro passa por ingestão, normalização, validação
          e enriquecimento antes de alimentar os 24 módulos que suportam decisões de investimento.
        </p>

        {/* Data flow infographic — 4 stages */}
        <div className="flex flex-col md:flex-row md:items-stretch gap-0 mb-10">
          <FlowStage
            label="30+ Fontes"
            sublabel="Dados brutos"
            items={[
              'Anatel (4 datasets)',
              'IBGE (7 datasets)',
              'NASA SRTM, ESA Sentinel-2',
              'PNCP, DOU, BNDES, INEP',
              'DATASUS, CAGED, OSM, INMET',
              'PeeringDB, IX.br, Ookla',
            ]}
          />
          <FlowArrow />
          <FlowStage
            label="38 Pipelines"
            sublabel="Extração → normalização → validação"
            items={[
              '4 Telecom — diário 02:00',
              '3 Intelligence — diário 02:30',
              '1 Clima — diário 03:00',
              '7 Econômico — semanal',
              '12 Geográfico — mensal',
              '5 Computados — automático',
            ]}
            accent
          />
          <FlowArrow />
          <FlowStage
            label="64+ Tabelas"
            sublabel="PostgreSQL + PostGIS"
            items={[
              '28M+ registros validados',
              'Materialized views',
              'Integridade referencial',
              'UPSERT (sem duplicatas)',
              'Freshness monitoring',
            ]}
          />
          <FlowArrow />
          <FlowStage
            label="24 Módulos"
            sublabel="Inteligência acionável"
            items={[
              'Market Intel + Expansion',
              'Competition + RF Design',
              'Compliance + M&A + Rural',
              'Peering + IXP + Weather Risk',
              'Starlink + FWA + Backhaul',
            ]}
            accent
          />
        </div>

        {/* Key metrics bar */}
        <div className="grid grid-cols-2 gap-0 md:grid-cols-5" style={{ border: '1px solid var(--border)' }}>
          {[
            { value: '30+', label: 'Fontes externas' },
            { value: '38', label: 'Pipelines' },
            { value: '64+', label: 'Tabelas' },
            { value: '28M+', label: 'Registros' },
            { value: '24', label: 'Módulos' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="p-4 text-center"
              style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}
            >
              <div className="font-mono text-lg font-bold" style={{ color: 'var(--accent)' }}>{stat.value}</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{stat.label}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* 5. Pipeline de Ingestão — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Pipeline de Ingestão
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          38 pipelines: como dados brutos se tornam inteligência
        </h2>
        <p className="text-sm leading-relaxed mb-10 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Cada pipeline segue o mesmo ciclo: extração da fonte → normalização de formato → validação de integridade →
          carga via UPSERT → pós-processamento (scores, views materializadas). Abaixo, a metodologia completa por grupo.
        </p>

        <div className="space-y-12">
          {pipelineGroups.map((group) => (
            <div key={group.name}>
              <div className="flex items-baseline gap-3 mb-4">
                <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {group.name}
                </h3>
                <span className="font-mono text-xs px-2 py-0.5" style={{ background: 'var(--bg-surface)', color: 'var(--accent)', border: '1px solid var(--border)' }}>
                  {group.count} {group.count === 1 ? 'pipeline' : 'pipelines'}
                </span>
                <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                  {group.schedule}
                </span>
              </div>

              <div className="overflow-x-auto mb-4" style={{ border: '1px solid var(--border)' }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                      <th className="px-4 py-2 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Pipeline</th>
                      <th className="px-4 py-2 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Registros</th>
                      <th className="px-4 py-2 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Tabela</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.pipelines.map((p) => (
                      <tr key={p.name} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--accent)' }}>{p.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{p.records}</td>
                        <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{p.table}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 mb-2">
                {[
                  { label: 'Fonte', value: group.source },
                  { label: 'Formato', value: group.format },
                  { label: 'Normalização', value: group.normalization },
                  { label: 'Validação', value: group.validation },
                ].map((item) => (
                  <div key={item.label} className="p-3 text-sm" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                    <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{item.label}:</span>{' '}
                    <span style={{ color: 'var(--text-secondary)' }}>{item.value}</span>
                  </div>
                ))}
              </div>
              <div className="p-3 text-sm" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>Pós-processamento:</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{group.postProcessing}</span>
              </div>
              <p className="mt-3 text-sm leading-relaxed max-w-3xl" style={{ color: 'var(--text-muted)' }}>
                {group.detail}
              </p>
            </div>
          ))}
        </div>

        {/* Opportunity Score Formula */}
        <div className="mt-14">
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Fórmula do Opportunity Score
          </h3>
          <p className="text-sm leading-relaxed mb-6 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
            Cada município recebe um score composto de 0-100, combinando 5 dimensões ponderadas. Os pesos
            refletem a importância relativa para a decisão de investimento de um ISP.
          </p>

          {/* Visual formula */}
          <div className="flex flex-wrap gap-2 mb-8">
            {[
              { label: 'Demanda', weight: '25%', color: 'var(--accent)' },
              { label: 'Competição', weight: '20%', color: 'var(--accent-hover)' },
              { label: 'Infraestrutura', weight: '20%', color: 'var(--accent)' },
              { label: 'Crescimento', weight: '15%', color: 'var(--accent-hover)' },
              { label: 'Social', weight: '20%', color: 'var(--accent)' },
            ].map((dim, i) => (
              <div key={dim.label} className="flex items-center gap-2">
                {i > 0 && <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>+</span>}
                <div
                  className="px-4 py-3 text-center"
                  style={{ background: 'var(--bg-surface)', border: '2px solid var(--border)' }}
                >
                  <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{dim.label}</div>
                  <div className="font-mono text-lg font-bold" style={{ color: dim.color }}>{dim.weight}</div>
                </div>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>=</span>
              <div
                className="px-4 py-3 text-center"
                style={{ background: 'var(--accent-subtle)', border: '2px solid var(--accent)' }}
              >
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Score</div>
                <div className="font-mono text-lg font-bold" style={{ color: 'var(--accent)' }}>0-100</div>
              </div>
            </div>
          </div>

          <h4 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            8 fatores de enriquecimento
          </h4>
          <p className="text-sm leading-relaxed mb-4 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
            Após o cálculo base, cada município é enriquecido com 8 fatores que ajustam os scores
            com base em dados concretos — escolas sem internet, presença de backhaul, segurança pública, etc.
          </p>
          <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                  <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Fator</th>
                  <th className="px-4 py-3 text-left font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Efeito no score</th>
                  <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Fonte</th>
                </tr>
              </thead>
              <tbody>
                {enrichmentFactors.map((row) => (
                  <tr key={row.factor} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.factor}</td>
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--accent)' }}>{row.effect}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>{row.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6 p-4 max-w-3xl" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Análise competitiva: HHI</h4>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Índice Herfindahl-Hirschman (HHI) é computado a partir de market shares reais dos assinantes de banda larga
              por município. Usamos os mesmos thresholds do DOJ/FTC americano:{' '}
              <span className="font-mono" style={{ color: 'var(--accent)' }}>{'<'}1500</span> competitivo,{' '}
              <span className="font-mono" style={{ color: 'var(--warning)' }}>1500-2500</span> moderado,{' '}
              <span className="font-mono" style={{ color: 'var(--danger)' }}>{'>'}2500</span> alta concentração,{' '}
              <span className="font-mono" style={{ color: 'var(--danger)' }}>{'>'}5000</span> monopólio de facto.
              Municípios com alta concentração representam oportunidades para novos entrantes.
            </p>
          </div>
        </div>
      </Section>

      {/* 6. Classificação de Confiança — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Classificação de Confiança
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          Proveniência rastreável para cada registro
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Investidores e ISPs precisam confiar nos dados que fundamentam decisões de milhões de reais.
          Cada tabela da plataforma carrega uma classificação de confiança baseada na origem e metodologia —
          para que o usuário saiba exatamente a confiabilidade de cada dado.
        </p>

        <div className="space-y-4 mb-10">
          {trustLevels.map((level) => (
            <div key={level.level} className="flex gap-4 p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="shrink-0">
                <span
                  className="inline-block font-mono text-base font-bold w-12 text-center py-1"
                  style={{ background: 'var(--bg-primary)', color: level.color, border: '2px solid var(--border)' }}
                >
                  {level.level}
                </span>
              </div>
              <div className="min-w-0">
                <div className="flex items-baseline gap-3 mb-2">
                  <span className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{level.name}</span>
                  <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{level.tables} tabelas</span>
                </div>
                <p className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>{level.sources}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{level.criteria}</p>
              </div>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Validação automatizada em 5 etapas
        </h3>
        <p className="text-sm leading-relaxed mb-6 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Cada execução de pipeline passa por 5 verificações automáticas antes que os dados entrem em produção.
          Falhas em qualquer etapa geram alertas e bloqueiam a ingestão.
        </p>
        <div className="max-w-3xl space-y-3">
          {validationSteps.map((step, i) => (
            <div key={step.step} className="flex gap-4 p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div
                className="shrink-0 w-8 h-8 flex items-center justify-center font-mono text-sm font-bold"
                style={{ background: 'var(--accent-subtle)', color: 'var(--accent)', border: '1px solid var(--border)' }}
              >
                {i + 1}
              </div>
              <div>
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{step.step}</span>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}> — {step.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 7. Fosso Tecnológico — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Fosso Tecnológico
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          Motor de cálculo RF em Rust — 9.000+ linhas de código
        </h2>
        <p className="text-base leading-relaxed mb-4 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          O componente mais sofisticado da plataforma é um motor de cálculo de radiofrequência escrito
          em Rust — uma linguagem compilada que oferece performance próxima a C++ com garantias de segurança de memória.
        </p>
        <p className="text-sm leading-relaxed mb-10 max-w-3xl" style={{ color: 'var(--text-muted)' }}>
          Por que isso importa: um ISP que planeja investir R$2M em uma nova torre precisa saber <em>antes</em> de
          investir se o sinal vai cobrir a área-alvo. Nosso motor calcula isso em segundos, usando terreno real
          do Brasil inteiro em resolução de 30 metros — o mesmo dado que a NASA usa.
        </p>

        <div className="overflow-x-auto mb-10" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Módulo</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>LOC</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>O que faz</th>
              </tr>
            </thead>
            <tbody>
              {rustModules.map((row) => (
                <tr key={row.module} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--accent)' }}>{row.module}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{row.loc}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>O que o motor resolve</h3>
        <p className="text-sm leading-relaxed mb-6 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Cada capacidade abaixo substitui semanas de trabalho manual de um engenheiro RF —
          ou centenas de milhares de reais em consultoria especializada.
        </p>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 max-w-5xl">
          {[
            {
              title: 'Simulação de cobertura RF',
              detail: '349K pontos de cálculo para raio de 10km em resolução de 30m. O ISP vê exatamente onde o sinal chega — e onde não chega — antes de investir.',
              metric: '349K grid points',
            },
            {
              title: '8 modelos de propagação ITU-R',
              detail: 'FSPL, Hata (urbano/suburbano), P.530 (fading), P.1812 (terreno), ITM (irregular terrain), TR38.901 (5G), P.676 (atmosférico), P.838 (chuva).',
              metric: '8 modelos',
            },
            {
              title: 'Terreno real verificado',
              detail: '1.681 tiles SRTM cobrindo todo o Brasil. Elevações validadas contra pontos conhecidos: Manaus 36-86m, Curitiba 905-945m, Salvador 9-71m, SP 726-852m.',
              metric: '40,6 GB terreno',
            },
            {
              title: 'Roteamento de fibra com BOM',
              detail: 'Algoritmo Dijkstra sobre 6,4M segmentos rodoviários (3,73M km). Retorna a rota ótima com bill of materials completo: metragem, tipo de cabo, emendas, caixas de passagem, custos.',
              metric: '6,4M segmentos',
            },
            {
              title: 'Otimização de posição de torres',
              detail: 'Simulated annealing encontra os posicionamentos que maximizam cobertura com menor CAPEX. Retorna coordenadas, altura, equipamento e estimativa de investimento.',
              metric: 'Annealing otimizado',
            },
            {
              title: 'Corredor de fibra com energia',
              detail: 'Co-locação de fibra óptica com 16.559 segmentos de linhas de energia (256K km). Usar postes existentes reduz custo de implantação em 30-50%.',
              metric: '30-50% economia',
            },
            {
              title: 'Design rural híbrido',
              detail: 'Combina backhaul (torre-a-torre), last mile (torre-a-cliente), dimensionamento de energia solar/rede, e custos específicos por bioma (Amazônia, Cerrado, Caatinga, etc.).',
              metric: '5 biomas',
            },
            {
              title: 'Link budget completo',
              detail: 'FSPL base + atenuação atmosférica (P.676) + atenuação por chuva (P.838) + margem de fading (P.530). Resultado: potência recebida em dBm e viabilidade do enlace.',
              metric: 'dBm → viabilidade',
            },
          ].map((item) => (
            <div key={item.title} className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
              <div className="flex items-baseline justify-between gap-3 mb-2">
                <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{item.title}</h4>
                <span className="shrink-0 font-mono text-xs px-2 py-0.5" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}>
                  {item.metric}
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{item.detail}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 8. Análise Competitiva — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Análise Competitiva
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          A única plataforma que cobre toda a cadeia de decisão
        </h2>
        <p className="text-sm leading-relaxed mb-4 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Hoje, um ISP que quer tomar uma decisão de investimento precisa contratar a McKinsey para análise de mercado
          (R$500K-2M por projeto), um consultor RF para projeto de rede, um escritório jurídico para compliance, e
          um banco de investimentos para M&A. Cada um entrega um relatório isolado, com dados diferentes, em prazos diferentes.
        </p>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-muted)' }}>
          O Pulso integra tudo isso em uma plataforma — com dados atualizados automaticamente, granularidade
          por município, e respostas em segundos em vez de semanas.
        </p>
        <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Capacidade</th>
                <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--accent)' }}>Pulso</th>
                <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Teleco</th>
                <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Anatel SFF</th>
                <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>McKinsey</th>
                <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Ookla</th>
              </tr>
            </thead>
            <tbody>
              {competitiveMatrix.map((row) => (
                <tr key={row.capability} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.capability}</td>
                  <td className="px-3 py-3 text-center"><CellValue value={row.pulso} /></td>
                  <td className="px-3 py-3 text-center"><CellValue value={row.teleco} /></td>
                  <td className="px-3 py-3 text-center"><CellValue value={row.anatel} /></td>
                  <td className="px-3 py-3 text-center"><CellValue value={row.mckinsey} /></td>
                  <td className="px-3 py-3 text-center"><CellValue value={row.ookla} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-6 text-sm leading-relaxed max-w-3xl" style={{ color: 'var(--text-muted)' }}>
          15 capacidades. 5 concorrentes analisados. Nenhum oferece mais que 3 das 15. O Pulso oferece as 15 — integradas,
          automatizadas, e atualizadas diariamente.
        </p>
      </Section>

      {/* 9. Avaliação de PI — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Avaliação de PI
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          R$16,4M para reproduzir
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Avaliação independente usando metodologia COCOMO II (padrão IVS 210 para software), considerando
          complexidade do código, domínio especializado (telecom + RF + geoespacial), e custo médio de engenheiros
          seniores no Brasil.
        </p>
        <div className="overflow-x-auto max-w-2xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <tbody>
              {valuationMetrics.map((row, i) => (
                <tr
                  key={row.metric}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: i >= valuationMetrics.length - 2 ? 'var(--bg-surface)' : undefined,
                  }}
                >
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {i >= valuationMetrics.length - 2 ? <strong style={{ color: 'var(--text-primary)' }}>{row.metric}</strong> : row.metric}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: i >= valuationMetrics.length - 2 ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {i >= valuationMetrics.length - 2 ? <strong>{row.value}</strong> : row.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* 10. Go-to-Market — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Estratégia Comercial
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          SaaS vertical com 5 tiers de precificação
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          O modelo SaaS vertical é o mais adequado para este mercado: os 13.534 ISPs brasileiros têm necessidades
          similares mas orçamentos diferentes. O tier gratuito funciona como funil de aquisição — o ISP experimenta
          o mapa de oportunidades e naturalmente evolui para módulos pagos quando identifica uma oportunidade concreta.
        </p>
        <div className="overflow-x-auto mb-12" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Tier</th>
                <th className="px-4 py-3 text-left font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Preço</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Público</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Módulos</th>
              </tr>
            </thead>
            <tbody>
              {tiers.map((tier) => (
                <tr key={tier.name} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{tier.name}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: 'var(--accent)' }}>{tier.price}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{tier.audience}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{tier.modules}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Projeção de receita (cenário base)</h3>
        <p className="text-sm leading-relaxed mb-6 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Considerando um TAM de 13.534 ISPs no Brasil, penetração de 0,4% no Ano 1 (50 assinantes Provedor) escalando
          para 3% no Ano 3. O ticket médio combina Provedor (R$1.500/mês) e Profissional (R$5.000/mês).
        </p>
        <div className="overflow-x-auto max-w-3xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Métrica</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Ano 1</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Ano 2</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Ano 3</th>
              </tr>
            </thead>
            <tbody>
              {revenueProjections.map((row, i) => (
                <tr
                  key={row.metric}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: i === revenueProjections.length - 1 ? 'var(--bg-surface)' : undefined,
                  }}
                >
                  <td className="px-4 py-3" style={{ color: i === revenueProjections.length - 1 ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {i === revenueProjections.length - 1 ? <strong>{row.metric}</strong> : row.metric}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--accent)' }}>{row.y1}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--accent)' }}>{row.y2}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--accent)' }}>{row.y3}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* 11. CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Pronto para avaliar a plataforma?{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Tier gratuito disponível.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/recursos" className="pulso-btn-ghost">
              Voltar a recursos
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
