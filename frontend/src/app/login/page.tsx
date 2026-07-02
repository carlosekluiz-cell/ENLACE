'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Radio, Eye, EyeOff, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import { api, setToken } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

// ---------------------------------------------------------------------------
// Estados brasileiros (27 UFs)
// ---------------------------------------------------------------------------
const BR_STATES = [
  { code: 'AC', name: 'Acre' },
  { code: 'AL', name: 'Alagoas' },
  { code: 'AP', name: 'Amapá' },
  { code: 'AM', name: 'Amazonas' },
  { code: 'BA', name: 'Bahia' },
  { code: 'CE', name: 'Ceará' },
  { code: 'DF', name: 'Distrito Federal' },
  { code: 'ES', name: 'Espírito Santo' },
  { code: 'GO', name: 'Goiás' },
  { code: 'MA', name: 'Maranhão' },
  { code: 'MT', name: 'Mato Grosso' },
  { code: 'MS', name: 'Mato Grosso do Sul' },
  { code: 'MG', name: 'Minas Gerais' },
  { code: 'PA', name: 'Pará' },
  { code: 'PB', name: 'Paraíba' },
  { code: 'PR', name: 'Paraná' },
  { code: 'PE', name: 'Pernambuco' },
  { code: 'PI', name: 'Piauí' },
  { code: 'RJ', name: 'Rio de Janeiro' },
  { code: 'RN', name: 'Rio Grande do Norte' },
  { code: 'RS', name: 'Rio Grande do Sul' },
  { code: 'RO', name: 'Rondônia' },
  { code: 'RR', name: 'Roraima' },
  { code: 'SC', name: 'Santa Catarina' },
  { code: 'SP', name: 'São Paulo' },
  { code: 'SE', name: 'Sergipe' },
  { code: 'TO', name: 'Tocantins' },
] as const;

const CO_DEPARTMENTS = [
  { code: '05', name: 'Antioquia' },
  { code: '08', name: 'Atlántico' },
  { code: '11', name: 'Bogotá D.C.' },
  { code: '13', name: 'Bolívar' },
  { code: '15', name: 'Boyacá' },
  { code: '17', name: 'Caldas' },
  { code: '18', name: 'Caquetá' },
  { code: '19', name: 'Cauca' },
  { code: '20', name: 'Cesar' },
  { code: '23', name: 'Córdoba' },
  { code: '25', name: 'Cundinamarca' },
  { code: '27', name: 'Chocó' },
  { code: '41', name: 'Huila' },
  { code: '44', name: 'La Guajira' },
  { code: '47', name: 'Magdalena' },
  { code: '50', name: 'Meta' },
  { code: '52', name: 'Nariño' },
  { code: '54', name: 'Norte de Santander' },
  { code: '63', name: 'Quindío' },
  { code: '66', name: 'Risaralda' },
  { code: '68', name: 'Santander' },
  { code: '70', name: 'Sucre' },
  { code: '73', name: 'Tolima' },
  { code: '76', name: 'Valle del Cauca' },
  { code: '81', name: 'Arauca' },
  { code: '85', name: 'Casanare' },
  { code: '86', name: 'Putumayo' },
  { code: '88', name: 'San Andrés y Providencia' },
  { code: '91', name: 'Amazonas' },
  { code: '94', name: 'Guainía' },
  { code: '95', name: 'Guaviare' },
  { code: '97', name: 'Vaupés' },
  { code: '99', name: 'Vichada' },
] as const;

type Tab = 'login' | 'register';

