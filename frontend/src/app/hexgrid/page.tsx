'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
import SidePanel from '@/components/layout/SidePanel';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  Hexagon,
  Layers,
  ChevronDown,
  AlertTriangle,
  Users,
  Wifi,
  BarChart3,
  Loader2,
  Settings2,
} from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center" style={{ background: 'var(--bg-subtle)' }}>
      <div className="absolute top-0 left-0 right-0 overflow-hidden" style={{ height: '2px' }}>
        <div className="pulso-progress-bar w-full" />
      </div>
    </div>
  ),
});

const DEFAULT_BBOX = '-73.99,-33.77,-34.79,5.27';

type MetricKey = 'subscribers' | 'penetration' | 'fiber_share';

const METRIC_OPTIONS: { value: MetricKey; label: string; icon: React.ReactNode }[] = [
  { value: 'subscribers', label: 'Assinantes', icon: <Users size={12} /> },
  { value: 'penetration', label: 'Penetracao', icon: <BarChart3 size={12} /> },
  { value: 'fiber_share', label: '% Fibra', icon: <Wifi size={12} /> },
];

const RESOLUTION_OPTIONS = [
  { value: 7, label: 'Res. 7 (macro)' },
  { value: 9, label: 'Res. 9 (micro)' },
];

// Color scale for subscribers: blue intensity
function subscriberColor(value: number, min: number, max: number): [number, number, number, number] {
  const t = max === min ? 0.5 : Math.max(0, Math.min(1, (value - min) / (max - min)));
  const r = Math.round(20 + (1 - t) * 60);
  const g = Math.round(60 + (1 - t) * 100);
  const b = Math.round(120 + t * 135);
  return [r, g, b, 180];
}

// Color scale for penetration/fiber_share: red (low) to green (high)
function divergingColor(value: number, min: number, max: number): [number, number, number, number] {
  const t = max === min ? 0.5 : Math.max(0, Math.min(1, (value - min) / (max - min)));
  let r: number, g: number, b: number;
  if (t < 0.5) {
    const s = t / 0.5;
    r = Math.round(220 - s * 100);
    g = Math.round(60 + s * 120);
    b = Math.round(60);
  } else {
    const s = (t - 0.5) / 0.5;
    r = Math.round(120 - s * 90);
    g = Math.round(180 + s * 40);
    b = Math.round(60 + s * 40);
  }
  return [r, g, b, 180];
}

