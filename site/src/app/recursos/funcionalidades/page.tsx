import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Matriz de Funcionalidades',
  description: '24 módulos x 5 tiers: funcionalidades detalhadas por nível de assinatura.',
  alternates: { canonical: 'https://pulso.network/recursos/funcionalidades' },
};

const tierOverview = [
  { tier: 'Gratuito', price: 'R$0/mês', audience: 'Exploração', users: '1', contract: '-' },
  { tier: 'Starter', price: 'R$99/mês', audience: 'Análises pontuais', users: '1', contract: 'Mensal' },
  { tier: 'Provedor', price: 'R$1.500/mês', audience: 'ISPs 1K-10K subs', users: '5', contract: 'Mensal' },
  { tier: 'Profissional', price: 'R$5.000/mês', audience: 'ISPs 10K-100K subs', users: '20', contract: 'Anual' },
  { tier: 'Empresa', price: 'Sob consulta', audience: 'Operadoras, fundos', users: 'Ilimitado', contract: 'Anual' },
];

type Feature = { name: string; free: string; starter: string; provider: string; pro: string; enterprise: string };

const modules: { title: string; number: string; features: Feature[] }[] = [
  {
    title: 'Inteligência de Mercado',
    number: '01',
    features: [
      { name: 'Resumo de mercado por município', free: 'Somente leitura', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Histórico de assinantes', free: '3 meses', starter: '12 meses', provider: '37 meses', pro: '60 meses', enterprise: '60 meses' },
      { name: 'Análise de concorrentes (HHI, share)', free: 'Top 3', starter: 'Top 10', provider: 'Completo', pro: 'Completo', enterprise: 'Completo' },
      { name: 'Heatmap de penetração/fibra', free: 'Visual', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Selos de qualidade RQual/IQS', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tendências de crescimento', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Exportação de dados', free: '—', starter: '—', provider: 'CSV', pro: 'CSV, XLSX, PDF', enterprise: 'CSV, XLSX, PDF, API' },
    ],
  },
  {
    title: 'Expansão e Oportunidades',
    number: '02',
    features: [
      { name: 'Ranking de oportunidades', free: 'Top 10', starter: 'Top 10', provider: 'Top 100', pro: 'Todos (5.572)', enterprise: 'Todos + filtros' },
      { name: 'Score detalhado (5 dimensões)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Análise financeira (NPV, IRR, payback)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Rota de fibra (6,4M segmentos)', free: '—', starter: '—', provider: '1/mês', pro: '10/mês', enterprise: 'Ilimitado' },
      { name: 'Bill of Materials (BOM)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Estações base no mapa', free: 'Visual', starter: 'Visual', provider: '✓', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Concorrência',
    number: '03',
    features: [
      { name: 'Índice HHI de concentração', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Market share por provedor', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tendência (growing/stable/declining)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Nível de ameaça', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Provider breakdown + tecnologia', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Alertas de mudança de mercado', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Saúde da Rede',
    number: '04',
    features: [
      { name: 'Risco climático + previsão 7 dias', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Benchmark de qualidade vs. pares', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Comparação nacional/estadual', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Prioridades de manutenção', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Calendário sazonal (12 meses)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Detecção de outlier e risco de churn', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Conformidade Regulatória',
    number: '05',
    features: [
      { name: 'Dashboard de conformidade', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Impacto Norma no. 4 (ICMS)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Impacto multi-estado (blended ICMS)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Check de licenciamento (5K subs)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Qualidade vs. thresholds Anatel', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Calendário de deadlines', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Relatório de compliance (export)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Projeto RF',
    number: '06',
    features: [
      { name: 'Cobertura RF com SRTM 30m', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Modelos ITU-R (6 modelos)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'P.676 (atmosfera) + P.838 (chuva)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Otimização de posicionamento', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Link budget microwave', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Perfil de terreno', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'CAPEX por torre', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Corredor de co-locação', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Conectividade Rural',
    number: '07',
    features: [
      { name: 'Design híbrido (backhaul + last mile)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Sistema solar off-grid', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Matching de financiamento (FUST, BNDES)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Perfil de demanda comunitária', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Design de travessia de rio', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Custos por bioma', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Inteligência M&A',
    number: '08',
    features: [
      { name: 'Avaliação por múltiplo de assinante', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Avaliação por múltiplo de receita', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Avaliação DCF', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Descoberta de targets', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Score estratégico e financeiro', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Preparação para venda', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Overview M&A por estado', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Contratos governamentais por provedor', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Inteligência Satelital',
    number: '09',
    features: [
      { name: 'Índices anuais (NDVI, NDBI, MNDWI, BSI)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Crescimento urbano vs. população', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Ranking por crescimento', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Metadata de compositos Sentinel-2', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Computação on-demand (GEE)', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
      { name: 'Tiles de overlay satelital', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Raio-X do Provedor',
    number: '10',
    features: [
      { name: 'Posição competitiva por município', free: 'Resumo', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Selos Anatel (SCM, STFC, SeAC)', free: '✓', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Diário Oficial (DOU + Querido Diário)', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Contratos BNDES/FUST', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Espectro licenciado (holdings)', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Exportação PDF do relatório completo', free: '—', starter: 'R$49/avulso', provider: '✓', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Histórico de Assinantes',
    number: '11',
    features: [
      { name: 'Evolução mensal por provedor', free: '—', starter: '37 meses', provider: '37 meses', pro: '60 meses', enterprise: '60 meses' },
      { name: 'Evolução mensal por município', free: '—', starter: '37 meses', provider: '37 meses', pro: '60 meses', enterprise: '60 meses' },
      { name: 'Breakdown por tecnologia (fibra, coaxial, rádio)', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Comparação multi-provedor', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tendência e projeção de crescimento', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Velocidade (Ookla)',
    number: '12',
    features: [
      { name: 'Rankings de download/upload por município', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Latência e jitter por município', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Comparação fixa vs. móvel', free: '—', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tiles de speedtest (mapa de calor)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Evolução trimestral de velocidade', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Hex Grid (H3)',
    number: '13',
    features: [
      { name: 'Visualização hexagonal com métricas', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Métricas por célula (assinantes, penetração)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Resolução ajustável (H3 res 4-7)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Sobreposição com dados de cobertura', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Exportação GeoJSON de células', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Análise Espacial',
    number: '14',
    features: [
      { name: 'Clustering DBSCAN de municípios', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Hotspot Getis-Ord Gi*', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Autocorrelação espacial Moran\'s I', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Mapa de clusters e significância', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Exportação de resultados estatísticos', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Índice Starlink',
    number: '15',
    features: [
      { name: 'Score de vulnerabilidade por município', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Análise de ameaça competitiva', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Fatores de risco (renda, cobertura, rural)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Ranking de municípios mais vulneráveis', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Recomendações de defesa por provedor', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'FWA vs Fibra',
    number: '16',
    features: [
      { name: 'Calculadora TCO (5 anos)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Calculadora ROI comparativa', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Comparação lado a lado (CAPEX, OPEX)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Análise de break-even por cenário', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Recomendação por perfil de município', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Backhaul',
    number: '17',
    features: [
      { name: 'Modelagem de capacidade de backhaul', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Previsão de congestionamento', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Análise de utilização por enlace', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Planejamento de upgrade', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Simulação de crescimento de tráfego', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Risco Climático',
    number: '18',
    features: [
      { name: 'Correlação clima-rede por município', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Análise de sazonalidade (12 meses)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Risco climático por município (score)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Previsão meteorológica 7 dias', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Alertas de eventos extremos', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Peering & IX.br',
    number: '19',
    features: [
      { name: 'Diretório PeeringDB (34K+ redes)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Mapa de 37 IXPs brasileiros', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Tráfego agregado por IXP', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Histórico de tráfego (evolução)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Análise de participantes por IXP', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Recomendações de peering', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Obrigações 5G',
    number: '20',
    features: [
      { name: 'Rastreamento de cobertura obrigatória', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Prazos regulatórios por faixa', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Gap analysis (cobertura atual vs. meta)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Dashboard de compliance por operadora', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Alertas de deadline próximo', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Espectro',
    number: '21',
    features: [
      { name: 'Valuation de licenças de espectro', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Holdings por operadora e faixa', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Comparação de portfólio entre operadoras', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Histórico de leilões e preços por MHz', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Integração com M&A (valor do espectro)', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Pulso Score',
    number: '22',
    features: [
      { name: 'Score composto S/A/B/C/D (13.534 ISPs)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: '7 sub-scores (crescimento, cobertura, qualidade...)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Ranking nacional e estadual', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Evolução temporal do score', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Benchmark vs. pares regionais', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Crédito ISP',
    number: '23',
    features: [
      { name: 'Rating AAA a CCC por provedor', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Modelo de probabilidade de default (PD)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Score de risco financeiro', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Fatores de risco detalhados', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Comparação de risco entre provedores', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Análise Cruzada',
    number: '24',
    features: [
      { name: 'Competição (HHI, overlap, gaps)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Cobertura social (escolas, saúde)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Correlações (clima, emprego, renda)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Prioridade de investimento (composite)', free: '—', starter: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Detecção de anomalias (pyod)', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
];

const crossCutting: Feature[] = [
  { name: 'Acesso API REST', free: '—', starter: '—', provider: '—', pro: 'Rate limited', enterprise: 'Ilimitado' },
  { name: 'Relatórios PDF/CSV/XLSX', free: '—', starter: '3/mês', provider: '10/mês', pro: '50/mês', enterprise: 'Ilimitado' },
  { name: 'SSE (eventos em tempo real)', free: '—', starter: '—', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Busca geográfica e raio', free: '✓', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Boundaries GeoJSON por município', free: '✓', starter: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Usuários por conta', free: '1', starter: '1', provider: '5', pro: '20', enterprise: 'Ilimitado' },
  { name: 'Suporte', free: 'FAQ', starter: 'Email (48h)', provider: 'Email (48h)', pro: 'Email (24h) + Chat', enterprise: 'Dedicado + SLA' },
  { name: 'SLA de uptime', free: '—', starter: '—', provider: '99,0%', pro: '99,5%', enterprise: '99,9%' },
  { name: 'White-label', free: '—', starter: '—', provider: '—', pro: '—', enterprise: '✓' },
];

function CellContent({ value }: { value: string }) {
  if (value === '✓') return <span style={{ color: 'var(--success)' }}>&#10003;</span>;
  if (value === '—') return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span>{value}</span>;
}

function FeatureTable({ features }: { features: Feature[] }) {
  return (
    <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Funcionalidade</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Gratuito</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Starter</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Provedor</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--accent)' }}>Profissional</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Empresa</th>
          </tr>
        </thead>
        <tbody>
          {features.map((f) => (
            <tr key={f.name} style={{ borderBottom: '1px solid var(--border)' }}>
              <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{f.name}</td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.free} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.starter} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.provider} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.pro} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.enterprise} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FuncionalidadesPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Funcionalidades
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            24 módulos. 5 tiers.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Cada funcionalidade detalhada.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Todos os tiers acessam os mesmos 28M+ registros reais. A diferença está na profundidade
            de análise e nas ferramentas disponíveis.
          </p>
        </div>
      </Section>

      {/* Tier Overview — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Tiers
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Visão geral dos planos
        </h2>
        <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Tier</th>
                <th className="px-4 py-3 text-left font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Preço</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Público</th>
                <th className="px-4 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Usuários</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Contrato</th>
              </tr>
            </thead>
            <tbody>
              {tierOverview.map((t) => (
                <tr key={t.tier} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{t.tier}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: 'var(--accent)' }}>{t.price}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{t.audience}</td>
                  <td className="px-4 py-3 text-center font-mono" style={{ color: 'var(--text-primary)' }}>{t.users}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{t.contract}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Modules — alternating backgrounds */}
      {modules.map((mod, i) => (
        <Section key={mod.number} background={i % 2 === 0 ? 'subtle' : 'surface'}>
          <div className="flex items-baseline gap-3 mb-6">
            <span className="font-mono text-sm font-bold" style={{ color: 'var(--accent)' }}>{mod.number}</span>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>{mod.title}</h2>
          </div>
          <FeatureTable features={mod.features} />
        </Section>
      ))}

      {/* Cross-cutting — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Transversal
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Funcionalidades transversais
        </h2>
        <FeatureTable features={crossCutting} />
      </Section>

      {/* Notes — Subtle */}
      <Section background="subtle">
        <div className="max-w-3xl space-y-3">
          {[
            'Todos os tiers incluem autenticação JWT e dados atualizados pelos 38 pipelines.',
            'O tier Gratuito é projetado para demonstrar valor e converter para tiers pagos.',
            'Preços em BRL. Provedor: cobrança mensal. Profissional e Empresa: anual com desconto de 15%.',
            'API rate limits: Profissional = 100 req/min, Empresa = sem limite.',
            'Todos os tiers acessam os mesmos dados reais (28M+ registros).',
          ].map((note, i) => (
            <p key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <span className="font-mono shrink-0" style={{ color: 'var(--accent)' }}>{i + 1}.</span>
              {note}
            </p>
          ))}
        </div>
      </Section>

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Comece com o tier gratuito.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Upgrade quando quiser.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Ver preços
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
