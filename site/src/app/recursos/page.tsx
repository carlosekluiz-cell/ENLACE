import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Recursos',
  description: 'Whitepaper, calculadora de ROI e matriz de funcionalidades para decisores.',
  alternates: { canonical: 'https://pulso.network/recursos' },
};

const heroStats = [
  { value: '28M+', label: 'Data points' },
  { value: '38+', label: 'Fontes de dados' },
  { value: '25', label: 'Módulos de análise' },
  { value: '5.570', label: 'Municípios cobertos' },
];

const resources = [
  {
    title: 'Whitepaper',
    href: '/recursos/whitepaper',
    tag: 'Investidores & Decisores',
    description: 'Como a Pulso Network transforma 38+ fontes públicas em telecom tech e inteligência acionável para o mercado de telecomunicações brasileiro.',
    highlights: [
      '13.534 ISPs ativos monitorados em 5.570 municípios',
      '19M+ registros cruzados de fontes públicas oficiais',
      'Compliance automatizado: regulatório, qualidade e obrigações',
      '37 períodos históricos de dinâmica competitiva',
    ],
    stat: { value: '19M+', label: 'Registros cruzados em produção' },
  },
  {
    title: 'Calculadora de ROI',
    href: '/recursos/roi',
    tag: 'ISPs & Decisores',
    description: '3 casos de uso reais com retorno calculado. Expansão, conformidade e M&A.',
    highlights: [
      'Caso 1: Expansão — R$2M CAPEX protegido, 96% menos tempo de análise',
      'Caso 2: Conformidade — R$100K em multas evitadas, 7,5x ROI total',
      'Caso 3: M&A — análise de mercado acelerada por município',
      'Payback em menos de 1 mês em todos os cenários',
    ],
    stat: { value: '3,3x–111x', label: 'ROI por caso de uso' },
  },
  {
    title: 'Matriz de Funcionalidades',
    href: '/recursos/funcionalidades',
    tag: 'Compradores & Avaliadores',
    description: 'Cada funcionalidade de cada módulo detalhada por tier. Gratuito, Provedor, Profissional e Empresa.',
    highlights: [
      '24 módulos: Mercado, Expansão, Concorrência, Espacial, Starlink, FWA, Peering, IX.br e mais',
      '100+ funcionalidades mapeadas por tier',
      'Funcionalidades transversais: API, SSE, relatórios, GeoJSON',
      'Notas sobre SLA, rate limits e onboarding',
    ],
    stat: { value: '100+', label: 'Funcionalidades detalhadas' },
  },
  {
    title: 'Confiança dos Dados',
    href: '/recursos/dados-confianca',
    tag: 'Técnicos & Compliance',
    description: 'Cada fonte classificada em 4 níveis (A1/A2/A3/B1) com metodologia, limitações e validação automática.',
    highlights: [
      'A1: Anatel, IBGE, INMET, DATASUS, INEP, PNCP, BNDES, CAGED, SNIS, ANP',
      'A2: SRTM/NASA (1.681 tiles), Sentinel-2/ESA, MapBiomas',
      'A3: OpenStreetMap (6,4M rodovias, 37K torres), Open-Meteo',
      'B1: Scores proprietários com fórmula documentada',
      '5 etapas de validação automática por fonte',
    ],
    stat: { value: '19+', label: 'Fontes classificadas' },
  },
];


export default function RecursosPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Recursos
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Tudo documentado.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Nada escondido.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Whitepaper para investidores, calculadora de ROI para ISPs, matriz de funcionalidades
            para compradores e classificação de dados para auditores. Cada documento baseado em dados reais de produção.
          </p>
        </div>

        {/* Hero stats bar */}
        <div className="mt-10 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ border: '1px solid var(--border-dark)' }}>
          {heroStats.map((stat) => (
            <div
              key={stat.label}
              className="p-5"
              style={{ borderRight: '1px solid var(--border-dark)' }}
            >
              <div className="font-mono text-xl font-bold" style={{ color: 'var(--accent)' }}>{stat.value}</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>{stat.label}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Resource Cards — each as its own rich section */}
      {resources.map((resource, i) => (
        <Section key={resource.href} background={i % 2 === 0 ? 'primary' : 'subtle'}>
          <div className="grid grid-cols-1 gap-8 md:grid-cols-5">
            {/* Left: content (3 cols) */}
            <div className="md:col-span-3">
              <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                {resource.tag}
              </div>
              <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {resource.title}
              </h2>
              <p className="mt-3 text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {resource.description}
              </p>
              <ul className="mt-5 space-y-2">
                {resource.highlights.map((h) => (
                  <li key={h} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                    {h}
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                <Link href={resource.href} className="pulso-btn-outline">
                  Ler documento completo →
                </Link>
              </div>
            </div>

            {/* Right: key stat card (2 cols) */}
            <div className="md:col-span-2 flex items-start">
              <div className="w-full p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <div className="font-mono text-3xl font-bold" style={{ color: 'var(--accent)' }}>
                  {resource.stat.value}
                </div>
                <div className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {resource.stat.label}
                </div>
                <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
                  <Link href={resource.href} className="text-sm font-medium" style={{ color: 'var(--accent)' }}>
                    Ver detalhes →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </Section>
      ))}

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Dados reais, documentação completa.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Avalie com transparência.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/recursos/funcionalidades" className="pulso-btn-ghost">
              Ver funcionalidades
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
