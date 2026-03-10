import Link from 'next/link';
import GeoCanvas from '@/components/ui/GeoCanvas';

const metrics = [
  { value: '37.325', label: 'Torres mapeadas' },
  { value: '6,4M', label: 'Seg. rodoviários' },
  { value: '5.572', label: 'Municípios' },
  { value: '17M+', label: 'Registros' },
];

export default function Hero() {
  return (
    <section className="relative overflow-hidden -mt-14" style={{ background: 'var(--bg-dark)', minHeight: '90vh' }}>
      {/* Canvas tower network */}
      <GeoCanvas variant="hero" />

      <div className="relative z-10 mx-auto max-w-6xl px-4 pt-32 pb-8 md:pt-40 md:pb-12">
        {/* Tag */}
        <div
          className="mb-6 inline-flex items-center gap-2 font-mono text-xs tracking-wider uppercase"
          style={{ color: 'var(--accent-hover)' }}
        >
          <span className="inline-block h-px w-8" style={{ background: 'var(--accent)' }} />
          Pulso Network
        </div>

        {/* Headline */}
        <h1
          className="font-serif text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl max-w-4xl"
          style={{ color: 'var(--text-on-dark)', lineHeight: 1.05 }}
        >
          37.325 torres.{' '}
          <br className="hidden md:block" />
          6,4 milhões de rotas.{' '}
          <span style={{ color: 'var(--text-on-dark-muted)' }}>
            <br className="hidden md:block" />
            Cobertura completa do Brasil.
          </span>
        </h1>

        {/* Sub */}
        <p
          className="mt-6 max-w-xl text-base leading-relaxed md:text-lg"
          style={{ color: 'var(--text-on-dark-secondary)' }}
        >
          A plataforma que transforma infraestrutura real em decisões de negócio
          para provedores de internet.
        </p>

        {/* CTAs */}
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="/cadastro" className="pulso-btn-dark">
            Começar gratuitamente
          </Link>
          <Link href="/produto" className="pulso-btn-ghost">
            Ver plataforma &rarr;
          </Link>
        </div>

        {/* Metrics */}
        <div
          className="mt-14 flex flex-wrap gap-x-12 gap-y-4 md:gap-x-16"
          style={{ borderTop: '1px solid var(--border-dark-strong)', paddingTop: '24px' }}
        >
          {metrics.map((m) => (
            <div key={m.label}>
              <div
                className="font-mono text-2xl font-bold tabular-nums md:text-3xl"
                style={{ color: 'var(--accent-hover)' }}
              >
                {m.value}
              </div>
              <div className="mt-1 text-xs uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)' }}>
                {m.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
