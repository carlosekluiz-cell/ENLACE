import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Matriz de Funcionalidades — Pulso Network',
  description: '9 módulos x 4 tiers: funcionalidades detalhadas por nível de assinatura.',
};

const tierOverview = [
  { tier: 'Gratuito', price: 'R$0/mês', audience: 'Exploração', users: '1', contract: '-' },
  { tier: 'Provedor', price: 'R$1.500/mês', audience: 'ISPs 1K-10K subs', users: '3', contract: 'Mensal' },
  { tier: 'Profissional', price: 'R$5.000/mês', audience: 'ISPs 10K-100K subs', users: '10', contract: 'Anual' },
  { tier: 'Empresa', price: 'Sob consulta', audience: 'Operadoras, fundos', users: 'Ilimitado', contract: 'Anual' },
];

type Feature = { name: string; free: string; provider: string; pro: string; enterprise: string };

const modules: { title: string; number: string; features: Feature[] }[] = [
  {
    title: 'Inteligência de Mercado',
    number: '01',
    features: [
      { name: 'Resumo de mercado por município', free: 'Somente leitura', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Histórico de assinantes', free: '3 meses', provider: '12 meses', pro: '60 meses', enterprise: '60 meses' },
      { name: 'Análise de concorrentes (HHI, share)', free: 'Top 3', provider: 'Completo', pro: 'Completo', enterprise: 'Completo' },
      { name: 'Heatmap de penetração/fibra', free: 'Visual', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Selos de qualidade RQual/IQS', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tendências de crescimento', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Exportação de dados', free: '—', provider: 'CSV', pro: 'CSV, XLSX, PDF', enterprise: 'CSV, XLSX, PDF, API' },
    ],
  },
  {
    title: 'Expansão e Oportunidades',
    number: '02',
    features: [
      { name: 'Ranking de oportunidades', free: 'Top 10', provider: 'Top 100', pro: 'Todos (5.570)', enterprise: 'Todos + filtros' },
      { name: 'Score detalhado (5 dimensões)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Análise financeira (NPV, IRR, payback)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Rota de fibra (6,4M segmentos)', free: '—', provider: '1/mês', pro: '10/mês', enterprise: 'Ilimitado' },
      { name: 'Bill of Materials (BOM)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Estações base no mapa', free: 'Visual', provider: '✓', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Concorrência',
    number: '03',
    features: [
      { name: 'Índice HHI de concentração', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Market share por provedor', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Tendência (growing/stable/declining)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Nível de ameaça', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Provider breakdown + tecnologia', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Alertas de mudança de mercado', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Saúde da Rede',
    number: '04',
    features: [
      { name: 'Risco climático + previsão 7 dias', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Benchmark de qualidade vs. pares', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Comparação nacional/estadual', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Prioridades de manutenção', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Calendário sazonal (12 meses)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Detecção de outlier e risco de churn', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Conformidade Regulatória',
    number: '05',
    features: [
      { name: 'Dashboard de conformidade', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Impacto Norma no. 4 (ICMS)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Impacto multi-estado (blended ICMS)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Check de licenciamento (5K subs)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Qualidade vs. thresholds Anatel', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Calendário de deadlines', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
      { name: 'Relatório de compliance (export)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Projeto RF',
    number: '06',
    features: [
      { name: 'Cobertura RF com SRTM 30m', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Modelos ITU-R (6 modelos)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'P.676 (atmosfera) + P.838 (chuva)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Otimização de posicionamento', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Link budget microwave', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Perfil de terreno', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'CAPEX por torre', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Corredor de co-locação', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Conectividade Rural',
    number: '07',
    features: [
      { name: 'Design híbrido (backhaul + last mile)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Sistema solar off-grid', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Matching de financiamento (FUST, BNDES)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Perfil de demanda comunitária', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Design de travessia de rio', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Custos por bioma', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
  {
    title: 'Inteligência M&A',
    number: '08',
    features: [
      { name: 'Avaliação por múltiplo de assinante', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Avaliação por múltiplo de receita', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Avaliação DCF', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Descoberta de targets', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Score estratégico e financeiro', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Preparação para venda', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Overview M&A por estado', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Contratos governamentais por provedor', free: '—', provider: '—', pro: '—', enterprise: '✓' },
    ],
  },
  {
    title: 'Inteligência Satelital',
    number: '09',
    features: [
      { name: 'Índices anuais (NDVI, NDBI, MNDWI, BSI)', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Crescimento urbano vs. população', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Ranking por crescimento', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Metadata de compositos Sentinel-2', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
      { name: 'Computação on-demand (GEE)', free: '—', provider: '—', pro: '—', enterprise: '✓' },
      { name: 'Tiles de overlay satelital', free: '—', provider: '—', pro: '✓', enterprise: '✓' },
    ],
  },
];

const crossCutting: Feature[] = [
  { name: 'Acesso API REST', free: '—', provider: '—', pro: 'Rate limited', enterprise: 'Ilimitado' },
  { name: 'Relatórios PDF/CSV/XLSX', free: '—', provider: '5/mês', pro: '50/mês', enterprise: 'Ilimitado' },
  { name: 'SSE (eventos em tempo real)', free: '—', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Busca geográfica e raio', free: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Boundaries GeoJSON por município', free: '✓', provider: '✓', pro: '✓', enterprise: '✓' },
  { name: 'Usuários por conta', free: '1', provider: '3', pro: '10', enterprise: 'Ilimitado' },
  { name: 'Suporte', free: 'FAQ', provider: 'Email (48h)', pro: 'Email (24h) + Chat', enterprise: 'Dedicado + SLA' },
  { name: 'SLA de uptime', free: '—', provider: '99,0%', pro: '99,5%', enterprise: '99,9%' },
  { name: 'White-label', free: '—', provider: '—', pro: '—', enterprise: '✓' },
];

function CellContent({ value }: { value: string }) {
  if (value === '✓') return <span style={{ color: 'var(--success)' }}>&#10003;</span>;
  if (value === '—') return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span>{value}</span>;
}

function FeatureTable({ features }: { features: Feature[] }) {
  return (
    <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Funcionalidade</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>Gratuito</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Provedor</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--accent)' }}>Profissional</th>
            <th className="px-3 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Empresa</th>
          </tr>
        </thead>
        <tbody>
          {features.map((f) => (
            <tr key={f.name} style={{ borderBottom: '1px solid var(--border)' }}>
              <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{f.name}</td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.free} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.provider} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.pro} /></td>
              <td className="px-3 py-3 text-center text-xs" style={{ color: 'var(--text-secondary)' }}><CellContent value={f.enterprise} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FuncionalidadesPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Funcionalidades
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            9 módulos. 4 tiers.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Cada funcionalidade detalhada.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Todos os tiers acessam os mesmos 17M+ registros reais. A diferença está na profundidade
            de análise e ferramentas disponíveis.
          </p>
        </div>
      </Section>

      {/* Tier Overview — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Tiers
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Visão geral dos planos
        </h2>
        <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Tier</th>
                <th className="px-4 py-3 text-left font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Preço</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Público</th>
                <th className="px-4 py-3 text-center font-medium" style={{ color: 'var(--text-primary)' }}>Usuários</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Contrato</th>
              </tr>
            </thead>
            <tbody>
              {tierOverview.map((t) => (
                <tr key={t.tier} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{t.tier}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: 'var(--accent)' }}>{t.price}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{t.audience}</td>
                  <td className="px-4 py-3 text-center font-mono" style={{ color: 'var(--text-primary)' }}>{t.users}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{t.contract}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Modules — alternating backgrounds */}
      {modules.map((mod, i) => (
        <Section key={mod.number} background={i % 2 === 0 ? 'subtle' : 'surface'}>
          <div className="flex items-baseline gap-3 mb-6">
            <span className="font-mono text-sm font-bold" style={{ color: 'var(--accent)' }}>{mod.number}</span>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>{mod.title}</h2>
          </div>
          <FeatureTable features={mod.features} />
        </Section>
      ))}

      {/* Cross-cutting — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Transversal
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Funcionalidades transversais
        </h2>
        <FeatureTable features={crossCutting} />
      </Section>

      {/* Notes — Subtle */}
      <Section background="subtle">
        <div className="max-w-3xl space-y-3">
          {[
            'Todos os tiers incluem autenticação JWT e dados atualizados pelos 31 pipelines.',
            'O tier Gratuito é projetado para demonstrar valor e converter para tiers pagos.',
            'Preços em BRL. Provedor: cobrança mensal. Profissional e Empresa: anual com desconto de 15%.',
            'API rate limits: Profissional = 100 req/min, Empresa = sem limite.',
            'Todos os tiers acessam os mesmos dados reais (17M+ registros).',
          ].map((note, i) => (
            <p key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <span className="font-mono shrink-0" style={{ color: 'var(--accent)' }}>{i + 1}.</span>
              {note}
            </p>
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
            Comece com o tier gratuito.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Upgrade quando quiser.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Ver preços
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
