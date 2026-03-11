'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatPct } from '@/lib/format';
import { Wifi, AlertTriangle, Shield, ChevronDown, MapPin } from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center" style={{ background: 'var(--bg-subtle)' }}>
      <div className="overflow-hidden absolute top-0 left-0 right-0" style={{ height: '2px' }}>
        <div className="pulso-progress-bar w-full" />
      </div>
    </div>
  ),
});

const STATES = ['', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];

function threatColor(score: number): [number, number, number, number] {
  if (score >= 80) return [239, 68, 68, 200];
  if (score >= 60) return [245, 158, 11, 200];
  if (score >= 40) return [234, 179, 8, 180];
  if (score >= 20) return [34, 197, 94, 160];
  return [59, 130, 246, 140];
}

function tierBadge(tier: string) {
  const map: Record<string, { bg: string; text: string }> = {
    Critical: { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', text: 'var(--danger)' },
    High: { bg: 'color-mix(in srgb, var(--warning) 15%, transparent)', text: 'var(--warning)' },
    Moderate: { bg: 'color-mix(in srgb, var(--accent) 15%, transparent)', text: 'var(--accent)' },
    Low: { bg: 'color-mix(in srgb, var(--success) 15%, transparent)', text: 'var(--success)' },
    Minimal: { bg: 'var(--bg-subtle)', text: 'var(--text-muted)' },
  };
  return map[tier] ?? map.Minimal;
}

export default function StarlinkPage() {
  const [stateFilter, setStateFilter] = useState('');
  const [selectedMuni, setSelectedMuni] = useState<any>(null);
  const [showTable, setShowTable] = useState(false);
  const deckRef = useRef<any>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer };
      setDeckReady(true);
    });
  }, []);

  const { data, loading } = useApi<any>(
    () => api.starlink.threat({ state: stateFilter || undefined, limit: 200 }),
    [stateFilter]
  );

  const mapLayers = useMemo(() => {
    if (!deckReady || !deckRef.current || !data?.municipalities?.length) return [];
    const { ScatterplotLayer } = deckRef.current;
    return [
      new ScatterplotLayer({
        id: 'starlink-threat',
        data: data.municipalities.filter((d: any) => d.area_km2),
        getPosition: (d: any) => {
          // Approximate center from l2_id -- we use population as proxy for size
          return [d.area_km2 ? -50 + (d.l2_id % 1000) * 0.02 : -46.6, d.area_km2 ? -15 + (d.l2_id % 500) * 0.02 : -23.5];
        },
        getFillColor: (d: any) => threatColor(d.threat_score),
        getRadius: (d: any) => Math.max(5000, Math.sqrt(d.population || 1000) * 50),
        radiusMinPixels: 4,
        radiusMaxPixels: 20,
        pickable: true,
        autoHighlight: true,
      }),
    ];
  }, [deckReady, data]);

  const municipalities = data?.municipalities ?? [];

  return (
    <div className="space-y-6 p-6">
      {loading && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Wifi size={28} style={{ color: 'var(--accent)' }} />
          Indice de Ameaca Starlink
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Analise de vulnerabilidade dos municipios a competicao satelital
        </p>
      </div>

      <div className="flex gap-3 items-center">
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="pulso-input text-sm">
          {STATES.map((s) => <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>)}
        </select>
        <button onClick={() => setShowTable(!showTable)} className="pulso-btn-primary text-sm px-3 py-1.5">
          {showTable ? 'Ver Cards' : 'Ver Tabela'}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        {['Critical', 'High', 'Moderate', 'Low'].map((tier) => {
          const count = data?.tier_distribution?.[tier] ?? 0;
          const badge = tierBadge(tier);
          return (
            <div key={tier} className="pulso-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{tier}</p>
                  <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{loading ? '...' : count}</p>
                </div>
                <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: badge.bg, color: badge.text }}>{tier}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Table view */}
      {showTable ? (
        <div className="pulso-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <th className="pb-2 pr-4">Municipio</th>
                <th className="pb-2 pr-4">UF</th>
                <th className="pb-2 pr-4">Populacao</th>
                <th className="pb-2 pr-4">Assinantes</th>
                <th className="pb-2 pr-4">Penetracao</th>
                <th className="pb-2 pr-4">% Fibra</th>
                <th className="pb-2 pr-4">Score</th>
                <th className="pb-2">Tier</th>
              </tr>
            </thead>
            <tbody>
              {municipalities.slice(0, 50).map((m: any) => {
                const badge = tierBadge(m.tier);
                return (
                  <tr key={m.l2_id} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}>
                    <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{m.municipality}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.state}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatNumber(m.population)}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatNumber(m.total_subscribers)}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatPct(m.penetration_pct)}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatPct(m.fiber_pct)}</td>
                    <td className="py-2 pr-4 font-bold" style={{ color: badge.text }}>{m.threat_score}</td>
                    <td className="py-2">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: badge.bg, color: badge.text }}>{m.tier}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {municipalities.slice(0, 12).map((m: any) => {
            const badge = tierBadge(m.tier);
            return (
              <div key={m.l2_id} className="pulso-card">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{m.municipality}</h3>
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: badge.bg, color: badge.text }}>{m.tier}</span>
                </div>
                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>{m.state} | Pop. {formatNumber(m.population)}</p>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl font-bold" style={{ color: badge.text }}>{m.threat_score}</span>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>/ 100</span>
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <div className="h-full rounded-full" style={{ width: `${m.threat_score}%`, backgroundColor: badge.text }} />
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1 text-[10px]">
                  <div className="flex justify-between px-2 py-1 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Penetracao</span>
                    <span style={{ color: 'var(--text-primary)' }}>{formatPct(m.penetration_pct)}</span>
                  </div>
                  <div className="flex justify-between px-2 py-1 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Fibra</span>
                    <span style={{ color: 'var(--text-primary)' }}>{formatPct(m.fiber_pct)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
