import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Confiança dos Dados — Pulso Network',
  description: 'Sistema de classificação de proveniência e confiabilidade: A1, A2, A3, B1 para cada fonte de dados.',
};

const classificationLevels = [
  { level: 'A1', name: 'Alta (Governamental)', description: 'Dados oficiais do governo brasileiro', criteria: 'Fonte governamental, metodologia pública, atualização regular, auditável' },
  { level: 'A2', name: 'Alta (Científica)', description: 'Dados científicos com metodologia peer-reviewed', criteria: 'Instituição científica, resolução conhecida, reproduzível' },
  { level: 'A3', name: 'Alta (Aberta)', description: 'Dados abertos colaborativos com validação', criteria: 'Comunidade ativa, validação cruzada, licença aberta' },
  { level: 'B1', name: 'Média (Computada)', description: 'Dados derivados por algoritmos proprietários', criteria: 'Fórmula documentada, inputs de nível A, atualização automática' },
];

type SourceEntry = { dataset: string; table: string; records: string; level: string };

const a1Sources: { name: string; fullName: string; entries: SourceEntry[]; limitations?: string }[] = [
  {
    name: 'Anatel',
    fullName: 'Agência Nacional de Telecomunicações',
    entries: [
      { dataset: 'Provedores SCM/SVA', table: 'providers', records: '13.534', level: 'A1' },
      { dataset: 'Assinantes banda larga', table: 'broadband_subscribers', records: '4.284.635', level: 'A1' },
      { dataset: 'Qualidade IQS/RQual', table: 'quality_indicators', records: '6.111.347', level: 'A1' },
      { dataset: 'Licenças de espectro', table: 'spectrum_licenses', records: '47', level: 'A1' },
      { dataset: 'Atos regulatórios (DOU)', table: 'regulatory_acts', records: 'Variável', level: 'A1' },
    ],
    limitations: 'Provedores menores podem sub-reportar assinantes. Qualidade limitada a provedores com mais de 50K assinantes em algumas métricas.',
  },
  {
    name: 'IBGE',
    fullName: 'Instituto Brasileiro de Geografia e Estatística',
    entries: [
      { dataset: 'Municípios (geometrias)', table: 'admin_level_2', records: '5.572', level: 'A1' },
      { dataset: 'População estimada', table: 'ibge_population', records: '5.570', level: 'A1' },
      { dataset: 'PIB municipal', table: 'municipal_gdp', records: 'Variável', level: 'A1' },
      { dataset: 'POF (gastos familiares)', table: 'household_expenditure', records: 'Variável', level: 'A1' },
      { dataset: 'MUNIC (planejamento)', table: 'municipal_planning', records: 'Variável', level: 'A1' },
      { dataset: 'CNEFE (endereços)', table: 'building_density', records: 'Variável', level: 'A1' },
    ],
    limitations: 'Último censo completo em 2022. Estimativas intercensitárias podem divergir em municípios pequenos.',
  },
  {
    name: 'INMET',
    fullName: 'Instituto Nacional de Meteorologia',
    entries: [
      { dataset: 'Estações meteorológicas', table: 'weather_stations', records: '671', level: 'A1' },
      { dataset: 'Observações meteorológicas', table: 'weather_observations', records: '61.061', level: 'A1*' },
    ],
    limitations: 'Observações obtidas via Open-Meteo (intermediário). Dados originais do INMET, verificados por limites físicos.',
  },
  {
    name: 'Outras fontes A1',
    fullName: 'DATASUS, INEP, PNCP, BNDES, CAGED, SNIS, ANP, IPEA',
    entries: [
      { dataset: 'Estabelecimentos de saúde', table: 'health_facilities', records: 'Variável', level: 'A1' },
      { dataset: 'Escolas (Censo Escolar)', table: 'schools', records: 'Variável', level: 'A1' },
      { dataset: 'Contratos governamentais', table: 'government_contracts', records: 'Variável', level: 'A1' },
      { dataset: 'Emprestimos BNDES', table: 'bndes_loans', records: 'Variável', level: 'A1' },
      { dataset: 'Indicadores de emprego', table: 'employment_indicators', records: 'Variável', level: 'A1' },
      { dataset: 'Indicadores de saneamento', table: 'sanitation_indicators', records: 'Variável', level: 'A1' },
      { dataset: 'Preços de combustível', table: 'fuel_prices', records: 'Variável', level: 'A1' },
      { dataset: 'Indicadores de segurança', table: 'safety_indicators', records: 'Variável', level: 'A1' },
      { dataset: 'Gazetas municipais', table: 'gazette_mentions', records: 'Variável', level: 'A1' },
    ],
  },
];

