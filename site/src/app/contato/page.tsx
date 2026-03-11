'use client';

import { useState, FormEvent } from 'react';
import Section from '@/components/ui/Section';
import { API_URL } from '@/lib/constants';

export default function ContatoPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus('sending');
    try {
      await fetch(`${API_URL}/api/v1/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, company, message }),
      });
      setStatus('sent');
    } catch {
      setStatus('error');
    }
  };

  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-2xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Contato
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Fale conosco.
          </h1>
          <p className="mt-3 text-base" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Dúvidas, demonstração ou parceria.
          </p>
        </div>
      </Section>

      {/* Form — Light */}
      <Section background="primary">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-2">
          <div>
            {status === 'sent' ? (
              <div className="p-6" style={{ border: '1px solid var(--accent)', background: 'var(--accent-subtle)' }}>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>Mensagem enviada</h3>
                <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>Responderemos em até 24 horas.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Nome</label>
                  <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className="pulso-input" placeholder="Seu nome" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>E-mail</label>
                  <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="pulso-input" placeholder="seu@email.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Empresa</label>
                  <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} className="pulso-input" placeholder="Nome da empresa" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Mensagem</label>
                  <textarea required value={message} onChange={(e) => setMessage(e.target.value)} className="pulso-input" rows={4} placeholder="Como podemos ajudar?" />
                </div>
                {status === 'error' && (
                  <p className="text-sm" style={{ color: 'var(--danger)' }}>Erro ao enviar. Tente novamente.</p>
                )}
                <button type="submit" disabled={status === 'sending'} className="pulso-btn-primary">
                  {status === 'sending' ? 'Enviando...' : 'Enviar mensagem'}
                </button>
              </form>
            )}
          </div>

          <div className="space-y-8">
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>WhatsApp</h3>
              <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>+55 (11) 9xxxx-xxxx</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>E-mail</h3>
              <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>contato@pulso.network</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Horário</h3>
              <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>Segunda a sexta, 9h-18h (Brasília)</p>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