export default function HexGridPage() {
  const [metric, setMetric] = useState<MetricKey>('subscribers');
  const [resolution, setResolution] = useState(7);
  const [metricDropdownOpen, setMetricDropdownOpen] = useState(false);
  const [resDropdownOpen, setResDropdownOpen] = useState(false);
  const [selectedCell, setSelectedCell] = useState<any | null>(null);
  const [analysisData, setAnalysisData] = useState<any | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const deckRef = useRef<{ H3HexagonLayer: any } | null>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/geo-layers').then((mod) => {
      deckRef.current = { H3HexagonLayer: mod.H3HexagonLayer };
      setDeckReady(true);
    });
  }, []);

  const {
    data: cellsResponse,
    loading,
    error,
  } = useApi(
    () => api.h3.cells({ bbox: DEFAULT_BBOX, resolution, metric }),
    [resolution, metric],
  );

  const cells = useMemo(() => {
    if (!cellsResponse) return [];
    if (Array.isArray(cellsResponse)) return cellsResponse;
    if (cellsResponse.cells && Array.isArray(cellsResponse.cells)) return cellsResponse.cells;
    if (cellsResponse.features && Array.isArray(cellsResponse.features)) return cellsResponse.features;
    return [];
  }, [cellsResponse]);

  // Fetch municipality analysis when a cell with municipality_id is clicked
  const fetchAnalysis = useCallback(async (municipalityId: number) => {
    setAnalysisLoading(true);
    try {
      const data = await api.h3.analysis(municipalityId);
      setAnalysisData(data);
    } catch {
      setAnalysisData(null);
    } finally {
      setAnalysisLoading(false);
    }
  }, []);

  const handleMapClick = useCallback(
    (info: any) => {
      if (info?.object) {
        setSelectedCell(info.object);
        const munId = info.object.municipality_id ?? info.object.properties?.municipality_id;
        if (munId) {
          fetchAnalysis(munId);
        } else {
          setAnalysisData(null);
        }
      }
    },
    [fetchAnalysis],
  );

  const handleClosePanel = useCallback(() => {
    setSelectedCell(null);
    setAnalysisData(null);
  }, []);

  // Build H3HexagonLayer
  const layers = useMemo(() => {
    if (!deckRef.current || !cells.length) return [];
    const { H3HexagonLayer } = deckRef.current;

    const values = cells
      .map((d: any) => d.value ?? d.properties?.value)
      .filter((v: any): v is number => v != null);
    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const maxVal = values.length > 0 ? Math.max(...values) : 1;

    const colorFn = metric === 'subscribers' ? subscriberColor : divergingColor;

    return [
      new H3HexagonLayer({
        id: 'h3-layer',
        data: cells,
        getHexagon: (d: any) => d.h3_index ?? d.properties?.h3_index ?? d.hex ?? d.id,
        getFillColor: (d: any) => {
          const val = d.value ?? d.properties?.value;
          if (val == null) return [128, 128, 128, 100] as [number, number, number, number];
          return colorFn(val, minVal, maxVal);
        },
        getElevation: 0,
        extruded: false,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 120],
        updateTriggers: {
          getFillColor: [metric, minVal, maxVal],
        },
      }),
    ];
  }, [cells, metric, deckReady]);

  const currentMetricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;
  const currentResLabel = RESOLUTION_OPTIONS.find((r) => r.value === resolution)?.label ?? `Res. ${resolution}`;

  // Stats from loaded cells
  const totalCells = cells.length;
  const avgValue = useMemo(() => {
    const values = cells.map((d: any) => d.value ?? d.properties?.value).filter((v: any): v is number => v != null);
    if (values.length === 0) return 0;
    return values.reduce((a: number, b: number) => a + b, 0) / values.length;
  }, [cells]);

  // Legend stops
  const legendStops = useMemo(() => {
    const values = cells.map((d: any) => d.value ?? d.properties?.value).filter((v: any): v is number => v != null);
    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const maxVal = values.length > 0 ? Math.max(...values) : 1;
    const colorFn = metric === 'subscribers' ? subscriberColor : divergingColor;
    return [
      { color: rgbString(colorFn(minVal, minVal, maxVal)), label: formatValue(minVal, metric) },
      { color: rgbString(colorFn((minVal + maxVal) / 2, minVal, maxVal)), label: formatValue((minVal + maxVal) / 2, metric) },
      { color: rgbString(colorFn(maxVal, minVal, maxVal)), label: formatValue(maxVal, metric) },
    ];
  }, [cells, metric]);

  // Derive cell details for SidePanel
  const cellHex = selectedCell?.h3_index ?? selectedCell?.properties?.h3_index ?? selectedCell?.hex ?? selectedCell?.id ?? '--';
  const cellValue = selectedCell?.value ?? selectedCell?.properties?.value;
  const cellMunicipality = selectedCell?.municipality_name ?? selectedCell?.properties?.municipality_name;
  const cellState = selectedCell?.state_abbrev ?? selectedCell?.properties?.state_abbrev;

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Loading progress bar */}
      {loading && (
        <div className="absolute top-0 left-0 right-0 z-20 overflow-hidden" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div
          className="absolute top-2 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-lg border px-4 py-2"
          style={{
            borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
            backgroundColor: 'var(--bg-surface)',
          }}
        >
          <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />
          <span className="text-xs" style={{ color: 'var(--danger)' }}>
            Erro ao carregar dados H3. Verifique sua conexao.
          </span>
        </div>
      )}

      {/* Map fills entire area */}
      <MapView className="h-full w-full" layers={layers} onMapClick={handleMapClick} />

      {/* Title overlay top-left */}
      <div
        className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-md px-3 py-2"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <Hexagon size={16} style={{ color: 'var(--accent)' }} />
        <div>
          <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Grade Hexagonal H3
          </h1>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {loading ? 'Carregando...' : `${totalCells.toLocaleString('pt-BR')} celulas`}
            {' | '}Media: {formatValue(avgValue, metric)}
          </p>
        </div>
      </div>

      {/* Metric selector top-right (below map zoom controls) */}
      <div className="absolute right-4 top-40 z-10 flex flex-col gap-2">
        {/* Metric dropdown */}
        <div className="relative">
          <button
            onClick={() => { setMetricDropdownOpen((v) => !v); setResDropdownOpen(false); }}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <Layers size={14} />
            {currentMetricLabel}
            <ChevronDown size={12} className={metricDropdownOpen ? 'rotate-180' : ''} />
          </button>

          {metricDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-44 rounded-md py-1"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            >
              {METRIC_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setMetric(opt.value); setMetricDropdownOpen(false); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm"
                  style={{
                    color: opt.value === metric ? 'var(--accent)' : 'var(--text-primary)',
                    background: opt.value === metric ? 'var(--accent-subtle)' : 'transparent',
                  }}
                >
                  {opt.icon}
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Resolution dropdown */}
        <div className="relative">
          <button
            onClick={() => { setResDropdownOpen((v) => !v); setMetricDropdownOpen(false); }}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <Settings2 size={14} />
            {currentResLabel}
            <ChevronDown size={12} className={resDropdownOpen ? 'rotate-180' : ''} />
          </button>

          {resDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-44 rounded-md py-1"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            >
              {RESOLUTION_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setResolution(opt.value); setResDropdownOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm"
                  style={{
                    color: opt.value === resolution ? 'var(--accent)' : 'var(--text-primary)',
                    background: opt.value === resolution ? 'var(--accent-subtle)' : 'transparent',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Legend bottom-left */}
      <div
        className="absolute bottom-12 left-4 z-10 rounded-md px-3 py-2"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <p className="mb-1.5 text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
          {currentMetricLabel}
        </p>
        <div className="flex items-center gap-1">
          {legendStops.map((stop, i) => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div
                className="h-3 w-8 rounded-sm"
                style={{ backgroundColor: stop.color }}
              />
              <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>
                {stop.label}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-1 text-[9px]" style={{ color: 'var(--text-muted)' }}>
          {metric === 'subscribers' ? 'Baixo → Alto (azul)' : 'Baixo (verm.) → Alto (verde)'}
        </p>
      </div>

      {/* Cell detail SidePanel */}
      <SidePanel
        open={selectedCell != null}
        onClose={handleClosePanel}
        title="Detalhes da Celula H3"
        subtitle={cellMunicipality ? `${cellMunicipality}${cellState ? ` - ${cellState}` : ''}` : undefined}
      >
        <div className="space-y-4">
          {/* H3 Index */}
          <div>
            <p className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
              Indice H3
            </p>
            <p
              className="mt-0.5 rounded px-2 py-1 font-mono text-xs"
              style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--text-primary)' }}
            >
              {cellHex}
            </p>
          </div>

          {/* Primary metric value */}
          <div
            className="rounded-lg p-3"
            style={{ backgroundColor: 'var(--accent-subtle)' }}
          >
            <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>
              {currentMetricLabel}
            </p>
            <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
              {cellValue != null ? formatValue(cellValue, metric) : '--'}
            </p>
          </div>

          {/* All metric values from the cell */}
          <div className="space-y-2">
            <p className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
              Metricas da Celula
            </p>
            <DetailRow
              label="Assinantes"
              value={formatCellField(selectedCell, 'subscribers')}
            />
            <DetailRow
              label="Penetracao"
              value={formatCellField(selectedCell, 'penetration', '%')}
            />
            <DetailRow
              label="% Fibra"
              value={formatCellField(selectedCell, 'fiber_share', '%')}
            />
            <DetailRow
              label="Populacao"
              value={formatCellField(selectedCell, 'population')}
            />
            <DetailRow
              label="Area (km2)"
              value={formatCellField(selectedCell, 'area_km2')}
            />
          </div>

          {/* Municipality info */}
          {cellMunicipality && (
            <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
              <p className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
                Municipio
              </p>
              <DetailRow label="Nome" value={cellMunicipality} />
              {cellState && <DetailRow label="Estado" value={cellState} />}
              {(selectedCell?.municipality_id ?? selectedCell?.properties?.municipality_id) && (
                <DetailRow
                  label="ID"
                  value={String(selectedCell?.municipality_id ?? selectedCell?.properties?.municipality_id)}
                />
              )}
            </div>
          )}

          {/* Municipality H3 Analysis */}
          {analysisLoading && (
            <div className="flex items-center gap-2 py-3">
              <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Carregando analise do municipio...
              </span>
            </div>
          )}

          {analysisData && !analysisLoading && (
            <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
              <p className="text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
                Analise H3 do Municipio
              </p>
              {analysisData.total_cells != null && (
                <DetailRow label="Total de celulas" value={String(analysisData.total_cells)} />
              )}
              {analysisData.covered_cells != null && (
                <DetailRow label="Celulas cobertas" value={String(analysisData.covered_cells)} />
              )}
              {analysisData.coverage_pct != null && (
                <DetailRow label="Cobertura" value={`${analysisData.coverage_pct.toFixed(1)}%`} />
              )}
              {analysisData.avg_subscribers != null && (
                <DetailRow label="Media de assinantes" value={analysisData.avg_subscribers.toLocaleString('pt-BR')} />
              )}
              {analysisData.avg_penetration != null && (
                <DetailRow label="Penetracao media" value={`${analysisData.avg_penetration.toFixed(1)}%`} />
              )}
              {analysisData.max_subscribers != null && (
                <DetailRow label="Max assinantes" value={analysisData.max_subscribers.toLocaleString('pt-BR')} />
              )}
              {analysisData.hotspot_count != null && (
                <DetailRow label="Hotspots" value={String(analysisData.hotspot_count)} />
              )}

              {/* Trigger computation */}
              {analysisData.status === 'not_computed' && (
                <ComputeButton
                  municipalityId={selectedCell?.municipality_id ?? selectedCell?.properties?.municipality_id}
                  onComplete={(data) => setAnalysisData(data)}
                />
              )}
            </div>
          )}
        </div>
      </SidePanel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-center justify-between rounded-lg px-3 py-2"
      style={{ backgroundColor: 'var(--bg-subtle)' }}
    >
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}

function ComputeButton({
  municipalityId,
  onComplete,
}: {
  municipalityId: number;
  onComplete: (data: any) => void;
}) {
  const [computing, setComputing] = useState(false);

  const handleCompute = async () => {
    if (!municipalityId) return;
    setComputing(true);
    try {
      const result = await api.h3.compute(municipalityId);
      onComplete(result);
    } catch {
      // failed silently
    } finally {
      setComputing(false);
    }
  };

  return (
    <button
      onClick={handleCompute}
      disabled={computing}
      className="pulso-btn-primary mt-2 flex w-full items-center justify-center gap-2"
    >
      {computing ? (
        <>
          <Loader2 size={14} className="animate-spin" />
          Computando...
        </>
      ) : (
        <>
          <Hexagon size={14} />
          Computar Analise H3
        </>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

function rgbString(color: [number, number, number, number]): string {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${(color[3] / 255).toFixed(2)})`;
}

function formatValue(value: number, metric: MetricKey): string {
  if (metric === 'penetration' || metric === 'fiber_share') {
    return `${value.toFixed(1)}%`;
  }
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
}

function formatCellField(cell: any, field: string, suffix = ''): string {
  if (!cell) return '--';
  const val = cell[field] ?? cell.properties?.[field];
  if (val == null) return '--';
  if (typeof val === 'number') {
    if (suffix === '%') return `${val.toFixed(1)}${suffix}`;
    return val.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + suffix;
  }
  return String(val) + suffix;
}
