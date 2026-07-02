import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import Section from '@/components/ui/Section';
import {
  getNationalData,
  getStateData,
  getMunicipalityData,
  formatSubscribers,
  formatNumber,
  getStateName,
} from '@/lib/market-data';

interface PageProps {
  params: { uf: string; slug: string };
}

export function generateStaticParams() {
  const national = getNationalData();
  const result: { uf: string; slug: string }[] = [];
  for (const st of national.states) {
    const state = getStateData(st.uf);
    if (state) {
      for (const city of state.cities) {
        result.push({ uf: st.uf.toLowerCase(), slug: city.slug });
      }
    }
  }
  return result;
}

export function generateMetadata({ params }: PageProps): Metadata {
  const data = getMunicipalityData(params.uf, params.slug);
  if (!data) return {};
  const { city, state } = data;
  const ouroCount = city.top_providers?.length || 0;
  const ouroNote = ouroCount > 0 ? ` ${ouroCount} provedores selo ouro.` : '';
  return {
    title: `Provedores de Internet em ${city.name}, ${state.uf.toUpperCase()} — Qualidade, Cobertura e Dados ${new Date().getFullYear()}`,
    description: `Compare ${city.isp_count} provedores de internet em ${city.name}/${state.uf.toUpperCase()}. Selos Anatel, ${city.fiber_pct}% fibra óptica, concentração de mercado e oportunidades. Dados atualizados.`,
    alternates: { canonical: `https://pulso.network/mercado/${params.uf}/${params.slug}` },
  };
}

const HHI_LABELS: Record<string, { label: string; color: string }> = {
  competitivo: { label: 'Competitivo', color: 'var(--success, #22c55e)' },
  moderado: { label: 'Moderadamente concentrado', color: 'var(--warning, #f59e0b)' },
  concentrado: { label: 'Altamente concentrado', color: 'var(--error, #ef4444)' },
};

const SEAL_COLORS: Record<string, string> = {
  ouro: '#eab308',
  prata: '#94a3b8',
  bronze: '#d97706',
};

