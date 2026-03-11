import Link from 'next/link';
import GeoCanvas from '@/components/ui/GeoCanvas';

const metrics = [
  { value: '28', label: 'Módulos' },
  { value: '19+', label: 'Fontes de dados' },
  { value: '28M+', label: 'Registros' },
  { value: '5.572', label: 'Municípios' },
  { value: '13.534', label: 'Provedores' },
  { value: '157', label: 'API endpoints' },
];

const dataSources = [
  'Anatel STEL', 'IBGE Censo', 'NASA SRTM', 'INMET', 'Sentinel-2 ESA',
  'DataSUS', 'INEP', 'CAGED', 'PeeringDB', 'IX.br/NIC.br', 'Ookla Speedtest',
  'OpenCellID', 'BNDES', 'PNCP', 'DOU', 'CNPJ/RFB', 'Atlas da Violência',
  'SNIS', 'IBGE POF',
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
          28 módulos.{' '}
          <br className="hidden md:block" />
          19 fontes de dados.{' '}
          <span style={{ color: 'var(--text-on-dark-muted)' }}>
            <br className="hidden md:block" />
            Uma decisão melhor.
          </span>
        </h1>

        {/* Sub */}
        <p
          className="mt-6 max-w-xl text-base leading-relaxed md:text-lg"
          style={{ color: 'var(--text-on-dark-secondary)' }}
        >
          A plataforma de inteligência telecom mais completa do Brasil.
          Expansão, concorrência, M&A, conformidade, satélite, RF e mais —
          tudo cruzado automaticamente por município.
        </p>

        {/* CTAs */}
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="/cadastro" className="pulso-btn-dark">
            Começar gratuitamente
          </Link>
          <Link href="/produto" className="pulso-btn-ghost">
            Ver 28 módulos &rarr;
          </Link>
        </div>

        {/* Metrics grid */}
        <div
          className="mt-14 grid grid-cols-3 gap-0 md:grid-cols-6"
          style={{ borderTop: '1px solid var(--border-dark-strong)', paddingTop: '24px' }}
        >
          {metrics.map((m) => (
            <div key={m.label} className="py-2 pr-4">
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

        {/* Data sources ticker */}
        <div className="mt-8 overflow-hidden" style={{ maskImage: 'linear-gradient(to right, transparent, black 5%, black 95%, transparent)' }}>
          <div className="hero-ticker flex gap-6 whitespace-nowrap font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
            {[...dataSources, ...dataSources].map((src, i) => (
              <span key={i} className="flex items-center gap-2">
                <span className="inline-block h-1 w-1" style={{ background: 'var(--accent)', borderRadius: '50%' }} />
                {src}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
