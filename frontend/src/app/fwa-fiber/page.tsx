'use client';

import { useState, useCallback } from 'react';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatBRL, formatNumber } from '@/lib/format';
import { Calculator, Radio, Cable, ArrowRight, AlertTriangle, CheckCircle2 } from 'lucide-react';

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-subtle)' }}>
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}

export default function FwaFiberPage() {
  const [l2Id, setL2Id] = useState('');
  const [targetSubs, setTargetSubs] = useState('');

  const { data: presets } = useApi<any[]>(() => api.fwaFiber.presets(), []);

  const { data: result, loading, error, execute } = useLazyApi<any, any>(
    useCallback((params: any) => api.fwaFiber.compare(params), [])
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    execute({
      l2_id: Number(l2Id),
      target_subscribers: targetSubs ? Number(targetSubs) : undefined,
    });
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Calculator size={28} style={{ color: 'var(--accent)' }} />
          FWA vs Fibra
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Compare custos de implantacao FWA e Fibra para qualquer municipio
        </p>
      </div>

      <form onSubmit={handleSubmit} className="pulso-card">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>ID do Municipio *</label>
            <input type="number" required min={1} className="pulso-input w-full" placeholder="Ex: 3550308" value={l2Id} onChange={(e) => setL2Id(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Assinantes Alvo</label>
            <input type="number" min={1} className="pulso-input w-full" placeholder="Auto-calculado" value={targetSubs} onChange={(e) => setTargetSubs(e.target.value)} />
          </div>
          <div className="flex items-end">
            <button type="submit" disabled={loading} className="pulso-btn-primary flex items-center gap-2 w-full justify-center">
              <Calculator size={16} />
              {loading ? 'Calculando...' : 'Comparar'}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border px-4 py-3" style={{ borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)', backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)' }}>
          <AlertTriangle size={18} style={{ color: 'var(--danger)' }} />
          <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Municipality info */}
          <div className="pulso-card">
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
              {result.municipality?.name} &mdash; {result.municipality?.state}
            </h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <DetailRow label="Populacao" value={formatNumber(result.municipality?.population)} />
              <DetailRow label="Area km2" value={result.municipality?.area_km2?.toFixed(1) ?? '--'} />
              <DetailRow label="Assinantes alvo" value={formatNumber(result.target_subscribers)} />
              <DetailRow label="Torres existentes" value={String(result.municipality?.existing_towers ?? 0)} />
            </div>
          </div>

          {/* Recommendation */}
          <div className="pulso-card" style={{ border: '2px solid color-mix(in srgb, var(--accent) 40%, transparent)' }}>
            <div className="flex items-center gap-3">
              <CheckCircle2 size={24} style={{ color: 'var(--accent)' }} />
              <div>
                <p className="text-lg font-bold" style={{ color: 'var(--accent)' }}>Recomendacao: {result.recommendation}</p>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{result.recommendation_reason}</p>
              </div>
            </div>
          </div>

          {/* Side by side comparison */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* FWA */}
            <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--warning) 30%, transparent)' }}>
              <h3 className="flex items-center gap-2 text-lg font-semibold mb-4" style={{ color: 'var(--warning)' }}>
                <Radio size={20} />
                FWA (Fixed Wireless)
              </h3>
              <div className="space-y-2">
                <DetailRow label="CAPEX Total" value={formatBRL(result.fwa?.capex_brl)} />
                <DetailRow label="CAPEX/Assinante" value={formatBRL(result.fwa?.capex_per_sub)} />
                <DetailRow label="OPEX Mensal" value={formatBRL(result.fwa?.monthly_opex_brl)} />
                <DetailRow label="TCO 5 anos" value={formatBRL(result.fwa?.tco_5yr_brl)} />
                <DetailRow label="Torres necessarias" value={String(result.fwa?.towers_needed ?? 0)} />
                <DetailRow label="Torres novas" value={String(result.fwa?.towers_new ?? 0)} />
                <DetailRow label="ARPU" value={formatBRL(result.fwa?.arpu)} />
                <DetailRow label="Payback" value={`${result.fwa?.payback_months ?? '--'} meses`} />
              </div>
            </div>

            {/* Fiber */}
            <div className="pulso-card" style={{ border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)' }}>
              <h3 className="flex items-center gap-2 text-lg font-semibold mb-4" style={{ color: 'var(--accent)' }}>
                <Cable size={20} />
                Fibra (FTTH)
              </h3>
              <div className="space-y-2">
                <DetailRow label="CAPEX Total" value={formatBRL(result.fiber?.capex_brl)} />
                <DetailRow label="CAPEX/Assinante" value={formatBRL(result.fiber?.capex_per_sub)} />
                <DetailRow label="OPEX Mensal" value={formatBRL(result.fiber?.monthly_opex_brl)} />
                <DetailRow label="TCO 5 anos" value={formatBRL(result.fiber?.tco_5yr_brl)} />
                <DetailRow label="Fibra trunk km" value={result.fiber?.fiber_trunk_km?.toFixed(1) ?? '--'} />
                <DetailRow label="OLTs" value={String(result.fiber?.olts_needed ?? 0)} />
                <DetailRow label="ARPU" value={formatBRL(result.fiber?.arpu)} />
                <DetailRow label="Payback" value={`${result.fiber?.payback_months ?? '--'} meses`} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Presets */}
      {presets && presets.length > 0 && (
        <div className="pulso-card">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>Cenarios Pre-definidos</h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            {presets.map((p: any, i: number) => (
              <div key={i} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.name}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{p.description}</p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{formatNumber(p.subscribers)} assinantes | {p.area_km2} km2</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
