'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Radio, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import { api, setToken } from '@/lib/api';

// ---------------------------------------------------------------------------
// Estados brasileiros (27 UFs)
// ---------------------------------------------------------------------------
const BR_STATES = [
  { code: 'AC', name: 'Acre' },
  { code: 'AL', name: 'Alagoas' },
  { code: 'AP', name: 'Amapa' },
  { code: 'AM', name: 'Amazonas' },
  { code: 'BA', name: 'Bahia' },
  { code: 'CE', name: 'Ceara' },
  { code: 'DF', name: 'Distrito Federal' },
  { code: 'ES', name: 'Espirito Santo' },
  { code: 'GO', name: 'Goias' },
  { code: 'MA', name: 'Maranhao' },
  { code: 'MT', name: 'Mato Grosso' },
  { code: 'MS', name: 'Mato Grosso do Sul' },
  { code: 'MG', name: 'Minas Gerais' },
  { code: 'PA', name: 'Para' },
  { code: 'PB', name: 'Paraiba' },
  { code: 'PR', name: 'Parana' },
  { code: 'PE', name: 'Pernambuco' },
  { code: 'PI', name: 'Piaui' },
  { code: 'RJ', name: 'Rio de Janeiro' },
  { code: 'RN', name: 'Rio Grande do Norte' },
  { code: 'RS', name: 'Rio Grande do Sul' },
  { code: 'RO', name: 'Rondonia' },
  { code: 'RR', name: 'Roraima' },
  { code: 'SC', name: 'Santa Catarina' },
  { code: 'SP', name: 'Sao Paulo' },
  { code: 'SE', name: 'Sergipe' },
  { code: 'TO', name: 'Tocantins' },
] as const;

type Tab = 'login' | 'register';

