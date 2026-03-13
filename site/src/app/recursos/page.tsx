import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Recursos',
  description: 'Documentação técnica, whitepaper, calculadora de ROI e matriz de funcionalidades para decisores.',
  alternates: { canonical: 'https://pulso.network/recursos' },
};

const heroStats = [
  { value: '28M+', label: 'Registros de produção' },
  { value: 'R$16,4M', label: 'Custo de reprodução' },
  { value: '38', label: 'Pipelines automatizados' },
  { value: '9.000+', label: 'LOC Rust (motor RF)' },
];

const resources = [
  {
    title: 'Whitepaper',
    href: '/recursos/whitepaper',
    tag: 'Investidores & Executivos',
    description: 'Visão completa da plataforma: mercado de R$250B, fosso tecnológico, análise competitiva e estratégia go-to-market.',
    highlights: [
      'Mercado de 13.534 ISPs movimentando R$250B+/ano',
      '5 dores críticas que a plataforma resolve',
      'Motor RF em Rust com 6 modelos ITU-R sobre terreno real',
      'Nenhum concorrente cobre RF + Mercado + Regulatório + M&A + Satélite',
      'Valuation: R$16,4M (306 person-months, COCOMO II)',
      'ARR projetado: R$1,8M → R$16,8M em 3 anos',
    ],
    stat: { value: 'R$16,4M', label: 'Custo de reprodução independente' },
  },
  {
    title: 'Calculadora de ROI',
    href: '/recursos/roi',
    tag: 'ISPs & Decisores',
    description: '3 casos de uso reais com retorno calculado. De 3,3x a 111x sobre o custo da assinatura.',
    highlights: [
      'Caso 1: Expansão — R$2M CAPEX protegido, 96% menos tempo de análise',
      'Caso 2: Conformidade — R$100K em multas evitadas, 7,5x ROI total',
      'Caso 3: M&A — 10 targets pelo preço de 1 due diligence tradicional',
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
      '5 etapas de validação automática por pipeline',
    ],
    stat: { value: '19+', label: 'Fontes classificadas' },
  },
];

const technicalDocs = [
  {
    title: 'Arquitetura do Sistema',
    description: 'Next.js 14 + FastAPI + Rust RF Engine (gRPC+TLS) + PostgreSQL/PostGIS.',
    details: [
      'Frontend: Next.js 14, TypeScript, Tailwind, Leaflet',
      'Backend: FastAPI (Python 3.11), JWT auth, SSE',
      'RF Engine: Rust, 6 crates, gRPC+TLS, SRTM 30m',
      'DB: PostgreSQL + PostGIS, materialized views',
      '38 pipelines (APScheduler), Sentinel-2 via GEE',
    ],
  },
  {
    title: 'Catálogo de Pipelines',
    description: '38 pipelines automatizados alimentando 62 tabelas.',
    details: [
      '7 diarios: Anatel, INMET, PNCP, DOU, Querido Diário',
      '7 semanais: IBGE, ANP, BNDES, CNPJ enriquecimento',
      '12 mensais: IBGE censo, SRTM, MapBiomas, OSM, DATASUS',
      '5 computados: scores, HHI, quality, market summary',
      'Validação: contagem, integridade, limites, freshness',
    ],
  },
  {
    title: 'Dicionário de Dados',
    description: '62 tabelas com esquema completo e exemplos de consulta.',
    details: [
      'providers (13.534 rows): national_id, name, uf, license_type',
      'broadband_subscribers (4,3M): provider_id, l2_id, subscribers, tech',
      'road_segments (6,4M): geom, highway_class, length_km',
      'base_stations (37.325): geom, provider_id, height_m',
      'opportunity_scores (5.572): composite, demand, competition, growth',
    ],
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

      {/* Technical Docs — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Documentação Técnica
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Para equipes de engenharia
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          Documentação detalhada da arquitetura, pipelines e esquema de dados. Disponível para clientes
          dos tiers Profissional e Empresa.
        </p>
        <div className="grid grid-cols-1 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {technicalDocs.map((doc) => (
            <div
              key={doc.title}
              className="p-6"
              style={{
                background: 'var(--bg-primary)',
                borderRight: '1px solid var(--border)',
              }}
            >
              <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {doc.title}
              </h3>
              <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                {doc.description}
              </p>
              <ul className="mt-4 space-y-1.5">
                {doc.details.map((d) => (
                  <li key={d} className="text-xs font-mono leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

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
            <Link href="/precos" className="pulso-btn-ghost">
              Ver planos
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
