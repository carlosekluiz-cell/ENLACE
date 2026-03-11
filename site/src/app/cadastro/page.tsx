'use client';

import { useState, FormEvent } from 'react';
import Section from '@/components/ui/Section';
import { API_URL, APP_URL, BR_STATES } from '@/lib/constants';

const SUBSCRIBER_RANGES = [
  'Até 1.000',
  '1.000 - 5.000',
  '5.000 - 15.000',
  '15.000 - 50.000',
  '50.000+',
];

export default function CadastroPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [state, setState] = useState('');
  const [subscribers, setSubscribers] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, organization: company, state_code: state || undefined }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Erro ao criar conta');
      }
      const data = await res.json();
      window.location.href = `${APP_URL}/login?token=${data.access_token}`;
    } catch (err: any) {
      setError(err.message || 'Erro ao criar conta. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section background="primary">
      <div className="mx-auto max-w-md">
        <div className="text-center mb-8">
          <div
            className="mx-auto flex h-10 w-10 items-center justify-center text-lg font-bold"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            P
          </div>
          <h1 className="mt-3 font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Criar conta
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Comece a usar o Pulso gratuitamente.
          </p>
        </div>

        <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Nome completo</label>
              <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className="pulso-input" placeholder="Seu nome" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>E-mail</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="pulso-input" placeholder="seu@email.com" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Empresa / ISP</label>
              <input type="text" required value={company} onChange={(e) => setCompany(e.target.value)} className="pulso-input" placeholder="Nome da empresa" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Estado</label>
              <select value={state} onChange={(e) => setState(e.target.value)} className="pulso-input">
                <option value="">Selecione</option>
                {BR_STATES.map((s) => (
                  <option key={s.code} value={s.code}>{s.code} - {s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Assinantes</label>
              <select value={subscribers} onChange={(e) => setSubscribers(e.target.value)} className="pulso-input">
                <option value="">Selecione</option>
                {SUBSCRIBER_RANGES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--text-primary)' }}>Senha</label>
              <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} className="pulso-input" placeholder="Mínimo 6 caracteres" />
            </div>

            {error && <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>}

            <button type="submit" disabled={loading} className="pulso-btn-primary w-full">
              {loading ? 'Criando conta...' : 'Criar conta'}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
          Já tem conta? <a href={`${APP_URL}/login`} style={{ color: 'var(--accent)' }}>Entrar</a>
        </p>
      </div>
    </Section>
  );
}
