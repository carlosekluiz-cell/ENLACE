'use client';

import { useState, useEffect } from 'react';
import { Users, Database, Play, Plus, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import RoleGuard from '@/components/auth/RoleGuard';
import DataTable from '@/components/dashboard/DataTable';
import { clsx } from 'clsx';
import type { AdminUser, PipelineRun } from '@/lib/types';

type Tab = 'users' | 'pipelines';

function AdminContent() {
  const [activeTab, setActiveTab] = useState<Tab>('users');

  // Users state
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);

  // Create user state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('viewer');
  const [creating, setCreating] = useState(false);

  // Pipelines state
  const [pipelines, setPipelines] = useState<PipelineRun[]>([]);
  const [pipelinesLoading, setPipelinesLoading] = useState(true);

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const data = await api.admin.listUsers();
      setUsers(data);
    } catch {
      setUsers([]);
    } finally {
      setUsersLoading(false);
    }
  };

  const loadPipelines = async () => {
    setPipelinesLoading(true);
    try {
      const data = await api.admin.listPipelines();
      setPipelines(data);
    } catch {
      setPipelines([]);
    } finally {
      setPipelinesLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
    loadPipelines();
  }, []);

  const handleCreateUser = async () => {
    setCreating(true);
    try {
      await api.admin.createUser({
        email: newEmail,
        password: newPassword,
        full_name: newName,
        role: newRole,
      });
      setShowCreateForm(false);
      setNewEmail('');
      setNewName('');
      setNewPassword('');
      setNewRole('viewer');
      loadUsers();
    } catch {
      // Error handled by API layer
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (user: AdminUser) => {
    await api.admin.updateUser(user.id, { is_active: !user.is_active } as any);
    loadUsers();
  };

  const handleChangeRole = async (user: AdminUser, role: string) => {
    await api.admin.updateUser(user.id, { role } as any);
    loadUsers();
  };

  const handleTriggerPipeline = async (name: string) => {
    await api.admin.triggerPipeline(name);
    loadPipelines();
  };

  const userColumns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'full_name', label: 'Nome', sortable: true },
    { key: 'email', label: 'Email', sortable: true },
    {
      key: 'role',
      label: 'Função',
      render: (val: string, row: AdminUser) => (
        <select
          value={val}
          onChange={(e) => handleChangeRole(row, e.target.value)}
          className="rounded px-2 py-1 text-xs"
          style={{
            backgroundColor: 'var(--bg-subtle)',
            color: 'var(--text-primary)',
          }}
        >
          <option value="admin">Admin</option>
          <option value="manager">Gerente</option>
          <option value="analyst">Analista</option>
          <option value="viewer">Visualizador</option>
        </select>
      ),
    },
    {
      key: 'is_active',
      label: 'Ativo',
      render: (val: boolean, row: AdminUser) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleToggleActive(row);
          }}
          className="rounded-full px-3 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: val
              ? 'color-mix(in srgb, var(--success) 20%, transparent)'
              : 'color-mix(in srgb, var(--danger) 20%, transparent)',
            color: val ? 'var(--success)' : 'var(--danger)',
          }}
        >
          {val ? 'Sim' : 'Não'}
        </button>
      ),
    },
    { key: 'tenant_id', label: 'Tenant' },
  ];

  const pipelineColumns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'pipeline_name', label: 'Pipeline', sortable: true },
    {
      key: 'status',
      label: 'Status',
      render: (val: string) => (
        <span
          className="rounded-full px-2 py-0.5 text-xs font-medium"
          style={{
            backgroundColor:
              val === 'completed'
                ? 'color-mix(in srgb, var(--success) 20%, transparent)'
                : val === 'running'
                  ? 'color-mix(in srgb, var(--accent) 20%, transparent)'
                  : val === 'failed'
                    ? 'color-mix(in srgb, var(--danger) 20%, transparent)'
                    : 'color-mix(in srgb, var(--warning) 20%, transparent)',
            color:
              val === 'completed'
                ? 'var(--success)'
                : val === 'running'
                  ? 'var(--accent)'
                  : val === 'failed'
                    ? 'var(--danger)'
                    : 'var(--warning)',
          }}
        >
          {val}
        </span>
      ),
    },
    { key: 'rows_processed', label: 'Linhas' },
    { key: 'started_at', label: 'Início', render: (v: string) => v ? new Date(v).toLocaleString('pt-BR') : '-' },
    { key: 'completed_at', label: 'Fim', render: (v: string) => v ? new Date(v).toLocaleString('pt-BR') : '-' },
    {
      key: 'pipeline_name',
      label: 'Ações',
      render: (_: string, row: PipelineRun) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleTriggerPipeline(row.pipeline_name);
          }}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs hover:opacity-80"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--accent) 20%, transparent)',
            color: 'var(--accent)',
          }}
        >
          <Play size={12} /> Re-executar
        </button>
      ),
    },
  ];

  const tabs = [
    { key: 'users' as Tab, label: 'Usuários', icon: Users },
    { key: 'pipelines' as Tab, label: 'Pipelines', icon: Database },
  ];

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Painel Administrativo</h1>
        <button
          onClick={() => activeTab === 'users' ? loadUsers() : loadPipelines()}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:opacity-80"
          style={{
            backgroundColor: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
          }}
        >
          <RefreshCw size={14} />
          Atualizar
        </button>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg p-1 w-fit" style={{ backgroundColor: 'var(--bg-subtle)' }}>
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

      {/* Users Tab */}
      {activeTab === 'users' && (
        <div>
          <div className="mb-4 flex justify-end">
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="pulso-btn-primary flex items-center gap-2 text-sm"
            >
              <Plus size={16} />
              Novo Usuário
            </button>
          </div>

          {showCreateForm && (
            <div className="pulso-card mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              <input
                type="text"
                placeholder="Nome completo"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="pulso-input"
              />
              <input
                type="email"
                placeholder="Email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="pulso-input"
              />
              <input
                type="password"
                placeholder="Senha"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="pulso-input"
              />
              <div className="flex gap-2">
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="pulso-input flex-1"
                >
                  <option value="viewer">Visualizador</option>
                  <option value="analyst">Analista</option>
                  <option value="manager">Gerente</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  onClick={handleCreateUser}
                  disabled={creating || !newEmail || !newName || !newPassword}
                  className="pulso-btn-primary px-4"
                >
                  {creating ? 'Criando...' : 'Criar'}
                </button>
              </div>
            </div>
          )}

          <DataTable
            columns={userColumns}
            data={users}
            loading={usersLoading}
            searchable
            searchKeys={['email', 'full_name']}
          />
        </div>
      )}

      {/* Pipelines Tab */}
      {activeTab === 'pipelines' && (
        <DataTable
          columns={pipelineColumns}
          data={pipelines}
          loading={pipelinesLoading}
          searchable
          searchKeys={['pipeline_name', 'status']}
        />
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <RoleGuard minRole="admin">
      <AdminContent />
    </RoleGuard>
  );
}
