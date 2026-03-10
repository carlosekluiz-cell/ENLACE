import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Preços — Pulso Network',
  description: 'Planos e preços do Pulso. Gratuito para sempre.',
};

const plans = [
  {
    name: 'Gratuito',
    price: 'R$ 0',
    period: '/mês',
    audience: 'Para conhecer a plataforma',
    features: ['Mapa interativo básico', '10 consultas/mês', '1 usuário', 'Dados de penetração'],
    cta: 'Começar',
    ctaLink: '/cadastro',
    highlight: false,
  },
  {
    name: 'Provedor',
    price: 'R$ 1.500',
    period: '/mês',
    audience: 'Até 10.000 assinantes',
    features: ['Consultas ilimitadas', '5 usuários', 'Expansão + Conformidade + Concorrência', 'Export PDF/Excel'],
    cta: 'Começar',
    ctaLink: '/cadastro',
    highlight: true,
  },
  {
    name: 'Profissional',
    price: 'R$ 5.000',
    period: '/mês',
    audience: '10.000 a 100.000 assinantes',
    features: ['20 usuários', 'Todos os 9 módulos', 'API REST', 'Suporte prioritário'],
    cta: 'Começar',
    ctaLink: '/cadastro',
    highlight: false,
  },
  {
    name: 'Empresa',
    price: 'Sob consulta',
    period: '',
    audience: '100.000+ assinantes',
    features: ['Usuários ilimitados', 'Dados proprietários', 'SSO/SAML + SLA 99,9%', 'Gerente de conta'],
    cta: 'Falar com vendas',
    ctaLink: '/contato',
    highlight: false,
  },
];

const faqs = [
  { q: 'O Gratuito é realmente gratuito?', a: 'Sim, permanente, sem cartão de crédito. Mapa interativo e dados básicos de penetração.' },
  { q: 'Posso cancelar a qualquer momento?', a: 'Sim. Mensal sem fidelidade. 15% desconto para pagamento anual.' },
  { q: 'De onde vêm os dados?', a: '12+ fontes públicas: Anatel, IBGE, NASA/SRTM, INMET, DataSUS, INEP e mais. Detalhes na página de Dados.' },
  { q: 'Posso importar meus dados?', a: 'Nos planos Profissional e Empresa. Upload de bases anonimizadas para cruzamento.' },
  { q: 'LGPD?', a: 'Dados públicos e agregados por município. Dados importados criptografados e segregados.' },
  { q: 'Qual a frequência de atualização dos dados?', a: 'Dados de telecom (Anatel) são atualizados diariamente. Dados econômicos (IBGE, BNDES) semanalmente. Dados geográficos e de infraestrutura (OSM, SRTM) mensalmente.' },
  { q: 'Os dados cobrem todo o Brasil?', a: 'Sim. Cobrimos todos os 5.572 municípios brasileiros, incluindo dados de 13.534 provedores, 6,4 milhões de segmentos de estrada e 37.325 torres de celular.' },
  { q: 'Tem API?', a: 'Sim, nos planos Profissional e Empresa. API REST com endpoints para todos os módulos, além de SSE (Server-Sent Events) para dados em tempo real.' },
  { q: 'Posso testar antes de assinar?', a: 'O plano Gratuito é permanente e sem limitação de tempo. Para experimentar funcionalidades dos planos pagos, oferecemos 14 dias gratuitos do plano Provedor.' },
  { q: 'Como funciona o suporte?', a: 'Provedor: suporte por e-mail em até 24h. Profissional: suporte prioritário em até 4h. Empresa: gerente de conta dedicado com canal direto.' },
  { q: 'Aceita PIX / boleto?', a: 'Sim. Aceitamos PIX, boleto bancário e cartão de crédito. Para pagamento anual, oferecemos 15% de desconto em qualquer modalidade.' },
  { q: 'Preciso de treinamento para usar?', a: 'A plataforma foi desenhada para ser intuitiva. Nos planos pagos, incluímos onboarding guiado com a equipe Pulso. O plano Empresa inclui treinamento presencial ou remoto para a equipe.' },
];

export default function PrecosPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-2xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Preços
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Proporcional ao tamanho{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>da sua operação.</span>
          </h1>
        </div>
      </Section>

      {/* Plans — Light */}
      <Section background="primary">
        <div className="grid grid-cols-1 gap-0 md:grid-cols-2 lg:grid-cols-4" style={{ border: '1px solid var(--border)' }}>
          {plans.map((plan) => (
            <div
              key={plan.name}
              className="p-6 flex flex-col"
              style={{
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border)',
                borderTop: plan.highlight ? '3px solid var(--accent)' : '3px solid transparent',
              }}
            >
              <div>
                <div
                  className="text-sm font-semibold"
                  style={{ color: plan.highlight ? 'var(--accent)' : 'var(--text-primary)' }}
                >
                  {plan.name}
                </div>
                <div className="mt-3">
                  <span className="font-mono text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                    {plan.price}
                  </span>
                  <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    {plan.period}
                  </span>
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {plan.audience}
                </div>
              </div>

              <ul className="mt-5 space-y-2 flex-1">
                {plan.features.map((feature) => (
                  <li key={feature} className="text-sm flex items-start gap-2" style={{ color: 'var(--text-secondary)' }}>
                    <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                    {feature}
                  </li>
                ))}
              </ul>

              <div className="mt-6">
                <Link
                  href={plan.ctaLink}
                  className={`w-full text-center ${plan.highlight ? 'pulso-btn-primary' : 'pulso-btn-outline'}`}
                >
                  {plan.cta}
                </Link>
              </div>
            </div>
          ))}
        </div>

        <p className="mt-4 font-mono text-xs text-center" style={{ color: 'var(--text-muted)' }}>
          Sem fidelidade. Cancelamento a qualquer momento.
        </p>
      </Section>

      {/* FAQ — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          FAQ
        </div>
        <h2 className="font-serif text-2xl font-bold mb-10" style={{ color: 'var(--text-primary)' }}>
          Perguntas frequentes
        </h2>
        <div className="max-w-3xl space-y-0">
          {faqs.map((faq) => (
            <div key={faq.q} className="py-5" style={{ borderBottom: '1px solid var(--border)' }}>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{faq.q}</h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{faq.a}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)' }}>
            Comece gratuitamente.
          </h2>
          <p className="mt-2 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Sem cartão de crédito. Dados reais desde o primeiro acesso.
          </p>
          <div className="mt-6">
            <Link href="/cadastro" className="pulso-btn-dark">
              Criar conta gratuita
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