// ---------------------------------------------------------------------------
// Componente de pagina
// ---------------------------------------------------------------------------
export default function LoginPage() {
  const router = useRouter();

  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>('login');

  // Shared state
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Login fields
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Register fields
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regOrganization, setRegOrganization] = useState('');
  const [regState, setRegState] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (!loginEmail.trim() || !loginPassword.trim()) {
      setError('Preencha todos os campos.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.auth.login({
        email: loginEmail.trim(),
        password: loginPassword,
      });
      setToken(response.access_token);
      router.push('/map');
    } catch (err: any) {
      if (err?.status === 401) {
        setError('E-mail ou senha incorretos.');
      } else if (err?.status === 422) {
        setError('Dados invalidos. Verifique o e-mail e a senha.');
      } else {
        setError(
          err?.message || 'Erro ao fazer login. Tente novamente mais tarde.'
        );
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (
      !regName.trim() ||
      !regEmail.trim() ||
      !regPassword.trim() ||
      !regOrganization.trim()
    ) {
      setError('Preencha todos os campos obrigatorios.');
      return;
    }

    if (regPassword.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.auth.register({
        email: regEmail.trim(),
        password: regPassword,
        name: regName.trim(),
        organization: regOrganization.trim(),
        state_code: regState || undefined,
      });
      setToken(response.access_token);
      router.push('/map');
    } catch (err: any) {
      if (err?.status === 409) {
        setError('Este e-mail ja esta cadastrado.');
      } else if (err?.status === 422) {
        setError('Dados invalidos. Verifique os campos e tente novamente.');
      } else {
        setError(
          err?.message || 'Erro ao criar conta. Tente novamente mais tarde.'
        );
      }
    } finally {
      setLoading(false);
    }
  }

  function switchTab(tab: Tab) {
    setActiveTab(tab);
    setError('');
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <Radio className="text-blue-500" size={32} />
          <span className="text-2xl font-bold tracking-tight text-slate-100">
            ENLACE
          </span>
        </div>

        {/* Card */}
        <div className="enlace-card p-0">
          {/* Tabs */}
          <div className="flex border-b border-slate-700">
            <button
              type="button"
              onClick={() => switchTab('login')}
              className={clsx(
                'flex-1 px-4 py-3 text-sm font-medium transition-colors',
                activeTab === 'login'
                  ? 'border-b-2 border-blue-500 text-blue-400'
                  : 'text-slate-400 hover:text-slate-200'
              )}
            >
              Entrar
            </button>
            <button
              type="button"
              onClick={() => switchTab('register')}
              className={clsx(
                'flex-1 px-4 py-3 text-sm font-medium transition-colors',
                activeTab === 'register'
                  ? 'border-b-2 border-blue-500 text-blue-400'
                  : 'text-slate-400 hover:text-slate-200'
              )}
            >
              Cadastrar
            </button>
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-6 mt-4 flex items-start gap-2 rounded-md border border-red-500/30 bg-red-900/20 px-3 py-2.5 text-sm text-red-400">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Login Form */}
          {activeTab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4 p-6">
              {/* Email */}
              <div>
                <label
                  htmlFor="login-email"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  E-mail
                </label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="seu@email.com"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className="enlace-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="login-password"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  Senha
                </label>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showLoginPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="Digite sua senha"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className="enlace-input w-full pr-10"
                    disabled={loading}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                    tabIndex={-1}
                    aria-label={
                      showLoginPassword ? 'Ocultar senha' : 'Mostrar senha'
                    }
                  >
                    {showLoginPassword ? (
                      <EyeOff size={16} />
                    ) : (
                      <Eye size={16} />
                    )}
                  </button>
                </div>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="enlace-btn-primary w-full flex items-center justify-center gap-2"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                {loading ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          )}

          {/* Register Form */}
          {activeTab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4 p-6">
              {/* Name */}
              <div>
                <label
                  htmlFor="reg-name"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  Nome completo
                </label>
                <input
                  id="reg-name"
                  type="text"
                  autoComplete="name"
                  placeholder="Seu nome completo"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  className="enlace-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Email */}
              <div>
                <label
                  htmlFor="reg-email"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  E-mail
                </label>
                <input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  placeholder="seu@email.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="enlace-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="reg-password"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  Senha
                </label>
                <div className="relative">
                  <input
                    id="reg-password"
                    type={showRegPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Minimo 6 caracteres"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    minLength={6}
                    className="enlace-input w-full pr-10"
                    disabled={loading}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowRegPassword(!showRegPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                    tabIndex={-1}
                    aria-label={
                      showRegPassword ? 'Ocultar senha' : 'Mostrar senha'
                    }
                  >
                    {showRegPassword ? (
                      <EyeOff size={16} />
                    ) : (
                      <Eye size={16} />
                    )}
                  </button>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  A senha deve ter pelo menos 6 caracteres.
                </p>
              </div>

              {/* Organization */}
              <div>
                <label
                  htmlFor="reg-org"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  Organizacao / ISP
                </label>
                <input
                  id="reg-org"
                  type="text"
                  autoComplete="organization"
                  placeholder="Nome da sua empresa ou ISP"
                  value={regOrganization}
                  onChange={(e) => setRegOrganization(e.target.value)}
                  className="enlace-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* State */}
              <div>
                <label
                  htmlFor="reg-state"
                  className="mb-1.5 block text-sm font-medium text-slate-300"
                >
                  Estado
                </label>
                <select
                  id="reg-state"
                  value={regState}
                  onChange={(e) => setRegState(e.target.value)}
                  className="enlace-input w-full"
                  disabled={loading}
                >
                  <option value="">Selecione o estado</option>
                  {BR_STATES.map((st) => (
                    <option key={st.code} value={st.code}>
                      {st.code} - {st.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="enlace-btn-primary w-full flex items-center justify-center gap-2"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                {loading ? 'Criando conta...' : 'Criar Conta'}
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-slate-500">
          Plataforma de inteligencia para provedores de internet brasileiros.
        </p>
      </div>
    </div>
  );
}
