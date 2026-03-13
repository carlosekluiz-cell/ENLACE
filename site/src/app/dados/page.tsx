import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Dados — Pulso Network',
  description: 'Mais de 38 fontes de dados públicos integradas: Anatel, IBGE, PGFN, Receita Federal, Portal da Transparência, PeeringDB e mais. 29M+ registros.',
  alternates: { canonical: 'https://pulso.network/dados' },
};

const sources = [
  { name: 'Anatel STEL', description: 'Acessos de banda larga por município e provedor (4,1M registros)', frequency: 'Mensal' },
  { name: 'Anatel MOSAICO', description: 'ERBs (37.700+) e licenças de espectro georreferenciadas', frequency: 'Mensal' },
  { name: 'IBGE Censo / Estimativas', description: 'Demografia, renda e domicílios para 5.572 municípios', frequency: 'Anual' },
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
  { name: 'Anatel RQUAL', description: 'Selos de qualidade Anatel (ouro/prata/bronze) para provedores por município', frequency: 'Mensal' },
  { name: 'Anatel Backhaul', description: 'Presença de backhaul de fibra por município', frequency: 'Mensal' },
  { name: 'IBGE POF', description: 'Pesquisa de orçamentos familiares — gastos com telecomunicações', frequency: 'Anual' },
  { name: 'IBGE MUNIC', description: 'Perfil municipal: plano diretor, código de obras, governança digital', frequency: 'Anual' },
  { name: 'IBGE CNEFE', description: 'Cadastro de endereços — densidade de edificações por setor censitário', frequency: 'Decenal' },
  { name: 'IBGE Projeções', description: 'Projeções populacionais por município (2010-2060)', frequency: 'Anual' },
  { name: 'ANEEL / OSM', description: 'Linhas de transmissão de energia (16.559 trechos, 256K km) para co-locação de fibra', frequency: 'Mensal' },
  { name: 'CAGED', description: 'Indicadores de emprego formal por município e setor (11K+ registros)', frequency: 'Mensal' },
  { name: 'Atlas da Violência', description: 'Indicadores de segurança pública por município (IPEA/FBSP)', frequency: 'Anual' },
  { name: 'DOU / Anatel', description: 'Atos regulatórios do Diário Oficial da União relacionados a telecomunicações', frequency: 'Diária' },
  { name: 'Querido Diário', description: 'Menções a telecomunicações em gazetas municipais (60.500+ menções)', frequency: 'Diária' },
  { name: 'MapBiomas', description: 'Uso e cobertura do solo — detecção de crescimento urbano', frequency: 'Anual' },
  { name: 'PeeringDB', description: 'Redes de peering e participação em IXPs (Internet Exchange Points)', frequency: 'Semanal' },
  { name: 'IX.br', description: 'Tráfego e localizações de pontos de troca de tráfego brasileiros', frequency: 'Semanal' },
  { name: 'OpenCelliD', description: 'Torres de celular crowdsourced para validação de cobertura', frequency: 'Mensal' },
  { name: 'Ookla Speedtest', description: 'Dados de velocidade agregados por tile e município', frequency: 'Trimestral' },
  { name: 'Microsoft Buildings', description: 'Footprints de edificações detectados por ML para estimativa de densidade', frequency: 'Estático' },
  { name: 'BrasilAPI CNPJ', description: 'Enriquecimento de CNPJs: razão social, natureza jurídica, capital social, QSA (sócios)', frequency: 'Semanal' },
  { name: 'PGFN Dívida Ativa', description: 'Dívidas fiscais federais: FGTS, previdenciário e não-previdenciário (261K+ registros)', frequency: 'Trimestral' },
  { name: 'Portal da Transparência', description: 'Listas de sanções CEIS/CNEP — empresas impedidas e punidas pelo governo federal', frequency: 'Semanal' },
  { name: 'consumidor.gov.br', description: 'Reclamações de consumidores contra operadoras de telecomunicações', frequency: 'Mensal' },
  { name: 'Receita Federal CNPJ', description: 'Quadro societário completo (56M CNPJs) — grafo de propriedade cruzada entre ISPs', frequency: 'Mensal' },
  { name: 'Anatel Outorgas', description: 'Cadastro de 128K+ prestadoras de serviços de telecomunicações com outorgas e licenças', frequency: 'Diária' },
];

