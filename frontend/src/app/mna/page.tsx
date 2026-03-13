'use client';

import { useState, useCallback } from 'react';
import SimpleChart from '@/components/charts/SimpleChart';
import DataTable from '@/components/dashboard/DataTable';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api, fetchApi } from '@/lib/api';
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
  Radio,
  Search,
} from 'lucide-react';
import { clsx } from 'clsx';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAZILIAN_STATES = [
  { value: 'AC', label: 'Acre' },
  { value: 'AL', label: 'Alagoas' },
  { value: 'AP', label: 'Amapá' },
  { value: 'AM', label: 'Amazonas' },
  { value: 'BA', label: 'Bahia' },
  { value: 'CE', label: 'Ceará' },
  { value: 'DF', label: 'Distrito Federal' },
  { value: 'ES', label: 'Espírito Santo' },
  { value: 'GO', label: 'Goiás' },
  { value: 'MA', label: 'Maranhão' },
  { value: 'MT', label: 'Mato Grosso' },
  { value: 'MS', label: 'Mato Grosso do Sul' },
  { value: 'MG', label: 'Minas Gerais' },
  { value: 'PA', label: 'Pará' },
  { value: 'PB', label: 'Paraíba' },
  { value: 'PR', label: 'Paraná' },
  { value: 'PE', label: 'Pernambuco' },
  { value: 'PI', label: 'Piauí' },
  { value: 'RJ', label: 'Rio de Janeiro' },
  { value: 'RN', label: 'Rio Grande do Norte' },
  { value: 'RS', label: 'Rio Grande do Sul' },
  { value: 'RO', label: 'Rondônia' },
  { value: 'RR', label: 'Roraima' },
  { value: 'SC', label: 'Santa Catarina' },
  { value: 'SP', label: 'São Paulo' },
  { value: 'SE', label: 'Sergipe' },
  { value: 'TO', label: 'Tocantins' },
];

type TabKey = 'valuation' | 'targets' | 'seller' | 'market' | 'espectro' | 'dossier';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'valuation', label: 'Valuation', icon: <Calculator size={16} /> },
  { key: 'targets', label: 'Alvos de Aquisição', icon: <Target size={16} /> },
  { key: 'seller', label: 'Preparação p/ Venda', icon: <FileText size={16} /> },
  { key: 'market', label: 'Visão de Mercado', icon: <TrendingUp size={16} /> },
  { key: 'espectro', label: 'Espectro', icon: <Radio size={16} /> },
  { key: 'dossier', label: 'Due Diligence', icon: <ShieldAlert size={16} /> },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

import { formatBRL, formatNumber, formatPct } from '@/lib/format';

function riskBadgeClass(risk: string): string {
  const r = risk?.toLowerCase();
  if (r === 'low' || r === 'baixo') return 'pulso-badge-green';
  if (r === 'medium' || r === 'médio') return 'pulso-badge-yellow';
  return 'pulso-badge-red';
}

