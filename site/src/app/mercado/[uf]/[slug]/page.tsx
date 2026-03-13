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
  return {
    title: `Internet em ${city.name}, ${state.uf} — ${city.isp_count} Provedores, ${formatSubscribers(city.subscribers)} Assinantes`,
    description: `Banda larga em ${city.name}/${state.uf}: ${city.isp_count} provedores, ${city.penetration}% de penetração, ${city.fiber_pct}% fibra. HHI ${city.hhi} (${city.hhi_class}). Dados Anatel atualizados.`,
    alternates: { canonical: `https://pulso.network/mercado/${params.uf}/${params.slug}` },
  };
}

const HHI_LABELS: Record<string, { label: string; color: string }> = {
  competitivo: { label: 'Competitivo', color: 'var(--success, #22c55e)' },
  moderado: { label: 'Moderadamente concentrado', color: 'var(--warning, #f59e0b)' },
  concentrado: { label: 'Altamente concentrado', color: 'var(--error, #ef4444)' },
};

export default function MunicipalityPage({ params }: PageProps) {
  const data = getMunicipalityData(params.uf, params.slug);
  if (!data) notFound();
  const { city, state } = data;

  const hhiInfo = HHI_LABELS[city.hhi_class] || HHI_LABELS.competitivo;

  // Find neighbors: same state, similar subscriber count (±50%), max 6
  const cityIdx = state.cities.findIndex((c) => c.slug === city.slug);
  const neighbors = state.cities
    .filter((c) => c.slug !== city.slug)
    .sort((a, b) => Math.abs(a.subscribers - city.subscribers) - Math.abs(b.subscribers - city.subscribers))
    .slice(0, 6);

  const totalQuality = city.quality.ouro + city.quality.prata + city.quality.bronze + city.quality.sem_selo;

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
            Internet em {city.name}
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

      {/* Demographics */}
      <Section background="subtle">
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

      {/* Neighboring municipalities */}
      {neighbors.length > 0 && (
        <Section background="primary">
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
                  background: 'var(--bg-surface)',
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

      {/* CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>
            Quer saber quais provedores atuam em {city.name}?
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Nomes, market share, qualidade, dívida ativa e sócios — tudo disponível na plataforma.
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
