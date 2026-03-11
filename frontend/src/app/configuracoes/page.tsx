'use client';

import { useState, useEffect } from 'react';
import { User, Lock, Settings, Save, Check } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { clsx } from 'clsx';

type Tab = 'profile' | 'security' | 'preferences';

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const { theme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<Tab>('profile');

  // Profile state
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState('');

  // Password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState('');

  // Language state
  const [language, setLanguage] = useState(() => {
    if (typeof window === 'undefined') return 'pt-BR';
    return localStorage.getItem('pulso_language') || 'pt-BR';
  });

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '');
      setEmail(user.email || '');
    }
  }, [user]);

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileMsg('');
    try {
      await api.auth.updateProfile({ full_name: fullName, email });
      await refresh();
      setProfileMsg('Perfil atualizado com sucesso');
    } catch (e: any) {
      setProfileMsg(e.message || 'Erro ao atualizar perfil');
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setPwMsg('As senhas não coincidem');
      return;
    }
    setPwSaving(true);
    setPwMsg('');
    try {
      await api.auth.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPwMsg('Senha alterada com sucesso');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (e: any) {
      setPwMsg(e.message || 'Erro ao alterar senha');
    } finally {
      setPwSaving(false);
    }
  };

  const tabs = [
    { key: 'profile' as Tab, label: 'Perfil', icon: User },
    { key: 'security' as Tab, label: 'Segurança', icon: Lock },
    { key: 'preferences' as Tab, label: 'Preferências', icon: Settings },
  ];

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Configurações</h1>

      {/* Tabs */}
      <div
        className="mb-6 flex gap-1 rounded-lg p-1 w-fit"
        style={{ backgroundColor: 'var(--bg-subtle)' }}
      >
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{
              backgroundColor: activeTab === key ? 'var(--accent)' : 'transparent',
              color: activeTab === key ? '#fff' : 'var(--text-secondary)',
            }}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="pulso-card max-w-lg space-y-4">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Informações do Perfil</h2>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Nome completo</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="pulso-input w-full"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="pulso-input w-full"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Função</label>
            <input
              type="text"
              value={user?.role || ''}
              disabled
              className="pulso-input w-full opacity-50"
            />
          </div>
          {profileMsg && (
            <p className="text-sm" style={{ color: profileMsg.includes('sucesso') ? 'var(--success)' : 'var(--danger)' }}>
              {profileMsg}
            </p>
          )}
          <button
            onClick={handleSaveProfile}
            disabled={profileSaving}
            className="pulso-btn-primary flex items-center gap-2"
          >
            <Save size={16} />
            {profileSaving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="pulso-card max-w-lg space-y-4">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Alterar Senha</h2>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Senha atual</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="pulso-input w-full"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Nova senha</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="pulso-input w-full"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm" style={{ color: 'var(--text-secondary)' }}>Confirmar nova senha</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="pulso-input w-full"
            />
          </div>
          {pwMsg && (
            <p className="text-sm" style={{ color: pwMsg.includes('sucesso') ? 'var(--success)' : 'var(--danger)' }}>
              {pwMsg}
            </p>
          )}
          <button
            onClick={handleChangePassword}
            disabled={pwSaving || !currentPassword || !newPassword}
            className="pulso-btn-primary flex items-center gap-2"
          >
            <Check size={16} />
            {pwSaving ? 'Salvando...' : 'Alterar Senha'}
          </button>
        </div>
      )}

      {/* Preferences Tab */}
      {activeTab === 'preferences' && (
        <div className="pulso-card max-w-lg space-y-6">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Preferências</h2>

          {/* Theme */}
          <div>
            <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Tema</label>
            <div className="flex gap-2">
              {(['light', 'dark', 'system'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className="rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                  style={{
                    backgroundColor: theme === t ? 'var(--accent)' : 'var(--bg-subtle)',
                    color: theme === t ? '#fff' : 'var(--text-secondary)',
                  }}
                >
                  {t === 'light' ? 'Claro' : t === 'dark' ? 'Escuro' : 'Sistema'}
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div>
            <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Idioma</label>
            <div className="flex gap-2">
              {[
                { code: 'pt-BR', label: 'Português (BR)' },
                { code: 'en', label: 'English' },
              ].map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => {
                    setLanguage(lang.code);
                    localStorage.setItem('pulso_language', lang.code);
                  }}
                  className="rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                  style={{
                    backgroundColor: language === lang.code ? 'var(--accent)' : 'var(--bg-subtle)',
                    color: language === lang.code ? '#fff' : 'var(--text-secondary)',
                  }}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
