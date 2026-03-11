'use client';

import { useState } from 'react';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Calculator,
  FileCheck,
  Calendar,
  Scale,
  Newspaper,
  Bell,
  Search,
} from 'lucide-react';
import { clsx } from 'clsx';
import { formatDecimal } from '@/lib/format';
import type {
  ComplianceCheck,
  ComplianceStatus,
  ComplianceDeadline,
  Norma4Impact,
  LicensingCheck,
} from '@/lib/types';

const STATES = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
  'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
  'SP', 'SE', 'TO',
];

const STATUS_LABELS: Record<string, string> = {
  compliant: 'Conforme',
  warning: 'Alerta',
  non_compliant: 'Não Conforme',
};

const RISK_LABELS: Record<string, string> = {
  low: 'BAIXO',
  medium: 'MÉDIO',
  high: 'ALTO',
};

export default function CompliancePage() {
  // Main tab state
  const [mainTab, setMainTab] = useState<'geral' | 'rgst777'>('geral');

  // Form state for Norma 4 calculator
  const [state, setState] = useState('SP');
  const [subscribers, setSubscribers] = useState('');
  const [revenue, setRevenue] = useState('');

  // Provider info for compliance status lookup
  const [providerName, setProviderName] = useState('');
  const [providerState, setProviderState] = useState('SP');
  const [providerSubs, setProviderSubs] = useState('');

  // RGST 777 state
  const [rgstProviderId, setRgstProviderId] = useState('');

  const {
    data: rgst777Data,
    loading: rgst777Loading,
    error: rgst777Error,
    execute: fetchRgst777,
  } = useLazyApi<any, number>(
    (providerId) => api.compliance.rgst777(providerId)
  );

  const {
    data: rgst777Overview,
    loading: rgst777OverviewLoading,
  } = useApi<any>(
    () => api.compliance.rgst777Overview(),
    []
  );

  const handleFetchRgst777 = () => {
    const id = parseInt(rgstProviderId);
    if (id > 0) {
      fetchRgst777(id);
    }
  };

  // RGST 777 helper maps
  const rgstStatusIcon: Record<string, React.ReactNode> = {
    pass: <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />,
    fail: <XCircle size={16} style={{ color: 'var(--danger)' }} />,
    warning: <AlertTriangle size={16} style={{ color: 'var(--warning)' }} />,
  };

  const rgstStatusBadge: Record<string, string> = {
    pass: 'pulso-badge-green',
    fail: 'pulso-badge-red',
    warning: 'pulso-badge-yellow',
  };

  const rgstStatusLabel: Record<string, string> = {
    pass: 'Conforme',
    fail: 'Não Conforme',
    warning: 'Alerta',
  };

  const rgstObligations = rgst777Data?.obligations ?? rgst777Data?.checks ?? [];
  const rgstSummary = {
    passed: rgstObligations.filter((o: any) => o.status === 'pass').length,
    failed: rgstObligations.filter((o: any) => o.status === 'fail').length,
    warnings: rgstObligations.filter((o: any) => o.status === 'warning').length,
    total: rgstObligations.length,
  };

  // Norma 4 impact calculation
  const {
    data: norma4Data,
    loading: norma4Loading,
    error: norma4Error,
    execute: fetchNorma4,
  } = useLazyApi<Norma4Impact, { state: string; subs: number; revenue: number }>(
    (params) => api.compliance.norma4Impact(params.state, params.subs, params.revenue)
  );

  // Compliance status (lazy, triggered when provider info is submitted)
  const {
    data: statusData,
    loading: statusLoading,
    error: statusError,
    execute: fetchStatus,
  } = useLazyApi<ComplianceStatus, { provider_name: string; state: string; subscribers: number }>(
    (params) => api.compliance.status(params)
  );

  // Licensing check (lazy, triggered alongside Norma 4)
  const {
    data: licensingData,
    loading: licensingLoading,
    error: licensingError,
    execute: fetchLicensing,
  } = useLazyApi<LicensingCheck, number>(
    (count) => api.compliance.licensingCheck(count)
  );

  // Regulatory deadlines (auto-fetched on mount)
  const {
    data: deadlines,
    loading: deadlinesLoading,
    error: deadlinesError,
  } = useApi<ComplianceDeadline[]>(
    () => api.compliance.deadlines(90),
    []
  );

  // Regulatory intelligence: DOU acts + gazette alerts
  const [regTab, setRegTab] = useState<'dou' | 'gazette' | 'alerts'>('alerts');

  const {
    data: regulatoryFeed,
    loading: regFeedLoading,
  } = useApi<any[]>(
    () => api.intelligence.regulatoryFeed({ days: '60', limit: '20' }),
    []
  );

  const {
    data: gazetteAlerts,
    loading: alertsLoading,
  } = useApi<any[]>(
    () => api.intelligence.gazetteAlerts({ min_score: '70', days: '60', limit: '20' }),
    []
  );

  const {
    data: gazetteMentions,
    loading: mentionsLoading,
  } = useApi<any[]>(
    () => api.intelligence.gazetteMentions({ days: '60', limit: '20' }),
    []
  );

  // Handlers
  const handleCalculateImpact = () => {
    const subsNum = parseInt(subscribers) || 0;
    const revNum = parseFloat(revenue) || 0;
    fetchNorma4({ state, subs: subsNum, revenue: revNum });
    if (subsNum > 0) {
      fetchLicensing(subsNum);
    }
  };

  const handleFetchStatus = () => {
    const subs = parseInt(providerSubs) || 0;
    if (providerName.trim() && subs > 0) {
      fetchStatus({ provider_name: providerName.trim(), state: providerState, subscribers: subs });
    }
  };

  // Derived data
  const checks = statusData?.checks ?? [];
  const statusCounts = {
    compliant: checks.filter((c) => c.status === 'compliant').length,
    warning: checks.filter((c) => c.status === 'at_risk' || c.status === 'warning').length,
    non_compliant: checks.filter((c) => c.status === 'non_compliant').length,
  };

  const chartData = checks.length > 0
    ? [
        { name: 'Conforme', value: statusCounts.compliant },
        { name: 'Alertas', value: statusCounts.warning },
        { name: 'Não Conforme', value: statusCounts.non_compliant },
      ]
    : [];

  const statusIcon: Record<string, React.ReactNode> = {
    compliant: <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />,
    warning: <AlertTriangle size={16} style={{ color: 'var(--warning)' }} />,
    non_compliant: <XCircle size={16} style={{ color: 'var(--danger)' }} />,
  };

  const statusBadge: Record<string, string> = {
    compliant: 'pulso-badge-green',
    warning: 'pulso-badge-yellow',
    non_compliant: 'pulso-badge-red',
  };

  const deadlineStatusBadge = (status: string) => {
    switch (status) {
      case 'upcoming':
      case 'on_track':
        return 'pulso-badge-green';
      case 'approaching':
      case 'warning':
        return 'pulso-badge-yellow';
      case 'overdue':
      case 'urgent':
        return 'pulso-badge-red';
      default:
        return 'pulso-badge-yellow';
    }
  };

  // Currency formatting helper
  const fmtBRL = (value: number | null | undefined) =>
    formatDecimal(value ?? 0, 2);

  return (
    <div className="space-y-6 p-6">
      {/* Main tab bar */}
      <div className="flex gap-2">
        {[
          { key: 'geral' as const, label: 'Conformidade Geral' },
          { key: 'rgst777' as const, label: 'RGST 777' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMainTab(tab.key)}
            className="rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: mainTab === tab.key ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
              color: mainTab === tab.key ? 'var(--accent)' : 'var(--text-muted)',
              border: `1px solid ${mainTab === tab.key ? 'var(--accent)' : 'var(--border)'}`,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* RGST 777 Tab */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {mainTab === 'rgst777' && (
        <div className="space-y-6">
          {/* Overview section */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Shield size={16} style={{ color: 'var(--accent)' }} />
              RGST 777/2025 — Visão Geral
            </h2>
            {rgst777OverviewLoading && (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-4 w-full rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                ))}
              </div>
            )}
            {rgst777Overview && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {rgst777Overview.total_providers != null && (
                  <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Provedores Avaliados</p>
                    <p className="mt-1 text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                      {rgst777Overview.total_providers?.toLocaleString('pt-BR') ?? '--'}
                    </p>
                  </div>
                )}
                {rgst777Overview.compliant_count != null && (
                  <div className="rounded-lg p-3" style={{ backgroundColor: 'color-mix(in srgb, var(--success) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)' }}>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Conformes</p>
                    <p className="mt-1 text-xl font-bold" style={{ color: 'var(--success)' }}>
                      {rgst777Overview.compliant_count?.toLocaleString('pt-BR') ?? '--'}
                    </p>
                  </div>
                )}
                {rgst777Overview.non_compliant_count != null && (
                  <div className="rounded-lg p-3" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)' }}>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Não Conformes</p>
                    <p className="mt-1 text-xl font-bold" style={{ color: 'var(--danger)' }}>
                      {rgst777Overview.non_compliant_count?.toLocaleString('pt-BR') ?? '--'}
                    </p>
                  </div>
                )}
                {rgst777Overview.avg_score != null && (
                  <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Score Médio</p>
                    <p className="mt-1 text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                      {typeof rgst777Overview.avg_score === 'number' ? rgst777Overview.avg_score.toFixed(1) : rgst777Overview.avg_score}
                    </p>
                  </div>
                )}
                {/* Fallback: render any top-level keys as stat cards if specific keys are missing */}
                {rgst777Overview.total_providers == null && rgst777Overview.summary && (
                  <>
                    {Object.entries(rgst777Overview.summary).map(([key, val]) => (
                      <div key={key} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                        <p className="text-xs capitalize" style={{ color: 'var(--text-muted)' }}>{key.replace(/_/g, ' ')}</p>
                        <p className="mt-1 text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {typeof val === 'number' ? val.toLocaleString('pt-BR') : String(val)}
                        </p>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
            {!rgst777Overview && !rgst777OverviewLoading && (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Dados gerais do RGST 777 indisponíveis.
              </p>
            )}
          </div>

          {/* Provider search */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Search size={16} style={{ color: 'var(--accent)' }} />
              Consultar Provedor — RGST 777/2025
            </h2>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  ID do Provedor
                </label>
                <input
                  type="number"
                  value={rgstProviderId}
                  onChange={(e) => setRgstProviderId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleFetchRgst777(); }}
                  placeholder="Digite o ID do provedor"
                  className="pulso-input w-full"
                />
              </div>
              <button
                onClick={handleFetchRgst777}
                disabled={rgst777Loading || !rgstProviderId.trim()}
                className="pulso-btn-primary flex items-center gap-2 whitespace-nowrap"
              >
                <Search size={16} />
                {rgst777Loading ? 'Consultando...' : 'Verificar RGST 777'}
              </button>
            </div>
          </div>

          {/* Error */}
          {rgst777Error && (
            <div
              className="pulso-card rounded-lg p-3 text-sm"
              style={{
                backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                color: 'var(--danger)',
              }}
            >
              <span className="font-medium">Erro:</span> {rgst777Error}
            </div>
          )}

          {/* Loading state */}
          {rgst777Loading && (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="pulso-card animate-pulse">
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5 h-4 w-4 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-48 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                      <div className="h-3 w-72 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Results: summary + checklist */}
          {rgstObligations.length > 0 && !rgst777Loading && (
            <>
              {/* Summary counts */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--success) 30%, transparent)' }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Conforme</p>
                      <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--success)' }}>
                        {rgstSummary.passed}
                      </p>
                    </div>
                    <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
                  </div>
                </div>
                <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)' }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Não Conforme</p>
                      <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--danger)' }}>
                        {rgstSummary.failed}
                      </p>
                    </div>
                    <XCircle size={18} style={{ color: 'var(--danger)' }} />
                  </div>
                </div>
                <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--warning) 30%, transparent)' }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Alertas</p>
                      <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--warning)' }}>
                        {rgstSummary.warnings}
                      </p>
                    </div>
                    <AlertTriangle size={18} style={{ color: 'var(--warning)' }} />
                  </div>
                </div>
                <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--accent) 30%, transparent)' }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Total Obrigações</p>
                      <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                        {rgstSummary.total}
                      </p>
                    </div>
                    <Shield size={18} style={{ color: 'var(--accent)' }} />
                  </div>
                </div>
              </div>

              {/* Provider info (if returned) */}
              {rgst777Data?.provider_name && (
                <div className="pulso-card">
                  <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {rgst777Data.provider_name}
                  </h3>
                  <div className="flex flex-wrap gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {rgst777Data.provider_id && <span>ID: {rgst777Data.provider_id}</span>}
                    {rgst777Data.state && <span>Estado: {rgst777Data.state}</span>}
                    {rgst777Data.overall_status && (
                      <span className={rgstStatusBadge[rgst777Data.overall_status] || 'pulso-badge-yellow'}>
                        {rgstStatusLabel[rgst777Data.overall_status] || rgst777Data.overall_status}
                      </span>
                    )}
                    {rgst777Data.score != null && (
                      <span className="font-semibold" style={{ color: 'var(--accent)' }}>
                        Score: {typeof rgst777Data.score === 'number' ? rgst777Data.score.toFixed(1) : rgst777Data.score}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Obligations checklist */}
              <div className="space-y-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  <FileCheck size={16} style={{ color: 'var(--accent)' }} />
                  Obrigações RGST 777/2025
                </h2>
                {rgstObligations.map((obligation: any, idx: number) => (
                  <div key={idx} className="pulso-card flex items-start gap-4">
                    <div className="mt-0.5">
                      {rgstStatusIcon[obligation.status] ?? <AlertTriangle size={16} style={{ color: 'var(--text-secondary)' }} />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {obligation.category || obligation.name || `Obrigação ${idx + 1}`}
                        </h3>
                        <span className={rgstStatusBadge[obligation.status] || 'pulso-badge-yellow'}>
                          {rgstStatusLabel[obligation.status] || obligation.status}
                        </span>
                      </div>
                      {(obligation.detail || obligation.description) && (
                        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {obligation.detail || obligation.description}
                        </p>
                      )}
                      {obligation.evidence_source && (
                        <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                          Fonte: {obligation.evidence_source}
                        </p>
                      )}
                      {obligation.evidence && !obligation.evidence_source && (
                        <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                          Evidência: {obligation.evidence}
                        </p>
                      )}
                      {obligation.deadline && (
                        <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                          Prazo: {obligation.deadline}
                        </p>
                      )}
                      {obligation.action_items && obligation.action_items.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {obligation.action_items.slice(0, 3).map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                              <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
                              {item}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Empty state when no results yet */}
          {!rgst777Data && !rgst777Loading && !rgst777Error && (
            <div className="pulso-card flex items-center justify-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
              Digite o ID do provedor e clique em Verificar para consultar a conformidade RGST 777/2025.
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Geral Tab (existing content) */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {mainTab === 'geral' && <>
      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--success) 30%, transparent)' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Conforme</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {statusLoading ? 'Carregando...' : statusCounts.compliant}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Regulamentações atendidas</p>
            </div>
            <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
          </div>
        </div>
        <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--warning) 30%, transparent)' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Alertas</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {statusLoading ? 'Carregando...' : statusCounts.warning}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Próximo dos limites</p>
            </div>
            <AlertTriangle size={18} style={{ color: 'var(--warning)' }} />
          </div>
        </div>
        <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Não Conforme</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {statusLoading ? 'Carregando...' : statusCounts.non_compliant}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Ação necessária</p>
            </div>
            <XCircle size={18} style={{ color: 'var(--danger)' }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT COLUMN: Norma 4 Calculator */}
        <div className="space-y-4 lg:col-span-1">
          {/* Calculator form */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Calculator size={16} style={{ color: 'var(--accent)' }} />
              Calculadora Norma n 4
            </h2>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Estado
                </label>
                <select
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="pulso-input w-full"
                >
                  {STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Assinantes
                </label>
                <input
                  type="number"
                  value={subscribers}
                  onChange={(e) => setSubscribers(e.target.value)}
                  placeholder="Número de assinantes"
                  className="pulso-input w-full"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Receita Mensal (BRL)
                </label>
                <input
                  type="number"
                  value={revenue}
                  onChange={(e) => setRevenue(e.target.value)}
                  placeholder="Receita mensal em reais"
                  className="pulso-input w-full"
                />
              </div>

              <button
                onClick={handleCalculateImpact}
                disabled={norma4Loading}
                className="pulso-btn-primary flex w-full items-center justify-center gap-2"
              >
                <Calculator size={16} />
                {norma4Loading ? 'Calculando...' : 'Calcular Impacto Norma 4'}
              </button>
            </div>

            {/* Error state */}
            {norma4Error && (
              <div
                className="mt-4 rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  color: 'var(--danger)',
                }}
              >
                <span className="font-medium">Erro:</span> {norma4Error}
              </div>
            )}

            {/* Norma 4 results */}
            {norma4Data && (
              <div className="mt-4 space-y-3 rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <h3 className="text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>
                  Impacto Norma n 4
                </h3>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>ICMS (%)</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {((norma4Data.icms_rate ?? 0) * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>Impacto sobre receita</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {(norma4Data.pct_of_revenue ?? 0).toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>ARPU estimado</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                      R$ {fmtBRL(norma4Data.arpu_brl)}
                    </span>
                  </div>

                  <div className="pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                    <div className="flex justify-between text-sm font-medium">
                      <span style={{ color: 'var(--text-secondary)' }}>Carga tributária adicional/mês</span>
                      <span style={{ color: 'var(--danger)' }}>
                        R$ {fmtBRL(norma4Data.additional_monthly_tax_brl)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm mt-1">
                      <span style={{ color: 'var(--text-secondary)' }}>Carga tributária adicional/ano</span>
                      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                        R$ {fmtBRL(norma4Data.additional_annual_tax_brl)}
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>Prazo</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {norma4Data.days_until_deadline} dias
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>Prontidão</span>
                    <span
                      className="font-semibold"
                      style={{
                        color: (norma4Data.readiness_score ?? 0) >= 70
                          ? 'var(--success)'
                          : (norma4Data.readiness_score ?? 0) >= 40
                            ? 'var(--warning)'
                            : 'var(--danger)',
                      }}
                    >
                      {(norma4Data.readiness_score ?? 0).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Restructuring options */}
                {norma4Data.restructuring_options && norma4Data.restructuring_options.length > 0 && (
                  <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                    <h4 className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>
                      Opções de Reestruturação
                    </h4>
                    <div className="space-y-2">
                      {norma4Data.restructuring_options.slice(0, 3).map((opt, idx) => (
                        <div key={idx} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{opt.strategy}</span>
                            <span className={`text-xs font-semibold ${opt.score >= 60 ? 'pulso-badge-green' : opt.score >= 30 ? 'pulso-badge-yellow' : 'pulso-badge-red'}`}>
                              {opt.score}pts
                            </span>
                          </div>
                          <p className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
                            Economia: R$ {fmtBRL(opt.estimated_monthly_savings_brl)}/mês — {opt.implementation_months} meses
                          </p>
                        </div>
                      ))}
                    </div>
                    {norma4Data.recommended_action && (
                      <p className="mt-2 text-xs font-medium" style={{ color: 'var(--accent)' }}>
                        Recomendado: {norma4Data.recommended_action}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Licensing check result */}
          {licensingData && (
            <div className="pulso-card">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Shield size={16} style={{ color: 'var(--accent)' }} />
                Licenciamento
              </h2>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span style={{ color: 'var(--text-secondary)' }}>Licença SCM Necessária</span>
                  <span
                    className="font-semibold"
                    style={{ color: licensingData.above_threshold ? 'var(--danger)' : 'var(--success)' }}
                  >
                    {licensingData.above_threshold ? 'Sim' : 'Não'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: 'var(--text-secondary)' }}>Limite</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {(licensingData.threshold ?? 0).toLocaleString('pt-BR')} assinantes
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: 'var(--text-secondary)' }}>Custo estimado licenciamento</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    R$ {fmtBRL(licensingData.estimated_licensing_cost_brl)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: 'var(--text-secondary)' }}>Custo anual estimado</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    R$ {fmtBRL(licensingData.estimated_annual_cost_brl)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: 'var(--text-secondary)' }}>Urgência</span>
                  <span className={licensingData.urgency === 'immediate' ? 'pulso-badge-red' : 'pulso-badge-green'}>
                    {licensingData.urgency === 'immediate' ? 'Imediata' : licensingData.urgency}
                  </span>
                </div>
                {licensingData.recommendation && (
                  <p className="mt-2 text-xs rounded-lg p-2" style={{ backgroundColor: 'color-mix(in srgb, var(--warning) 10%, transparent)', color: 'var(--text-secondary)' }}>
                    {licensingData.recommendation}
                  </p>
                )}
                {licensingData.requirements && licensingData.requirements.length > 0 && (
                  <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                    <h4 className="mb-1 text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Requisitos</h4>
                    <ul className="space-y-1">
                      {licensingData.requirements.slice(0, 5).map((req, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                          <Scale size={10} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
                          {req}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {licensingError && (
            <div className="pulso-card">
              <div
                className="rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  color: 'var(--danger)',
                }}
              >
                <span className="font-medium">Erro no licenciamento:</span> {licensingError}
              </div>
            </div>
          )}
        </div>

        {/* CENTER + RIGHT COLUMNS */}
        <div className="space-y-4 lg:col-span-2">
          {/* Provider info for compliance status */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Shield size={16} style={{ color: 'var(--accent)' }} />
              Informações do Provedor
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <input
                type="text"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                placeholder="Nome do provedor"
                className="pulso-input sm:col-span-2"
              />
              <select
                value={providerState}
                onChange={(e) => setProviderState(e.target.value)}
                className="pulso-input"
              >
                {STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <input
                type="number"
                value={providerSubs}
                onChange={(e) => setProviderSubs(e.target.value)}
                placeholder="Assinantes"
                className="pulso-input"
              />
            </div>
            <button
              onClick={handleFetchStatus}
              disabled={statusLoading || !providerName.trim() || !providerSubs}
              className="pulso-btn-primary mt-3 flex items-center gap-2 whitespace-nowrap"
            >
              <FileCheck size={16} />
              {statusLoading ? 'Carregando...' : 'Verificar Conformidade'}
            </button>
          </div>

          {/* Compliance checks */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <FileCheck size={16} style={{ color: 'var(--accent)' }} />
                Verificações de Conformidade
              </h2>
              {statusData && (
                <span
                  className="text-xs font-medium"
                  style={{
                    color:
                      statusData.overall_status === 'compliant'
                        ? 'var(--success)'
                        : statusData.overall_status === 'warning'
                          ? 'var(--warning)'
                          : 'var(--danger)',
                  }}
                >
                  Status geral: {statusData.overall_status ? (STATUS_LABELS[statusData.overall_status] ?? statusData.overall_status) : 'N/A'}
                </span>
              )}
            </div>

            {statusError && (
              <div
                className="pulso-card rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  color: 'var(--danger)',
                }}
              >
                <span className="font-medium">Erro:</span> {statusError}
              </div>
            )}

            {!statusData && !statusLoading && !statusError && (
              <div className="pulso-card flex items-center justify-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
                Preencha os dados do provedor e clique em Verificar para ver o status de conformidade.
              </div>
            )}

            {statusLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="pulso-card animate-pulse">
                    <div className="flex items-start gap-4">
                      <div className="mt-0.5 h-4 w-4 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-48 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                        <div className="h-3 w-72 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {checks.length > 0 && (
              <div className="space-y-3">
                {checks.map((check, idx) => (
                  <div key={idx} className="pulso-card flex items-start gap-4">
                    <div className="mt-0.5">
                      {statusIcon[check.status] ?? <AlertTriangle size={16} style={{ color: 'var(--text-secondary)' }} />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {check.regulation_name || check.regulation_id}
                        </h3>
                        <span className={statusBadge[check.status] || statusBadge[check.urgency] || 'pulso-badge-yellow'}>
                          {STATUS_LABELS[check.status] ?? check.status}
                        </span>
                      </div>
                      <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>{check.description}</p>
                      {check.action_items && check.action_items.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {check.action_items.slice(0, 3).map((item, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                              <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
                              {item}
                            </li>
                          ))}
                        </ul>
                      )}
                      {check.estimated_cost_brl != null && (
                        <p className="mt-2 text-xs font-medium" style={{ color: 'var(--warning)' }}>
                          Custo estimado: R$ {check.estimated_cost_brl.toLocaleString('pt-BR')}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Compliance overview chart */}
          <SimpleChart
            data={chartData}
            type="bar"
            xKey="name"
            yKey="value"
            title="Visão Geral de Conformidade"
            height={250}
            loading={statusLoading}
          />

          {/* Regulatory Deadlines */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Calendar size={16} style={{ color: 'var(--accent)' }} />
              Prazos Regulatórios
            </h2>

            {deadlinesError && (
              <div
                className="rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  color: 'var(--danger)',
                }}
              >
                <span className="font-medium">Erro:</span> {deadlinesError}
              </div>
            )}

            {deadlinesLoading && (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-4">
                    <div className="h-4 w-32 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="h-4 w-24 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="h-4 w-16 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="h-4 flex-1 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                  </div>
                ))}
              </div>
            )}

            {deadlines && deadlines.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                      <th className="pb-2 pr-4 font-medium">Regulamentação</th>
                      <th className="pb-2 pr-4 font-medium">Prazo</th>
                      <th className="pb-2 pr-4 font-medium">Dias Restantes</th>
                      <th className="pb-2 pr-4 font-medium">Status</th>
                      <th className="pb-2 font-medium">Descrição</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deadlines.map((dl, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)', color: 'var(--text-secondary)' }}>
                        <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>
                          {dl.name || dl.regulation_id}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap">
                          {dl.deadline_date ? new Date(dl.deadline_date).toLocaleDateString('pt-BR') : '--'}
                        </td>
                        <td className="py-2 pr-4">
                          <span
                            className="font-semibold"
                            style={{
                              color:
                                dl.days_remaining <= 7
                                  ? 'var(--danger)'
                                  : dl.days_remaining <= 30
                                    ? 'var(--warning)'
                                    : 'var(--success)',
                            }}
                          >
                            {dl.days_remaining}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={deadlineStatusBadge(dl.urgency)}>
                            {({
                              critical: 'Crítico',
                              urgent: 'Urgente',
                              warning: 'Alerta',
                              approaching: 'Próximo',
                              upcoming: 'Previsto',
                              on_track: 'No prazo',
                              overdue: 'Vencido',
                            } as Record<string, string>)[dl.urgency] ?? dl.urgency}
                          </span>
                        </td>
                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{dl.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {deadlines && deadlines.length === 0 && (
              <p className="py-6 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                Nenhum prazo regulatório encontrado para os próximos 90 dias.
              </p>
            )}
          </div>

          {/* Regulatory Intelligence */}
          <div className="pulso-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Newspaper size={16} style={{ color: 'var(--accent)' }} />
              Inteligência Regulatória
            </h2>

            {/* Tab buttons */}
            <div className="mb-4 flex gap-2">
              {[
                { key: 'alerts' as const, label: 'Alertas', count: gazetteAlerts?.length },
                { key: 'dou' as const, label: 'DOU ANATEL', count: regulatoryFeed?.length },
                { key: 'gazette' as const, label: 'Diários Municipais', count: gazetteMentions?.length },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setRegTab(tab.key)}
                  className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
                  style={{
                    background: regTab === tab.key ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
                    color: regTab === tab.key ? 'var(--accent)' : 'var(--text-muted)',
                    border: `1px solid ${regTab === tab.key ? 'var(--accent)' : 'var(--border)'}`,
                  }}
                >
                  {tab.label}
                  {tab.count != null && tab.count > 0 && (
                    <span className="ml-1 rounded-full px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: 'var(--accent)', color: 'white' }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Alerts tab: gazette mentions in high-opportunity municipalities */}
            {regTab === 'alerts' && (
              <div className="space-y-2">
                {alertsLoading && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando alertas...</p>}
                {gazetteAlerts && gazetteAlerts.length === 0 && (
                  <p className="py-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                    Nenhum alerta nos últimos 60 dias.
                  </p>
                )}
                {gazetteAlerts?.map((alert) => (
                  <div key={alert.id} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <Bell size={12} style={{ color: 'var(--warning)' }} />
                        <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                          {alert.municipality} ({alert.state})
                        </span>
                      </div>
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ backgroundColor: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}>
                        Score: {alert.opportunity_score?.toFixed(1)}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <span className="font-medium">{alert.type}</span>
                      {alert.excerpt && ` — ${alert.excerpt.substring(0, 150)}...`}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{alert.date}</span>
                      {alert.days_ago != null && (
                        <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>({alert.days_ago}d atrás)</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* DOU tab: ANATEL regulatory acts */}
            {regTab === 'dou' && (
              <div className="space-y-2">
                {regFeedLoading && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando atos...</p>}
                {regulatoryFeed && regulatoryFeed.length === 0 && (
                  <p className="py-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                    Nenhum ato regulatório nos últimos 60 dias.
                  </p>
                )}
                {regulatoryFeed?.map((act) => (
                  <div key={act.id} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium" style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}>
                        {act.type || 'Ato'}
                      </span>
                      <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{act.date}</span>
                    </div>
                    <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{act.title}</p>
                    {act.summary && (
                      <p className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{act.summary.substring(0, 200)}</p>
                    )}
                    {act.keywords && act.keywords.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {act.keywords.slice(0, 5).map((kw: string, i: number) => (
                          <span key={i} className="rounded-full px-1.5 py-0.5 text-[9px]" style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Gazette tab: municipal gazette mentions */}
            {regTab === 'gazette' && (
              <div className="space-y-2">
                {mentionsLoading && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando menções...</p>}
                {gazetteMentions && gazetteMentions.length === 0 && (
                  <p className="py-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                    Nenhuma menção nos últimos 60 dias.
                  </p>
                )}
                {gazetteMentions?.map((m) => (
                  <div key={m.id} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{m.municipality}</span>
                      <span className="rounded px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}>
                        {m.type}
                      </span>
                    </div>
                    {m.excerpt && (
                      <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{m.excerpt.substring(0, 200)}</p>
                    )}
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{m.date}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      </>}
    </div>
  );
}