function riskLabel(risk: string): string {
  const r = risk?.toLowerCase();
  if (r === 'low') return 'Baixo';
  if (r === 'medium') return 'Médio';
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
      {error && <ErrorBanner message={`Erro no cálculo: ${error}`} />}

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
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Dívida Líquida R$</label>
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
                <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>Valor Médio</p>
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
                Múltiplo de Assinante
              </h4>
              <div className="space-y-2">
                <DetailRow label="Valuation Ajustado" value={formatBRL(result.subscriber_multiple?.adjusted_valuation_brl)} />
                <DetailRow label="Mult. Fibra" value={`${result.subscriber_multiple?.fiber_multiple?.toFixed(2) ?? '--'}x`} />
                <DetailRow label="Mult. Outros" value={`${result.subscriber_multiple?.other_multiple?.toFixed(2) ?? '--'}x`} />
                <DetailRow label="Confiança" value={typeof result.subscriber_multiple?.confidence === 'string' ? result.subscriber_multiple.confidence : formatPct(result.subscriber_multiple?.confidence != null ? result.subscriber_multiple.confidence * 100 : null)} />
              </div>
            </div>

            <div className="pulso-card">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <DollarSign size={16} style={{ color: 'var(--success)' }} />
                Múltiplo de Receita
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

          <SimpleChart data={chartData} type="bar" xKey="name" yKey="valor" title="Comparação de Métodos de Valuation (R$)" height={280} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 2 : Alvos de Aquisição
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
      <span style={{ color: (value ?? 0) * 100 > 60 ? 'var(--success)' : (value ?? 0) * 100 > 30 ? 'var(--warning)' : 'var(--danger)' }}>
        {formatPct((value ?? 0) * 100)}
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
        <span className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>{((value ?? 0) * 100).toFixed(0)}</span>
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
          Busca de Alvos de Aquisição
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Estados do Adquirente</label>
            <input type="text" className="pulso-input w-full" placeholder="SP,MG,PR" value={form.acquirer_states} onChange={(e) => update('acquirer_states', e.target.value)} />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>Separados por vírgula</p>
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
            <DataTable columns={targetColumns} data={targets} loading={loading} searchable searchKeys={['provider_name']} onRowClick={(row) => setSelectedTarget(row)} emptyMessage="Nenhum alvo encontrado com os critérios informados" />
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
                  <DetailRow label="% Fibra" value={formatPct((selectedTarget.fiber_pct ?? 0) * 100)} />
                  <DetailRow label="Receita Estimada" value={formatBRL(selectedTarget.estimated_revenue_brl)} />
                  <DetailRow label="Score Estratégico" value={((selectedTarget.strategic_score ?? 0) * 100).toFixed(0)} />
                  <DetailRow label="Score Financeiro" value={((selectedTarget.financial_score ?? 0) * 100).toFixed(0)} />
                  <DetailRow label="Score Geral" value={((selectedTarget.overall_score ?? 0) * 100).toFixed(0)} />
                  <DetailRow label="Risco Integração" value={riskLabel(selectedTarget.integration_risk)} />
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
// TAB 3 : Preparação para Venda
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
      {error && <ErrorBanner message={`Erro ao gerar relatório: ${error}`} />}

      <form onSubmit={handleSubmit} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <FileText size={20} style={{ color: 'var(--accent)' }} />
          Preparação para Venda
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Nome do Provedor *</label>
            <input type="text" required className="pulso-input w-full" placeholder="Ex: ISP Brasil Telecom" value={form.provider_name} onChange={(e) => update('provider_name', e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Estados</label>
            <input type="text" className="pulso-input w-full" placeholder="SP,MG" value={form.state_codes} onChange={(e) => update('state_codes', e.target.value)} />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>Separados por vírgula</p>
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
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Dívida Líquida R$</label>
            <input type="number" min={0} className="pulso-input w-full" value={form.net_debt_brl} onChange={(e) => update('net_debt_brl', e.target.value)} />
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2">
            <FileText size={16} />
            {loading ? 'Gerando...' : 'Gerar Relatório de Preparação'}
          </button>
        </div>
      </form>

      {report && (
        <div className="space-y-6">
          <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
            <SectionLabel>Faixa de Valor Estimado</SectionLabel>
            <div className="flex items-center justify-center gap-6">
              <div className="text-center">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Mínimo</p>
                <p className="text-xl font-bold" style={{ color: 'var(--danger)' }}>{formatBRL(report.estimated_value_range?.[0])}</p>
              </div>
              <ChevronRight size={24} style={{ color: 'var(--text-muted)' }} />
              <div className="text-center">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Máximo</p>
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
              Oportunidades de Valorização
            </h4>
            {report.value_enhancement_opportunities && report.value_enhancement_opportunities.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {report.value_enhancement_opportunities.map((opp, i) => (
                  <div key={i} className="rounded-lg border p-3" style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg-subtle)' }}>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{opp.title || opp.name || `Oportunidade ${i + 1}`}</p>
                    {opp.description && <p className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{opp.description}</p>}
                    {opp.estimated_impact_brl != null && <p className="mt-2 text-xs font-medium" style={{ color: 'var(--success)' }}>Impacto: {formatBRL(opp.estimated_impact_brl)}</p>}
                    {opp.effort && <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>Esforço: {opp.effort}</p>}
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
              Checklist de Preparação
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
                        {isDone ? 'Concluído' : 'Pendente'}
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
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Tempo estimado para conclusão do processo de venda</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 4 : Visão de Mercado
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
          Visão de Mercado M&A
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
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Valuation Médio/Assinante</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? 'Carregando...' : overview?.avg_valuation_per_sub ? formatBRL(overview.avg_valuation_per_sub) : '--'}</p>
            </div>
            <DollarSign size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>% Fibra Médio</p>
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
            { name: 'Val. Médio (R$)', valor: overview.avg_valuation_per_sub ?? 0 },
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
          Transações Recentes - {selectedState}
        </h3>
        <DataTable columns={transactionColumns} data={overview?.recent_transactions ?? []} loading={loading} emptyMessage="Nenhuma transação recente encontrada para este estado" searchable searchKeys={['acquirer', 'target']} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 5 : Espectro (Spectrum Asset Valuation)
// ---------------------------------------------------------------------------

interface SpectrumHolding {
  id: number | null;
  frequency_mhz: number;
  bandwidth_mhz: number | null;
  band_name: string;
  license_expiry: string | null;
  population_covered: number | null;
  net_value_brl: number;
  gross_value_brl: number;
  life_factor: number;
  price_per_mhz_pop: number;
  source: string;
}

interface SpectrumValuationResult {
  provider_id: number;
  provider_name: string;
  holdings: SpectrumHolding[];
  total_spectrum_value_brl: number;
  total_bandwidth_mhz: number;
  bands_count: number;
  error?: string;
}

function EspectroTab() {
  const [providerId, setProviderId] = useState('');
  const {
    data: result,
    loading,
    error,
    execute,
  } = useLazyApi<SpectrumValuationResult, number>(
    useCallback((id: number) => api.spectrum.valuation(id), [])
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = Number(providerId);
    if (id > 0) execute(id);
  };

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Erro na avaliação: ${error}`} />}

      <form onSubmit={handleSubmit} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <Radio size={20} style={{ color: 'var(--accent)' }} />
          Avaliação de Ativos de Espectro
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>ID do Provedor *</label>
            <input
              type="number"
              required
              min={1}
              className="pulso-input w-full"
              placeholder="Ex: 1234"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
            />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Identificador numérico do provedor na base Anatel
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2">
            <Radio size={16} />
            {loading ? 'Avaliando...' : 'Avaliar Espectro'}
          </button>
        </div>
      </form>

      {result && !result.error && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="pulso-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Largura Total</p>
                  <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                    {formatNumber(result.total_bandwidth_mhz)} MHz
                  </p>
                </div>
                <Radio size={18} style={{ color: 'var(--accent)' }} />
              </div>
            </div>
            <div className="pulso-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Bandas</p>
                  <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                    {formatNumber(result.bands_count)}
                  </p>
                </div>
                <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
              </div>
            </div>
            <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>Valor Total do Espectro</p>
                  <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                    {formatBRL(result.total_spectrum_value_brl)}
                  </p>
                </div>
                <DollarSign size={18} style={{ color: 'var(--accent)' }} />
              </div>
            </div>
          </div>

          {/* Provider info */}
          <div className="pulso-card">
            <SectionLabel>Provedor</SectionLabel>
            <div className="space-y-2">
              <DetailRow label="ID" value={String(result.provider_id)} />
              <DetailRow label="Nome" value={result.provider_name} />
            </div>
          </div>

          {/* Holdings Table */}
          <div className="pulso-card">
            <SectionLabel>Detalhamento por Banda</SectionLabel>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Banda</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Frequência MHz</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Largura MHz</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Pop. Coberta</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Valor (R$)</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Vencimento Licença</th>
                  </tr>
                </thead>
                <tbody>
                  {result.holdings.map((h, i) => (
                    <tr
                      key={i}
                      className="transition-colors hover:bg-[var(--bg-subtle)]"
                      style={{ borderBottom: '1px solid var(--border)' }}
                    >
                      <td className="px-3 py-2 font-medium" style={{ color: 'var(--text-primary)' }}>{h.band_name}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{formatNumber(h.frequency_mhz)}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{formatNumber(h.bandwidth_mhz)}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{h.population_covered ? formatNumber(h.population_covered) : '--'}</td>
                      <td className="px-3 py-2 text-right font-medium" style={{ color: 'var(--accent)' }}>{formatBRL(h.net_value_brl)}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{h.license_expiry ?? '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {result.holdings.length === 0 && (
              <p className="mt-4 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                Nenhum ativo de espectro encontrado para este provedor.
              </p>
            )}
          </div>
        </div>
      )}

      {result && result.error && (
        <ErrorBanner message={result.error} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 6 : Due Diligence Dossier
// ---------------------------------------------------------------------------

interface DossierProvider {
  id: number;
  name: string;
  national_id: string | null;
}

interface DossierRegistration {
  legal_name: string | null;
  trade_name: string | null;
  legal_nature: string | null;
  capital_social: number | null;
  founding_date: string | null;
  status: string | null;
  partner_count: number | null;
  address_city: string | null;
  address_state: string | null;
  cnae_primary: string | null;
}

interface DossierTaxDebts {
  total_brl: number;
  count: number;
  by_type: Record<string, { count: number; total_brl: number }>;
  with_legal_action: number;
}

interface DossierPartner {
  name: string;
  document: string | null;
  type: string | null;
  role: string | null;
}

interface DossierRelatedCompany {
  cnpj_root: string | null;
  name: string | null;
  type: string | null;
}

interface DossierOwnership {
  partners: DossierPartner[];
  related_companies: DossierRelatedCompany[];
  related_isps: number;
}

interface DossierSanctionEntry {
  list_type: string | null;
  sanction_type: string | null;
  sanctioning_authority: string | null;
  process_number: string | null;
  start_date: string | null;
  end_date: string | null;
}

interface DossierSanctions {
  active: DossierSanctionEntry[];
  expired: DossierSanctionEntry[];
  has_active: boolean;
}

interface DossierComplaints {
  total: number;
  avg_satisfaction: number | null;
  by_category: Record<string, number>;
  monthly_trend: { month: string; count: number; avg_satisfaction: number | null }[];
}

interface DossierRiskSummary {
  level: string;
  flags: string[];
}

interface DossierResult {
  provider: DossierProvider;
  subscribers: { total: number; municipalities: number; states: string[] };
  registration: DossierRegistration;
  tax_debts: DossierTaxDebts;
  ownership: DossierOwnership;
  sanctions: DossierSanctions;
  complaints: DossierComplaints;
  risk_summary: DossierRiskSummary;
  error?: string;
}

interface ProviderMatch {
  provider_id: number;
  name: string;
}

function debtRiskColor(total: number): string {
  if (total > 1_000_000) return 'var(--danger)';
  if (total > 100_000) return 'var(--warning)';
  return 'var(--success)';
}

function debtRiskBadge(total: number): { cls: string; label: string } {
  if (total > 1_000_000) return { cls: 'pulso-badge-red', label: 'Alto' };
  if (total > 100_000) return { cls: 'pulso-badge-yellow', label: 'Moderado' };
  return { cls: 'pulso-badge-green', label: 'Baixo' };
}

function DossierTab() {
  const [searchName, setSearchName] = useState('');
  const [matches, setMatches] = useState<ProviderMatch[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedProvider, setSelectedProvider] = useState<{ id: number; name: string } | null>(null);

  const {
    data: dossier,
    loading: dossierLoading,
    error: dossierError,
    execute: fetchDossier,
  } = useLazyApi<DossierResult, number>(
    useCallback(
      (providerId: number) =>
        fetchApi<DossierResult>(`/api/v1/mna/due-diligence-dossier?provider_id=${providerId}`),
      []
    )
  );

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchName.trim()) return;

    setSearching(true);
    setSearchError(null);
    setMatches(null);
    setSelectedProvider(null);

    try {
      const result = await fetchApi<any>('/api/v1/mna/due-diligence', {
        method: 'POST',
        body: JSON.stringify({ target_provider_name: searchName.trim() }),
      });

      // If the endpoint returns matches (ambiguous), show selection
      if (result.error && result.matches) {
        setMatches(result.matches);
      } else if (result.error) {
        setSearchError(result.error);
      } else if (result.target_provider_id) {
        // Resolved successfully — fetch dossier
        const pid = result.target_provider_id;
        const pname = result.target_provider_name || searchName;
        setSelectedProvider({ id: pid, name: pname });
        fetchDossier(pid);
      } else {
        // Fallback: result may contain a provider directly
        setSearchError('Nenhum provedor encontrado com este nome.');
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Erro na busca');
    } finally {
      setSearching(false);
    }
  };

  const handleSelectMatch = (match: ProviderMatch) => {
    setMatches(null);
    setSelectedProvider({ id: match.provider_id, name: match.name });
    fetchDossier(match.provider_id);
  };

  const reg = dossier?.registration;
  const debts = dossier?.tax_debts;
  const ownership = dossier?.ownership;
  const sanctions = dossier?.sanctions;
  const complaints = dossier?.complaints;
  const risk = dossier?.risk_summary;

  return (
    <div className="space-y-6">
      {(searchError || dossierError) && (
        <ErrorBanner message={searchError || dossierError || 'Erro desconhecido'} />
      )}

      {/* Search form */}
      <form onSubmit={handleSearch} className="pulso-card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          <ShieldAlert size={20} style={{ color: 'var(--accent)' }} />
          Due Diligence — Dossiê do Provedor
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-3">
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              Nome do Provedor *
            </label>
            <input
              type="text"
              required
              className="pulso-input w-full"
              placeholder="Ex: Brisanet, Algar, Desktop..."
              value={searchName}
              onChange={(e) => setSearchName(e.target.value)}
            />
            <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Busca por nome — selecione se houver mais de um resultado
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" disabled={searching || dossierLoading} className="pulso-btn-primary flex items-center gap-2">
            <Search size={16} />
            {searching ? 'Buscando...' : 'Buscar Dossiê'}
          </button>
        </div>
      </form>

      {/* Disambiguation: multiple matches */}
      {matches && matches.length > 0 && (
        <div className="pulso-card">
          <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
            Múltiplos provedores encontrados — selecione um:
          </h3>
          <div className="space-y-2">
            {matches.map((m) => (
              <button
                key={m.provider_id}
                onClick={() => handleSelectMatch(m)}
                className="flex w-full items-center justify-between rounded-lg px-4 py-3 text-left transition-colors hover:bg-[var(--bg-subtle)]"
                style={{ border: '1px solid var(--border)' }}
              >
                <div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{m.name}</span>
                  <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>ID {m.provider_id}</span>
                </div>
                <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading state */}
      {dossierLoading && (
        <div className="pulso-card text-center">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Carregando dossiê...</p>
        </div>
      )}

      {/* Dossier results */}
      {dossier && !dossier.error && (
        <div className="space-y-6">
          {/* Header card: provider + subscribers + risk summary */}
          <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                  {dossier.provider.name}
                </h3>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  ID {dossier.provider.id}
                  {dossier.provider.national_id && ` | CNPJ ${dossier.provider.national_id}`}
                </p>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {formatNumber(dossier.subscribers.total)} assinantes em {formatNumber(dossier.subscribers.municipalities)} municípios
                  {dossier.subscribers.states.length > 0 && ` (${dossier.subscribers.states.join(', ')})`}
                </p>
              </div>
              {risk && (
                <span
                  className={clsx(
                    'rounded-full px-4 py-1.5 text-sm font-semibold',
                    riskBadgeClass(risk.level)
                  )}
                >
                  Risco {riskLabel(risk.level)}
                </span>
              )}
            </div>
          </div>

          {/* Section 1: Company Info (Registration) */}
          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Building2 size={16} style={{ color: 'var(--accent)' }} />
              Dados Cadastrais
            </h4>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <DetailRow label="Razão Social" value={reg?.legal_name || '--'} />
              <DetailRow label="Nome Fantasia" value={reg?.trade_name || '--'} />
              <DetailRow label="CNAE Principal" value={reg?.cnae_primary || '--'} />
              <DetailRow label="Natureza Jurídica" value={reg?.legal_nature || '--'} />
              <DetailRow label="Data de Fundação" value={reg?.founding_date || '--'} />
              <DetailRow label="Capital Social" value={reg?.capital_social != null ? formatBRL(reg.capital_social) : '--'} />
              <DetailRow label="Status" value={reg?.status || '--'} />
              <DetailRow label="Localização" value={reg?.address_city && reg?.address_state ? `${reg.address_city}/${reg.address_state}` : '--'} />
            </div>
          </div>

          {/* Section 2: Tax Debts */}
          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <DollarSign size={16} style={{ color: 'var(--danger)' }} />
              Débitos Tributários
            </h4>
            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Dívida Total</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: debtRiskColor(debts?.total_brl ?? 0) }}>
                  {formatBRL(debts?.total_brl ?? 0)}
                </p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Qtd. Débitos</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                  {formatNumber(debts?.count ?? 0)}
                </p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Ações Judiciais</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: (debts?.with_legal_action ?? 0) > 0 ? 'var(--danger)' : 'var(--success)' }}>
                  {formatNumber(debts?.with_legal_action ?? 0)}
                </p>
              </div>
            </div>

            {debts && Object.keys(debts.by_type).length > 0 && (
              <div>
                <SectionLabel>Detalhamento por Tipo</SectionLabel>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Tipo</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Quantidade</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Valor (R$)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(debts.by_type).map(([type, info]) => (
                        <tr key={type} className="transition-colors hover:bg-[var(--bg-subtle)]" style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="px-3 py-2 font-medium" style={{ color: 'var(--text-primary)' }}>{type}</td>
                          <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{formatNumber(info.count)}</td>
                          <td className="px-3 py-2 text-right font-medium" style={{ color: 'var(--danger)' }}>{formatBRL(info.total_brl)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {debts && Object.keys(debts.by_type).length === 0 && (
              <p className="text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nenhum débito tributário encontrado.</p>
            )}

            <div className="mt-3 flex justify-end">
              <span className={clsx('rounded px-2 py-0.5 text-xs font-medium', debtRiskBadge(debts?.total_brl ?? 0).cls)}>
                Risco Tributário: {debtRiskBadge(debts?.total_brl ?? 0).label}
              </span>
            </div>
          </div>

          {/* Section 3: Ownership Structure */}
          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Users size={16} className="text-purple-400" />
              Estrutura Societária
            </h4>

            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Sócios</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                  {formatNumber(ownership?.partners.length ?? 0)}
                </p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>ISPs Relacionados</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: (ownership?.related_isps ?? 0) > 0 ? 'var(--warning)' : 'var(--text-primary)' }}>
                  {formatNumber(ownership?.related_isps ?? 0)}
                </p>
                {(ownership?.related_isps ?? 0) > 0 && (
                  <p className="mt-0.5 text-[10px]" style={{ color: 'var(--warning)' }}>Atenção: grupo econômico</p>
                )}
              </div>
            </div>

            {ownership && ownership.partners.length > 0 && (
              <div className="mb-4">
                <SectionLabel>Quadro Societário</SectionLabel>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Nome</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Cargo</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Tipo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ownership.partners.map((p, i) => (
                        <tr key={i} className="transition-colors hover:bg-[var(--bg-subtle)]" style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="px-3 py-2 font-medium" style={{ color: 'var(--text-primary)' }}>{p.name}</td>
                          <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{p.role || '--'}</td>
                          <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>
                            <span className={clsx('rounded px-2 py-0.5 text-[10px] font-medium', p.type === 'PJ' ? 'pulso-badge-yellow' : 'pulso-badge-green')}>
                              {p.type || '--'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {ownership && ownership.related_companies.length > 0 && (
              <div>
                <SectionLabel>Empresas Relacionadas</SectionLabel>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Empresa</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>CNPJ Raiz</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Tipo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ownership.related_companies.map((rc, i) => (
                        <tr key={i} className="transition-colors hover:bg-[var(--bg-subtle)]" style={{ borderBottom: '1px solid var(--border)' }}>
                          <td className="px-3 py-2 font-medium" style={{ color: 'var(--text-primary)' }}>{rc.name || '--'}</td>
                          <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{rc.cnpj_root || '--'}</td>
                          <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{rc.type || '--'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {ownership && ownership.partners.length === 0 && ownership.related_companies.length === 0 && (
              <p className="text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nenhum dado societário encontrado.</p>
            )}
          </div>

          {/* Section 4: Sanctions */}
          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <AlertTriangle size={16} style={{ color: sanctions?.has_active ? 'var(--danger)' : 'var(--success)' }} />
              Sanções
            </h4>

            {sanctions?.has_active && (
              <div
                className="mb-4 flex items-center gap-3 rounded-lg border px-4 py-3"
                style={{
                  borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                }}
              >
                <AlertTriangle size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
                <p className="text-sm font-medium" style={{ color: 'var(--danger)' }}>
                  {sanctions.active.length} sanção(ões) ativa(s) — risco elevado
                </p>
              </div>
            )}

            {sanctions && sanctions.active.length > 0 && (
              <div className="mb-4">
                <SectionLabel>Sanções Ativas</SectionLabel>
                <div className="space-y-2">
                  {sanctions.active.map((s, i) => (
                    <div key={i} className="rounded-lg border px-4 py-3" style={{ borderColor: 'color-mix(in srgb, var(--danger) 20%, transparent)', backgroundColor: 'color-mix(in srgb, var(--danger) 5%, transparent)' }}>
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{s.sanction_type || s.list_type || 'Sanção'}</p>
                          {s.sanctioning_authority && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Órgão: {s.sanctioning_authority}</p>}
                          {s.process_number && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Processo: {s.process_number}</p>}
                        </div>
                        <span className="rounded px-2 py-0.5 text-[10px] font-medium pulso-badge-red">Ativa</span>
                      </div>
                      <div className="mt-1 flex gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                        {s.start_date && <span>Início: {s.start_date}</span>}
                        {s.end_date && <span>Fim: {s.end_date}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sanctions && sanctions.expired.length > 0 && (
              <div>
                <SectionLabel>Sanções Expiradas</SectionLabel>
                <div className="space-y-2">
                  {sanctions.expired.map((s, i) => (
                    <div key={i} className="rounded-lg px-4 py-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{s.sanction_type || s.list_type || 'Sanção'}</p>
                          {s.sanctioning_authority && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Órgão: {s.sanctioning_authority}</p>}
                        </div>
                        <span className="rounded px-2 py-0.5 text-[10px] font-medium pulso-badge-green">Expirada</span>
                      </div>
                      <div className="mt-1 flex gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                        {s.start_date && <span>Início: {s.start_date}</span>}
                        {s.end_date && <span>Fim: {s.end_date}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sanctions && !sanctions.has_active && sanctions.expired.length === 0 && (
              <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--success)' }}>
                <CheckCircle2 size={16} />
                Nenhuma sanção encontrada — situação limpa.
              </div>
            )}
          </div>

          {/* Section 5: Consumer Complaints */}
          <div className="pulso-card">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Briefcase size={16} className="text-amber-400" />
              Reclamações de Consumidores
            </h4>

            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Total de Reclamações</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: (complaints?.total ?? 0) > 100 ? 'var(--danger)' : 'var(--text-primary)' }}>
                  {formatNumber(complaints?.total ?? 0)}
                </p>
              </div>
              <div className="rounded-lg p-4 text-center" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Satisfação Média</p>
                <p className="mt-1 text-2xl font-bold" style={{ color: complaints?.avg_satisfaction != null ? (complaints.avg_satisfaction >= 3 ? 'var(--success)' : complaints.avg_satisfaction >= 2 ? 'var(--warning)' : 'var(--danger)') : 'var(--text-primary)' }}>
                  {complaints?.avg_satisfaction != null ? `${complaints.avg_satisfaction.toFixed(1)}/5` : '--'}
                </p>
              </div>
            </div>

            {complaints && Object.keys(complaints.by_category).length > 0 && (
              <div>
                <SectionLabel>Por Categoria</SectionLabel>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="px-3 py-2 text-left text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Categoria</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Quantidade</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(complaints.by_category)
                        .sort((a, b) => b[1] - a[1])
                        .map(([cat, count]) => (
                          <tr key={cat} className="transition-colors hover:bg-[var(--bg-subtle)]" style={{ borderBottom: '1px solid var(--border)' }}>
                            <td className="px-3 py-2 font-medium" style={{ color: 'var(--text-primary)' }}>{cat}</td>
                            <td className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{formatNumber(count)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {complaints && complaints.total === 0 && (
              <p className="text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nenhuma reclamação encontrada.</p>
            )}
          </div>

          {/* Section 6: Risk Summary */}
          {risk && (
            <div className="pulso-card" style={{ border: `1px solid color-mix(in srgb, ${risk.level === 'high' ? 'var(--danger)' : risk.level === 'medium' ? 'var(--warning)' : 'var(--success)'} 30%, transparent)` }}>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <ShieldAlert size={16} style={{ color: risk.level === 'high' ? 'var(--danger)' : risk.level === 'medium' ? 'var(--warning)' : 'var(--success)' }} />
                Resumo de Risco
              </h4>

              <div className="mb-4 flex items-center gap-3">
                <span
                  className={clsx(
                    'rounded-full px-4 py-1.5 text-sm font-semibold',
                    riskBadgeClass(risk.level)
                  )}
                >
                  Nível: {riskLabel(risk.level)}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {risk.flags.length} alerta{risk.flags.length !== 1 ? 's' : ''} identificado{risk.flags.length !== 1 ? 's' : ''}
                </span>
              </div>

              {risk.flags.length > 0 ? (
                <ul className="space-y-2">
                  {risk.flags.map((flag, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--danger)' }} />
                      {flag}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--success)' }}>
                  <CheckCircle2 size={16} />
                  Nenhum alerta de risco identificado — provedor em boa situação.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {dossier && dossier.error && (
        <ErrorBanner message={dossier.error} />
      )}
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
          Inteligência M&A
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Valuation, busca de alvos e preparação para fusões e aquisições no setor ISP brasileiro
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
      {activeTab === 'espectro' && <EspectroTab />}
      {activeTab === 'dossier' && <DossierTab />}
    </div>
  );
}
