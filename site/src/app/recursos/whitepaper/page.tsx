import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Whitepaper',
  description: 'Como a Pulso Network transforma dados públicos em telecom tech e inteligência decisional para provedores de internet no Brasil.',
  alternates: { canonical: 'https://pulso.network/recursos/whitepaper' },
};

/* ── Every number below comes from production database queries (2026-03-15) ── */

const marketContext = [
  { value: '13.534', label: 'ISPs ativos reportando à Anatel' },
  { value: '5.570', label: 'Municípios com dados de banda larga' },
  { value: '27', label: 'Estados cobertos' },
  { value: '128 mil', label: 'Outorgas de telecomunicações mapeadas' },
];

const platformScale = [
  { value: '19M+', label: 'Registros cruzados' },
  { value: '25', label: 'Módulos de análise' },
  { value: '38+', label: 'Fontes de dados públicos' },
  { value: '37', label: 'Períodos históricos' },
];

const painPoints = [
  {
    title: 'Expansão sem dados',
    description:
      'ISPs investem milhões em CAPEX para expandir rede sem visibilidade real da concorrência, demanda ou infraestrutura existente no município-alvo. Decisões baseadas em feeling, não em dados.',
  },
  {
    title: 'Risco regulatório invisível',
    description:
      'Exigências de qualidade da Anatel, obrigações de cobertura 5G, conformidade SCM e prazos de licenciamento criam risco de multas para ISPs que não monitoram ativamente.',
  },
  {
    title: 'M&A sem inteligência integrada',
    description:
      'O mercado brasileiro de ISPs está em consolidação acelerada. Compradores e vendedores negociam sem acesso centralizado a dados societários, operacionais e regulatórios dos alvos.',
  },
  {
    title: 'Fragmentação de fontes',
    description:
      'Os dados necessários existem — Anatel, IBGE, Receita Federal, Diários Oficiais, INMET, DATASUS, INEP — mas estão espalhados em dezenas de portais com formatos incompatíveis.',
  },
];

const dataCategories = [
  {
    category: 'Mercado & Concorrência',
    description: 'Assinantes por provedor, município e tecnologia. Análise de concentração (HHI). Dinâmica competitiva em 37 períodos históricos.',
    verified: '4,3M registros de assinantes · 206K análises competitivas',
  },
  {
    category: 'Qualidade & Reputação',
    description: 'Selos de qualidade Anatel (ouro/prata/bronze). Reclamações de consumidores. Indicadores de desempenho por provedor.',
    verified: '88.619 selos de qualidade · 463K reclamações · 6,1M indicadores',
  },
  {
    category: 'Regulatório & Conformidade',
    description: 'Indicadores regulatórios, outorgas, selos de qualidade e conformidade Anatel.',
    verified: '128K outorgas mapeadas · 88.619 selos de qualidade',
  },
  {
    category: 'Infraestrutura & Cobertura',
    description: 'Torres e estações base. Segmentos rodoviários para modelagem de fibra. Velocidade de banda larga por município.',
    verified: '37.325 estações base · 6,5M segmentos de rodovias',
  },
  {
    category: 'Inteligência Territorial',
    description: 'Escolas e unidades de saúde para análise de gaps sociais. Indicadores econômicos municipais. Menções em diários oficiais.',
    verified: '180K escolas · 573K unidades de saúde · 61K menções em gazetas',
  },
  {
    category: 'Regulatório & Espectro',
    description: 'Licenças de espectro. Obrigações de cobertura 5G. FUST (Fundo de Universalização). Conformidade regulatória.',
    verified: '4.602 registros FUST · Monitoramento contínuo de obrigações',
  },
];

