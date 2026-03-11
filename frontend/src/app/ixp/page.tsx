'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import { Zap, MapPin, TrendingUp } from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center" style={{ background: 'var(--bg-subtle)', height: '400px' }}>
      <div className="overflow-hidden absolute top-0 left-0 right-0" style={{ height: '2px' }}>
        <div className="pulso-progress-bar w-full" />
      </div>
    </div>
  ),
});

const STATES = ['', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];

export default function IxpPage() {
  const [stateFilter, setStateFilter] = useState('');
  const deckRef = useRef<any>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer };
      setDeckReady(true);
    });
  }, []);

  const { data: locations, loading: locLoading } = useApi<any>(
    () => api.ixp.locations({ state: stateFilter || undefined }),
    [stateFilter]
  );

  const { data: traffic, loading: trafLoading } = useApi<any>(
    () => api.ixp.traffic(),
    []
  );

  const locs = locations?.locations ?? [];

  const mapLayers = useMemo(() => {
    if (!deckReady || !deckRef.current || !locs.length) return [];
    const { ScatterplotLayer } = deckRef.current;
    const withCoords = locs.filter((l: any) => l.latitude && l.longitude);
    if (!withCoords.length) return [];
    return [
      new ScatterplotLayer({
        id: 'ixp-locations',
        data: withCoords,
        getPosition: (d: any) => [d.longitude, d.latitude],
        getFillColor: [59, 130, 246, 200],
        getRadius: (d: any) => Math.max(10000, Math.sqrt(d.traffic_gbps || 100) * 1000),
        radiusMinPixels: 6,
        radiusMaxPixels: 40,
        pickable: true,
        autoHighlight: true,
      }),
    ];
  }, [deckReady, locs]);

  const trafficChartData = (traffic?.traffic ?? []).slice(0, 15).map((t: any) => ({
    name: t.ixp_code,
    tráfego: Math.round(t.peak_gbps ?? 0),
  }));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Zap size={28} style={{ color: 'var(--accent)' }} />
          IX.br
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Pontos de troca de tráfego IX.br — localização e dados de tráfego
        </p>
      </div>

      <div className="flex gap-3">
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="pulso-input text-sm">
          {STATES.map((s) => <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>)}
        </select>
      </div>

      {/* Map */}
      <div className="pulso-card" style={{ padding: 0, overflow: 'hidden', height: '400px' }}>
        <MapView className="h-full w-full" layers={mapLayers} />
      </div>

      {/* Traffic chart */}
      <SimpleChart data={trafficChartData} type="bar" xKey="name" yKey="tráfego" title="Pico de Tráfego por IX (Gbps)" height={280} loading={trafLoading} />

      {/* Location cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {locs.map((l: any) => (
          <div key={l.code} className="pulso-card">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{l.name}</h3>
              <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}>{l.code}</span>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{l.city}, {l.state}</p>
            <div className="mt-2 flex gap-3">
              {l.traffic_gbps != null && (
                <div>
                  <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Tráfego</p>
                  <p className="text-lg font-bold" style={{ color: 'var(--accent)' }}>{formatNumber(Math.round(l.traffic_gbps))} Gbps</p>
                </div>
              )}
              {l.participants != null && (
                <div>
                  <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Participantes</p>
                  <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{l.participants}</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