// ---------------------------------------------------------------------------
// Componente de página
// ---------------------------------------------------------------------------
export default function LoginPage() {
  const router = useRouter();
  const { login: authLogin } = useAuth();

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
  const [regCountry, setRegCountry] = useState('BR');
  const [showRegPassword, setShowRegPassword] = useState(false);

  const isCO = regCountry === 'CO';

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
      await authLogin(response.access_token);
      router.push('/');
    } catch (err: any) {
      if (err?.status === 401) {
        setError('E-mail ou senha incorretos.');
      } else if (err?.status === 422) {
        setError('Dados inválidos. Verifique o e-mail e a senha.');
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
      setError(isCO ? 'Complete todos los campos obligatorios.' : 'Preencha todos os campos obrigatórios.');
      return;
    }

    if (regPassword.length < 6) {
      setError(isCO ? 'La contraseña debe tener al menos 6 caracteres.' : 'A senha deve ter pelo menos 6 caracteres.');
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
        country_code: regCountry,
      });
      localStorage.setItem('pulso_country', regCountry);
      if (isCO) localStorage.setItem('pulso_language', 'es');
      await authLogin(response.access_token);
      router.push('/');
    } catch (err: any) {
      if (err?.status === 409) {
        setError(isCO ? 'Este correo ya está registrado.' : 'Este e-mail já está cadastrado.');
      } else if (err?.status === 422) {
        setError(isCO ? 'Datos inválidos. Verifique los campos e intente de nuevo.' : 'Dados inválidos. Verifique os campos e tente novamente.');
      } else {
        setError(
          err?.message || (isCO ? 'Error al crear cuenta. Intente más tarde.' : 'Erro ao criar conta. Tente novamente mais tarde.')
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
    <div
      className="flex min-h-screen items-center justify-center px-4 py-12"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <Radio style={{ color: 'var(--accent)' }} size={32} />
          <span className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Pulso
          </span>
        </div>

        {/* Card */}
        <div className="pulso-card p-0">
          {/* Tabs */}
          <div className="flex" style={{ borderBottom: '1px solid var(--border)' }}>
            <button
              type="button"
              onClick={() => switchTab('login')}
              className="flex-1 px-4 py-3 text-sm font-medium transition-colors"
              style={{
                borderBottom: activeTab === 'login' ? '2px solid var(--accent)' : '2px solid transparent',
                color: activeTab === 'login' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              Entrar
            </button>
            <button
              type="button"
              onClick={() => switchTab('register')}
              className="flex-1 px-4 py-3 text-sm font-medium transition-colors"
              style={{
                borderBottom: activeTab === 'register' ? '2px solid var(--accent)' : '2px solid transparent',
                color: activeTab === 'register' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              Cadastrar
            </button>
          </div>

          {/* Error message */}
          {error && (
            <div
              className="mx-6 mt-4 flex items-start gap-2 rounded-md px-3 py-2.5 text-sm"
              style={{
                border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
                backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                color: 'var(--danger)',
              }}
            >
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
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
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
                  className="pulso-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="login-password"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
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
                    className="pulso-input w-full pr-10"
                    disabled={loading}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 hover:opacity-80"
                    style={{ color: 'var(--text-secondary)' }}
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
                className="pulso-btn-primary w-full flex items-center justify-center gap-2"
              >
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
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {isCO ? 'Nombre completo' : 'Nome completo'}
                </label>
                <input
                  id="reg-name"
                  type="text"
                  autoComplete="name"
                  placeholder={isCO ? 'Su nombre completo' : 'Seu nome completo'}
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  className="pulso-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Email */}
              <div>
                <label
                  htmlFor="reg-email"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {isCO ? 'Correo electrónico' : 'E-mail'}
                </label>
                <input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  placeholder={isCO ? 'tu@correo.com' : 'seu@email.com'}
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="pulso-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="reg-password"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {isCO ? 'Contraseña' : 'Senha'}
                </label>
                <div className="relative">
                  <input
                    id="reg-password"
                    type={showRegPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Mínimo 6 caracteres"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    minLength={6}
                    className="pulso-input w-full pr-10"
                    disabled={loading}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowRegPassword(!showRegPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 hover:opacity-80"
                    style={{ color: 'var(--text-secondary)' }}
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
                <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {isCO ? 'La contraseña debe tener al menos 6 caracteres.' : 'A senha deve ter pelo menos 6 caracteres.'}
                </p>
              </div>

              {/* Organization */}
              <div>
                <label
                  htmlFor="reg-org"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {isCO ? 'Organización / ISP' : 'Organização / ISP'}
                </label>
                <input
                  id="reg-org"
                  type="text"
                  autoComplete="organization"
                  placeholder={isCO ? 'Nombre de su empresa o ISP' : 'Nome da sua empresa ou ISP'}
                  value={regOrganization}
                  onChange={(e) => setRegOrganization(e.target.value)}
                  className="pulso-input w-full"
                  disabled={loading}
                  required
                />
              </div>

              {/* Country */}
              <div>
                <label
                  htmlFor="reg-country"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  País
                </label>
                <select
                  id="reg-country"
                  value={regCountry}
                  onChange={(e) => { setRegCountry(e.target.value); setRegState(''); }}
                  className="pulso-input w-full"
                  disabled={loading}
                >
                  <option value="BR">Brasil</option>
                  <option value="CO">Colombia</option>
                </select>
              </div>

              {/* State / Department */}
              <div>
                <label
                  htmlFor="reg-state"
                  className="mb-1.5 block text-sm font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {isCO ? 'Departamento' : 'Estado'}
                </label>
                <select
                  id="reg-state"
                  value={regState}
                  onChange={(e) => setRegState(e.target.value)}
                  className="pulso-input w-full"
                  disabled={loading}
                >
                  <option value="">{isCO ? 'Seleccione el departamento' : 'Selecione o estado'}</option>
                  {isCO
                    ? CO_DEPARTMENTS.map((dept) => (
                        <option key={dept.code} value={dept.code}>
                          {dept.name}
                        </option>
                      ))
                    : BR_STATES.map((st) => (
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
                className="pulso-btn-primary w-full flex items-center justify-center gap-2"
              >
                {loading ? (isCO ? 'Creando cuenta...' : 'Criando conta...') : (isCO ? 'Crear Cuenta' : 'Criar Conta')}
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
          Plataforma de inteligência para provedores de internet.
        </p>
      </div>
    </div>
  );
}