const useCases = [
  {
    title: 'Para ISPs em expansão',
    description: 'Identifique municípios com alta demanda e baixa competição. Cruze dados de assinantes, infraestrutura existente e indicadores econômicos antes de investir.',
    outcome: 'Decisões de CAPEX baseadas em dados reais, não em estimativas.',
  },
  {
    title: 'Para fundos de investimento',
    description: 'Inteligência M&A com dados societários, regulatórios e operacionais. Análise de concentração de mercado e posicionamento competitivo de alvos de aquisição.',
    outcome: 'Dossiers completos em minutos, não em semanas.',
  },
  {
    title: 'Para consultorias de telecom',
    description: 'Acesse 37 períodos históricos de dinâmica competitiva. Análise de qualidade regulatória. Cruzamento de dados de múltiplas fontes em uma interface.',
    outcome: 'Relatórios fundamentados em dados públicos verificáveis.',
  },
  {
    title: 'Para equipes de compliance',
    description: 'Monitore obrigações regulatórias, selos de qualidade Anatel e indicadores de conformidade. Alertas sobre mudanças no panorama competitivo do seu mercado.',
    outcome: 'Conformidade proativa, não reativa.',
  },
];

export default function WhitepaperPage() {
  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Whitepaper
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Inteligência decisional{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>para telecomunicações no Brasil</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            A Pulso Network integra e cruza dados de 38+ fontes públicas para transformar informação
            fragmentada em inteligência acionável para provedores de internet, investidores e consultorias.
          </p>
        </div>

        <div className="mt-10 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ border: '1px solid var(--border-dark)' }}>
          {marketContext.map((stat) => (
            <div key={stat.label} className="p-5" style={{ borderRight: '1px solid var(--border-dark)' }}>
              <div className="font-mono text-xl font-bold" style={{ color: 'var(--accent)' }}>{stat.value}</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>{stat.label}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* O Problema */}
      <Section background="primary">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            O problema
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Dados existem. Inteligência, não.
          </h2>
          <p className="mt-3 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            O Brasil tem um dos mercados de telecomunicações mais dinâmicos do mundo, com mais de 13 mil ISPs
            ativos competindo em 5.570 municípios. Os dados para tomar boas decisões são públicos — Anatel, IBGE,
            Receita Federal, DATASUS, INEP, INMET e dezenas de outras fontes. O problema é que ninguém
            os cruza de forma sistemática.
          </p>
        </div>
        <div className="mt-8 grid grid-cols-1 gap-0 md:grid-cols-2" style={{ border: '1px solid var(--border)' }}>
          {painPoints.map((point) => (
            <div key={point.title} className="p-6" style={{ borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{point.title}</h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{point.description}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Escala da plataforma */}
      <Section background="subtle">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Escala
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            O que a Pulso Network integra
          </h2>
          <p className="mt-3 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            A plataforma coleta, normaliza e cruza dados de fontes públicas oficiais em uma base de dados
            unificada. Cada número abaixo é verificável e auditável.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-0 md:grid-cols-4" style={{ border: '1px solid var(--border)' }}>
          {platformScale.map((stat) => (
            <div key={stat.label} className="p-5" style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-primary)' }}>
              <div className="font-mono text-xl font-bold" style={{ color: 'var(--accent)' }}>{stat.value}</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>{stat.label}</div>
            </div>
          ))}
        </div>

        <div className="mt-8 space-y-0" style={{ border: '1px solid var(--border)' }}>
          {dataCategories.map((cat) => (
            <div key={cat.category} className="p-6" style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{cat.category}</h3>
                </div>
                <div>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{cat.description}</p>
                </div>
                <div>
                  <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{cat.verified}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Fontes */}
      <Section background="primary">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Fontes de dados
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            100% dados públicos. Zero scraping privado.
          </h2>
          <p className="mt-3 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            Toda informação na plataforma vem de fontes públicas oficiais. Isso significa que cada dado
            é verificável, auditável e legalmente utilizável para decisões empresariais.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            'Anatel', 'IBGE', 'Receita Federal', 'BNDES',
            'Diários Oficiais', 'DATASUS', 'INEP', 'PeeringDB',
            'INMET', 'CAGED', 'SNIS', 'BNDES',
            'ANP', 'PeeringDB', 'IX.br', 'OpenStreetMap',
          ].map((source) => (
            <div key={source} className="p-3 text-center text-sm font-medium" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
              {source}
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs" style={{ color: 'var(--text-muted)' }}>
          E mais de 20 outras fontes públicas. Lista completa disponível na{' '}
          <Link href="/recursos/dados-confianca" style={{ color: 'var(--accent)' }}>documentação de confiança dos dados</Link>.
        </p>
      </Section>

      {/* Casos de uso */}
      <Section background="surface">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Para quem
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Quem usa e como usa
          </h2>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-0 md:grid-cols-2" style={{ border: '1px solid var(--border)' }}>
          {useCases.map((uc) => (
            <div key={uc.title} className="p-6" style={{ borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{uc.title}</h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{uc.description}</p>
              <p className="mt-3 text-xs font-medium" style={{ color: 'var(--accent)' }}>{uc.outcome}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Diferencial */}
      <Section background="subtle">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Diferencial
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            O que ninguém mais faz
          </h2>
          <p className="mt-3 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            Existem ferramentas de telecom, de M&A, de compliance e de geoprocessamento. Nenhuma cruza
            todas essas dimensões em uma plataforma única, com dados atualizados automaticamente e
            cobertura nacional ao nível de município.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {[
            {
              title: 'Cruzamento de dados',
              description: 'Dados regulatórios, de qualidade e de mercado cruzados por provedor e por município. Relações que só aparecem quando você conecta as fontes.',
              example: '88.619 selos de qualidade cruzados com speedtest e assinantes por município',
            },
            {
              title: 'Cobertura municipal completa',
              description: 'Cada um dos 5.570 municípios com dados de banda larga tem perfil completo: concorrência, infraestrutura, indicadores econômicos e sociais.',
              example: '37 períodos de histórico competitivo por município',
            },
            {
              title: 'Atualização contínua',
              description: 'Dados coletados e processados automaticamente — diariamente, semanalmente e mensalmente. A plataforma reflete a realidade atual do mercado.',
              example: 'Dados de assinantes de jan/2023 a jan/2026',
            },
          ].map((diff) => (
            <div key={diff.title} className="p-6" style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-primary)' }}>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{diff.title}</h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{diff.description}</p>
              <p className="mt-3 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{diff.example}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Modelo de acesso */}
      <Section background="primary">
        <div className="max-w-3xl">
          <div className="mb-2 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            Acesso
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Modelo de acesso por tiers
          </h2>
          <p className="mt-3 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-secondary)' }}>
            A plataforma opera em modelo SaaS com tiers progressivos, desde acesso gratuito para exploração
            até planos enterprise para operadoras e fundos de investimento. Estamos em fase de lista de espera.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-0 md:grid-cols-5" style={{ border: '1px solid var(--border)' }}>
          {[
            { tier: 'Gratuito', audience: 'Exploração', users: '1 usuário' },
            { tier: 'Starter', audience: 'Análises pontuais', users: '1 usuário' },
            { tier: 'Provedor', audience: 'ISPs regionais', users: 'Até 5 usuários' },
            { tier: 'Profissional', audience: 'ISPs de médio porte', users: 'Até 20 usuários' },
            { tier: 'Empresa', audience: 'Operadoras e fundos', users: 'Ilimitado' },
          ].map((t) => (
            <div key={t.tier} className="p-5 text-center" style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{t.tier}</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{t.audience}</div>
              <div className="mt-2 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{t.users}</div>
            </div>
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
            19 milhões de registros cruzados.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Uma plataforma.</span>
          </h2>
          <p className="mt-4 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Entre na lista de espera para acesso antecipado à plataforma.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/dados" className="pulso-btn-ghost">
              Ver fontes de dados
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