const a2Sources: { name: string; entries: SourceEntry[]; methodology?: string; limitations?: string }[] = [
  {
    name: 'SRTM — NASA/USGS',
    entries: [
      { dataset: 'Terreno 30m', table: 'srtm_tiles', records: '1.681 tiles / 40,6 GB', level: 'A2' },
    ],
    methodology: 'Shuttle Radar Topography Mission (2000). Resolução 30m. Validado: Manaus 36-86m, Curitiba 905-945m, Salvador 9-71m, São Paulo 726-852m.',
    limitations: 'Dados de 2000. Mudanças topográficas (mineração, aterros) não refletidas. Precisão: +/-6m típica.',
  },
  {
    name: 'Sentinel-2 — ESA/Copernicus',
    entries: [
      { dataset: 'Índices urbanos', table: 'sentinel_urban_indices', records: '87+', level: 'A2' },
      { dataset: 'Compositos', table: 'sentinel_composites', records: 'Variável', level: 'A2' },
    ],
    methodology: 'Sentinel-2 MSI via Google Earth Engine. Resolução 10m. Compositos anuais (2016-2026). Índices: NDVI, NDBI, MNDWI, BSI.',
    limitations: 'Cobertura de nuvens reduz qualidade no Norte do Brasil. Threshold de nuvens: 20%.',
  },
  {
    name: 'MapBiomas',
    entries: [
      { dataset: 'Cobertura do solo', table: 'land_cover', records: 'Variável', level: 'A2' },
    ],
    methodology: 'Classificação supervisionada por Random Forest sobre Landsat. Acurácia geral > 85%.',
  },
];

const a3Sources: SourceEntry[] = [
  { dataset: 'Segmentos rodoviários (OSM)', table: 'road_segments', records: '6.457.585', level: 'A3' },
  { dataset: 'Torres de telecomunicação (OSM)', table: 'base_stations', records: '37.325', level: 'A3' },
  { dataset: 'Linhas de energia (OSM)', table: 'power_lines', records: '16.559', level: 'A3' },
  { dataset: 'Observações meteo (Open-Meteo)', table: 'weather_observations', records: '61.061', level: 'A3' },
];

const b1Sources: SourceEntry[] = [
  { dataset: 'Scores de oportunidade', table: 'opportunity_scores', records: '5.572', level: 'B1' },
  { dataset: 'Análise competitiva (HHI)', table: 'competitive_analysis', records: '~5.572', level: 'B1' },
  { dataset: 'Atribuição de operadora', table: 'base_stations', records: '37.325', level: 'B1' },
  { dataset: 'Indicadores de qualidade', table: 'quality_indicators', records: '6.111.347', level: 'B1' },
];

