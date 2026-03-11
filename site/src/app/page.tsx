import Hero from '@/components/sections/Hero';
import Section from '@/components/ui/Section';
import Link from 'next/link';
import {
  Map, BarChart3, Radio, Shield, CloudRain, TreePine, ArrowRight,
  Satellite, Building2, Brain, Layers, Wifi, Globe, Award, GitCompareArrows,
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
    description: 'Valuation de ISPs por município, simulação de aquisições e projeções financeiras.',
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
];

const steps = [
  {
    number: '01',
    title: 'Integramos dados públicos',
    description: 'Anatel, IBGE, NASA/SRTM, INMET, DataSUS, INEP e mais. 19+ fontes normalizadas e cruzadas por código IBGE.',
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
            13.534 provedores respondem por 52% da banda larga fixa brasileira — mais
            que Vivo, Claro e Oi juntas. Mercado de R$ 50 bi/ano crescendo 8-12% ao ano.
            A maioria ainda decide com planilhas e intuição.
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

      {/* Modules — Dark section for contrast */}
      <Section background="dark" grain>
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
          Plataforma
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-2xl"
          style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
        >
          15+ módulos integrados.{' '}
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
            Comece gratuitamente. Mapa interativo e dados básicos de penetração sem cartão de crédito.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/cadastro" className="pulso-btn-dark">
              Criar conta gratuita
            </Link>
            <Link href="/precos" className="pulso-btn-ghost">
              Ver planos
            </Link>
          </div>
          <p className="mt-5 font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
            Plano gratuito permanente. Sem cartão de crédito.
          </p>
        </div>
      </Section>
    </>
  );
}
