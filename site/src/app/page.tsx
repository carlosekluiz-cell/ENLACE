import Hero from '@/components/sections/Hero';
import Section from '@/components/ui/Section';
import Link from 'next/link';
import {
  Map, BarChart3, Radio, Shield, CloudRain, TreePine, ArrowRight,
  Satellite, Building2, Brain, Layers, Wifi, Globe, Award, GitCompareArrows,
  Network, Zap, FileCheck, Scale, CreditCard, Share2, FileText, MapPin,
} from 'lucide-react';

const modules = [
  {
    icon: Map,
    title: 'Expansão',
    description: 'Identifique os municípios com maior potencial de retorno. Scoring proprietário com 15+ variáveis.',
    metric: '5.572 municípios',
  },
  {
    icon: BarChart3,
    title: 'Concorrência',
    description: 'HHI por município, market share por provedor, mapeamento de ERBs e tendências de mercado.',
    metric: '13.534 provedores',
  },
  {
    icon: Radio,
    title: 'Projeto RF',
    description: 'Link budget terrain-aware com dados de elevação reais. Perfil de terreno e conformidade EIRP.',
    metric: 'Resolução 30m',
  },
  {
    icon: Shield,
    title: 'Conformidade',
    description: 'Rastreamento de obrigações Anatel. Prazos, documentação e indicadores por faixa de assinantes.',
    metric: 'Alertas automáticos',
  },
  {
    icon: CloudRain,
    title: 'Saúde da Rede',
    description: 'Correlação climática, benchmarking vs peers e priorização de manutenção por impacto em receita.',
    metric: '671 estações',
  },
  {
    icon: TreePine,
    title: 'Rural',
    description: 'Elegibilidade para financiamento público, scoring de infraestrutura e áreas desatendidas.',
    metric: '2.700+ municípios',
  },
  {
    icon: Satellite,
    title: 'Satélite',
    description: 'Índices urbanos via Sentinel-2 da ESA. Análise de uso do solo, vegetação e expansão urbana.',
    metric: 'Sentinel-2 10m',
  },
  {
    icon: Building2,
    title: 'M&A',
    description: 'Valuation de ISPs, due diligence com dívidas PGFN, grafo societário e simulação de aquisições.',
    metric: '13.534 ISPs avaliados',
  },
  {
    icon: Brain,
    title: 'Inteligência',
    description: 'Análise preditiva de mercado, alertas de oportunidade e recomendações automatizadas.',
    metric: 'Machine learning',
  },
  {
    icon: Layers,
    title: 'Análise Espacial',
    description: 'Clustering DBSCAN, hotspot detection Getis-Ord e autocorrelação espacial sobre dados georreferenciados.',
    metric: 'Clustering + Hotspots',
  },
  {
    icon: Wifi,
    title: 'Índice Starlink',
    description: 'Score de vulnerabilidade por município e provedor frente à expansão da Starlink no Brasil.',
    metric: 'Threat scoring',
  },
  {
    icon: Radio,
    title: 'FWA vs Fibra',
    description: 'Calculadora de decisão tecnológica com comparação de TCO, ROI e análise por densidade demográfica.',
    metric: 'Decisão tecnológica',
  },
  {
    icon: Globe,
    title: 'Peering & IX.br',
    description: 'Inteligência de interconexão: 34K+ redes, 37 IXPs brasileiros, tráfego e políticas de peering.',
    metric: '34K+ redes',
  },
  {
    icon: Award,
    title: 'Pulso Score',
    description: 'Scoring de saúde do provedor: crescimento, qualidade, cobertura e indicadores financeiros.',
    metric: '13.534 provedores',
  },
  {
    icon: GitCompareArrows,
    title: 'Análise Cruzada',
    description: 'Correlações multi-dimensionais, detecção de anomalias e scoring de prioridade de investimento.',
    metric: '10 endpoints analíticos',
  },
  {
    icon: Network,
    title: 'Backhaul',
    description: 'Modelagem de capacidade, previsão de congestionamento e análise de utilização por município.',
    metric: 'Previsão mensal',
  },
  {
    icon: Zap,
    title: 'Velocidade',
    description: 'Rankings de download, upload e latência por município baseados em dados Ookla agregados.',
    metric: 'Speedtest tiles',
  },
  {
    icon: FileCheck,
    title: 'Obrigações 5G',
    description: 'Rastreamento de obrigações de cobertura 5G: prazos, populações atendidas e gap analysis por estado.',
    metric: 'CLARO, VIVO, TIM',
  },
  {
    icon: Scale,
    title: 'Espectro',
    description: 'Valuation de licenças de espectro, holdings por operadora e análise de faixas de frequência.',
    metric: 'Integrado ao M&A',
  },
  {
    icon: CreditCard,
    title: 'Crédito ISP',
    description: 'Credit scoring para provedores: probabilidade de default, rating AAA-CCC e 6 fatores de risco.',
    metric: 'Modelo PD',
  },
  {
    icon: Share2,
    title: 'Compartilhamento',
    description: 'Identificação de oportunidades de colocation em torres: scoring por densidade, gap e cobertura.',
    metric: 'Torre a torre',
  },
  {
    icon: FileText,
    title: 'Raio-X do Provedor',
    description: 'Relatório gratuito com posição competitiva, selos Anatel, dívidas fiscais, estrutura societária e diário oficial.',
    metric: 'Grátis + Premium',
  },
  {
    icon: MapPin,
    title: 'Hex Grid',
    description: 'Visualização hexagonal H3 com métricas de assinantes, penetração e market share por célula.',
    metric: 'Resolução 7-9',
  },
  {
    icon: Shield,
    title: 'Due Diligence',
    description: 'Dívidas fiscais federais (PGFN), sanções CEIS/CNEP, reclamações de consumidores e grafo de propriedade cruzada.',
    metric: '1M+ registros',
  },
];

