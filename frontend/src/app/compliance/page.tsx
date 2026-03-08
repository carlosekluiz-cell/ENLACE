'use client';

import { useState } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
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
} from 'lucide-react';
import { clsx } from 'clsx';
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
  non_compliant: 'Nao Conforme',
};

const RISK_LABELS: Record<string, string> = {
  low: 'BAIXO',
  medium: 'MEDIO',
  high: 'ALTO',
};

export default function CompliancePage() {
  // Form state for Norma 4 calculator
  const [state, setState] = useState('SP');
  const [subscribers, setSubscribers] = useState('');
  const [revenue, setRevenue] = useState('');

  // Provider ID for compliance status lookup
  const [providerId, setProviderId] = useState('');
  const [submittedProviderId, setSubmittedProviderId] = useState<number | null>(null);

  // Norma 4 impact calculation
  const {
    data: norma4Data,
    loading: norma4Loading,
    error: norma4Error,
    execute: fetchNorma4,
  } = useLazyApi<Norma4Impact, { state: string; subs: number; revenue: number }>(
    (params) => api.compliance.norma4Impact(params.state, params.subs, params.revenue)
  );

  // Compliance status (lazy, triggered when provider ID is submitted)
  const {
    data: statusData,
    loading: statusLoading,
    error: statusError,
    execute: fetchStatus,
  } = useLazyApi<ComplianceStatus, number>(
    (id) => api.compliance.status(id)
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

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleCalculateImpact = () => {
    const subsNum = parseInt(subscribers) || 0;
    const revNum = parseFloat(revenue) || 0;
    fetchNorma4({ state, subs: subsNum, revenue: revNum });
    if (subsNum > 0) {
      fetchLicensing(subsNum);
    }
  };

  const handleFetchStatus = () => {
    const id = parseInt(providerId);
    if (id > 0) {
      setSubmittedProviderId(id);
      fetchStatus(id);
    }
  };

  // ── Derived data ────────────────────────────────────────────────────────

  const checks = statusData?.checks ?? [];
  const statusCounts = {
    compliant: checks.filter((c) => c.status === 'compliant').length,
    warning: checks.filter((c) => c.status === 'warning').length,
    non_compliant: checks.filter((c) => c.status === 'non_compliant').length,
  };

  const chartData = checks.length > 0
    ? [
        { name: 'Conforme', value: statusCounts.compliant },
        { name: 'Alertas', value: statusCounts.warning },
        { name: 'Nao Conforme', value: statusCounts.non_compliant },
      ]
    : [];

  const statusIcon: Record<string, React.ReactNode> = {
    compliant: <CheckCircle2 size={16} className="text-green-400" />,
    warning: <AlertTriangle size={16} className="text-yellow-400" />,
    non_compliant: <XCircle size={16} className="text-red-400" />,
  };

  const statusBadge: Record<string, string> = {
    compliant: 'enlace-badge-green',
    warning: 'enlace-badge-yellow',
    non_compliant: 'enlace-badge-red',
  };

  const deadlineStatusBadge = (status: string) => {
    switch (status) {
      case 'upcoming':
      case 'on_track':
        return 'enlace-badge-green';
      case 'approaching':
      case 'warning':
        return 'enlace-badge-yellow';
      case 'overdue':
      case 'urgent':
        return 'enlace-badge-red';
      default:
        return 'enlace-badge-yellow';
    }
  };

  // ── Currency formatting helper ──────────────────────────────────────────

  const fmtBRL = (value: number) =>
    value.toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 p-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Conforme"
          value={statusCounts.compliant}
          icon={<CheckCircle2 size={18} className="text-green-400" />}
          subtitle="Regulamentacoes atendidas"
          loading={statusLoading}
          className="border-green-900/30"
        />
        <StatsCard
          title="Alertas"
          value={statusCounts.warning}
          icon={<AlertTriangle size={18} className="text-yellow-400" />}
          subtitle="Proximo dos limites"
          loading={statusLoading}
          className="border-yellow-900/30"
        />
        <StatsCard
          title="Nao Conforme"
          value={statusCounts.non_compliant}
          icon={<XCircle size={18} className="text-red-400" />}
          subtitle="Acao necessaria"
          loading={statusLoading}
          className="border-red-900/30"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── LEFT COLUMN: Norma 4 Calculator ──────────────────────────── */}
        <div className="space-y-4 lg:col-span-1">
          {/* Calculator form */}
          <div className="enlace-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Calculator size={16} className="text-blue-400" />
              Calculadora Norma n 4
            </h2>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Estado
                </label>
                <select
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="enlace-input w-full"
                >
                  {STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Assinantes
                </label>
                <input
                  type="number"
                  value={subscribers}
                  onChange={(e) => setSubscribers(e.target.value)}
                  placeholder="Numero de assinantes"
                  className="enlace-input w-full"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Receita Mensal (BRL)
                </label>
                <input
                  type="number"
                  value={revenue}
                  onChange={(e) => setRevenue(e.target.value)}
                  placeholder="Receita mensal em reais"
                  className="enlace-input w-full"
                />
              </div>

              <button
                onClick={handleCalculateImpact}
                disabled={norma4Loading}
                className="enlace-btn-primary flex w-full items-center justify-center gap-2"
              >
                <Calculator size={16} />
                {norma4Loading ? 'Calculando...' : 'Calcular Impacto Norma 4'}
              </button>
            </div>

            {/* Error state */}
            {norma4Error && (
              <div className="mt-4 rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                <span className="font-medium">Erro:</span> {norma4Error}
              </div>
            )}

            {/* Norma 4 results */}
            {norma4Data && (
              <div className="mt-4 space-y-3 rounded-lg bg-slate-900 p-4">
                <h3 className="text-xs font-semibold uppercase text-slate-400">
                  Impacto Norma n 4
                </h3>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">ICMS (%)</span>
                    <span className="font-semibold text-slate-200">
                      {norma4Data.icms_rate_pct}%
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Contribuicao FUST</span>
                    <span className="font-semibold text-slate-200">
                      R$ {fmtBRL(norma4Data.fust_contribution)}
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Contribuicao FUNTTEL</span>
                    <span className="font-semibold text-slate-200">
                      R$ {fmtBRL(norma4Data.funttel_contribution)}
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Contribuicao ao Fundo</span>
                    <span className="font-semibold text-slate-200">
                      R$ {fmtBRL(norma4Data.estimated_fund_contribution)}
                    </span>
                  </div>

                  <div className="border-t border-slate-700 pt-2">
                    <div className="flex justify-between text-sm font-medium">
                      <span className="text-slate-300">Carga tributaria total/mes</span>
                      <span className="text-blue-400">
                        R$ {fmtBRL(norma4Data.total_tax_burden_monthly)}
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Nivel de Risco</span>
                    <span
                      className={clsx(
                        'font-semibold',
                        norma4Data.risk_level === 'low'
                          ? 'text-green-400'
                          : norma4Data.risk_level === 'medium'
                            ? 'text-yellow-400'
                            : 'text-red-400'
                      )}
                    >
                      {RISK_LABELS[norma4Data.risk_level] ?? norma4Data.risk_level?.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Compliance requirements list */}
                {norma4Data.compliance_requirements && norma4Data.compliance_requirements.length > 0 && (
                  <div className="mt-3 border-t border-slate-700 pt-3">
                    <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                      Requisitos de Conformidade
                    </h4>
                    <ul className="space-y-1">
                      {norma4Data.compliance_requirements.map((req, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                          <Scale size={12} className="mt-0.5 shrink-0 text-blue-400" />
                          {req}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Licensing check result */}
          {licensingData && (
            <div className="enlace-card">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <Shield size={16} className="text-blue-400" />
                Licenciamento
              </h2>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Licenca SCM Necessaria</span>
                  <span
                    className={clsx(
                      'font-semibold',
                      licensingData.requires_scm_license ? 'text-red-400' : 'text-green-400'
                    )}
                  >
                    {licensingData.requires_scm_license ? 'Sim' : 'Nao'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Limite</span>
                  <span className="font-semibold text-slate-200">
                    {licensingData.threshold.toLocaleString('pt-BR')} assinantes
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-400">{licensingData.message}</p>
              </div>
            </div>
          )}

          {licensingError && (
            <div className="enlace-card">
              <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                <span className="font-medium">Erro no licenciamento:</span> {licensingError}
              </div>
            </div>
          )}
        </div>

        {/* ── CENTER + RIGHT COLUMNS ───────────────────────────────────── */}
        <div className="space-y-4 lg:col-span-2">
          {/* Provider ID input for compliance status */}
          <div className="enlace-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Shield size={16} className="text-blue-400" />
              Informacoes do Provedor
            </h2>
            <div className="flex gap-3">
              <input
                type="number"
                value={providerId}
                onChange={(e) => setProviderId(e.target.value)}
                placeholder="ID do provedor"
                className="enlace-input flex-1"
              />
              <button
                onClick={handleFetchStatus}
                disabled={statusLoading || !providerId}
                className="enlace-btn-primary flex items-center gap-2 whitespace-nowrap"
              >
                <FileCheck size={16} />
                {statusLoading ? 'Carregando...' : 'Verificar Conformidade'}
              </button>
            </div>
          </div>

          {/* Compliance checks */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                <FileCheck size={16} className="text-blue-400" />
                Verificacoes de Conformidade
              </h2>
              {statusData && (
                <span
                  className={clsx(
                    'text-xs font-medium',
                    statusData.overall_status === 'compliant'
                      ? 'text-green-400'
                      : statusData.overall_status === 'warning'
                        ? 'text-yellow-400'
                        : 'text-red-400'
                  )}
                >
                  Status geral: {STATUS_LABELS[statusData.overall_status] ?? statusData.overall_status}
                </span>
              )}
            </div>

            {statusError && (
              <div className="enlace-card rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                <span className="font-medium">Erro:</span> {statusError}
              </div>
            )}

            {!submittedProviderId && !statusLoading && (
              <div className="enlace-card flex items-center justify-center py-12 text-sm text-slate-500">
                Informe o ID do provedor para visualizar as verificacoes de conformidade.
              </div>
            )}

            {statusLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="enlace-card animate-pulse">
                    <div className="flex items-start gap-4">
                      <div className="mt-0.5 h-4 w-4 rounded bg-slate-700" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 w-48 rounded bg-slate-700" />
                        <div className="h-3 w-72 rounded bg-slate-700" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {checks.length > 0 && (
              <div className="space-y-3">
                {checks.map((check, idx) => (
                  <div key={idx} className="enlace-card flex items-start gap-4">
                    <div className="mt-0.5">
                      {statusIcon[check.status] ?? <AlertTriangle size={16} className="text-slate-400" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-slate-200">
                          {check.regulation}
                        </h3>
                        <span className={statusBadge[check.status] ?? 'enlace-badge-yellow'}>
                          {STATUS_LABELS[check.status] ?? check.status}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-400">{check.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Compliance overview chart */}
          <SimpleChart
            data={chartData}
            type="pie"
            xKey="name"
            yKey="value"
            title="Visao Geral de Conformidade"
            height={250}
            loading={statusLoading}
          />

          {/* ── Regulatory Deadlines ─────────────────────────────────── */}
          <div className="enlace-card">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Calendar size={16} className="text-blue-400" />
              Prazos Regulatorios
            </h2>

            {deadlinesError && (
              <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                <span className="font-medium">Erro:</span> {deadlinesError}
              </div>
            )}

            {deadlinesLoading && (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-4">
                    <div className="h-4 w-32 rounded bg-slate-700" />
                    <div className="h-4 w-24 rounded bg-slate-700" />
                    <div className="h-4 w-16 rounded bg-slate-700" />
                    <div className="h-4 flex-1 rounded bg-slate-700" />
                  </div>
                ))}
              </div>
            )}

            {deadlines && deadlines.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-left text-xs uppercase text-slate-400">
                      <th className="pb-2 pr-4 font-medium">Regulamentacao</th>
                      <th className="pb-2 pr-4 font-medium">Prazo</th>
                      <th className="pb-2 pr-4 font-medium">Dias Restantes</th>
                      <th className="pb-2 pr-4 font-medium">Status</th>
                      <th className="pb-2 font-medium">Descricao</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {deadlines.map((dl, idx) => (
                      <tr key={idx} className="text-slate-300">
                        <td className="py-2 pr-4 font-medium text-slate-200">
                          {dl.regulation}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap">
                          {new Date(dl.deadline).toLocaleDateString('pt-BR')}
                        </td>
                        <td className="py-2 pr-4">
                          <span
                            className={clsx(
                              'font-semibold',
                              dl.days_remaining <= 7
                                ? 'text-red-400'
                                : dl.days_remaining <= 30
                                  ? 'text-yellow-400'
                                  : 'text-green-400'
                            )}
                          >
                            {dl.days_remaining}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={deadlineStatusBadge(dl.status)}>
                            {dl.status}
                          </span>
                        </td>
                        <td className="py-2 text-slate-400">{dl.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {deadlines && deadlines.length === 0 && (
              <p className="py-6 text-center text-sm text-slate-500">
                Nenhum prazo regulatorio encontrado para os proximos 90 dias.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