const provenanceCategories = [
  {
    tier: 'Alta Governamental',
    description: 'Dados oficiais de órgãos reguladores e institutos públicos brasileiros.',
    sources: ['Anatel (STEL, MOSAICO, RQUAL, Outorgas)', 'IBGE (Censo, Estimativas, POF, MUNIC, CNEFE)', 'INMET', 'SNIS', 'ANP', 'DataSUS', 'INEP', 'PNCP', 'BNDES', 'FUST', 'CAGED', 'Atlas da Violência (IPEA/FBSP)', 'ANEEL', 'Querido Diário', 'PGFN Dívida Ativa', 'Portal da Transparência (CEIS/CNEP)', 'consumidor.gov.br', 'Receita Federal (CNPJ/Sócios)'],
  },
  {
    tier: 'Alta Científica',
    description: 'Dados de missões espaciais com validação científica rigorosa.',
    sources: ['NASA SRTM (elevação 30m)', 'ESA Sentinel-2 (óptico 10m)', 'MapBiomas (uso do solo, >85% acurácia)'],
  },
  {
    tier: 'Alta Aberta',
    description: 'Dados colaborativos com alta cobertura e atualização frequente.',
    sources: ['OpenStreetMap (malha viária, infraestrutura)', 'PeeringDB (redes de peering)', 'IX.br (tráfego IXP)', 'OpenCelliD (torres)', 'Ookla (speedtest)', 'Microsoft Buildings (ML)'],
  },
  {
    tier: 'Média Computada',
    description: 'Indicadores derivados calculados pelo Pulso a partir das fontes primárias.',
    sources: ['Scores de oportunidade', 'Índice HHI por município', 'Projeções financeiras M&A', 'Índices urbanos Sentinel-2', 'Pulso Score (13.534 ISPs)', 'Crédito ISP', 'Índice Starlink', 'Risco Climático', 'Análise Espacial', 'Grafo de propriedade cruzada', 'Due diligence M&A'],
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
            38+ fontes públicas.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>28 milhões de data points.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Todos os dados são de acesso público. O Pulso integra, normaliza e cruza
            essas fontes para produzir inteligência acionável para provedores de internet.
          </p>
        </div>

        {/* Quick stats */}
        <div className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ borderTop: '1px solid var(--border-dark-strong)' }}>
          {[
            { value: '28M+', label: 'Data points' },
            { value: '38+', label: 'Fontes públicas' },
            { value: '68', label: 'Tabelas de dados' },
            { value: '5.572', label: 'Municípios' },
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

      {/* Cross-References — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Cruzamentos
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          O que emerge quando se cruza tudo
        </h2>
        <p className="mb-10 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
          Nenhuma dessas informações existe pronta em nenhuma fonte individual.
          São o resultado de cruzar, normalizar e correlacionar as 38+ fontes acima.
        </p>

        <div className="grid grid-cols-1 gap-0 md:grid-cols-2 lg:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {[
            { value: '10.740', label: 'Provedores com dívida ativa federal', sources: 'PGFN × Anatel' },
            { value: '783K', label: 'Vínculos societários mapeados', sources: 'Receita Federal × ISPs' },
            { value: '463K', label: 'Reclamações de consumidores', sources: 'consumidor.gov.br × Telecom' },
            { value: '88.619', label: 'Selos de qualidade Anatel', sources: 'RQUAL × Municípios' },
            { value: '16.375', label: 'Escolas offline em áreas com ISPs', sources: 'INEP × Anatel STEL' },
            { value: '318', label: 'Municípios com monopólio efetivo', sources: 'HHI × Assinantes' },
            { value: '60.581', label: 'Menções em diários oficiais', sources: 'Querido Diário × Telecom' },
            { value: '1.709', label: 'Pares de ISPs com sócios em comum', sources: 'Grafo societário' },
            { value: '37', label: 'Meses de série temporal completa', sources: 'Jan/2023 → Jan/2026' },
          ].map((item) => (
            <div
              key={item.label}
              className="p-5"
              style={{
                background: 'var(--bg-primary)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {item.value}
              </div>
              <div className="mt-1 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {item.label}
              </div>
              <div className="mt-2 font-mono text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                {item.sources}
              </div>
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
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
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
