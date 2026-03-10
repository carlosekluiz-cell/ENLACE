import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Sobre — Pulso Network',
  description: 'De Telebras a 13.500 ISPs: a história das telecomunicações brasileiras e o Pulso.',
};

const timeline = [
  { year: '1972', title: 'Criação da Telebras', description: 'Monopólio estatal consolida dezenas de operadoras estaduais.' },
  { year: '1998', title: 'Privatização', description: 'Maior leilão da América Latina: R$ 22 bilhões. Nascem Vivo, Oi, Brasil Telecom.' },
  { year: '2001', title: 'ISPs regionais', description: 'Empreendedores locais começam a oferecer internet via rádio. Anatel cria outorga SCM.' },
  { year: '2010', title: 'Explosão do mercado', description: 'Fibra acessível + demanda reprimida. ISPs ultrapassam 5.000 licenciados.' },
  { year: '2016', title: 'Revolução da fibra', description: 'Maior expansão de FTTH do mundo em termos relativos. ISPs lideram.' },
  { year: '2024', title: '52% do mercado', description: '13.500+ ISPs. 52% dos 54M de acessos. R$ 50 bi/ano. O Pulso nasce.' },
];

const platformStats = [
  { value: '17M+', label: 'Registros de produção' },
  { value: '31', label: 'Pipelines automatizados' },
  { value: '45', label: 'Tabelas de dados' },
  { value: '9', label: 'Módulos de inteligência' },
  { value: '13.534', label: 'ISPs rastreados' },
  { value: '5.572', label: 'Municípios cobertos' },
];

export default function SobrePage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Sobre
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            De Telebras a 13.500 ISPs.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Por que o Pulso existe.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            O Brasil construiu o maior ecossistema de provedores regionais de internet do mundo.
            13.500+ empresas conectam 52% dos domicílios. O Pulso existe para dar inteligência de dados a esse ecossistema.
          </p>
        </div>
      </Section>

      {/* Timeline — Light */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          História
        </div>
        <h2 className="font-serif text-2xl font-bold mb-12" style={{ color: 'var(--text-primary)' }}>
          50 anos de telecomunicações
        </h2>
        <div className="max-w-3xl space-y-0">
          {timeline.map((event, i) => (
            <div
              key={event.year}
              className="relative pl-10 pb-10"
              style={{
                borderLeft: `1px solid ${i === timeline.length - 1 ? 'var(--accent)' : 'var(--border-strong)'}`,
              }}
            >
              <div
                className="absolute -left-[5px] top-0 h-2.5 w-2.5"
                style={{
                  background: i === timeline.length - 1 ? 'var(--accent)' : 'var(--border-strong)',
                }}
              />
              <div className="font-mono text-sm font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {event.year}
              </div>
              <h3 className="mt-1 text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {event.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {event.description}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* The problem — Subtle */}
      <Section background="subtle">
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
            O problema
          </div>
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            A lacuna de inteligência
          </h2>
          <div className="mt-6 space-y-4">
            <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Os dados existem — Anatel, IBGE, INMET, NASA. O problema é que estão dispersos em portais
              diferentes, formatos incompatíveis e lógicas distintas. Nenhum ISP com menos de 100.000
              assinantes tem equipe para integrar tudo isso.
            </p>
            <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Resultado: decisões de CAPEX de milhões baseadas em intuição e WhatsApp.
              O Pulso resolve isso.
            </p>
          </div>
        </div>
      </Section>

      {/* Platform Stats — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Números
        </div>
        <h2 className="font-serif text-2xl font-bold mb-10" style={{ color: 'var(--text-primary)' }}>
          A plataforma em dados
        </h2>
        <div className="grid grid-cols-2 gap-0 md:grid-cols-3" style={{ border: '1px solid var(--border)' }}>
          {platformStats.map((stat) => (
            <div
              key={stat.label}
              className="p-7"
              style={{
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="font-mono text-2xl font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                {stat.value}
              </div>
              <div className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                {stat.label}
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
            Dados reais, atualizados automaticamente.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Explore nossos recursos técnicos.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/recursos" className="pulso-btn-dark">
              Ver recursos
            </Link>
            <Link href="/cadastro" className="pulso-btn-ghost">
              Acessar plataforma
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
