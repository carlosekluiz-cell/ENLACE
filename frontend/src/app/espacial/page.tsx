'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import { Layers, Hexagon, MapPin, ChevronDown, AlertTriangle, Loader2 } from 'lucide-react';

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

const STATES = [
  '', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO',
  'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR',
  'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
];

type ViewMode = 'clusters' | 'voronoi' | 'footprint';

function clusterColor(idx: number): [number, number, number, number] {
  const colors: [number, number, number][] = [
    [59, 130, 246], [16, 185, 129], [245, 158, 11], [239, 68, 68],
    [139, 92, 246], [236, 72, 153], [20, 184, 166], [249, 115, 22],
    [99, 102, 241], [34, 197, 94],
  ];
  const c = colors[idx % colors.length];
  return [c[0], c[1], c[2], 180];
}

export default function EspacialPage() {
  const [stateFilter, setStateFilter] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('clusters');
  const [numClusters, setNumClusters] = useState(10);
  const [providerId, setProviderId] = useState('');
  const deckRef = useRef<any>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer, GeoJsonLayer: mod.GeoJsonLayer };
      setDeckReady(true);
    });
  }, []);

  const { data: clusterData, loading: clusterLoading } = useApi<any>(
    () => api.spatial.clusters({ num_clusters: numClusters, state: stateFilter || undefined }),
    [numClusters, stateFilter]
  );

  const mapLayers = useMemo(() => {
    if (!deckReady || !deckRef.current) return [];
    const { ScatterplotLayer } = deckRef.current;

    if (viewMode === 'clusters' && clusterData?.clusters) {
      return [
        new ScatterplotLayer({
          id: 'cluster-centers',
          data: clusterData.clusters,
          getPosition: (d: any) => [d.center.lon, d.center.lat],
          getFillColor: (d: any) => clusterColor(d.cluster_id),
          getRadius: (d: any) => Math.max(5000, Math.sqrt(d.tower_count) * 3000),
          radiusMinPixels: 8,
          radiusMaxPixels: 30,
          pickable: true,
          autoHighlight: true,
        }),
      ];
    }
    return [];
  }, [deckReady, viewMode, clusterData]);

  const isLoading = clusterLoading;

  return (
    <div className="relative flex h-[calc(100vh-56px)] flex-col">
      {isLoading && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <div className="relative flex-1">
        <MapView className="h-full w-full" layers={mapLayers} />

        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2" style={{ maxWidth: '300px' }}>
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Layers size={16} style={{ color: 'var(--accent)' }} />
              <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Analise Espacial</h1>
            </div>

            <div className="space-y-2 mb-3">
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="pulso-input w-full text-xs"
              >
                {STATES.map((s) => (
                  <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>
                ))}
              </select>

              <div className="flex gap-1">
                {(['clusters', 'voronoi', 'footprint'] as ViewMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setViewMode(mode)}
                    className="flex-1 rounded-md px-2 py-1 text-[10px] font-medium"
                    style={{
                      background: viewMode === mode ? 'var(--accent)' : 'var(--bg-subtle)',
                      color: viewMode === mode ? '#fff' : 'var(--text-muted)',
                    }}
                  >
                    {mode === 'clusters' ? 'Clusters' : mode === 'voronoi' ? 'Voronoi' : 'Footprint'}
                  </button>
                ))}
              </div>

              {viewMode === 'clusters' && (
                <div>
                  <label className="text-[10px] mb-0.5 block" style={{ color: 'var(--text-muted)' }}>Clusters: {numClusters}</label>
                  <input type="range" min={2} max={30} value={numClusters} onChange={(e) => setNumClusters(Number(e.target.value))} className="w-full" />
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span style={{ color: 'var(--text-muted)' }}>Torres totais</span>
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{isLoading ? '...' : formatNumber(clusterData?.total_towers ?? null)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span style={{ color: 'var(--text-muted)' }}>Clusters</span>
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{isLoading ? '...' : clusterData?.clusters?.length ?? '--'}</span>
              </div>
            </div>
          </div>

          {clusterData?.clusters && !isLoading && (
            <div className="rounded-lg p-2 max-h-60 overflow-y-auto" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
              <p className="text-[10px] font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>Clusters</p>
              {clusterData.clusters.map((c: any) => (
                <div key={c.cluster_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px]" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: `rgb(${clusterColor(c.cluster_id).slice(0, 3).join(',')})` }} />
                  <span style={{ color: 'var(--text-primary)' }}>{c.tower_count} torres</span>
                  <span style={{ color: 'var(--text-muted)' }}>{c.providers?.length ?? 0} prov.</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