export default function MunicipalityPage({ params }: PageProps) {
  const data = getMunicipalityData(params.uf, params.slug);
  if (!data) notFound();
  const { city, state } = data;

  const hhiInfo = HHI_LABELS[city.hhi_class] || HHI_LABELS.competitivo;

  // Find neighbors: same state, similar subscriber count, max 6
  const neighbors = state.cities
    .filter((c) => c.slug !== city.slug)
    .sort((a, b) => Math.abs(a.subscribers - city.subscribers) - Math.abs(b.subscribers - city.subscribers))
    .slice(0, 6);

  // Cross-state similar cities: 4 cities with similar subscribers from different states
  const national = getNationalData();
  const crossStateCities: { name: string; slug: string; uf: string; subscribers: number; isp_count: number; fiber_pct: number }[] = [];
  for (const st of national.states) {
    if (st.uf.toLowerCase() === params.uf.toLowerCase()) continue;
    const otherState = getStateData(st.uf);
    if (!otherState) continue;
    for (const c of otherState.cities) {
      if (c.subscribers > 0 && Math.abs(c.subscribers - city.subscribers) / Math.max(city.subscribers, 1) < 0.3) {
        crossStateCities.push({ name: c.name, slug: c.slug, uf: st.uf.toLowerCase(), subscribers: c.subscribers, isp_count: c.isp_count, fiber_pct: c.fiber_pct });
      }
    }
    if (crossStateCities.length >= 20) break;
  }
  crossStateCities.sort((a, b) => Math.abs(a.subscribers - city.subscribers) - Math.abs(b.subscribers - city.subscribers));
  const topCrossState = crossStateCities.slice(0, 4);

  const totalQuality = city.quality.ouro + city.quality.prata + city.quality.bronze + city.quality.sem_selo;

  const hasOpp = city.opportunity && 'level' in city.opportunity;
  const hasSchools = city.schools && 'total' in city.schools;
  const hasHealth = city.health && 'facilities' in city.health;
  const hasSanitation = city.sanitation && 'water_pct' in city.sanitation;
  const hasPlanning = city.planning && 'plano_diretor' in city.planning;
  const hasDensity = city.density && 'addresses' in city.density;
  const hasEconomy = city.economy && 'pib_per_capita' in city.economy;
  const hasEmployment = city.employment && 'telecom_jobs' in city.employment;
  const hasInfra = hasSchools || hasHealth || hasSanitation || hasPlanning || hasDensity;
  const hasHHITrend = city.hhi_trend && 'direction' in city.hhi_trend;

  // Build FAQ items dynamically
  const faqItems: { question: string; answer: string }[] = [
    {
      question: `Quantos provedores de internet existem em ${city.name}?`,
      answer: `${city.isp_count} provedores de internet atuam em ${city.name}, ${state.name}, atendendo ${formatSubscribers(city.subscribers)} assinantes de banda larga fixa.`,
    },
  ];

  if (city.quality.ouro > 0) {
    faqItems.push({
      question: `Qual a melhor internet em ${city.name}?`,
      answer: `Segundo dados da Anatel, ${city.quality.ouro} provedores em ${city.name} possuem selo ouro de qualidade RQUAL.`,
    });
  }

  faqItems.push(
    {
      question: `O mercado de internet em ${city.name} é competitivo?`,
      answer: `O índice HHI de ${city.hhi} indica mercado ${hhiInfo.label.toLowerCase()} em ${city.name}. ${city.isp_count} provedores disputam ${formatSubscribers(city.subscribers)} assinantes.`,
    },
    {
      question: `Qual o percentual de fibra óptica em ${city.name}?`,
      answer: `${city.fiber_pct}% dos acessos de banda larga em ${city.name} são via fibra óptica (FTTH).`,
    },
  );

  if (hasSchools && city.schools.no_internet > 0) {
    faqItems.push({
      question: `Quantas escolas em ${city.name} não têm internet?`,
      answer: `${city.schools.no_internet} escolas em ${city.name} não possuem acesso à internet, segundo dados do INEP.`,
    });
  }

  return (
    <>
      {/* JSON-LD */}
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
                {
                  '@type': 'ListItem',
                  position: 4,
                  name: city.name,
                  item: `https://pulso.network/mercado/${params.uf}/${params.slug}`,
                },
              ],
            },
            {
              '@context': 'https://schema.org',
              '@type': 'Dataset',
              name: `Dados de banda larga — ${city.name}, ${state.uf}`,
              description: `Indicadores de banda larga fixa para ${city.name}, ${state.name}: assinantes, provedores, tecnologias, concentração de mercado e selos de qualidade.`,
              url: `https://pulso.network/mercado/${params.uf}/${params.slug}`,
              license: 'https://creativecommons.org/licenses/by/4.0/',
              creator: { '@type': 'Organization', name: 'Pulso Network' },
              temporalCoverage: state.period,
              spatialCoverage: { '@type': 'Place', name: `${city.name}, ${state.name}, Brasil` },
            },
            {
              '@context': 'https://schema.org',
              '@type': 'FAQPage',
              mainEntity: faqItems.map((faq) => ({
                '@type': 'Question',
                name: faq.question,
                acceptedAnswer: {
                  '@type': 'Answer',
                  text: faq.answer,
                },
              })),
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
          <Link
            href={`/mercado/${params.uf}`}
            style={{ color: 'var(--accent-hover)', textDecoration: 'none' }}
          >
            {state.name}
          </Link>
          {' / '}
          <span style={{ color: 'var(--text-on-dark-secondary)' }}>{city.name}</span>
        </nav>

        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            {state.uf} — IBGE {city.code}
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Provedores de Internet em {city.name}
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            {city.isp_count} provedor{city.isp_count !== 1 ? 'es' : ''} de banda larga,{' '}
            {formatSubscribers(city.subscribers)} assinantes e {city.penetration}% de penetração
            em {city.name}, {state.name}.
          </p>
        </div>

        {/* Stats */}
        <div
          className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4"
          style={{ borderTop: '1px solid var(--border-dark-strong)' }}
        >
          {[
            { value: formatSubscribers(city.subscribers), label: 'Assinantes' },
            { value: `${city.isp_count}`, label: 'Provedores' },
            { value: `${city.penetration}%`, label: 'Penetração' },
            {
              value: city.growth_pct != null
                ? `${city.growth_pct > 0 ? '+' : ''}${city.growth_pct}%`
                : `${city.hhi}`,
              label: city.growth_pct != null ? 'Crescimento 3a' : 'HHI',
            },
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

      {/* Market concentration + Tech + Quality */}
      <Section background="primary">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* HHI */}
          <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Concentração de mercado
            </div>
            <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
              {city.hhi}
            </div>
            <div
              className="mt-2 inline-block px-2 py-0.5 text-xs font-semibold rounded-sm"
              style={{
                background: hhiInfo.color,
                color: '#fff',
              }}
            >
              {hhiInfo.label}
            </div>
            <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              HHI &lt; 1.500 = competitivo, 1.500–2.500 = moderado, &gt; 2.500 = concentrado
            </p>
          </div>

          {/* Technology */}
          <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Tecnologia
            </div>
            <div className="space-y-3">
              {[
                { label: 'Fibra', pct: city.fiber_pct, color: 'var(--accent)' },
                { label: 'Rádio', pct: city.radio_pct, color: 'var(--warning, #f59e0b)' },
                { label: 'Cabo', pct: city.cable_pct, color: 'var(--info, #3b82f6)' },
                { label: 'DSL', pct: city.dsl_pct, color: 'var(--text-muted)' },
                { label: 'FWA', pct: city.fwa_pct, color: '#8b5cf6' },
              ]
                .filter((t) => t.pct > 0)
                .map((tech) => (
                  <div key={tech.label}>
                    <div className="flex justify-between text-sm mb-1">
                      <span style={{ color: 'var(--text-primary)' }}>{tech.label}</span>
                      <span className="font-mono tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                        {tech.pct}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full" style={{ background: 'var(--border)' }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${Math.min(tech.pct, 100)}%`, background: tech.color }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Quality seals */}
          <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Selos Anatel
            </div>
            {totalQuality > 0 ? (
              <div className="space-y-2">
                {[
                  { label: 'Ouro', count: city.quality.ouro, color: '#eab308' },
                  { label: 'Prata', count: city.quality.prata, color: '#94a3b8' },
                  { label: 'Bronze', count: city.quality.bronze, color: '#d97706' },
                  { label: 'Sem selo', count: city.quality.sem_selo, color: 'var(--text-muted)' },
                ]
                  .filter((s) => s.count > 0)
                  .map((seal) => (
                    <div key={seal.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ background: seal.color }}
                        />
                        <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                          {seal.label}
                        </span>
                      </div>
                      <span
                        className="font-mono text-sm font-bold tabular-nums"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {seal.count}
                      </span>
                    </div>
                  ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Sem dados de selos para este município.
              </p>
            )}
          </div>
        </div>
      </Section>

      {/* A. Melhores Provedores — Top ouro-seal ISPs */}
      {city.top_providers && city.top_providers.length > 0 ? (
        <Section background="subtle">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: '#eab308' }}>
            Selo ouro Anatel
          </div>
          <h2 className="font-serif text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Melhores provedores em {city.name}
          </h2>
          <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Provedores com selo ouro de qualidade RQUAL da Anatel. Dados públicos.
          </p>

          <div style={{ border: '1px solid var(--border)', overflow: 'hidden' }}>
            <div
              className="hidden md:grid font-mono text-[11px] uppercase tracking-wider"
              style={{
                gridTemplateColumns: '1fr 80px 80px 80px 80px',
                background: 'var(--bg-surface)',
                color: 'var(--text-muted)',
                borderBottom: '1px solid var(--border)',
                padding: '10px 16px',
              }}
            >
              <span>Provedor</span>
              <span className="text-right">Geral</span>
              <span className="text-right">Velocidade</span>
              <span className="text-right">Disponib.</span>
              <span className="text-right">Latência</span>
            </div>
            {city.top_providers.map((p, i) => (
              <div
                key={i}
                className="md:grid p-3 md:px-4 md:py-3"
                style={{
                  gridTemplateColumns: '1fr 80px 80px 80px 80px',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                  background: 'var(--bg-primary)',
                }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: '#eab308' }}
                  />
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {p.name}
                  </span>
                </div>
                <span className="block md:text-right font-mono text-sm font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {p.score}
                </span>
                <span className="block md:text-right font-mono text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                  {p.speed}
                </span>
                <span className="block md:text-right font-mono text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                  {p.availability}
                </span>
                <span className="block md:text-right font-mono text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                  {p.latency}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            Fonte: Anatel RQUAL — Regulamento de Qualidade dos Serviços de Telecomunicações. Scores de 0 a 100.
          </p>
        </Section>
      ) : (
        totalQuality > 0 && (
          <Section background="subtle">
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Qualidade Anatel
            </div>
            <h2 className="font-serif text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
              Provedores de qualidade em {city.name}
            </h2>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Nenhum provedor com selo ouro neste município.{' '}
              {city.quality.prata > 0 && `${city.quality.prata} com selo prata. `}
              {city.quality.bronze > 0 && `${city.quality.bronze} com selo bronze.`}
            </p>
            <Link href="/qualidade" className="mt-3 inline-block text-sm" style={{ color: 'var(--accent)' }}>
              Pesquisar qualidade por cidade &rarr;
            </Link>
          </Section>
        )
      )}

      {/* B. Infraestrutura Digital */}
      {hasInfra && (
        <Section background="surface">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Infraestrutura digital
          </div>
          <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Contexto municipal
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {hasSchools && 'total' in city.schools && (
              <>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {city.schools.total.toLocaleString('pt-BR')}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Escolas</div>
                </div>
                {city.schools.no_internet > 0 && (
                  <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                    <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--error, #ef4444)' }}>
                      {city.schools.no_internet.toLocaleString('pt-BR')}
                    </div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Escolas sem internet</div>
                  </div>
                )}
              </>
            )}
            {hasHealth && 'facilities' in city.health && (
              <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {city.health.facilities.toLocaleString('pt-BR')}
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Unidades de saúde ({city.health.beds.toLocaleString('pt-BR')} leitos)
                </div>
              </div>
            )}
            {hasSanitation && 'water_pct' in city.sanitation && city.sanitation.water_pct > 0 && (
              <>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {city.sanitation.water_pct}%
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Cobertura de água</div>
                </div>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {city.sanitation.sewage_pct}%
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Cobertura de esgoto</div>
                </div>
                {city.sanitation.water_loss_pct > 0 && (
                  <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                    <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--warning, #f59e0b)' }}>
                      {city.sanitation.water_loss_pct}%
                    </div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Perdas de água</div>
                  </div>
                )}
              </>
            )}
            {hasDensity && 'addresses' in city.density && (
              <>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {city.density.per_km2}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Endereços/km²</div>
                </div>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {city.density.rural_pct}%
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Endereços rurais</div>
                </div>
              </>
            )}
            {hasEconomy && 'pib_per_capita' in city.economy && city.economy.pib_per_capita > 0 && (
              <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  R$ {city.economy.pib_per_capita.toLocaleString('pt-BR')}
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>PIB per capita</div>
              </div>
            )}
            {hasEmployment && 'telecom_jobs' in city.employment && city.employment.telecom_jobs > 0 && (
              <>
                <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                  <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                    {city.employment.telecom_jobs.toLocaleString('pt-BR')}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Empregos telecom</div>
                </div>
                {city.employment.telecom_salary > 0 && (
                  <div className="p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                    <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                      R$ {city.employment.telecom_salary.toLocaleString('pt-BR')}
                    </div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Salário médio telecom</div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Planning badges */}
          {hasPlanning && 'plano_diretor' in city.planning && (
            <div className="mt-6 flex flex-wrap gap-2">
              {[
                { key: 'plano_diretor', label: 'Plano Diretor', val: city.planning.plano_diretor },
                { key: 'zoning', label: 'Zoneamento', val: city.planning.zoning },
                { key: 'building_code', label: 'Código de Obras', val: city.planning.building_code },
                { key: 'digital_governance', label: 'Governança Digital', val: city.planning.digital_governance },
              ].map((badge) => (
                <span
                  key={badge.key}
                  className="inline-block px-3 py-1 text-xs font-medium rounded-sm"
                  style={{
                    background: badge.val ? 'var(--accent-subtle, rgba(0,122,255,0.1))' : 'var(--bg-subtle)',
                    color: badge.val ? 'var(--accent)' : 'var(--text-muted)',
                    border: `1px solid ${badge.val ? 'var(--accent)' : 'var(--border)'}`,
                  }}
                >
                  {badge.val ? '✓' : '—'} {badge.label}
                </span>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* C. Score de Oportunidade — classification only, no raw scores */}
      {hasOpp && 'level' in city.opportunity && (
        <Section background="primary">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Oportunidade
          </div>
          <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Potencial de mercado — {city.name}
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="font-mono text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                Score geral
              </div>
              <div
                className="font-serif text-2xl font-bold capitalize"
                style={{
                  color: city.opportunity.level === 'alto' ? 'var(--success, #22c55e)'
                    : city.opportunity.level === 'moderado' ? 'var(--warning, #f59e0b)'
                    : 'var(--text-muted)',
                }}
              >
                {city.opportunity.level === 'muito_baixo' ? 'Muito baixo' : city.opportunity.level.charAt(0).toUpperCase() + city.opportunity.level.slice(1)}
              </div>
            </div>

            <div className="md:col-span-4 p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {([
                  { label: 'Demanda', level: city.opportunity.demand_level, color: '#3b82f6' },
                  { label: 'Competição', level: city.opportunity.competition_level, color: '#22c55e' },
                  { label: 'Infraestrutura', level: city.opportunity.infrastructure_level, color: '#f59e0b' },
                  { label: 'Crescimento', level: city.opportunity.growth_level, color: '#8b5cf6' },
                ] as const).map((dim) => (
                  <div key={dim.label}>
                    <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{dim.label}</div>
                    <span
                      className="inline-block px-2 py-0.5 text-xs font-semibold rounded-sm capitalize"
                      style={{
                        background: dim.level === 'alto' ? dim.color : dim.level === 'moderado' ? 'var(--bg-subtle)' : 'var(--border)',
                        color: dim.level === 'alto' ? '#fff' : 'var(--text-secondary)',
                      }}
                    >
                      {dim.level}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                Scores detalhados disponíveis na plataforma.{' '}
                <Link href="/precos" style={{ color: 'var(--accent)' }}>Saiba mais</Link>
              </p>
            </div>
          </div>
        </Section>
      )}

      {/* D. Dinâmica Competitiva — trend summary only */}
      {hasHHITrend && 'direction' in city.hhi_trend && (
        <Section background="subtle">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Dinâmica competitiva
          </div>
          <h2 className="font-serif text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Tendência de concentração
          </h2>

          <div className="max-w-2xl flex items-center gap-4 p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div
              className="font-mono text-3xl"
              style={{
                color: city.hhi_trend.direction === 'caindo' ? 'var(--success, #22c55e)'
                  : city.hhi_trend.direction === 'subindo' ? 'var(--error, #ef4444)'
                  : 'var(--text-muted)',
              }}
            >
              {city.hhi_trend.direction === 'caindo' ? '↓' : city.hhi_trend.direction === 'subindo' ? '↑' : '→'}
            </div>
            <div>
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {city.hhi_trend.direction === 'caindo'
                  ? 'Mercado ficando mais competitivo'
                  : city.hhi_trend.direction === 'subindo'
                  ? 'Concentração aumentando'
                  : 'Concentração estável'}
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                HHI atual: {city.hhi_trend.current} · Análise de {city.hhi_trend.periods} trimestres
              </div>
              <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                Série histórica completa na plataforma.{' '}
                <Link href="/precos" style={{ color: 'var(--accent)' }}>Saiba mais</Link>
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* Demographics — enhanced */}
      <Section background={hasHHITrend ? 'primary' : 'subtle'}>
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Dados demográficos
        </div>
        <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
          {city.name} em números
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { value: city.population ? city.population.toLocaleString('pt-BR') : '—', label: 'População' },
            { value: city.households ? city.households.toLocaleString('pt-BR') : '—', label: 'Domicílios' },
            { value: `${city.penetration}%`, label: 'Assin. / Domicílio' },
            { value: city.code, label: 'Código IBGE' },
          ].map((item) => (
            <div
              key={item.label}
              className="p-4"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
            >
              <div className="font-mono text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {item.value}
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Cross-reference teasers */}
      {(city.teasers.tax_debt_isps > 0 || city.teasers.complaints > 0 || city.teasers.ouro_isps > 0) && (
        <Section background="surface">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Cruzamento de dados
          </div>
          <h2 className="font-serif text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            O que os dados revelam
          </h2>
          <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Informações cruzadas de múltiplas fontes públicas. Detalhes por provedor na plataforma.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {city.teasers.tax_debt_isps > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                  {city.teasers.tax_debt_isps}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  provedor{city.teasers.tax_debt_isps !== 1 ? 'es' : ''} com débitos na PGFN
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: Procuradoria-Geral da Fazenda Nacional
                </div>
              </div>
            )}
            {city.teasers.ouro_isps > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: '#eab308' }}>
                  {city.teasers.ouro_isps}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  provedor{city.teasers.ouro_isps !== 1 ? 'es' : ''} com selo ouro de qualidade
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: Anatel RQUAL
                </div>
              </div>
            )}
            {city.teasers.complaints > 0 && (
              <div className="p-5" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                  {city.teasers.complaints.toLocaleString('pt-BR')}
                </div>
                <div className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                  reclamações de consumidores
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Fonte: consumidor.gov.br
                </div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* E. Narrative paragraph */}
      {city.narrative && (
        <Section background="primary">
          <div className="max-w-3xl">
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Visão geral
            </div>
            <h2 className="font-serif text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
              Banda larga em {city.name}
            </h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {city.narrative}
            </p>
          </div>
        </Section>
      )}

      {/* Neighboring municipalities */}
      {neighbors.length > 0 && (
        <Section background="surface">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Municípios similares
          </div>
          <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Outros municípios em {state.name}
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {neighbors.map((n) => (
              <Link
                key={n.code}
                href={`/mercado/${params.uf}/${n.slug}`}
                className="block p-4 transition-colors"
                style={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  textDecoration: 'none',
                }}
              >
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {n.name}
                </div>
                <div className="mt-1 flex gap-4 font-mono text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  <span>{formatSubscribers(n.subscribers)} assin.</span>
                  <span>{n.isp_count} ISPs</span>
                  <span>{n.fiber_pct}% fibra</span>
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* FAQ */}
      <Section background="subtle">
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Perguntas frequentes
          </div>
          <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Dúvidas sobre internet em {city.name}
          </h2>

          <div className="space-y-3">
            {faqItems.map((faq, i) => (
              <details
                key={i}
                className="group"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <summary
                  className="cursor-pointer select-none p-4 text-sm font-medium list-none flex items-center justify-between gap-4"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {faq.question}
                  <span
                    className="shrink-0 font-mono text-xs transition-transform group-open:rotate-45"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    +
                  </span>
                </summary>
                <div
                  className="px-4 pb-4 text-sm leading-relaxed"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {faq.answer}
                </div>
              </details>
            ))}
          </div>
        </div>
      </Section>

      {/* Related blog posts */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Artigos relacionados
        </div>
        <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
          Leitura recomendada
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {city.growth_pct != null && city.growth_pct > 50 && (
            <Link
              href="/blog/crescimento-banda-larga-interior-2026"
              className="block p-4"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', textDecoration: 'none' }}
            >
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Crescimento de banda larga no interior
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                10 cidades que mais que dobraram de tamanho em 12 meses
              </div>
            </Link>
          )}
          {city.hhi > 6000 && (
            <Link
              href="/blog/concentracao-mercado-hhi-caindo"
              className="block p-4"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', textDecoration: 'none' }}
            >
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Concentração de mercado: onde o HHI está caindo
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Municípios onde a concorrência está aumentando
              </div>
            </Link>
          )}
          {city.fiber_pct > 80 && (
            <Link
              href="/blog/fibra-vs-radio-evolucao-tecnologica"
              className="block p-4"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', textDecoration: 'none' }}
            >
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Fibra vs. rádio: a evolução tecnológica
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                A transição para fibra óptica município a município
              </div>
            </Link>
          )}
          {city.population != null && city.population < 30000 && (
            <Link
              href="/blog/internet-rural-municipios-30-mil"
              className="block p-4"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', textDecoration: 'none' }}
            >
              <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Internet rural: municípios com menos de 30 mil hab.
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Oportunidades e custos reais para ISPs
              </div>
            </Link>
          )}
          <Link
            href="/blog/custo-fibra-optica-km-brasil"
            className="block p-4"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', textDecoration: 'none' }}
          >
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              Custo real de fibra óptica por km no Brasil
            </div>
            <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              De R$ 18 mil a R$ 95 mil dependendo do terreno
            </div>
          </Link>
        </div>
      </Section>

      {/* Cross-state similar cities */}
      {topCrossState.length > 0 && (
        <Section background="primary">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Comparação inter-estadual
          </div>
          <h2 className="font-serif text-xl font-bold mb-6" style={{ color: 'var(--text-primary)' }}>
            Cidades similares em outros estados
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {topCrossState.map((cs) => (
              <Link
                key={`${cs.uf}-${cs.slug}`}
                href={`/mercado/${cs.uf}/${cs.slug}`}
                className="block p-4 transition-colors"
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  textDecoration: 'none',
                }}
              >
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {cs.name} <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>({cs.uf.toUpperCase()})</span>
                </div>
                <div className="mt-1 flex gap-4 font-mono text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  <span>{formatSubscribers(cs.subscribers)} assin.</span>
                  <span>{cs.isp_count} ISPs</span>
                  <span>{cs.fiber_pct}% fibra</span>
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>
            Quer saber quais provedores atuam em {city.name}?
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Nomes, market share, qualidade, compliance e mais — disponíveis na plataforma.
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
