'use client';

import { useState, FormEvent } from 'react';
import Section from '@/components/ui/Section';
import { API_URL } from '@/lib/constants';

export default function WaitlistPage() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/public/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          name: name.trim() || undefined,
          company: company.trim() || undefined,
          role: role || undefined,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Erro ao registrar.');
      }
      await res.json();
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Erro ao registrar. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-2xl mx-auto text-center">
          <div
            className="inline-block mb-6 px-3 py-1 font-mono text-xs uppercase tracking-wider"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Pre-Launch
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Inteligência telecom{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>como nunca existiu no Brasil.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-xl mx-auto" style={{ color: 'var(--text-on-dark-secondary)' }}>
            38+ fontes de dados cruzadas. 5.570 municípios. 13.500+ provedores mapeados.
            Entre na lista de espera para acesso antecipado.
          </p>
        </div>

        {/* Stats */}
        <div
          className="mt-12 grid grid-cols-2 gap-0 md:grid-cols-4 max-w-3xl mx-auto"
          style={{ borderTop: '1px solid var(--border-dark-strong)' }}
        >
          {[
            { value: '38+', label: 'Fontes de dados' },
            { value: '28M+', label: 'Data points' },
            { value: '25', label: 'Módulos' },
            { value: '5.570', label: 'Municípios' },
          ].map((stat) => (
            <div key={stat.label} className="py-5 pr-6 text-center">
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

      {/* Form */}
      <Section background="primary">
        <div className="mx-auto max-w-md">
          {submitted ? (
            <div className="text-center py-12">
              <div
                className="mx-auto flex h-16 w-16 items-center justify-center text-3xl font-bold mb-6"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                &#10003;
              </div>
              <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                Você está na lista!
              </h2>
              <p className="mt-3 text-base" style={{ color: 'var(--text-secondary)' }}>
                Vamos avisar por e-mail quando lançarmos.
              </p>
            </div>
          ) : (
            <>
              <div className="text-center mb-8">
                <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                  Lista de espera
                </div>
                <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                  Garanta acesso antecipado
                </h2>
                <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Seja avisado quando a plataforma estiver pronta.
                </p>
              </div>

              <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>
                      E-mail *
                    </label>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="pulso-input"
                      placeholder="seu@email.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>
                      Nome
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="pulso-input"
                      placeholder="Seu nome"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>
                      Empresa / ISP
                    </label>
                    <input
                      type="text"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      className="pulso-input"
                      placeholder="Nome da empresa"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>
                      Eu sou...
                    </label>
                    <select value={role} onChange={(e) => setRole(e.target.value)} className="pulso-input">
                      <option value="">Selecione</option>
                      <option value="isp_owner">Dono / sócio de provedor</option>
                      <option value="isp_manager">Gerente / diretor de ISP</option>
                      <option value="isp_tech">Técnico / engenheiro de ISP</option>
                      <option value="consultant">Consultor telecom</option>
                      <option value="investor">Investidor / M&A</option>
                      <option value="vendor">Fornecedor / fabricante</option>
                      <option value="other">Outro</option>
                    </select>
                  </div>

                  {error && <p className="text-sm" style={{ color: 'var(--danger, #ef4444)' }}>{error}</p>}

                  <button type="submit" disabled={loading} className="pulso-btn-primary w-full">
                    {loading ? 'Registrando...' : 'Entrar na lista de espera'}
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      </Section>

      {/* What you get */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          O que está vindo
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Por que entrar na lista
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-0" style={{ border: '1px solid var(--border)' }}>
          {[
            {
              title: 'Market share por município',
              desc: 'Saiba exatamente quem são seus concorrentes em cada cidade — assinantes, tecnologias e tendências.',
            },
            {
              title: 'Due diligence automatizada',
              desc: 'Dívida fiscal, sócios, reclamações, sanções e selos de qualidade de qualquer provedor em segundos.',
            },
            {
              title: 'Expansão baseada em dados',
              desc: 'Identifique municípios com baixa concorrência, alta demanda e infraestrutura de backhaul disponível.',
            },
            {
              title: 'Conformidade RGST',
              desc: 'Checklist automatizado do regulamento de prestação de serviços de telecomunicações.',
            },
            {
              title: 'Risco climático',
              desc: 'Mapeamento de risco meteorológico para antenas, rotas de fibra e estações de energia.',
            },
            {
              title: 'Cruzamento de 38+ fontes',
              desc: 'Anatel, IBGE, PGFN, Receita Federal, PeeringDB, BNDES, consumidor.gov.br e mais — tudo cruzado.',
            },
          ].map((item, i) => (
            <div
              key={item.title}
              className="p-6"
              style={{
                background: 'var(--bg-surface)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div className="font-mono text-xs mb-2" style={{ color: 'var(--accent)' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                {item.title}
              </h3>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Bottom CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>
            Não perca o lançamento.
          </h2>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Deixe seu e-mail e seja o primeiro a saber.
          </p>
          <div className="mt-6">
            <button
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              className="pulso-btn-dark"
            >
              Entrar na lista de espera
            </button>
          </div>
        </div>
      </Section>
    </>
  );
}
