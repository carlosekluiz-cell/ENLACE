import type { Metadata } from 'next';
import Link from 'next/link';
import Section from '@/components/ui/Section';
import { getNationalData, formatSubscribers, getStateName } from '@/lib/market-data';

export const metadata: Metadata = {
  title: 'Mercado de Banda Larga no Brasil — Dados Atualizados',
  description:
    'Panorama completo do mercado de banda larga brasileiro: 54M+ assinantes, 13.500+ provedores em 5.570 municípios. Dados Anatel atualizados por estado e cidade.',
  alternates: { canonical: 'https://pulso.network/mercado' },
};

export default function MercadoPage() {
  const data = getNationalData();

  const totalISPs = data.states.reduce((sum, s) => {
    // approximate unique ISP count — use state-level data
    return sum;
  }, 0);

  return (
    <>
      {/* JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            itemListElement: [
              { '@type': 'ListItem', position: 1, name: 'Início', item: 'https://pulso.network' },
              { '@type': 'ListItem', position: 2, name: 'Mercado', item: 'https://pulso.network/mercado' },
            ],
          }),
        }}
      />

      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Inteligência de mercado
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Mercado de Banda Larga no Brasil
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Panorama completo com dados Anatel: assinantes, provedores, tecnologias e concentração de mercado para
            todos os 27 estados e {data.municipalities.toLocaleString('pt-BR')} municípios.
          </p>
        </div>

        {/* Stats */}
        <div
          className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4"
          style={{ borderTop: '1px solid var(--border-dark-strong)' }}
        >
          {[
            { value: formatSubscribers(data.subscribers), label: 'Assinantes' },
            { value: '13.500+', label: 'Provedores' },
            { value: data.municipalities.toLocaleString('pt-BR'), label: 'Municípios' },
            { value: '27', label: 'Estados' },
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

      {/* State ranking table */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Ranking por estado
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Banda larga por UF
        </h2>
        <p className="mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Clique em um estado para ver detalhes por município. Dados Anatel referência {data.period}.
        </p>

        <div style={{ border: '1px solid var(--border)', overflow: 'hidden' }}>
          {/* Header */}
          <div
            className="hidden md:grid font-mono text-[11px] uppercase tracking-wider"
            style={{
              gridTemplateColumns: '1fr 120px 100px 90px 80px 80px',
              background: 'var(--bg-subtle)',
              color: 'var(--text-muted)',
              borderBottom: '1px solid var(--border)',
              padding: '10px 16px',
            }}
          >
            <span>Estado</span>
            <span className="text-right">Assinantes</span>
            <span className="text-right">Municípios</span>
            <span className="text-right">Penetração</span>
            <span className="text-right">HHI Médio</span>
            <span className="text-right">Fibra %</span>
          </div>

          {/* Rows */}
          {[...data.states]
            .sort((a, b) => b.subscribers - a.subscribers)
            .map((st, i) => (
              <Link
                key={st.uf}
                href={`/mercado/${st.uf.toLowerCase()}`}
                className="block md:grid transition-colors"
                style={{
                  gridTemplateColumns: '1fr 120px 100px 90px 80px 80px',
                  background: 'var(--bg-surface)',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                  padding: '12px 16px',
                  textDecoration: 'none',
                }}
                onMouseEnter={undefined}
              >
                <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                  {st.name}{' '}
                  <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                    {st.uf}
                  </span>
                </span>
                <span
                  className="block md:text-right font-mono text-sm tabular-nums"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {formatSubscribers(st.subscribers)}
                </span>
                <span
                  className="block md:text-right font-mono text-sm tabular-nums"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {st.municipalities}
                </span>
                <span
                  className="block md:text-right font-mono text-sm tabular-nums"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {st.avg_penetration}%
                </span>
                <span
                  className="block md:text-right font-mono text-sm tabular-nums"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {st.avg_hhi}
                </span>
                <span
                  className="block md:text-right font-mono text-sm tabular-nums"
                  style={{ color: 'var(--accent)' }}
                >
                  {st.fiber_pct}%
                </span>
              </Link>
            ))}
        </div>
      </Section>

      {/* CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Dados por provedor.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Disponíveis na plataforma.</span>
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Nomes dos provedores, market share, análise de M&A, due diligence e 25+ módulos de inteligência.
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
