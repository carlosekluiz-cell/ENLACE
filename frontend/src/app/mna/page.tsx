'use client';

import { useState, useCallback } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import DataTable from '@/components/dashboard/DataTable';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type {
  ValuationResponse,
  AcquisitionTarget,
  SellerReport,
  MnaMarketOverview,
} from '@/lib/types';
import {
  Briefcase,
  Calculator,
  Target,
  FileText,
  TrendingUp,
  DollarSign,
  Users,
  Building2,
  Scale,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  Clock,
  ChevronRight,
  Zap,
  ShieldAlert,
  BarChart3,
} from 'lucide-react';
import { clsx } from 'clsx';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAZILIAN_STATES = [
  { value: 'AC', label: 'Acre' },
  { value: 'AL', label: 'Alagoas' },
  { value: 'AP', label: 'Amapa' },
  { value: 'AM', label: 'Amazonas' },
  { value: 'BA', label: 'Bahia' },
  { value: 'CE', label: 'Ceara' },
  { value: 'DF', label: 'Distrito Federal' },
  { value: 'ES', label: 'Espirito Santo' },
  { value: 'GO', label: 'Goias' },
  { value: 'MA', label: 'Maranhao' },
  { value: 'MT', label: 'Mato Grosso' },
  { value: 'MS', label: 'Mato Grosso do Sul' },
  { value: 'MG', label: 'Minas Gerais' },
  { value: 'PA', label: 'Para' },
  { value: 'PB', label: 'Paraiba' },
  { value: 'PR', label: 'Parana' },
  { value: 'PE', label: 'Pernambuco' },
  { value: 'PI', label: 'Piaui' },
  { value: 'RJ', label: 'Rio de Janeiro' },
  { value: 'RN', label: 'Rio Grande do Norte' },
  { value: 'RS', label: 'Rio Grande do Sul' },
  { value: 'RO', label: 'Rondonia' },
  { value: 'RR', label: 'Roraima' },
  { value: 'SC', label: 'Santa Catarina' },
  { value: 'SP', label: 'Sao Paulo' },
  { value: 'SE', label: 'Sergipe' },
  { value: 'TO', label: 'Tocantins' },
];

type TabKey = 'valuation' | 'targets' | 'seller' | 'market';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'valuation', label: 'Valuation', icon: <Calculator size={16} /> },
  { key: 'targets', label: 'Alvos de Aquisicao', icon: <Target size={16} /> },
  { key: 'seller', label: 'Preparacao p/ Venda', icon: <FileText size={16} /> },
  { key: 'market', label: 'Visao de Mercado', icon: <TrendingUp size={16} /> },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBRL(value: number | undefined | null): string {
  if (value === undefined || value === null) return 'R$ --';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '--';
  return value.toLocaleString('pt-BR');
}

function formatPct(value: number | undefined | null, decimals = 1): string {
  if (value === undefined || value === null) return '--%';
  return `${value.toFixed(decimals)}%`;
}

function riskBadgeClass(risk: string): string {
  const r = risk?.toLowerCase();
  if (r === 'low' || r === 'baixo') return 'enlace-badge-green';
  if (r === 'medium' || r === 'medio') return 'enlace-badge-yellow';
  return 'enlace-badge-red';
}

function riskLabel(risk: string): string {
  const r = risk?.toLowerCase();
  if (r === 'low') return 'Baixo';
  if (r === 'medium') return 'Medio';
  if (r === 'high') return 'Alto';
  return risk;
}

// ---------------------------------------------------------------------------
// Error Banner
// ---------------------------------------------------------------------------

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
      <AlertTriangle size={18} className="shrink-0 text-red-400" />
      <p className="text-sm text-red-300">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section Label
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
      {children}
    </h3>
  );
}

// ---------------------------------------------------------------------------
// Detail Row (reusable)
// ---------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-900 px-3 py-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-200">{value}</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 1 : Calculadora de Valuation
// ═══════════════════════════════════════════════════════════════════════════