const steps = [
  {
    number: '01',
    title: 'Integramos dados públicos',
    description: 'Anatel, IBGE, PGFN, Receita Federal, Portal da Transparência, BNDES, PeeringDB e mais. 38+ fontes normalizadas e cruzadas por código IBGE.',
  },
  {
    number: '02',
    title: 'Geramos inteligência',
    description: 'Scoring de oportunidade, análise competitiva, risco climático e conformidade regulatória.',
  },
  {
    number: '03',
    title: 'Você decide melhor',
    description: 'Mapa interativo, filtros inteligentes, exportação para diretoria e investidores.',
  },
];

export default function HomePage() {
  return (
    <>
      <Hero />

      {/* Value Prop — Light section */}
      <Section background="primary">
        <div className="text-center max-w-3xl mx-auto">
          <div
            className="mb-4 font-mono text-xs uppercase tracking-wider"
            style={{ color: 'var(--accent)' }}
          >
            Por que o Pulso
          </div>
          <h2
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}
          >
            O maior ecossistema ISP do mundo{' '}
            <span style={{ color: 'var(--text-muted)' }}>merece ferramentas à altura.</span>
          </h2>
          <p className="mt-5 text-base leading-relaxed mx-auto max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            28 milhões de data points. 38 fontes públicas. 128 mil provedores.
            A maior base de inteligência do setor ISP do mundo — concorrência, due diligence
            fiscal, grafo societário, reclamações — tudo cruzado automaticamente.
          </p>
        </div>

        {/* Stats */}
        <div className="mt-14 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ borderTop: '1px solid var(--border)' }}>
          {[
            { value: 'R$ 50 bi', label: 'Mercado anual' },
            { value: '8-12%', label: 'Crescimento/ano' },
            { value: '52%', label: 'Share dos ISPs' },
            { value: '3,2M km', label: 'Fibra implantada' },
          ].map((stat) => (
            <div key={stat.label} className="py-6 pr-6" style={{ borderBottom: '1px solid var(--border)' }}>
              <div
                className="font-mono text-xl font-bold tabular-nums md:text-2xl"
                style={{ color: 'var(--accent)' }}
              >
                {stat.value}
              </div>
              <div className="mt-1 text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
          Fontes: Anatel STEL dez/2024, Teleco, Abrint.
        </p>
      </Section>

      {/* How it works — Subtle light section */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Como funciona
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-2xl"
          style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}
        >
          Três etapas.{' '}
          <span style={{ color: 'var(--text-muted)' }}>Dados públicos → decisões melhores.</span>
        </h2>

        <div className="mt-14 grid grid-cols-1 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {steps.map((step) => (
            <div
              key={step.number}
              className="p-8"
              style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-surface)' }}
            >
              <div className="font-mono text-3xl font-bold" style={{ color: 'var(--accent)' }}>
                {step.number}
              </div>
              <h3 className="mt-3 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                {step.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Cross-Reference Intelligence — Surface section */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Cruzamento de dados
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-3xl"
          style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}
        >
          38 fontes cruzadas.{' '}
          <span style={{ color: 'var(--text-muted)' }}>Inteligência que não existe em nenhum outro lugar.</span>
        </h2>
        <p className="mt-4 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          Cada número abaixo é o resultado de cruzar duas ou mais bases de dados públicas.
          Nenhuma dessas conexões existe de forma pronta — o Pulso as constrói automaticamente.
        </p>

        <div className="mt-12 grid grid-cols-1 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {[
            {
              sources: 'PGFN × Base de Provedores',
              value: '10.740',
              unit: 'provedores com exposição fiscal',
              detail: 'R$ 582 bi em dívida ativa federal cruzada com 128K provedores licenciados pela Anatel.',
            },
            {
              sources: 'Receita Federal × Provedores',
              value: '777',
              unit: 'sócios controlam múltiplos ISPs',
              detail: '783K vínculos societários analisados. Maior grupo: 16 provedores sob um mesmo controlador.',
            },
            {
              sources: 'consumidor.gov.br × Telecom',
              value: '463K',
              unit: 'reclamações de consumidores',
              detail: 'Categorias, tempo de resposta (média 7,9 dias) e satisfação por operadora desde nov/2023.',
            },
            {
              sources: 'INEP × Anatel STEL',
              value: '16.375',
              unit: 'escolas offline em áreas com ISPs',
              detail: '1 milhão de alunos em escolas sem internet — em municípios onde já existem provedores ativos.',
            },
            {
              sources: 'Anatel RQUAL × Municípios',
              value: '88.619',
              unit: 'selos de qualidade mapeados',
              detail: 'Ouro (17,6%), Prata (32,3%), Bronze (20,1%) — qualidade por provedor e município.',
            },
            {
              sources: 'HHI × Assinantes × Demografia',
              value: '318',
              unit: 'municípios com monopólio efetivo',
              detail: 'Índice Herfindahl-Hirschman calculado para 5.570 municípios. 52,6% moderadamente concentrados.',
            },
            {
              sources: 'Diários Oficiais × Telecomunicações',
              value: '60.581',
              unit: 'menções em gazetas municipais',
              detail: '65 anos de registros (1961–2026). Infraestrutura, licitações e regulamentação local.',
            },
            {
              sources: 'BNDES × Setor Telecom',
              value: 'R$ 12,9 bi',
              unit: 'em financiamento mapeado',
              detail: '52 operações de crédito com taxas, prazos e valores. Histórico desde 2002.',
            },
            {
              sources: 'PGFN × CEIS/CNEP × Receita',
              value: '6 fontes',
              unit: 'de due diligence cruzadas',
              detail: 'Dívida fiscal, sanções federais, reclamações, sócios, espectro e compliance — em um dossier.',
            },
          ].map((item) => (
            <div
              key={item.sources}
              className="p-6"
              style={{
                background: 'var(--bg-primary)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="font-mono text-[10px] uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
                {item.sources}
              </div>
              <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {item.value}
              </div>
              <div className="mt-1 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {item.unit}
              </div>
              <p className="mt-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {item.detail}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Link href="/dados" className="pulso-btn inline-flex items-center gap-2">
            Ver todas as fontes <ArrowRight size={14} />
          </Link>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Todos os dados são públicos e verificáveis na origem.
          </span>
        </div>
      </Section>

      {/* Market data by state — internal linking for SEO */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Dados de mercado
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-3xl"
          style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}
        >
          Inteligência por estado.{' '}
          <span style={{ color: 'var(--text-muted)' }}>5.570 municípios cobertos.</span>
        </h2>
        <p className="mt-4 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          Market share, HHI, penetração de fibra e perfil competitivo para cada município brasileiro.
        </p>

        <div className="mt-10 grid grid-cols-3 gap-0 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-9" style={{ border: '1px solid var(--border)' }}>
          {[
            { uf: 'ac', label: 'AC' }, { uf: 'al', label: 'AL' }, { uf: 'am', label: 'AM' },
            { uf: 'ap', label: 'AP' }, { uf: 'ba', label: 'BA' }, { uf: 'ce', label: 'CE' },
            { uf: 'df', label: 'DF' }, { uf: 'es', label: 'ES' }, { uf: 'go', label: 'GO' },
            { uf: 'ma', label: 'MA' }, { uf: 'mg', label: 'MG' }, { uf: 'ms', label: 'MS' },
            { uf: 'mt', label: 'MT' }, { uf: 'pa', label: 'PA' }, { uf: 'pb', label: 'PB' },
            { uf: 'pe', label: 'PE' }, { uf: 'pi', label: 'PI' }, { uf: 'pr', label: 'PR' },
            { uf: 'rj', label: 'RJ' }, { uf: 'rn', label: 'RN' }, { uf: 'ro', label: 'RO' },
            { uf: 'rr', label: 'RR' }, { uf: 'rs', label: 'RS' }, { uf: 'sc', label: 'SC' },
            { uf: 'se', label: 'SE' }, { uf: 'sp', label: 'SP' }, { uf: 'to', label: 'TO' },
          ].map((s) => (
            <Link
              key={s.uf}
              href={`/mercado/${s.uf}`}
              className="flex items-center justify-center py-4 text-sm font-semibold transition-colors"
              style={{
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
                color: 'var(--text-primary)',
              }}
            >
              {s.label}
            </Link>
          ))}
        </div>

        <div className="mt-6">
          <Link href="/mercado" className="pulso-btn inline-flex items-center gap-2">
            Ver panorama nacional <ArrowRight size={14} />
          </Link>
        </div>
      </Section>

      {/* Modules — Dark section for contrast */}
      <Section background="dark" grain>
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
          Plataforma
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-2xl"
          style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
        >
          25 módulos integrados.{' '}
          <span style={{ color: 'var(--text-on-dark-muted)' }}>Uma base integrada.</span>
        </h2>

        <div className="mt-14 grid grid-cols-1 gap-px md:grid-cols-2 lg:grid-cols-3" style={{ border: '1px solid var(--border-dark-strong)' }}>
          {modules.map((mod) => {
            const Icon = mod.icon;
            return (
              <div
                key={mod.title}
                className="p-7"
                style={{
                  background: 'var(--bg-dark-surface)',
                  borderRight: '1px solid var(--border-dark)',
                  borderBottom: '1px solid var(--border-dark)',
                }}
              >
                <div className="flex items-start gap-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center"
                    style={{ border: '1px solid var(--border-dark-strong)', color: 'var(--accent-hover)' }}
                  >
                    <Icon size={18} />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold" style={{ color: 'var(--text-on-dark)' }}>
                      {mod.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-on-dark-secondary)' }}>
                      {mod.description}
                    </p>
                    <div className="mt-3 font-mono text-xs" style={{ color: 'var(--accent-hover)' }}>
                      {mod.metric}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-10">
          <Link href="/produto" className="pulso-btn-ghost inline-flex items-center gap-2">
            Ver detalhes de cada módulo <ArrowRight size={14} />
          </Link>
        </div>
      </Section>

      {/* Platform Preview — Light section with mockup */}
      <Section background="surface">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            A plataforma
          </div>
          <h2
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}
          >
            Mapa interativo com dados reais.{' '}
            <span style={{ color: 'var(--text-muted)' }}>Não simulação.</span>
          </h2>
        </div>

        {/* Browser mockup showing expansion module */}
        <div className="browser-frame mx-auto max-w-4xl">
          <div className="browser-chrome">
            <div className="browser-dot" />
            <div className="browser-dot" />
            <div className="browser-dot" />
            <div className="ml-3 flex-1">
              <div className="mx-auto max-w-[200px] h-5 rounded-full" style={{ background: '#e7e5e4', fontSize: '10px', lineHeight: '20px', textAlign: 'center', color: '#a8a29e' }}>
                app.pulso.network
              </div>
            </div>
          </div>
          <div className="relative" style={{ height: '320px', background: 'linear-gradient(135deg, #1c1917 0%, #292524 100%)' }}>
            {/* Table-like layout */}
            <div className="absolute inset-0 flex">
              {/* Data table area */}
              <div className="flex-1 p-4 overflow-hidden">
                <div className="mb-3 flex items-center gap-3">
                  <div className="h-7 px-3 flex items-center text-[10px]" style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--accent-hover)' }}>
                    Expansão
                  </div>
                  <div className="h-7 px-3 flex items-center text-[10px]" style={{ border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-on-dark-muted)' }}>
                    Top 50 municípios
                  </div>
                </div>
                {/* Table header */}
                <div className="flex gap-0 text-[9px] py-2 uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="w-[30%]">Município</div>
                  <div className="w-[15%] text-right">Score</div>
                  <div className="w-[15%] text-right">Pop.</div>
                  <div className="w-[15%] text-right">HHI</div>
                  <div className="w-[25%] text-right">Penetração</div>
                </div>
                {/* Table rows */}
                {[
                  { city: 'Ribeirão Preto, SP', score: '87', pop: '711K', hhi: '2.340', pen: '72.4%' },
                  { city: 'Uberlândia, MG', score: '84', pop: '699K', hhi: '1.890', pen: '68.1%' },
                  { city: 'Maringá, PR', score: '82', pop: '436K', hhi: '2.100', pen: '74.2%' },
                  { city: 'Campina Grande, PB', score: '79', pop: '411K', hhi: '3.450', pen: '45.8%' },
                  { city: 'Feira de Santana, BA', score: '77', pop: '619K', hhi: '4.120', pen: '38.6%' },
                  { city: 'Juiz de Fora, MG', score: '76', pop: '577K', hhi: '2.780', pen: '62.3%' },
                  { city: 'S. J. Rio Preto, SP', score: '75', pop: '464K', hhi: '2.550', pen: '69.7%' },
                ].map((row, i) => (
                  <div key={i} className="flex gap-0 text-[10px] py-2" style={{
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    color: i === 0 ? 'var(--text-on-dark)' : 'var(--text-on-dark-secondary)',
                    background: i === 0 ? 'rgba(99,102,241,0.05)' : 'transparent',
                  }}>
                    <div className="w-[30%] font-medium">{row.city}</div>
                    <div className="w-[15%] text-right font-mono font-semibold" style={{ color: 'var(--accent-hover)' }}>{row.score}</div>
                    <div className="w-[15%] text-right font-mono">{row.pop}</div>
                    <div className="w-[15%] text-right font-mono">{row.hhi}</div>
                    <div className="w-[25%] text-right font-mono">{row.pen}</div>
                  </div>
                ))}
              </div>
              {/* Side chart area */}
              <div className="w-[240px] hidden md:block p-4" style={{ borderLeft: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="text-[10px] font-semibold mb-3" style={{ color: 'var(--text-on-dark)' }}>Distribuição de Score</div>
                {/* Bar chart mockup */}
                <div className="space-y-2">
                  {[
                    { range: '80-100', pct: 85, count: '847' },
                    { range: '60-79', pct: 65, count: '1.923' },
                    { range: '40-59', pct: 45, count: '1.456' },
                    { range: '20-39', pct: 30, count: '892' },
                    { range: '0-19', pct: 15, count: '452' },
                  ].map((bar) => (
                    <div key={bar.range}>
                      <div className="flex justify-between text-[9px] mb-1">
                        <span style={{ color: 'var(--text-on-dark-muted)' }}>{bar.range}</span>
                        <span className="font-mono" style={{ color: 'var(--text-on-dark-muted)' }}>{bar.count}</span>
                      </div>
                      <div className="h-2 w-full" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <div className="h-full" style={{ width: `${bar.pct}%`, background: 'var(--accent)' }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
        <p className="mt-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
          Dados reais de municípios brasileiros. Interface da plataforma Pulso.
        </p>
      </Section>

      {/* CTA — Dark section */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Dados públicos existem.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>
              O que faltava era uma plataforma que os tornasse úteis.
            </span>
          </h2>
          <p className="mt-5 text-base leading-relaxed" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Estamos quase prontos. Entre na lista de espera para ser avisado no lançamento.
          </p>
          <div className="mt-8">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