function SourceTable({ entries }: { entries: SourceEntry[] }) {
  return (
    <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Dataset</th>
            <th className="px-4 py-3 text-left font-mono font-medium text-xs" style={{ color: 'var(--text-primary)' }}>Tabela</th>
            <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Registros</th>
            <th className="px-3 py-3 text-center font-mono font-medium" style={{ color: 'var(--accent)' }}>Nível</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.dataset + e.table} style={{ borderBottom: '1px solid var(--border)' }}>
              <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{e.dataset}</td>
              <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{e.table}</td>
              <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{e.records}</td>
              <td className="px-3 py-3 text-center font-mono font-bold" style={{ color: 'var(--accent)' }}>{e.level}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DadosConfiancaPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Confiança dos Dados
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Proveniência rastreável.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Cada fonte classificada.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Classificamos cada fonte de dados em quatro níveis de confiança (A1, A2, A3, B1) baseados
            na origem, metodologia de coleta e rastreabilidade.
          </p>
        </div>
      </Section>

      {/* Classification System — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Sistema de Classificação
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Quatro níveis de confiança
        </h2>
        <div className="grid grid-cols-1 gap-0 md:grid-cols-2" style={{ border: '1px solid var(--border)' }}>
          {classificationLevels.map((cl) => (
            <div
              key={cl.level}
              className="p-6"
              style={{
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono text-lg font-bold" style={{ color: 'var(--accent)' }}>{cl.level}</span>
                <span className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{cl.name}</span>
              </div>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{cl.description}</p>
              <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>{cl.criteria}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* A1 Sources — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Nível A1
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Alta (Governamental)
        </h2>
        <div className="space-y-10">
          {a1Sources.map((source) => (
            <div key={source.name}>
              <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                {source.name}
              </h3>
              <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>{source.fullName}</p>
              <SourceTable entries={source.entries} />
              {source.limitations && (
                <p className="mt-3 text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  Limitações: {source.limitations}
                </p>
              )}
            </div>
          ))}
        </div>
      </Section>

      {/* A2 Sources — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Nível A2
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Alta (Científica)
        </h2>
        <div className="space-y-10">
          {a2Sources.map((source) => (
            <div key={source.name}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                {source.name}
              </h3>
              <SourceTable entries={source.entries} />
              {source.methodology && (
                <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {source.methodology}
                </p>
              )}
              {source.limitations && (
                <p className="mt-2 text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  Limitações: {source.limitations}
                </p>
              )}
            </div>
          ))}
        </div>
      </Section>

      {/* A3 Sources — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Nível A3
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          Alta (Aberta)
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Dados colaborativos de OpenStreetMap e Open-Meteo. Validação cruzada com dados oficiais. Cobertura pode ser
          incompleta em áreas rurais remotas.
        </p>
        <SourceTable entries={a3Sources} />
      </Section>

      {/* B1 Sources — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Nível B1
        </div>
        <h2 className="font-serif text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          Média (Computada)
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Dados derivados por algoritmos proprietários da plataforma. Fórmula documentada, inputs exclusivamente
          de fontes nível A, atualização automática via pipelines.
        </p>
        <SourceTable entries={b1Sources} />
        <div className="mt-6 p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Fórmula de scoring de oportunidade
          </h4>
          <div className="font-mono text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            <p>composite = demand * 0.25 + competition * 0.20 + infrastructure * 0.20 + growth * 0.15 + social * 0.20</p>
            <p className="mt-2" style={{ color: 'var(--text-muted)' }}>
              8 fatores de enriquecimento: backhaul, escolas, saúde, emprego, qualidade, segurança, densidade, planejamento
            </p>
          </div>
        </div>
      </Section>

      {/* Validation Process — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Validação
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Processo de validação automática
        </h2>
        <div className="max-w-3xl space-y-6">
          {[
            { step: 'Contagem de registros', detail: 'Compara com a última ingestão. Alertas se variação > 20%.' },
            { step: 'Integridade referencial', detail: 'Foreign keys verificadas (l2_id, provider_id).' },
            { step: 'Limites físicos', detail: 'Coordenadas dentro do Brasil. Temperaturas -50 a +60C. Scores 0-100.' },
            { step: 'Duplicatas', detail: 'Detecção via UPSERT (ON CONFLICT DO UPDATE).' },
            { step: 'Freshness', detail: 'Alertas se a fonte não atualizar dentro do prazo esperado.' },
          ].map((item, i) => (
            <div key={item.step} className="flex gap-4">
              <div className="shrink-0 font-mono text-sm font-bold mt-0.5" style={{ color: 'var(--accent)' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div>
                <h4 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{item.step}</h4>
                <p className="mt-1 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{item.detail}</p>
              </div>
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
            Dados reais, proveniência rastreável.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Veja todas as fontes.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/dados" className="pulso-btn-dark">
              Ver fontes de dados
            </Link>
            <Link href="/recursos" className="pulso-btn-ghost">
              Voltar a recursos
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
