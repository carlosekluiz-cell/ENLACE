import Link from 'next/link';
import GeoCanvas from '@/components/ui/GeoCanvas';

const metrics = [
  { value: '28M+', label: 'Data points cruzados' },
  { value: '128K+', label: 'Provedores rastreados' },
  { value: '5.572', label: 'Municípios cobertos' },
  { value: '38+', label: 'Fontes públicas' },
  { value: '68', label: 'Tabelas de dados' },
  { value: 'R$ 50 bi', label: 'Mercado mapeado' },
];

const dataSources = [
  'Anatel STEL', 'IBGE Censo', 'NASA SRTM', 'INMET', 'Sentinel-2 ESA',
  'DataSUS', 'INEP', 'CAGED', 'PeeringDB', 'IX.br/NIC.br', 'Ookla Speedtest',
  'OpenCellID', 'BNDES', 'PNCP', 'DOU', 'CNPJ/RFB', 'Atlas da Violência',
  'SNIS', 'IBGE POF', 'PGFN Dívida Ativa', 'Portal da Transparência',
  'consumidor.gov.br', 'Receita Federal Sócios', 'MapBiomas', 'ANEEL',
  'Querido Diário', 'Anatel RQUAL',
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

        {/* Headline — outcome-centric */}
        <h1
          className="font-serif text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl max-w-4xl"
          style={{ color: 'var(--text-on-dark)', lineHeight: 1.05 }}
        >
          5.572 municípios.{' '}
          <br className="hidden md:block" />
          Cada um, uma decisão.{' '}
          <span style={{ color: 'var(--text-on-dark-muted)' }}>
            <br className="hidden md:block" />
            Agora você acerta mais.
          </span>
        </h1>

        {/* Sub — specific and vivid */}
        <p
          className="mt-6 max-w-xl text-base leading-relaxed md:text-lg"
          style={{ color: 'var(--text-on-dark-secondary)' }}
        >
          28 milhões de data points cruzados de 38+ fontes públicas — concorrência,
          expansão, M&A, due diligence fiscal, conformidade — tudo ao vivo.
          A maior base de inteligência ISP do mundo.
        </p>

        {/* CTAs */}
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="/precos" className="pulso-btn-dark">
            Entrar na lista de espera
          </Link>
          <Link href="/produto" className="pulso-btn-ghost">
            Ver a plataforma ao vivo &rarr;
          </Link>
        </div>

        {/* Metrics grid — buyer-centric */}
        <div
          className="mt-10 grid grid-cols-3 gap-0 md:grid-cols-6"
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
