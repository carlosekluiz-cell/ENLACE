'use client';

import { useState, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { ScatterplotLayer } from 'deck.gl';
import SidePanel from '@/components/layout/SidePanel';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { HeatmapFeatureCollection } from '@/lib/types';
import { Users, BarChart3, AlertTriangle, ChevronDown, Layers } from 'lucide-react';

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

const DEFAULT_BBOX = '-73.99,-33.77,-34.79,5.27';

type LayerType = 'hhi' | 'provider_count';

const LAYER_OPTIONS: { value: LayerType; label: string }[] = [
  { value: 'hhi', label: 'Concentração (HHI)' },
  { value: 'provider_count', label: 'Provedores ativos' },
];

function hhiColor(hhi: number): [number, number, number, number] {
  // HHI: 0-2500 (low) green, 2500-5000 yellow, 5000-10000 red
  const t = Math.min(hhi / 10000, 1);
  if (t < 0.25) return [34, 197, 94, 180];   // green
  if (t < 0.5) return [234, 179, 8, 180];     // yellow
  return [239, 68, 68, 180];                    // red
}

export default function ConcorrenciaPage() {
  const [layer, setLayer] = useState<LayerType>('hhi');
  const [layerDropdownOpen, setLayerDropdownOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: heatmapData, loading } = useApi<HeatmapFeatureCollection>(
    () => api.market.heatmap(DEFAULT_BBOX, 'penetration'),
    []
  );

  const { data: competitors, loading: competitorLoading } = useApi<any>(
    () => {
      if (selectedId == null) return Promise.resolve(null);
      return api.market.competitors(selectedId);
    },
    [selectedId]
  );

  const layers = useMemo(() => {
    if (!heatmapData?.features?.length) return [];
    return [
      new ScatterplotLayer({
        id: 'competition-layer',
        data: heatmapData.features,
        getPosition: (d: any) => d.geometry.coordinates,
        getRadius: 6000,
        getFillColor: (d: any) => {
          if (layer === 'hhi') {
            const hhi = d.properties.hhi || d.properties.value * 100 || 2500;
            return hhiColor(hhi);
          }
          const count = d.properties.provider_count || 1;
          const t = Math.min(count / 10, 1);
          return [15, 118, 110, Math.round(80 + t * 170)] as [number, number, number, number];
        },
        pickable: true,
        radiusMinPixels: 3,
        radiusMaxPixels: 20,
        updateTriggers: { getFillColor: [layer] },
      }),
    ];
  }, [heatmapData, layer]);

  const handleMapClick = useCallback((info: any) => {
    if (info?.object?.properties?.municipality_id) {
      setSelectedId(info.object.properties.municipality_id);
    }
  }, []);

  return (
    <div className="relative h-full w-full">
      {loading && (
        <div className="absolute top-0 left-0 right-0 z-20 overflow-hidden" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <MapView className="h-full w-full" layers={layers} onMapClick={handleMapClick} />

      {/* Layer selector */}
      <div className="absolute right-4 top-40 z-10">
        <div className="relative">
          <button
            onClick={() => setLayerDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
          >
            <Layers size={14} />
            {LAYER_OPTIONS.find((o) => o.value === layer)?.label}
            <ChevronDown size={12} />
          </button>

          {layerDropdownOpen && (
            <div className="absolute right-0 mt-1 w-48 rounded-md py-1" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
              {LAYER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setLayer(opt.value); setLayerDropdownOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm"
                  style={{ color: opt.value === layer ? 'var(--accent)' : 'var(--text-primary)', background: opt.value === layer ? 'var(--accent-subtle)' : 'transparent' }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 rounded-md px-3 py-2 text-xs"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
        {layer === 'hhi' ? (
          <>
            <span>Baixa conc.</span>
            <div className="flex h-2 w-20 overflow-hidden rounded">
              <div className="flex-1" style={{ background: '#22c55e' }} />
              <div className="flex-1" style={{ background: '#eab308' }} />
              <div className="flex-1" style={{ background: '#ef4444' }} />
            </div>
            <span>Alta conc.</span>
          </>
        ) : (
          <span>Opacidade = número de provedores</span>
        )}
      </div>

      {/* Detail panel */}
      <SidePanel
        open={selectedId != null}
        onClose={() => setSelectedId(null)}
        title="Análise Competitiva"
        subtitle="Município selecionado"
      >
        {competitorLoading ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando...</p>
        ) : competitors ? (
          <div className="space-y-4">
            <div className="space-y-3">
              <KeyValue icon={<BarChart3 size={14} />} label="Índice HHI" value={competitors.hhi?.toLocaleString('pt-BR') || 'N/A'} />
              <KeyValue icon={<Users size={14} />} label="Provedores" value={String(competitors.provider_count || 'N/A')} />
            </div>

            {competitors.providers?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>Provedores</h4>
                <div className="space-y-1">
                  {competitors.providers.map((p: any, i: number) => (
                    <div key={i} className="flex justify-between text-sm py-1" style={{ borderBottom: '1px solid var(--border)' }}>
                      <span style={{ color: 'var(--text-primary)' }}>{p.name || p.provider_name}</span>
                      <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{p.market_share ? `${p.market_share.toFixed(1)}%` : '-'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {competitors.alerts?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-1" style={{ color: 'var(--warning)' }}>
                  <AlertTriangle size={14} /> Alertas
                </h4>
                {competitors.alerts.map((a: string, i: number) => (
                  <p key={i} className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>{a}</p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Clique em um município para ver a análise.</p>
        )}
      </SidePanel>
    </div>
  );
}

function KeyValue({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1" style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
        <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}
