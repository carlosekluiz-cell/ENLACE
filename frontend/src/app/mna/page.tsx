'use client';

import { useState, useCallback } from 'react';
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
  if (r === 'low' || r === 'baixo') return 'pulso-badge-green';
  if (r === 'medium' || r === 'medio') return 'pulso-badge-yellow';
  return 'pulso-badge-red';
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
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{
        borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
        backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
      }}
    >
      <AlertTriangle size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
      <p className="text-sm" style={{ color: 'var(--danger)' }}>{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section Label
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
      {children}
    </h3>
  );
}

// ---------------------------------------------------------------------------
// Detail Row (reusable)
// ---------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-subtle)' }}>
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 1 : Calculadora de Valuation
// ---------------------------------------------------------------------------

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

  const chartData = result
    ? [
        { name: 'Mult. Assinante', valor: result.subscriber_multiple?.adjusted_valuation_brl ?? result.subscriber_multiple?.valuation_brl ?? 0 },
        { name: 'Mult. Receita', valor: result.revenue_multiple?.ev_revenue_brl ?? result.revenue_multiple?.valuation_brl ?? 0 },
        { name: 'DCF', valor: result.dcf?.enterprise_value_brl ?? result.dcf?.valuation_brl ?? 0 },
      ]
    : [];

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro no calculo: ${error}`} />}

      <form onSubmit={handleSubmit} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <Calculator size={20} style={{ color: 'var(--accent)' }} />
          Calculadora de Valuation
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes *</label>
            <input type="number" required min={1} className="pulso-input w-full" placeholder="Ex: 5000" value={form.subscriber_count} onChange={(e) => update('subscriber_count', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>% Fibra</label>
            <input type="number" min={0} max={100} className="pulso-input w-full" value={form.fiber_pct} onChange={(e) => update('fiber_pct', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Receita Mensal R$ *</label>
            <input type="number" required min={0} className="pulso-input w-full" placeholder="Ex: 250000" value={form.monthly_revenue_brl} onChange={(e) => update('monthly_revenue_brl', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Margem EBITDA %</label>
            <input type="number" min={0} max={100} className="pulso-input w-full" value={form.ebitda_margin_pct} onChange={(e) => update('ebitda_margin_pct', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Estado</label>
            <select className="pulso-input w-full" value={form.state_code} onChange={(e) => update('state_code', e.target.value)}>
              {BRAZILIAN_STATES.map((s) => (<option key={s.value} value={s.value}>{s.value} - {s.label}</option>))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Churn Mensal %</label>
            <input type="number" min={0} max={100} step="0.1" className="pulso-input w-full" value={form.monthly_churn_pct} onChange={(e) => update('monthly_churn_pct', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Crescimento 12m %</label>
            <input type="number" step="0.1" className="pulso-input w-full" value={form.growth_rate_12m} onChange={(e) => update('growth_rate_12m', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Divida Liquida R$</label>
            <input type="number" min={0} className="pulso-input w-full" value={form.net_debt_brl} onChange={(e) => update('net_debt_brl', e.target.value)} />
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2">
            <Calculator size={16} />
            {loading ? 'Calculando...' : 'Calcular Valuation'}
          </button>
        </div>
      </form>

      {result && (
        <div className="space-y-6">
          <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
            <SectionLabel>Faixa de Valuation Combinada</SectionLabel>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Conservador</p>
                <p className="mt-1 text-xl font-bold" style={{ color: 'var(--danger)' }}>{formatBRL(result.combined_range.low_brl)}</p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)', boxShadow: '0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>Valor Medio</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--accent)' }}>{formatBRL(result.combined_range.mid_brl)}</p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Otimista</p>
                <p className="mt-1 text-xl font-bold" style={{ color: 'var(--success)' }}>{formatBRL(result.combined_range.high_brl)}</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Users size={16} className="text-purple-400" />
                Multiplo de Assinante
              </h4>
              <div className="space-y-2">
                <DetailRow label="Valuation Ajustado" value={formatBRL(result.subscriber_multiple?.adjusted_valuation_brl)} />
                <DetailRow label="Mult. Fibra" value={`${result.subscriber_multiple?.fiber_multiple?.toFixed(2) ?? '--'}x`} />
                <DetailRow label="Mult. Outros" value={`${result.subscriber_multiple?.other_multiple?.toFixed(2) ?? '--'}x`} />
                <DetailRow label="Confianca" value={typeof result.subscriber_multiple?.confidence === 'string' ? result.subscriber_multiple.confidence : formatPct(result.subscriber_multiple?.confidence != null ? result.subscriber_multiple.confidence * 100 : null)} />
              </div>
            </div>

            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <DollarSign size={16} style={{ color: 'var(--success)' }} />
                Multiplo de Receita
              </h4>
              <div className="space-y-2">
                <DetailRow label="EV/Receita" value={formatBRL(result.revenue_multiple?.ev_revenue_brl)} />
                <DetailRow label="EV/EBITDA" value={formatBRL(result.revenue_multiple?.ev_ebitda_brl)} />
                <DetailRow label="Mult. Receita" value={`${result.revenue_multiple?.revenue_multiple?.toFixed(2) ?? '--'}x`} />
                <DetailRow label="Mult. EBITDA" value={`${result.revenue_multiple?.ebitda_multiple?.toFixed(2) ?? '--'}x`} />
              </div>
            </div>

            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Scale size={16} className="text-cyan-400" />
                DCF (Fluxo Descontado)
              </h4>
              <div className="space-y-2">
                <DetailRow label="Enterprise Value" value={formatBRL(result.dcf?.enterprise_value_brl)} />
                <DetailRow label="Equity Value" value={formatBRL(result.dcf?.equity_value_brl)} />
                <DetailRow label="WACC" value={formatPct(result.dcf?.wacc_pct)} />
              </div>
            </div>
          </div>

          <SimpleChart data={chartData} type="bar" xKey="name" yKey="valor" title="Comparacao de Metodos de Valuation (R$)" height={280} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 2 : Alvos de Aquisicao
// ---------------------------------------------------------------------------

const targetColumns = [
  {
    key: 'provider_name',
    label: 'Provedor',
    sortable: true,
    render: (value: string, row: AcquisitionTarget) => (
      <div>
        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
        <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>{row.state_codes?.join(', ')}</span>
      </div>
    ),
  },
  { key: 'subscriber_count', label: 'Assinantes', sortable: true, render: (value: number) => formatNumber(value) },
  {
    key: 'fiber_pct',
    label: '% Fibra',
    sortable: true,
    render: (value: number) => (
      <span style={{ color: value * 100 > 60 ? 'var(--success)' : value * 100 > 30 ? 'var(--warning)' : 'var(--danger)' }}>
        {formatPct(value * 100)}
      </span>
    ),
  },
  { key: 'estimated_revenue_brl', label: 'Receita Est.', sortable: true, render: (value: number) => formatBRL(value) },
  {
    key: 'overall_score',
    label: 'Score',
    sortable: true,
    render: (value: number) => (
      <div className="flex items-center gap-2">
        <div className="h-2 w-16 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
          <div className="h-full rounded-full" style={{ width: `${Math.min(value * 100, 100)}%`, backgroundColor: 'var(--accent)' }} />
        </div>
        <span className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>{(value * 100).toFixed(0)}</span>
      </div>
    ),
  },
  {
    key: 'integration_risk',
    label: 'Risco',
    sortable: true,
    render: (value: string) => (
      <span className={clsx('rounded px-2 py-0.5 text-xs font-medium', riskBadgeClass(value))}>{riskLabel(value)}</span>
    ),
  },
];

function TargetsTab() {
  const [form, setForm] = useState({ acquirer_states: '', acquirer_subscribers: '', min_subs: '1000', max_subs: '50000' });
  const { data: targets, loading, error, execute } = useLazyApi<AcquisitionTarget[], Parameters<typeof api.mna.targets>[0]>(
    useCallback((params) => api.mna.targets(params), [])
  );
  const [selectedTarget, setSelectedTarget] = useState<AcquisitionTarget | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSelectedTarget(null);
    execute({
      acquirer_states: form.acquirer_states.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
      acquirer_subscribers: Number(form.acquirer_subscribers),
      min_subs: Number(form.min_subs),
      max_subs: Number(form.max_subs),
    });
  };

  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro na busca: ${error}`} />}

      <form onSubmit={handleSubmit} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <Target size={20} style={{ color: 'var(--accent)' }} />
          Busca de Alvos de Aquisicao
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Estados do Adquirente</label>
            <input type="text" className="pulso-input w-full" placeholder="SP,MG,PR" value={form.acquirer_states} onChange={(e) => update('acquirer_states', e.target.value)} />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>Separados por virgula</p>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes do Adquirente</label>
            <input type="number" className="pulso-input w-full" placeholder="Ex: 20000" value={form.acquirer_subscribers} onChange={(e) => update('acquirer_subscribers', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes Min. do Alvo</label>
            <input type="number" min={0} className="pulso-input w-full" value={form.min_subs} onChange={(e) => update('min_subs', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes Max. do Alvo</label>
            <input type="number" min={0} className="pulso-input w-full" value={form.max_subs} onChange={(e) => update('max_subs', e.target.value)} />
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2">
            <Target size={16} />
            {loading ? 'Buscando...' : 'Buscar Alvos'}
          </button>
        </div>
      </form>

      {targets && (
        <div className="flex gap-6">
          <div className="flex-1">
            <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              {targets.length} alvo{targets.length !== 1 ? 's' : ''} encontrado{targets.length !== 1 ? 's' : ''}
            </h3>
            <DataTable columns={targetColumns} data={targets} loading={loading} searchable searchKeys={['provider_name']} onRowClick={(row) => setSelectedTarget(row)} emptyMessage="Nenhum alvo encontrado com os criterios informados" />
          </div>

          {selectedTarget && (
            <div className="w-80 shrink-0">
              <div className="pulso-card sticky top-6">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Detalhes do Alvo</h3>
                  <button onClick={() => setSelectedTarget(null)} style={{ color: 'var(--text-secondary)' }} aria-label="Fechar">&times;</button>
                </div>
                <h4 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedTarget.provider_name}</h4>
                <p className="mb-4 text-xs" style={{ color: 'var(--text-muted)' }}>{selectedTarget.state_codes?.join(', ')} | ID {selectedTarget.provider_id}</p>
                <div className="space-y-2">
                  <DetailRow label="Assinantes" value={formatNumber(selectedTarget.subscriber_count)} />
                  <DetailRow label="% Fibra" value={formatPct(selectedTarget.fiber_pct * 100)} />
                  <DetailRow label="Receita Estimada" value={formatBRL(selectedTarget.estimated_revenue_brl)} />
                  <DetailRow label="Score Estrategico" value={(selectedTarget.strategic_score * 100).toFixed(0)} />
                  <DetailRow label="Score Financeiro" value={(selectedTarget.financial_score * 100).toFixed(0)} />
                  <DetailRow label="Score Geral" value={(selectedTarget.overall_score * 100).toFixed(0)} />
                  <DetailRow label="Risco Integracao" value={riskLabel(selectedTarget.integration_risk)} />
                  <DetailRow label="Sinergias Estimadas" value={formatBRL(selectedTarget.synergy_estimate_brl)} />
                </div>
                <div className="mt-4">
                  <SectionLabel>Valuations</SectionLabel>
                  <div className="space-y-2">
                    <DetailRow label="Mult. Assinante" value={formatBRL(selectedTarget.valuation_subscriber)} />
                    <DetailRow label="Mult. Receita" value={formatBRL(selectedTarget.valuation_revenue)} />
                    <DetailRow label="DCF" value={formatBRL(selectedTarget.valuation_dcf)} />
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

// ---------------------------------------------------------------------------
// TAB 3 : Preparacao para Venda
// ---------------------------------------------------------------------------

function SellerTab() {
  const [form, setForm] = useState({ provider_name: '', state_codes: '', subscriber_count: '', fiber_pct: '50', monthly_revenue_brl: '', ebitda_margin_pct: '30', net_debt_brl: '0' });
  const { data: report, loading, error, execute } = useLazyApi<SellerReport, Parameters<typeof api.mna.sellerPrepare>[0]>(
    useCallback((params) => api.mna.sellerPrepare(params), [])
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    execute({
      provider_name: form.provider_name,
      state_codes: form.state_codes.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
      subscriber_count: Number(form.subscriber_count),
      fiber_pct: Number(form.fiber_pct) / 100,
      monthly_revenue_brl: Number(form.monthly_revenue_brl),
      ebitda_margin_pct: Number(form.ebitda_margin_pct) / 100,
      net_debt_brl: Number(form.net_debt_brl),
    });
  };

  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro ao gerar relatorio: ${error}`} />}

      <form onSubmit={handleSubmit} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <FileText size={20} style={{ color: 'var(--accent)' }} />
          Preparacao para Venda
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Nome do Provedor *</label>
            <input type="text" required className="pulso-input w-full" placeholder="Ex: ISP Brasil Telecom" value={form.provider_name} onChange={(e) => update('provider_name', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Estados</label>
            <input type="text" className="pulso-input w-full" placeholder="SP,MG" value={form.state_codes} onChange={(e) => update('state_codes', e.target.value)} />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>Separados por virgula</p>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes *</label>
            <input type="number" required min={1} className="pulso-input w-full" placeholder="Ex: 8000" value={form.subscriber_count} onChange={(e) => update('subscriber_count', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>% Fibra</label>
            <input type="number" min={0} max={100} className="pulso-input w-full" value={form.fiber_pct} onChange={(e) => update('fiber_pct', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Receita Mensal R$ *</label>
            <input type="number" required min={0} className="pulso-input w-full" placeholder="Ex: 400000" value={form.monthly_revenue_brl} onChange={(e) => update('monthly_revenue_brl', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Margem EBITDA %</label>
            <input type="number" min={0} max={100} className="pulso-input w-full" value={form.ebitda_margin_pct} onChange={(e) => update('ebitda_margin_pct', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Divida Liquida R$</label>
            <input type="number" min={0} className="pulso-input w-full" value={form.net_debt_brl} onChange={(e) => update('net_debt_brl', e.target.value)} />
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2">
            <FileText size={16} />
            {loading ? 'Gerando...' : 'Gerar Relatorio de Preparacao'}
          </button>
        </div>
      </form>

      {report && (
        <div className="space-y-6">
          <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
            <SectionLabel>Faixa de Valor Estimado</SectionLabel>
            <div className="flex items-center justify-center gap-6">
              <div className="text-center">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Minimo</p>
                <p className="text-xl font-bold" style={{ color: 'var(--danger)' }}>{formatBRL(report.estimated_value_range?.[0])}</p>
              </div>
              <ChevronRight size={24} style={{ color: 'var(--text-muted)' }} />
              <div className="text-center">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Maximo</p>
                <p className="text-xl font-bold" style={{ color: 'var(--success)' }}>{formatBRL(report.estimated_value_range?.[1])}</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--success)' }}>
                <CheckCircle2 size={16} />
                Pontos Fortes
              </h4>
              <ul className="space-y-2">
                {report.strengths?.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--success)' }} />
                    {s}
                  </li>
                ))}
                {(!report.strengths || report.strengths.length === 0) && (
                  <li className="text-sm" style={{ color: 'var(--text-muted)' }}>Nenhum ponto forte identificado</li>
                )}
              </ul>
            </div>

            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--danger)' }}>
                <ShieldAlert size={16} />
                Pontos Fracos
              </h4>
              <ul className="space-y-2">
                {report.weaknesses?.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <ShieldAlert size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--danger)' }} />
                    {w}
                  </li>
                ))}
                {(!report.weaknesses || report.weaknesses.length === 0) && (
                  <li className="text-sm" style={{ color: 'var(--text-muted)' }}>Nenhum ponto fraco identificado</li>
                )}
              </ul>
            </div>
          </div>

          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Zap size={16} className="text-amber-400" />
              Oportunidades de Valorizacao
            </h4>
            {report.value_enhancement_opportunities && report.value_enhancement_opportunities.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {report.value_enhancement_opportunities.map((opp, i) => (
                  <div key={i} className="rounded-lg border p-3" style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg-subtle)' }}>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{opp.title || opp.name || `Oportunidade ${i + 1}`}</p>
                    {opp.description && <p className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{opp.description}</p>}
                    {opp.estimated_impact_brl != null && <p className="mt-2 text-xs font-medium" style={{ color: 'var(--success)' }}>Impacto: {formatBRL(opp.estimated_impact_brl)}</p>}
                    {opp.effort && <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>Esforco: {opp.effort}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Nenhuma oportunidade identificada</p>
            )}
          </div>

          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Briefcase size={16} style={{ color: 'var(--accent)' }} />
              Checklist de Preparacao
            </h4>
            {report.preparation_checklist && report.preparation_checklist.length > 0 ? (
              <div className="space-y-2">
                {report.preparation_checklist.map((item, i) => {
                  const rawStatus: string = item.status?.toLowerCase() || (item.completed ? 'done' : 'pending');
                  const isDone = rawStatus === 'done' || rawStatus === 'completed' || rawStatus === 'concluido';
                  return (
                    <div key={i} className="flex items-center gap-3 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                      {isDone ? <CheckCircle2 size={16} className="shrink-0" style={{ color: 'var(--success)' }} /> : <Clock size={16} className="shrink-0 text-amber-400" />}
                      <div className="flex-1">
                        <p className={clsx('text-sm', isDone && 'line-through')} style={{ color: isDone ? 'var(--text-secondary)' : 'var(--text-primary)' }}>
                          {item.task || item.title || item.name || item.item}
                        </p>
                        {item.description && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{item.description}</p>}
                      </div>
                      <span className={clsx('rounded px-2 py-0.5 text-[10px] font-medium', isDone ? 'pulso-badge-green' : 'pulso-badge-yellow')}>
                        {isDone ? 'Concluido' : 'Pendente'}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Nenhum item no checklist</p>
            )}
          </div>

          {report.estimated_timeline_months != null && (
            <div className="pulso-card">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Clock size={16} className="text-cyan-400" />
                Cronograma Estimado
              </h4>
              <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>{report.estimated_timeline_months} meses</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Tempo estimado para conclusao do processo de venda</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 4 : Visao de Mercado
// ---------------------------------------------------------------------------

function MarketTab() {
  const [selectedState, setSelectedState] = useState('SP');
  const { data: overview, loading, error } = useApi<MnaMarketOverview>(
    () => api.mna.marketOverview(selectedState),
    [selectedState]
  );

  const transactionColumns = [
    { key: 'acquirer', label: 'Adquirente', sortable: true, render: (value: string) => (<span className="font-medium" style={{ color: 'var(--text-primary)' }}>{value ?? '--'}</span>) },
    { key: 'target', label: 'Alvo', sortable: true },
    { key: 'date', label: 'Data', sortable: true },
    { key: 'subscribers', label: 'Assinantes', sortable: true, render: (value: number) => (value ? formatNumber(value) : '--') },
    { key: 'value_brl', label: 'Valor (R$)', sortable: true, render: (value: number) => (value ? formatBRL(value) : '--') },
    { key: 'value_per_sub', label: 'R$/Assinante', sortable: true, render: (value: number) => (value ? formatBRL(value) : '--') },
  ];

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro ao carregar dados: ${error}`} />}

      <div className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <Building2 size={20} style={{ color: 'var(--accent)' }} />
          Visao de Mercado M&A
        </h2>
        <div className="max-w-xs">
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Selecione o Estado</label>
          <select className="pulso-input w-full" value={selectedState} onChange={(e) => setSelectedState(e.target.value)}>
            {BRAZILIAN_STATES.map((s) => (<option key={s.value} value={s.value}>{s.value} - {s.label}</option>))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Total ISPs</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? 'Carregando...' : overview?.total_isps ?? '--'}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Estado: {selectedState}</p>
            </div>
            <Building2 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Total Assinantes</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? 'Carregando...' : overview?.total_subscribers ? formatNumber(overview.total_subscribers) : '--'}</p>
            </div>
            <Users size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Valuation Medio/Assinante</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? 'Carregando...' : overview?.avg_valuation_per_sub ? formatBRL(overview.avg_valuation_per_sub) : '--'}</p>
            </div>
            <DollarSign size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>% Fibra Medio</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? 'Carregando...' : overview?.fiber_pct_avg ? formatPct(overview.fiber_pct_avg * 100) : '--'}</p>
            </div>
            <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {overview && (
        <SimpleChart
          data={[
            { name: 'ISPs', valor: overview.total_isps ?? 0 },
            { name: 'Assinantes (mil)', valor: overview.total_subscribers ? Math.round(overview.total_subscribers / 1000) : 0 },
            { name: 'Val. Medio (R$)', valor: overview.avg_valuation_per_sub ?? 0 },
            { name: '% Fibra', valor: overview.fiber_pct_avg ? Math.round(overview.fiber_pct_avg * 100) : 0 },
          ]}
          type="bar"
          xKey="name"
          yKey="valor"
          title={`Indicadores de Mercado - ${selectedState}`}
          height={250}
          loading={loading}
        />
      )}

      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
          <Briefcase size={16} style={{ color: 'var(--text-secondary)' }} />
          Transacoes Recentes - {selectedState}
        </h3>
        <DataTable columns={transactionColumns} data={overview?.recent_transactions ?? []} loading={loading} emptyMessage="Nenhuma transacao recente encontrada para este estado" searchable searchKeys={['acquirer', 'target']} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MAIN PAGE
// ---------------------------------------------------------------------------

export default function MnaPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('valuation');

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Briefcase size={28} style={{ color: 'var(--accent)' }} />
          Inteligencia M&A
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Valuation, busca de alvos e preparacao para fusoes e aquisicoes no setor ISP brasileiro
        </p>
      </div>

      <div className="flex gap-1 overflow-x-auto rounded-lg p-1" style={{ backgroundColor: 'var(--bg-subtle)' }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="flex items-center gap-2 whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{
              backgroundColor: activeTab === tab.key ? 'var(--accent)' : 'transparent',
              color: activeTab === tab.key ? '#fff' : 'var(--text-secondary)',
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'valuation' && <ValuationTab />}
      {activeTab === 'targets' && <TargetsTab />}
      {activeTab === 'seller' && <SellerTab />}
      {activeTab === 'market' && <MarketTab />}
    </div>
  );
}
