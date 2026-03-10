import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Dados — Pulso Network',
  description: 'Fontes de dados públicos integradas no Pulso: Anatel, IBGE, SRTM/NASA, INMET, DataSUS, INEP e mais.',
};

const sources = [
  { name: 'Anatel STEL', description: 'Acessos de banda larga por município e provedor (4,1M registros)', frequency: 'Mensal' },
  { name: 'Anatel MOSAICO', description: 'ERBs (37.700+) e licenças de espectro georreferenciadas', frequency: 'Mensal' },
  { name: 'IBGE Censo / Estimativas', description: 'Demografia, renda e domicílios para 5.570+ municípios', frequency: 'Anual' },
  { name: 'SRTM / NASA', description: 'Modelo de elevação digital (30m) — 1.681 tiles cobrindo todo o Brasil', frequency: 'Estático' },
  { name: 'ESA Sentinel-2', description: 'Imagens satélite para índices urbanos e uso do solo (10m)', frequency: 'Quinzenal' },
  { name: 'OpenStreetMap', description: 'Malha viária (6,4M segmentos) e linhas de transmissão (16.559 trechos)', frequency: 'Semanal' },
  { name: 'INMET / Open-Meteo', description: 'Dados meteorológicos de 671 estações (61.000+ observações)', frequency: 'Diária' },
  { name: 'SNIS', description: 'Infraestrutura de saneamento por município', frequency: 'Anual' },
  { name: 'ANP', description: 'Vendas de combustível por município (proxy de atividade econômica)', frequency: 'Mensal' },
  { name: 'DataSUS', description: 'Indicadores de saúde e unidades de atendimento por município', frequency: 'Anual' },
  { name: 'INEP', description: 'Censo escolar — escolas e matrículas por município', frequency: 'Anual' },
  { name: 'PNCP', description: 'Contratos públicos de telecomunicações', frequency: 'Diária' },
  { name: 'BNDES', description: 'Financiamentos e operações de crédito no setor telecom', frequency: 'Mensal' },
  { name: 'FUST / Transparência', description: 'Fundo de universalização dos serviços de telecomunicações', frequency: 'Mensal' },
];

const provenanceCategories = [
  {
    tier: 'Alta Governamental',
    description: 'Dados oficiais de órgãos reguladores e institutos públicos brasileiros.',
    sources: ['Anatel (STEL, MOSAICO)', 'IBGE (Censo, Estimativas, POF, MUNIC)', 'INMET', 'SNIS', 'ANP', 'DataSUS', 'INEP', 'PNCP', 'BNDES', 'FUST'],
  },
  {
    tier: 'Alta Científica',
    description: 'Dados de missões espaciais com validação científica rigorosa.',
    sources: ['NASA SRTM (elevação 30m)', 'ESA Sentinel-2 (óptico 10m)'],
  },
  {
    tier: 'Alta Aberta',
    description: 'Dados colaborativos com alta cobertura e atualização frequente.',
    sources: ['OpenStreetMap (malha viária, infraestrutura)'],
  },
  {
    tier: 'Média Computada',
    description: 'Indicadores derivados calculados pelo Pulso a partir das fontes primárias.',
    sources: ['Scores de oportunidade', 'Índice HHI por município', 'Projeções financeiras M&A', 'Índices urbanos Sentinel-2'],
  },
];

export default function DadosPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Fontes de dados
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            12+ fontes públicas.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>17M+ registros.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Todos os dados são de acesso público. O Pulso integra, normaliza e cruza
            essas fontes para produzir inteligência acionável para provedores de internet.
          </p>
        </div>

        {/* Quick stats */}
        <div className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ borderTop: '1px solid var(--border-dark-strong)' }}>
          {[
            { value: '12+', label: 'Fontes' },
            { value: '5.570+', label: 'Municípios' },
            { value: '17M+', label: 'Registros' },
            { value: '671', label: 'Estações meteo' },
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

      {/* Sources — Light */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Fontes integradas
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          De onde vem os dados
        </h2>

        <div style={{ border: '1px solid var(--border)' }}>
          {sources.map((source, i) => (
            <div
              key={source.name}
              className="flex items-start gap-4 p-5"
              style={{
                background: 'var(--bg-surface)',
                borderTop: i > 0 ? '1px solid var(--border)' : 'none',
              }}
            >
              <span className="font-mono text-sm font-bold tabular-nums shrink-0 w-8 mt-0.5" style={{ color: 'var(--accent)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="flex-1">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {source.name}
                </h3>
                <p className="mt-0.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {source.description}
                </p>
              </div>
              <span className="font-mono text-xs shrink-0" style={{ color: 'var(--text-muted)' }}>
                {source.frequency}
              </span>
            </div>
          ))}
        </div>

        <p className="mt-4 text-sm" style={{ color: 'var(--text-muted)' }}>
          Documentação técnica detalhada e metodologia disponíveis dentro da plataforma para usuários autenticados.
        </p>
      </Section>

      {/* Provenance — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Procedência
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          Confiabilidade por categoria
        </h2>
        <p className="mb-10 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          Classificamos cada fonte de dados pelo nível de confiabilidade e rastreabilidade.
          Todos os dados utilizados são públicos e verificáveis na origem.
        </p>

        <div className="grid grid-cols-1 gap-0 md:grid-cols-2" style={{ border: '1px solid var(--border)' }}>
          {provenanceCategories.map((cat) => (
            <div
              key={cat.tier}
              className="p-6"
              style={{
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="inline-block h-2 w-2"
                  style={{
                    background: cat.tier.startsWith('Alta') ? 'var(--success)' : 'var(--warning, #f59e0b)',
                  }}
                />
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {cat.tier}
                </h3>
              </div>
              <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                {cat.description}
              </p>
              <ul className="space-y-1">
                {cat.sources.map((s) => (
                  <li key={s} className="text-sm flex items-start gap-2" style={{ color: 'var(--text-secondary)' }}>
                    <span className="mt-1 text-[10px]" style={{ color: 'var(--accent)' }}>&#8226;</span>
                    {s}
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
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>
            Dados públicos.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Inteligência proprietária.</span>
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Acesse a plataforma para explorar os dados em detalhe.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/cadastro" className="pulso-btn-dark">
              Criar conta gratuita
            </Link>
            <Link href="/produto" className="pulso-btn-ghost">
              Ver módulos &rarr;
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
