import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import Section from '@/components/ui/Section';
import {
  getNationalData,
  getStateData,
  formatSubscribers,
  formatNumber,
  getStateName,
} from '@/lib/market-data';

interface PageProps {
  params: { uf: string };
}

export function generateStaticParams() {
  const national = getNationalData();
  return national.states.map((s) => ({ uf: s.uf.toLowerCase() }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const state = getStateData(params.uf);
  if (!state) return {};

  // Enhanced meta description with growth %
  const ts = state.timeseries;
  let growthNote = '';
  if (ts.length >= 2) {
    const first = ts[0].subscribers;
    const last = ts[ts.length - 1].subscribers;
    const pct = first > 0 ? Math.round((last - first) / first * 100) : 0;
    if (pct > 0) growthNote = ` Crescimento de ${pct}% desde 2023.`;
  }

  return {
    title: `Internet em ${state.name} — ${state.municipalities} Municípios, ${formatSubscribers(state.subscribers)} Assinantes`,
    description: `Mercado de banda larga em ${state.name}: ${state.municipalities} municípios, ${state.fiber_pct}% fibra, HHI ${state.avg_hhi}.${growthNote} Dados Anatel + reclamações + emprego telecom.`,
    alternates: { canonical: `https://pulso.network/mercado/${params.uf}` },
  };
}

export default function StatePage({ params }: PageProps) {
  const state = getStateData(params.uf);
  if (!state) notFound();

  const top20 = state.cities.slice(0, 20);
  const coverageGaps = state.cities.filter((c) => c.isp_count <= 2);
  const monopolies = state.cities.filter((c) => c.isp_count <= 1);

  const totalQuality =
    state.quality.ouro + state.quality.prata + state.quality.bronze + state.quality.sem_selo || 1;

  // Timeseries chart data
  const ts = state.timeseries;
  const maxSubs = ts.length > 0 ? Math.max(...ts.map((t) => t.subscribers)) : 1;

  // Growth data
  let stateGrowthPct = 0;
  if (ts.length >= 2) {
    const first = ts[0].subscribers;
    const last = ts[ts.length - 1].subscribers;
    stateGrowthPct = first > 0 ? Math.round((last - first) / first * 100) : 0;
  }

  // Top 5 fastest growing cities (exclude 999.9 = new markets, require > 50 subs)
  const topGrowth = state.cities
    .filter((c) => c.growth_pct < 500 && c.growth_pct > 0 && c.subscribers >= 100)
    .sort((a, b) => b.growth_pct - a.growth_pct)
    .slice(0, 5);

  // Tech evolution
  const techBefore = state.tech_evolution?.before;
  const techAfter = state.tech_evolution?.after;

  // Complaints summary
  const complaints = state.complaints || [];
  const totalComplaints = complaints.reduce((s, c) => s + c.count, 0);
  const avgResponse = complaints.filter((c) => c.avg_response_days != null);
  const avgResponseDays = avgResponse.length > 0
    ? Math.round(avgResponse.reduce((s, c) => s + (c.avg_response_days || 0), 0) / avgResponse.length)
    : null;
  const avgSat = complaints.filter((c) => c.avg_satisfaction != null);
  const avgSatisfaction = avgSat.length > 0
    ? (avgSat.reduce((s, c) => s + (c.avg_satisfaction || 0), 0) / avgSat.length).toFixed(1)
    : null;

  // Employment
  const employment = state.employment || [];
  const latestEmployment = employment.length > 0 ? employment[employment.length - 1] : null;

  // Economy
  const economy = state.economy && 'year' in state.economy ? state.economy : null;

  // JSON-LD temporal coverage
  const temporalStart = ts.length > 0 ? ts[0].quarter.replace('-Q', '-0').replace('Q1', '01').replace('Q2', '04').replace('Q3', '07').replace('Q4', '10') : state.period;
  const temporalEnd = state.period;

  return (
    <>
      {/* JSON-LD: Breadcrumb + Dataset */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify([
            {
              '@context': 'https://schema.org',
              '@type': 'BreadcrumbList',
              itemListElement: [
                { '@type': 'ListItem', position: 1, name: 'Início', item: 'https://pulso.network' },
                { '@type': 'ListItem', position: 2, name: 'Mercado', item: 'https://pulso.network/mercado' },
                {
                  '@type': 'ListItem',
                  position: 3,
                  name: state.name,
                  item: `https://pulso.network/mercado/${params.uf}`,
                },
              ],
            },
            {
              '@context': 'https://schema.org',
              '@type': 'Dataset',
              name: `Mercado de banda larga — ${state.name}`,
              description: `Série histórica de banda larga fixa em ${state.name}: assinantes, provedores, tecnologias, concentração, reclamações e emprego telecom.`,
              url: `https://pulso.network/mercado/${params.uf}`,
              license: 'https://creativecommons.org/licenses/by/4.0/',
              creator: { '@type': 'Organization', name: 'Pulso Network' },
              temporalCoverage: `2023-01/${temporalEnd}`,
              spatialCoverage: { '@type': 'Place', name: `${state.name}, Brasil` },
            },
          ]),
        }}
      />

      {/* Hero */}
      <Section background="dark" grain hero>
        <nav className="mb-6 text-sm" style={{ color: 'var(--text-on-dark-muted)' }}>
          <Link href="/mercado" style={{ color: 'var(--accent-hover)', textDecoration: 'none' }}>
            Mercado
          </Link>
          {' / '}
          <span style={{ color: 'var(--text-on-dark-secondary)' }}>{state.name}</span>
        </nav>

        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            {state.uf} — {state.municipalities} municípios
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Internet em {state.name}
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Dados de banda larga para todos os {state.municipalities} municípios de {state.name}:
            assinantes, provedores, tecnologias e concentração de mercado.
          </p>
        </div>

        {/* Stats */}
        <div
          className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4"
          style={{ borderTop: '1px solid var(--border-dark-strong)' }}
        >
          {[
            { value: formatSubscribers(state.subscribers), label: 'Assinantes' },
            { value: `${state.municipalities}`, label: 'Municípios' },
            { value: `${state.avg_penetration}%`, label: 'Penetração média' },
            { value: `${state.avg_hhi}`, label: 'HHI médio' },
          ].map((stat) => (
            <div key={stat.label} className="py-5 pr-6">
              <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent-hover)' }}>
                {stat.value}
              </div>
              <div className="mt-1 text-xs uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)' }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Narrative — unique prose per state */}
      {state.insights?.narrative && (
        <Section background="primary">
          <div className="max-w-3xl">
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Visão geral
            </div>
            <h2 className="font-serif text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
              Mercado de banda larga em {state.name}
            </h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {state.insights.narrative}
            </p>
          </div>
        </Section>
      )}

      {/* Market Evolution — quarterly bar chart */}
      {ts.length > 2 && (
        <Section background="subtle">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Evolução
          </div>
          <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Crescimento trimestral
          </h2>
          <p className="mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Assinantes de banda larga fixa por trimestre em {state.name} ({ts[0].quarter} a {ts[ts.length - 1].quarter}).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Bar chart */}
            <div className="md:col-span-2">
              <div className="bar-chart">
                {ts.map((t) => (
                  <div
                    key={t.quarter}
                    className="bar"
                    style={{
                      height: `${(t.subscribers / maxSubs) * 100}%`,
                      background: 'var(--accent)',
                      minHeight: 4,
                    }}
                    title={`${t.quarter}: ${formatSubscribers(t.subscribers)} assinantes`}
                  />
                ))}
              </div>
              <div className="flex justify-between mt-2 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span>{ts[0].quarter}</span>
                <span>{ts[ts.length - 1].quarter}</span>
              </div>
            </div>

            {/* Fiber + ISP trend */}
            <div className="space-y-4">
              <div className="p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                  Fibra óptica
                </div>
                <div className="flex items-end gap-2">
                  <span className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                    {ts[ts.length - 1].fiber_pct}%
                  </span>
                  {ts.length >= 2 && (
                    <span
                      className="font-mono text-xs tabular-nums mb-1"
                      style={{ color: ts[ts.length - 1].fiber_pct >= ts[0].fiber_pct ? 'var(--success)' : 'var(--danger)' }}
                    >
                      {ts[ts.length - 1].fiber_pct >= ts[0].fiber_pct ? '+' : ''}
                      {(ts[ts.length - 1].fiber_pct - ts[0].fiber_pct).toFixed(1)}pp
                    </span>
                  )}
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  era {ts[0].fiber_pct}% em {ts[0].quarter}
                </div>
              </div>

              <div className="p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                  ISPs ativos
                </div>
                <div className="flex items-end gap-2">
                  <span className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {ts[ts.length - 1].isp_count.toLocaleString('pt-BR')}
                  </span>
                  {ts.length >= 2 && ts[ts.length - 1].isp_count !== ts[0].isp_count && (
                    <span
                      className="font-mono text-xs tabular-nums mb-1"
                      style={{ color: ts[ts.length - 1].isp_count >= ts[0].isp_count ? 'var(--success)' : 'var(--danger)' }}
                    >
                      {ts[ts.length - 1].isp_count >= ts[0].isp_count ? '+' : ''}
                      {ts[ts.length - 1].isp_count - ts[0].isp_count}
                    </span>
                  )}
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  era {ts[0].isp_count.toLocaleString('pt-BR')} em {ts[0].quarter}
                </div>
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* Technology + Quality + Tech Evolution */}
      <Section background="primary">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Technology breakdown with before/after */}
          <div>
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Tecnologia
            </div>
            <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
              Distribuição por tecnologia
            </h2>

            <div className="space-y-4">
              {[
                { label: 'Fibra (FTTH/FTTB)', pct: state.fiber_pct, color: 'var(--accent)' },
                { label: 'Rádio / FWA', pct: state.radio_pct, color: 'var(--warning, #f59e0b)' },
                { label: 'Cabo coaxial', pct: state.cable_pct, color: 'var(--info, #3b82f6)' },
                {
                  label: 'Outros (DSL, etc.)',
                  pct: Math.max(0, 100 - state.fiber_pct - state.radio_pct - state.cable_pct),
                  color: 'var(--text-muted)',
                },
              ].map((tech) => (
                <div key={tech.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span style={{ color: 'var(--text-primary)' }}>{tech.label}</span>
                    <span className="font-mono tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      {tech.pct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full" style={{ background: 'var(--border)' }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${Math.min(tech.pct, 100)}%`, background: tech.color }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Tech evolution comparison */}
            {techBefore && techAfter && (
              <div className="mt-6 space-y-3">
                <div className="font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Evolução tecnológica
                </div>
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>
                    {techBefore.period} (antes)
                  </div>
                  <div className="tech-compare-bar">
                    <div style={{ width: `${techBefore.fiber_pct}%`, background: 'var(--accent)' }} title={`Fibra ${techBefore.fiber_pct}%`} />
                    <div style={{ width: `${techBefore.radio_pct}%`, background: 'var(--warning, #f59e0b)' }} title={`Rádio ${techBefore.radio_pct}%`} />
                    <div style={{ width: `${techBefore.cable_pct}%`, background: 'var(--info, #3b82f6)' }} title={`Cabo ${techBefore.cable_pct}%`} />
                    <div style={{ width: `${techBefore.dsl_pct}%`, background: 'var(--text-muted)' }} title={`DSL ${techBefore.dsl_pct}%`} />
                  </div>
                </div>
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>
                    {techAfter.period} (atual)
                  </div>
                  <div className="tech-compare-bar">
                    <div style={{ width: `${techAfter.fiber_pct}%`, background: 'var(--accent)' }} title={`Fibra ${techAfter.fiber_pct}%`} />
                    <div style={{ width: `${techAfter.radio_pct}%`, background: 'var(--warning, #f59e0b)' }} title={`Rádio ${techAfter.radio_pct}%`} />
                    <div style={{ width: `${techAfter.cable_pct}%`, background: 'var(--info, #3b82f6)' }} title={`Cabo ${techAfter.cable_pct}%`} />
                    <div style={{ width: `${techAfter.dsl_pct}%`, background: 'var(--text-muted)' }} title={`DSL ${techAfter.dsl_pct}%`} />
                  </div>
                </div>
                <div className="flex gap-4 text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                  <span style={{ color: 'var(--accent)' }}>■ Fibra</span>
                  <span style={{ color: 'var(--warning, #f59e0b)' }}>■ Rádio</span>
                  <span style={{ color: 'var(--info, #3b82f6)' }}>■ Cabo</span>
                  <span>■ DSL</span>
                </div>
              </div>
            )}
          </div>

          {/* Quality seals */}
          <div>
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Qualidade Anatel
            </div>
            <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
              Selos de qualidade
            </h2>

            <div className="space-y-3">
              {[
                { label: 'Ouro', count: state.quality.ouro, color: '#eab308' },
                { label: 'Prata', count: state.quality.prata, color: '#94a3b8' },
                { label: 'Bronze', count: state.quality.bronze, color: '#d97706' },
                { label: 'Sem selo', count: state.quality.sem_selo, color: 'var(--text-muted)' },
              ].map((seal) => (
                <div
                  key={seal.label}
                  className="flex items-center justify-between p-3"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-full" style={{ background: seal.color }} />
                    <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                      {seal.label}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-sm font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                      {seal.count.toLocaleString('pt-BR')}
                    </span>
                    <span className="font-mono text-xs ml-2" style={{ color: 'var(--text-muted)' }}>
                      {((seal.count / totalQuality) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* Coverage insights */}
      {(monopolies.length > 0 || coverageGaps.length > 0) && (
        <Section background="subtle">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Cobertura
          </div>
          <h2 className="font-serif text-2xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Oportunidades de mercado
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {monopolies.length}
              </div>
              <div className="mt-1 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Municípios com monopólio
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Apenas 1 provedor com assinantes
              </div>
            </div>
            <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {coverageGaps.length}
              </div>
              <div className="mt-1 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Municípios com baixa concorrência
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                2 ou menos provedores atuando
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* Growth highlights — top 5 fastest-growing cities */}
      {topGrowth.length > 0 && (
        <Section background="surface">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Crescimento
          </div>
          <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Municípios que mais cresceram
          </h2>
          <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Variação de assinantes entre {ts.length > 0 ? ts[0].quarter : '2023'} e {state.period}.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {topGrowth.map((city, i) => (
              <Link
                key={city.code}
                href={`/mercado/${params.uf}/${city.slug}`}
                className="block p-4 transition-colors"
                style={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  textDecoration: 'none',
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="font-mono text-xs font-bold px-1.5 py-0.5"
                    style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}
                  >
                    #{i + 1}
                  </span>
                </div>
                <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                  {city.name}
                </div>
                <div className="mt-1 font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--success)' }}>
                  +{city.growth_pct}%
                </div>
                <div className="mt-1 font-mono text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  {formatSubscribers(city.subscribers)} assin.
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* Top municipalities table — with growth column */}
      <Section background={topGrowth.length > 0 ? 'primary' : 'surface'}>
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Maiores mercados
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Top {Math.min(20, state.cities.length)} municípios por assinantes
        </h2>
        <p className="mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Clique em um município para ver detalhes. Dados referência {state.period}.
        </p>

        <div style={{ border: '1px solid var(--border)', overflow: 'hidden' }}>
          {/* Header */}
          <div
            className="hidden md:grid font-mono text-[11px] uppercase tracking-wider"
            style={{
              gridTemplateColumns: '1fr 110px 80px 80px 80px 90px 80px',
              background: 'var(--bg-subtle)',
              color: 'var(--text-muted)',
              borderBottom: '1px solid var(--border)',
              padding: '10px 16px',
            }}
          >
            <span>Município</span>
            <span className="text-right">Assinantes</span>
            <span className="text-right">ISPs</span>
            <span className="text-right">Penetração</span>
            <span className="text-right">HHI</span>
            <span className="text-right">Fibra %</span>
            <span className="text-right">Cresc.</span>
          </div>

          {top20.map((city, i) => (
            <Link
              key={city.code}
              href={`/mercado/${params.uf}/${city.slug}`}
              className="block md:grid transition-colors"
              style={{
                gridTemplateColumns: '1fr 110px 80px 80px 80px 90px 80px',
                background: 'var(--bg-surface)',
                borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                padding: '12px 16px',
                textDecoration: 'none',
              }}
            >
              <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                {city.name}
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: 'var(--text-secondary)' }}
              >
                {formatSubscribers(city.subscribers)}
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: 'var(--text-secondary)' }}
              >
                {city.isp_count}
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: 'var(--text-secondary)' }}
              >
                {city.penetration}%
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: 'var(--text-secondary)' }}
              >
                {city.hhi}
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: 'var(--accent)' }}
              >
                {city.fiber_pct}%
              </span>
              <span
                className="block md:text-right font-mono text-sm tabular-nums"
                style={{ color: city.growth_pct > 0 ? 'var(--success)' : city.growth_pct < 0 ? 'var(--danger)' : 'var(--text-muted)' }}
              >
                {city.growth_pct > 0 ? '+' : ''}{city.growth_pct}%
              </span>
            </Link>
          ))}
        </div>

        {state.cities.length > 20 && (
          <p className="mt-4 text-sm" style={{ color: 'var(--text-muted)' }}>
            Mostrando os 20 maiores de {state.cities.length} municípios.{' '}
            <Link href="/precos" style={{ color: 'var(--accent)' }}>
              Acesse a plataforma
            </Link>{' '}
            para dados completos.
          </p>
        )}
      </Section>

      {/* Consumer satisfaction */}
      {totalComplaints > 0 && (
        <Section background="subtle">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Satisfação do consumidor
          </div>
          <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Reclamações em {state.name}
          </h2>
          <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Dados consolidados do consumidor.gov.br para provedores de internet no estado.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {totalComplaints.toLocaleString('pt-BR')}
              </div>
              <div className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                Reclamações registradas
              </div>
            </div>
            {avgResponseDays != null && (
              <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {avgResponseDays} dias
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Tempo médio de resposta
                </div>
              </div>
            )}
            {avgSatisfaction != null && (
              <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {avgSatisfaction}/5
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Satisfação média
                </div>
              </div>
            )}
          </div>

          {/* Quarterly complaints trend */}
          {complaints.length > 2 && (
            <div>
              <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
                Tendência trimestral
              </div>
              <div className="bar-chart" style={{ height: 80 }}>
                {complaints.map((c) => {
                  const maxC = Math.max(...complaints.map((x) => x.count));
                  return (
                    <div
                      key={c.quarter}
                      className="bar"
                      style={{
                        height: `${(c.count / maxC) * 100}%`,
                        background: 'var(--warning, #f59e0b)',
                        minHeight: 4,
                      }}
                      title={`${c.quarter}: ${c.count.toLocaleString('pt-BR')} reclamações`}
                    />
                  );
                })}
              </div>
              <div className="flex justify-between mt-2 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span>{complaints[0].quarter}</span>
                <span>{complaints[complaints.length - 1].quarter}</span>
              </div>
            </div>
          )}
        </Section>
      )}

      {/* Employment & Economy */}
      {(latestEmployment || economy) && (
        <Section background="surface">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Contexto econômico
          </div>
          <h2 className="font-serif text-2xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Emprego e economia em {state.name}
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {latestEmployment && latestEmployment.telecom_jobs > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                  {latestEmployment.telecom_jobs.toLocaleString('pt-BR')}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  Empregos formais em telecom
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: CAGED {latestEmployment.year}
                </div>
              </div>
            )}
            {latestEmployment?.avg_salary_brl != null && latestEmployment.avg_salary_brl > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  R$ {latestEmployment.avg_salary_brl.toLocaleString('pt-BR')}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  Salário médio telecom
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: CAGED {latestEmployment.year}
                </div>
              </div>
            )}
            {economy && economy.proxy_pib > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {formatNumber(economy.proxy_pib)}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  Volume econômico (proxy)
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: ANP {economy.year}
                </div>
              </div>
            )}
          </div>

          {/* Employment trend */}
          {employment.length > 1 && (
            <div className="mt-6">
              <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
                Tendência de emprego telecom
              </div>
              <div className="flex items-end gap-1" style={{ height: 60 }}>
                {employment.map((e) => {
                  const maxJobs = Math.max(...employment.map((x) => x.telecom_jobs));
                  return (
                    <div
                      key={e.year}
                      className="flex-1 rounded-t-sm"
                      style={{
                        height: `${(e.telecom_jobs / maxJobs) * 100}%`,
                        background: 'var(--accent)',
                        minHeight: 4,
                      }}
                      title={`${e.year}: ${e.telecom_jobs.toLocaleString('pt-BR')} empregos`}
                    />
                  );
                })}
              </div>
              <div className="flex justify-between mt-1 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span>{employment[0].year}</span>
                <span>{employment[employment.length - 1].year}</span>
              </div>
            </div>
          )}
        </Section>
      )}

      {/* All municipalities list */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Todos os municípios
        </div>
        <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
          {state.municipalities} municípios em {state.name}
        </h2>

        <div className="columns-2 md:columns-3 lg:columns-4 gap-4">
          {state.cities.map((city) => (
            <Link
              key={city.code}
              href={`/mercado/${params.uf}/${city.slug}`}
              className="block text-sm py-0.5 break-inside-avoid"
              style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}
            >
              {city.name}
            </Link>
          ))}
        </div>
      </Section>

      {/* CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>
            Acesse detalhes por provedor.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Dados que a Anatel não mostra assim.</span>
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Market share, due diligence, sócios, dívida ativa e mais — para cada provedor em {state.name}.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/raio-x" className="pulso-btn-ghost">
              Raio-X gratuito &rarr;
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