function ValuationTab() {
  const [form, setForm] = useState({
    subscriber_count: '',
    fiber_pct: '50',
    monthly_revenue_brl: '',
    ebitda_margin_pct: '30',
    state_code: 'SP',
    monthly_churn_pct: '2',
    growth_rate_12m: '5',
    net_debt_brl: '0',
  });

  const {
    data: result,
    loading,
    error,
    execute,
  } = useLazyApi<ValuationResponse, Parameters<typeof api.mna.valuation>[0]>(
    useCallback((params) => api.mna.valuation(params), [])
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    execute({
      subscriber_count: Number(form.subscriber_count),
      fiber_pct: Number(form.fiber_pct) / 100,
      monthly_revenue_brl: Number(form.monthly_revenue_brl),
      ebitda_margin_pct: Number(form.ebitda_margin_pct) / 100,
      state_code: form.state_code,
      monthly_churn_pct: Number(form.monthly_churn_pct) / 100,
      growth_rate_12m: Number(form.growth_rate_12m) / 100,
      net_debt_brl: Number(form.net_debt_brl),
    });
  };

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  // Chart data from the three methods
  const chartData = result
    ? [
        {
          name: 'Mult. Assinante',
          valor:
            result.subscriber_multiple?.adjusted_valuation_brl ??
            result.subscriber_multiple?.valuation_brl ??
            0,
        },
        {
          name: 'Mult. Receita',
          valor:
            result.revenue_multiple?.ev_revenue_brl ??
            result.revenue_multiple?.valuation_brl ??
            0,
        },
        {
          name: 'DCF',
          valor:
            result.dcf?.enterprise_value_brl ??
            result.dcf?.valuation_brl ??
            0,
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro no calculo: ${error}`} />}

      {/* Form */}
      <form onSubmit={handleSubmit} className="enlace-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-200">
          <Calculator size={20} className="text-blue-400" />
          Calculadora de Valuation
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Assinantes *
            </label>
            <input
              type="number"
              required
              min={1}
              className="enlace-input w-full"
              placeholder="Ex: 5000"
              value={form.subscriber_count}
              onChange={(e) => update('subscriber_count', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              % Fibra
            </label>
            <input
              type="number"
              min={0}
              max={100}
              className="enlace-input w-full"
              value={form.fiber_pct}
              onChange={(e) => update('fiber_pct', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Receita Mensal R$ *
            </label>
            <input
              type="number"
              required
              min={0}
              className="enlace-input w-full"
              placeholder="Ex: 250000"
              value={form.monthly_revenue_brl}
              onChange={(e) => update('monthly_revenue_brl', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Margem EBITDA %
            </label>
            <input
              type="number"
              min={0}
              max={100}
              className="enlace-input w-full"
              value={form.ebitda_margin_pct}
              onChange={(e) => update('ebitda_margin_pct', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Estado
            </label>
            <select
              className="enlace-input w-full"
              value={form.state_code}
              onChange={(e) => update('state_code', e.target.value)}
            >
              {BRAZILIAN_STATES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.value} - {s.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Churn Mensal %
            </label>
            <input
              type="number"
              min={0}
              max={100}
              step="0.1"
              className="enlace-input w-full"
              value={form.monthly_churn_pct}
              onChange={(e) => update('monthly_churn_pct', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Crescimento 12m %
            </label>
            <input
              type="number"
              step="0.1"
              className="enlace-input w-full"
              value={form.growth_rate_12m}
              onChange={(e) => update('growth_rate_12m', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Divida Liquida R$
            </label>
            <input
              type="number"
              min={0}
              className="enlace-input w-full"
              value={form.net_debt_brl}
              onChange={(e) => update('net_debt_brl', e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="enlace-btn-primary flex items-center gap-2"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Calculator size={16} />
            )}
            {loading ? 'Calculando...' : 'Calcular Valuation'}
          </button>
        </div>
      </form>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Combined Range */}
          <div className="enlace-card border border-blue-500/20">
            <SectionLabel>Faixa de Valuation Combinada</SectionLabel>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-900 p-4 text-center">
                <p className="text-xs font-medium text-slate-500">
                  Conservador
                </p>
                <p className="mt-1 text-xl font-bold text-red-400">
                  {formatBRL(result.combined_range.low_brl)}
                </p>
              </div>
              <div className="rounded-lg bg-slate-900 p-4 text-center ring-2 ring-blue-500/30">
                <p className="text-xs font-medium text-blue-400">
                  Valor Medio
                </p>
                <p className="mt-1 text-2xl font-bold text-blue-300">
                  {formatBRL(result.combined_range.mid_brl)}
                </p>
              </div>
              <div className="rounded-lg bg-slate-900 p-4 text-center">
                <p className="text-xs font-medium text-slate-500">Otimista</p>
                <p className="mt-1 text-xl font-bold text-green-400">
                  {formatBRL(result.combined_range.high_brl)}
                </p>
              </div>
            </div>
          </div>

          {/* Three method cards */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Subscriber Multiple */}
            <div className="enlace-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <Users size={16} className="text-purple-400" />
                Multiplo de Assinante
              </h4>
              <div className="space-y-2">
                <DetailRow
                  label="Valuation Ajustado"
                  value={formatBRL(
                    result.subscriber_multiple?.adjusted_valuation_brl
                  )}
                />
                <DetailRow
                  label="Mult. Fibra"
                  value={`${result.subscriber_multiple?.fiber_multiple?.toFixed(2) ?? '--'}x`}
                />
                <DetailRow
                  label="Mult. Outros"
                  value={`${result.subscriber_multiple?.other_multiple?.toFixed(2) ?? '--'}x`}
                />
                <DetailRow
                  label="Confianca"
                  value={formatPct(
                    result.subscriber_multiple?.confidence != null
                      ? result.subscriber_multiple.confidence * 100
                      : null
                  )}
                />
              </div>
            </div>

            {/* Revenue Multiple */}
            <div className="enlace-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <DollarSign size={16} className="text-green-400" />
                Multiplo de Receita
              </h4>
              <div className="space-y-2">
                <DetailRow
                  label="EV/Receita"
                  value={formatBRL(result.revenue_multiple?.ev_revenue_brl)}
                />
                <DetailRow
                  label="EV/EBITDA"
                  value={formatBRL(result.revenue_multiple?.ev_ebitda_brl)}
                />
                <DetailRow
                  label="Mult. Receita"
                  value={`${result.revenue_multiple?.revenue_multiple?.toFixed(2) ?? '--'}x`}
                />
                <DetailRow
                  label="Mult. EBITDA"
                  value={`${result.revenue_multiple?.ebitda_multiple?.toFixed(2) ?? '--'}x`}
                />
              </div>
            </div>

            {/* DCF */}
            <div className="enlace-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <Scale size={16} className="text-cyan-400" />
                DCF (Fluxo Descontado)
              </h4>
              <div className="space-y-2">
                <DetailRow
                  label="Enterprise Value"
                  value={formatBRL(result.dcf?.enterprise_value_brl)}
                />
                <DetailRow
                  label="Equity Value"
                  value={formatBRL(result.dcf?.equity_value_brl)}
                />
                <DetailRow
                  label="WACC"
                  value={formatPct(result.dcf?.wacc_pct)}
                />
              </div>
            </div>
          </div>

          {/* Comparison Chart */}
          <SimpleChart
            data={chartData}
            type="bar"
            xKey="name"
            yKey="valor"
            title="Comparacao de Metodos de Valuation (R$)"
            height={280}
          />
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 2 : Alvos de Aquisicao
// ═══════════════════════════════════════════════════════════════════════════

const targetColumns = [
  {
    key: 'provider_name',
    label: 'Provedor',
    sortable: true,
    render: (value: string, row: AcquisitionTarget) => (
      <div>
        <span className="font-medium text-slate-100">{value}</span>
        <span className="ml-2 text-xs text-slate-500">
          {row.state_codes?.join(', ')}
        </span>
      </div>
    ),
  },
  {
    key: 'subscriber_count',
    label: 'Assinantes',
    sortable: true,
    render: (value: number) => formatNumber(value),
  },
  {
    key: 'fiber_pct',
    label: '% Fibra',
    sortable: true,
    render: (value: number) => (
      <span
        className={
          value * 100 > 60
            ? 'text-green-400'
            : value * 100 > 30
              ? 'text-yellow-400'
              : 'text-red-400'
        }
      >
        {formatPct(value * 100)}
      </span>
    ),
  },
  {
    key: 'estimated_revenue_brl',
    label: 'Receita Est.',
    sortable: true,
    render: (value: number) => formatBRL(value),
  },
  {
    key: 'overall_score',
    label: 'Score',
    sortable: true,
    render: (value: number) => (
      <div className="flex items-center gap-2">
        <div className="h-2 w-16 overflow-hidden rounded-full bg-slate-700">
          <div
            className="h-full rounded-full bg-blue-500"
            style={{ width: `${Math.min(value * 100, 100)}%` }}
          />
        </div>
        <span className="text-sm font-semibold text-blue-400">
          {(value * 100).toFixed(0)}
        </span>
      </div>
    ),
  },
  {
    key: 'integration_risk',
    label: 'Risco',
    sortable: true,
    render: (value: string) => (
      <span className={clsx('rounded px-2 py-0.5 text-xs font-medium', riskBadgeClass(value))}>
        {riskLabel(value)}
      </span>
    ),
  },
];

function TargetsTab() {
  const [form, setForm] = useState({
    acquirer_states: '',
    acquirer_subscribers: '',
    min_subs: '1000',
    max_subs: '50000',
  });

  const {
    data: targets,
    loading,
    error,
    execute,
  } = useLazyApi<AcquisitionTarget[], Parameters<typeof api.mna.targets>[0]>(
    useCallback((params) => api.mna.targets(params), [])
  );

  const [selectedTarget, setSelectedTarget] =
    useState<AcquisitionTarget | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSelectedTarget(null);
    execute({
      acquirer_states: form.acquirer_states
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
      acquirer_subscribers: Number(form.acquirer_subscribers),
      min_subs: Number(form.min_subs),
      max_subs: Number(form.max_subs),
    });
  };

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro na busca: ${error}`} />}

      {/* Form */}
      <form onSubmit={handleSubmit} className="enlace-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-200">
          <Target size={20} className="text-blue-400" />
          Busca de Alvos de Aquisicao
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Estados do Adquirente
            </label>
            <input
              type="text"
              className="enlace-input w-full"
              placeholder="SP,MG,PR"
              value={form.acquirer_states}
              onChange={(e) => update('acquirer_states', e.target.value)}
            />
            <p className="mt-0.5 text-[10px] text-slate-600">
              Separados por virgula
            </p>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Assinantes do Adquirente
            </label>
            <input
              type="number"
              className="enlace-input w-full"
              placeholder="Ex: 20000"
              value={form.acquirer_subscribers}
              onChange={(e) => update('acquirer_subscribers', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Assinantes Min. do Alvo
            </label>
            <input
              type="number"
              min={0}
              className="enlace-input w-full"
              value={form.min_subs}
              onChange={(e) => update('min_subs', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Assinantes Max. do Alvo
            </label>
            <input
              type="number"
              min={0}
              className="enlace-input w-full"
              value={form.max_subs}
              onChange={(e) => update('max_subs', e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="enlace-btn-primary flex items-center gap-2"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Target size={16} />
            )}
            {loading ? 'Buscando...' : 'Buscar Alvos'}
          </button>
        </div>
      </form>

      {/* Results */}
      {targets && (
        <div className="flex gap-6">
          <div className="flex-1">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">
              {targets.length} alvo{targets.length !== 1 ? 's' : ''}{' '}
              encontrado{targets.length !== 1 ? 's' : ''}
            </h3>
            <DataTable
              columns={targetColumns}
              data={targets}
              loading={loading}
              searchable
              searchKeys={['provider_name']}
              onRowClick={(row) => setSelectedTarget(row)}
              emptyMessage="Nenhum alvo encontrado com os criterios informados"
            />
          </div>

          {/* Detail sidebar */}
          {selectedTarget && (
            <div className="w-80 shrink-0">
              <div className="enlace-card sticky top-6">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-200">
                    Detalhes do Alvo
                  </h3>
                  <button
                    onClick={() => setSelectedTarget(null)}
                    className="text-slate-400 hover:text-slate-200"
                    aria-label="Fechar"
                  >
                    &times;
                  </button>
                </div>

                <h4 className="text-lg font-bold text-slate-100">
                  {selectedTarget.provider_name}
                </h4>
                <p className="mb-4 text-xs text-slate-500">
                  {selectedTarget.state_codes?.join(', ')} | ID{' '}
                  {selectedTarget.provider_id}
                </p>

                <div className="space-y-2">
                  <DetailRow
                    label="Assinantes"
                    value={formatNumber(selectedTarget.subscriber_count)}
                  />
                  <DetailRow
                    label="% Fibra"
                    value={formatPct(selectedTarget.fiber_pct * 100)}
                  />
                  <DetailRow
                    label="Receita Estimada"
                    value={formatBRL(selectedTarget.estimated_revenue_brl)}
                  />
                  <DetailRow
                    label="Score Estrategico"
                    value={(selectedTarget.strategic_score * 100).toFixed(0)}
                  />
                  <DetailRow
                    label="Score Financeiro"
                    value={(selectedTarget.financial_score * 100).toFixed(0)}
                  />
                  <DetailRow
                    label="Score Geral"
                    value={(selectedTarget.overall_score * 100).toFixed(0)}
                  />
                  <DetailRow
                    label="Risco Integracao"
                    value={riskLabel(selectedTarget.integration_risk)}
                  />
                  <DetailRow
                    label="Sinergias Estimadas"
                    value={formatBRL(selectedTarget.synergy_estimate_brl)}
                  />
                </div>

                <div className="mt-4">
                  <SectionLabel>Valuations</SectionLabel>
                  <div className="space-y-2">
                    <DetailRow
                      label="Mult. Assinante"
                      value={formatBRL(selectedTarget.valuation_subscriber)}
                    />
                    <DetailRow
                      label="Mult. Receita"
                      value={formatBRL(selectedTarget.valuation_revenue)}
                    />
                    <DetailRow
                      label="DCF"
                      value={formatBRL(selectedTarget.valuation_dcf)}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 3 : Preparacao para Venda
// ═══════════════════════════════════════════════════════════════════════════

function SellerTab() {
  const [form, setForm] = useState({
    provider_name: '',
    state_codes: '',
    subscriber_count: '',
    fiber_pct: '50',
    monthly_revenue_brl: '',
    ebitda_margin_pct: '30',
    net_debt_brl: '0',
  });

  const {
    data: report,
    loading,
    error,
    execute,
  } = useLazyApi<SellerReport, Parameters<typeof api.mna.sellerPrepare>[0]>(
    useCallback((params) => api.mna.sellerPrepare(params), [])
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    execute({
      provider_name: form.provider_name,
      state_codes: form.state_codes
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
      subscriber_count: Number(form.subscriber_count),
      fiber_pct: Number(form.fiber_pct) / 100,
      monthly_revenue_brl: Number(form.monthly_revenue_brl),
      ebitda_margin_pct: Number(form.ebitda_margin_pct) / 100,
      net_debt_brl: Number(form.net_debt_brl),
    });
  };

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro ao gerar relatorio: ${error}`} />}

      {/* Form */}
      <form onSubmit={handleSubmit} className="enlace-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-200">
          <FileText size={20} className="text-blue-400" />
          Preparacao para Venda
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Nome do Provedor *
            </label>
            <input
              type="text"
              required
              className="enlace-input w-full"
              placeholder="Ex: ISP Brasil Telecom"
              value={form.provider_name}
              onChange={(e) => update('provider_name', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Estados
            </label>
            <input
              type="text"
              className="enlace-input w-full"
              placeholder="SP,MG"
              value={form.state_codes}
              onChange={(e) => update('state_codes', e.target.value)}
            />
            <p className="mt-0.5 text-[10px] text-slate-600">
              Separados por virgula
            </p>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Assinantes *
            </label>
            <input
              type="number"
              required
              min={1}
              className="enlace-input w-full"
              placeholder="Ex: 8000"
              value={form.subscriber_count}
              onChange={(e) => update('subscriber_count', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              % Fibra
            </label>
            <input
              type="number"
              min={0}
              max={100}
              className="enlace-input w-full"
              value={form.fiber_pct}
              onChange={(e) => update('fiber_pct', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Receita Mensal R$ *
            </label>
            <input
              type="number"
              required
              min={0}
              className="enlace-input w-full"
              placeholder="Ex: 400000"
              value={form.monthly_revenue_brl}
              onChange={(e) => update('monthly_revenue_brl', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Margem EBITDA %
            </label>
            <input
              type="number"
              min={0}
              max={100}
              className="enlace-input w-full"
              value={form.ebitda_margin_pct}
              onChange={(e) => update('ebitda_margin_pct', e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Divida Liquida R$
            </label>
            <input
              type="number"
              min={0}
              className="enlace-input w-full"
              value={form.net_debt_brl}
              onChange={(e) => update('net_debt_brl', e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="enlace-btn-primary flex items-center gap-2"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <FileText size={16} />
            )}
            {loading ? 'Gerando...' : 'Gerar Relatorio de Preparacao'}
          </button>
        </div>
      </form>

      {/* Report Results */}
      {report && (
        <div className="space-y-6">
          {/* Value Range */}
          <div className="enlace-card border border-blue-500/20">
            <SectionLabel>Faixa de Valor Estimado</SectionLabel>
            <div className="flex items-center justify-center gap-6">
              <div className="text-center">
                <p className="text-xs text-slate-500">Minimo</p>
                <p className="text-xl font-bold text-red-400">
                  {formatBRL(report.estimated_value_range?.[0])}
                </p>
              </div>
              <ChevronRight size={24} className="text-slate-600" />
              <div className="text-center">
                <p className="text-xs text-slate-500">Maximo</p>
                <p className="text-xl font-bold text-green-400">
                  {formatBRL(report.estimated_value_range?.[1])}
                </p>
              </div>
            </div>
          </div>

          {/* Strengths & Weaknesses */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="enlace-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-green-400">
                <CheckCircle2 size={16} />
                Pontos Fortes
              </h4>
              <ul className="space-y-2">
                {report.strengths?.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-slate-300"
                  >
                    <CheckCircle2
                      size={14}
                      className="mt-0.5 shrink-0 text-green-500"
                    />
                    {s}
                  </li>
                ))}
                {(!report.strengths || report.strengths.length === 0) && (
                  <li className="text-sm text-slate-500">
                    Nenhum ponto forte identificado
                  </li>
                )}
              </ul>
            </div>

            <div className="enlace-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-400">
                <ShieldAlert size={16} />
                Pontos Fracos
              </h4>
              <ul className="space-y-2">
                {report.weaknesses?.map((w, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-slate-300"
                  >
                    <ShieldAlert
                      size={14}
                      className="mt-0.5 shrink-0 text-red-500"
                    />
                    {w}
                  </li>
                ))}
                {(!report.weaknesses || report.weaknesses.length === 0) && (
                  <li className="text-sm text-slate-500">
                    Nenhum ponto fraco identificado
                  </li>
                )}
              </ul>
            </div>
          </div>

          {/* Value Enhancement Opportunities */}
          <div className="enlace-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Zap size={16} className="text-amber-400" />
              Oportunidades de Valorizacao
            </h4>
            {report.value_enhancement_opportunities &&
            report.value_enhancement_opportunities.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {report.value_enhancement_opportunities.map((opp, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-slate-700 bg-slate-900 p-3"
                  >
                    <p className="text-sm font-medium text-slate-200">
                      {opp.title || opp.name || `Oportunidade ${i + 1}`}
                    </p>
                    {opp.description && (
                      <p className="mt-1 text-xs text-slate-400">
                        {opp.description}
                      </p>
                    )}
                    {opp.estimated_impact_brl != null && (
                      <p className="mt-2 text-xs font-medium text-green-400">
                        Impacto: {formatBRL(opp.estimated_impact_brl)}
                      </p>
                    )}
                    {opp.effort && (
                      <p className="mt-0.5 text-xs text-slate-500">
                        Esforco: {opp.effort}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                Nenhuma oportunidade identificada
              </p>
            )}
          </div>

          {/* Preparation Checklist */}
          <div className="enlace-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Briefcase size={16} className="text-blue-400" />
              Checklist de Preparacao
            </h4>
            {report.preparation_checklist &&
            report.preparation_checklist.length > 0 ? (
              <div className="space-y-2">
                {report.preparation_checklist.map((item, i) => {
                  const rawStatus: string =
                    item.status?.toLowerCase() || (item.completed ? 'done' : 'pending');
                  const isDone =
                    rawStatus === 'done' ||
                    rawStatus === 'completed' ||
                    rawStatus === 'concluido';
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-lg bg-slate-900 px-3 py-2"
                    >
                      {isDone ? (
                        <CheckCircle2
                          size={16}
                          className="shrink-0 text-green-400"
                        />
                      ) : (
                        <Clock
                          size={16}
                          className="shrink-0 text-amber-400"
                        />
                      )}
                      <div className="flex-1">
                        <p
                          className={clsx(
                            'text-sm',
                            isDone
                              ? 'text-slate-400 line-through'
                              : 'text-slate-200'
                          )}
                        >
                          {item.task || item.title || item.name || item.item}
                        </p>
                        {item.description && (
                          <p className="text-xs text-slate-500">
                            {item.description}
                          </p>
                        )}
                      </div>
                      <span
                        className={clsx(
                          'rounded px-2 py-0.5 text-[10px] font-medium',
                          isDone ? 'enlace-badge-green' : 'enlace-badge-yellow'
                        )}
                      >
                        {isDone ? 'Concluido' : 'Pendente'}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Nenhum item no checklist</p>
            )}
          </div>

          {/* Timeline */}
          {report.estimated_timeline_months != null && (
            <div className="enlace-card">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <Clock size={16} className="text-cyan-400" />
                Cronograma Estimado
              </h4>
              <p className="text-2xl font-bold text-blue-300">
                {report.estimated_timeline_months} meses
              </p>
              <p className="text-xs text-slate-500">
                Tempo estimado para conclusao do processo de venda
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 4 : Visao de Mercado
// ═══════════════════════════════════════════════════════════════════════════

function MarketTab() {
  const [selectedState, setSelectedState] = useState('SP');

  const {
    data: overview,
    loading,
    error,
  } = useApi<MnaMarketOverview>(
    () => api.mna.marketOverview(selectedState),
    [selectedState]
  );

  const transactionColumns = [
    {
      key: 'acquirer',
      label: 'Adquirente',
      sortable: true,
      render: (value: string) => (
        <span className="font-medium text-slate-100">{value ?? '--'}</span>
      ),
    },
    {
      key: 'target',
      label: 'Alvo',
      sortable: true,
    },
    {
      key: 'date',
      label: 'Data',
      sortable: true,
    },
    {
      key: 'subscribers',
      label: 'Assinantes',
      sortable: true,
      render: (value: number) => (value ? formatNumber(value) : '--'),
    },
    {
      key: 'value_brl',
      label: 'Valor (R$)',
      sortable: true,
      render: (value: number) => (value ? formatBRL(value) : '--'),
    },
    {
      key: 'value_per_sub',
      label: 'R$/Assinante',
      sortable: true,
      render: (value: number) => (value ? formatBRL(value) : '--'),
    },
  ];

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro ao carregar dados: ${error}`} />}

      {/* State selector */}
      <div className="enlace-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-200">
          <Building2 size={20} className="text-blue-400" />
          Visao de Mercado M&A
        </h2>
        <div className="max-w-xs">
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Selecione o Estado
          </label>
          <select
            className="enlace-input w-full"
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
          >
            {BRAZILIAN_STATES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.value} - {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Total ISPs"
          value={overview?.total_isps ?? '--'}
          icon={<Building2 size={18} />}
          subtitle={`Estado: ${selectedState}`}
          loading={loading}
        />
        <StatsCard
          title="Total Assinantes"
          value={
            overview?.total_subscribers
              ? formatNumber(overview.total_subscribers)
              : '--'
          }
          icon={<Users size={18} />}
          loading={loading}
        />
        <StatsCard
          title="Valuation Medio/Assinante"
          value={
            overview?.avg_valuation_per_sub
              ? formatBRL(overview.avg_valuation_per_sub)
              : '--'
          }
          icon={<DollarSign size={18} />}
          loading={loading}
        />
        <StatsCard
          title="% Fibra Medio"
          value={
            overview?.fiber_pct_avg
              ? formatPct(overview.fiber_pct_avg * 100)
              : '--'
          }
          icon={<BarChart3 size={18} />}
          loading={loading}
        />
      </div>

      {/* Summary Chart */}
      {overview && (
        <SimpleChart
          data={[
            {
              name: 'ISPs',
              valor: overview.total_isps ?? 0,
            },
            {
              name: 'Assinantes (mil)',
              valor: overview.total_subscribers
                ? Math.round(overview.total_subscribers / 1000)
                : 0,
            },
            {
              name: 'Val. Medio (R$)',
              valor: overview.avg_valuation_per_sub ?? 0,
            },
            {
              name: '% Fibra',
              valor: overview.fiber_pct_avg
                ? Math.round(overview.fiber_pct_avg * 100)
                : 0,
            },
          ]}
          type="bar"
          xKey="name"
          yKey="valor"
          title={`Indicadores de Mercado - ${selectedState}`}
          height={250}
          loading={loading}
        />
      )}

      {/* Recent Transactions */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Briefcase size={16} className="text-slate-400" />
          Transacoes Recentes - {selectedState}
        </h3>
        <DataTable
          columns={transactionColumns}
          data={overview?.recent_transactions ?? []}
          loading={loading}
          emptyMessage="Nenhuma transacao recente encontrada para este estado"
          searchable
          searchKeys={['acquirer', 'target']}
        />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function MnaPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('valuation');

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold text-slate-100">
          <Briefcase size={28} className="text-blue-400" />
          Inteligencia M&A
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Valuation, busca de alvos e preparacao para fusoes e aquisicoes no
          setor ISP brasileiro
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-800/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex items-center gap-2 whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-200'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active Tab Content */}
      {activeTab === 'valuation' && <ValuationTab />}
      {activeTab === 'targets' && <TargetsTab />}
      {activeTab === 'seller' && <SellerTab />}
      {activeTab === 'market' && <MarketTab />}
    </div>
  );
}
