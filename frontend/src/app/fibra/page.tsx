'use client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import SidePanel from '@/components/layout/SidePanel';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatBRL, formatNumber, formatCompact } from '@/lib/format';
import {
  Cable,
  MapPin,
  Navigation,
  Loader2,
  RotateCcw,
  Ruler,
  DollarSign,
  Layers,
  Package,
  AlertTriangle,
  MousePointerClick,
  ChevronRight,
} from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-full w-full items-center justify-center"
      style={{ background: 'var(--bg-subtle)' }}
    >
      <Loader2 className="animate-spin" size={32} style={{ color: 'var(--accent)' }} />
    </div>
  ),
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RoutePoint {
  lat: number;
  lng: number;
}

interface RouteSegment {
  distance_m?: number;
  road_name?: string;
  highway_class?: string;
  geometry?: number[][];
}

interface RouteResult {
  distance_km: number;
  estimated_cost_brl: number;
  segments?: RouteSegment[];
  geometry?: number[][];
  path?: number[][];
  route_geometry?: number[][];
  total_distance_km?: number;
  bom?: BomItem[];
}

interface BomItem {
  item: string;
  description?: string;
  quantity: number;
  unit: string;
  unit_cost_brl?: number;
  total_cost_brl?: number;
}

interface CorridorResult {
  power_lines_nearby?: number;
  co_location_savings_pct?: number;
  corridor_width_m?: number;
  recommended?: boolean;
  segments?: any[];
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FiberRoutePage() {
  // Map interaction state
  const [startPoint, setStartPoint] = useState<RoutePoint | null>(null);
  const [endPoint, setEndPoint] = useState<RoutePoint | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [flyTo, setFlyTo] = useState<{ latitude: number; longitude: number; zoom?: number } | null>(null);

  // deck.gl layers loaded dynamically
  const deckRef = useRef<{ ScatterplotLayer: any; PathLayer: any } | null>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer, PathLayer: mod.PathLayer };
      setDeckReady(true);
    }).catch(() => {});
  }, []);

  // API hooks
  const {
    data: routeData,
    loading: routeLoading,
    error: routeError,
    execute: executeRoute,
    reset: resetRoute,
  } = useLazyApi<RouteResult, { start_lat: number; start_lon: number; end_lat: number; end_lon: number }>(
    (params) => api.fiber.route(params)
  );

  const {
    data: bomData,
    loading: bomLoading,
    execute: executeBom,
    reset: resetBom,
  } = useLazyApi<{ items?: BomItem[]; total_cost_brl?: number }, { distance_km: number; terrain?: string }>(
    (params) => api.fiber.bom(params)
  );

  const {
    data: corridorData,
    loading: corridorLoading,
    execute: executeCorridor,
    reset: resetCorridor,
  } = useLazyApi<CorridorResult, { start_lat: number; start_lon: number; end_lat: number; end_lon: number }>(
    (params) => api.fiber.corridor(params)
  );

  // Handle map clicks to set start/end points
  const handleMapClick = useCallback((info: any) => {
    if (!info?.coordinate) return;
    const [lng, lat] = info.coordinate;

    if (!startPoint) {
      setStartPoint({ lat, lng });
    } else if (!endPoint) {
      setEndPoint({ lat, lng });
    }
    // If both are already set, ignore further clicks until reset
  }, [startPoint, endPoint]);

  // Calculate route
  const handleCalculateRoute = useCallback(async () => {
    if (!startPoint || !endPoint) return;

    const params = {
      start_lat: startPoint.lat,
      start_lon: startPoint.lng,
      end_lat: endPoint.lat,
      end_lon: endPoint.lng,
    };

    const result = await executeRoute(params);

    if (result) {
      setPanelOpen(true);

      // Also fetch BOM and corridor analysis
      const distKm = result.distance_km ?? result.total_distance_km ?? 0;
      if (distKm > 0) {
        executeBom({ distance_km: distKm });
      }
      executeCorridor(params);
    }
  }, [startPoint, endPoint, executeRoute, executeBom, executeCorridor]);

  // Reset everything
  const handleReset = useCallback(() => {
    setStartPoint(null);
    setEndPoint(null);
    setPanelOpen(false);
    resetRoute();
    resetBom();
    resetCorridor();
  }, [resetRoute, resetBom, resetCorridor]);

  // Extract route path for the PathLayer
  const routePath = useMemo(() => {
    if (!routeData) return null;

    // The API may return geometry in different formats
    const geom = routeData.geometry ?? routeData.path ?? routeData.route_geometry;
    if (geom && geom.length > 0) {
      // geometry is [[lon, lat], ...] or [[lat, lon], ...]
      // deck.gl PathLayer expects [lng, lat]
      return geom;
    }

    // Fallback: build path from segments
    if (routeData.segments) {
      const coords: number[][] = [];
      for (const seg of routeData.segments) {
        if (seg.geometry) {
          coords.push(...seg.geometry);
        }
      }
      if (coords.length > 0) return coords;
    }

    // Minimal fallback: straight line from start to end
    if (startPoint && endPoint) {
      return [
        [startPoint.lng, startPoint.lat],
        [endPoint.lng, endPoint.lat],
      ];
    }

    return null;
  }, [routeData, startPoint, endPoint]);

  // Build deck.gl layers
  const layers = useMemo(() => {
    if (!deckReady || !deckRef.current) return [];
    const { ScatterplotLayer, PathLayer } = deckRef.current;
    const result: any[] = [];

    // Marker data
    const markers: { position: [number, number]; color: [number, number, number, number]; label: string }[] = [];
    if (startPoint) {
      markers.push({
        position: [startPoint.lng, startPoint.lat],
        color: [34, 197, 94, 220],  // green
        label: 'start',
      });
    }
    if (endPoint) {
      markers.push({
        position: [endPoint.lng, endPoint.lat],
        color: [239, 68, 68, 220],  // red
        label: 'end',
      });
    }

    if (markers.length > 0) {
      result.push(
        new ScatterplotLayer({
          id: 'fiber-markers',
          data: markers,
          getPosition: (d: any) => d.position,
          getFillColor: (d: any) => d.color,
          getRadius: 600,
          radiusMinPixels: 6,
          radiusMaxPixels: 14,
          pickable: true,
          stroked: true,
          getLineColor: [255, 255, 255, 200],
          lineWidthMinPixels: 2,
        })
      );
    }

    // Route path
    if (routePath) {
      result.push(
        new PathLayer({
          id: 'fiber-route',
          data: [{ path: routePath }],
          getPath: (d: any) => d.path,
          getColor: [59, 130, 246, 200],  // blue
          getWidth: 4,
          widthMinPixels: 3,
          widthMaxPixels: 8,
          capRounded: true,
          jointRounded: true,
          pickable: false,
        })
      );
    }

    return result;
  }, [deckReady, startPoint, endPoint, routePath]);

  // Distance and cost from result
  const distanceKm = routeData?.distance_km ?? routeData?.total_distance_km ?? 0;
  const estimatedCost = routeData?.estimated_cost_brl ?? 0;

  // BOM items
  const bomItems: BomItem[] = bomData?.items ?? (routeData?.bom ?? []);
  const bomTotal = bomData?.total_cost_brl ?? bomItems.reduce((acc, i) => acc + (i.total_cost_brl ?? 0), 0);

  // Segment count
  const segmentCount = routeData?.segments?.length ?? 0;

  // Status label for the instruction bar
  const statusLabel = !startPoint
    ? 'Clique no mapa para definir o ponto de partida'
    : !endPoint
      ? 'Clique no mapa para definir o ponto de chegada'
      : routeLoading
        ? 'Calculando rota...'
        : routeData
          ? `Rota calculada: ${distanceKm.toFixed(1)} km`
          : 'Pronto para calcular a rota';

  return (
    <div className="relative flex h-[calc(100vh-64px)] flex-col">
      {/* Top bar */}
      <div
        className="z-20 flex items-center justify-between px-4 py-2"
        style={{
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-3">
          <Cable size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Planejamento de Rota de Fibra
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Roteamento sobre 6,4 milhoes de segmentos de estradas reais
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Status indicator */}
          <div
            className="flex items-center gap-2 rounded-md px-3 py-1.5 text-xs"
            style={{
              background: 'var(--bg-subtle)',
              color: routeLoading ? 'var(--accent)' : 'var(--text-secondary)',
            }}
          >
            {routeLoading ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <MousePointerClick size={12} />
            )}
            {statusLabel}
          </div>

          {/* Calculate button */}
          {startPoint && endPoint && !routeData && (
            <button
              onClick={handleCalculateRoute}
              disabled={routeLoading}
              className="pulso-btn-primary flex items-center gap-2 text-xs"
            >
              {routeLoading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Navigation size={14} />
              )}
              {routeLoading ? 'Calculando...' : 'Calcular Rota'}
            </button>
          )}

          {/* Reset button */}
          {(startPoint || routeData) && (
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors"
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border)',
              }}
            >
              <RotateCcw size={12} />
              Limpar
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {routeLoading && (
        <div className="relative z-20 h-1 w-full overflow-hidden" style={{ background: 'var(--bg-subtle)' }}>
          <div
            className="h-full animate-pulse"
            style={{
              background: 'var(--accent)',
              width: '60%',
              animation: 'indeterminate 1.5s ease-in-out infinite',
            }}
          />
          <style>{`
            @keyframes indeterminate {
              0% { transform: translateX(-100%); width: 40%; }
              50% { transform: translateX(60%); width: 60%; }
              100% { transform: translateX(200%); width: 40%; }
            }
          `}</style>
        </div>
      )}

      {/* Point coordinates bar */}
      {(startPoint || endPoint) && (
        <div
          className="z-20 flex items-center gap-4 px-4 py-1.5 text-xs"
          style={{
            background: 'color-mix(in srgb, var(--bg-surface) 95%, transparent)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {startPoint && (
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: 'rgb(34, 197, 94)' }}
              />
              <span style={{ color: 'var(--text-muted)' }}>Partida:</span>
              <span style={{ color: 'var(--text-primary)' }}>
                {startPoint.lat.toFixed(5)}, {startPoint.lng.toFixed(5)}
              </span>
            </span>
          )}
          {startPoint && endPoint && (
            <ChevronRight size={12} style={{ color: 'var(--text-muted)' }} />
          )}
          {endPoint && (
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: 'rgb(239, 68, 68)' }}
              />
              <span style={{ color: 'var(--text-muted)' }}>Chegada:</span>
              <span style={{ color: 'var(--text-primary)' }}>
                {endPoint.lat.toFixed(5)}, {endPoint.lng.toFixed(5)}
              </span>
            </span>
          )}
        </div>
      )}

      {/* Error banner */}
      {routeError && (
        <div
          className="z-20 flex items-center gap-3 px-4 py-2"
          style={{
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            borderBottom: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
          }}
        >
          <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />
          <p className="text-xs" style={{ color: 'var(--danger)' }}>
            {routeError}
          </p>
        </div>
      )}

      {/* Map */}
      <div className="relative flex-1">
        <MapView
          className="h-full w-full"
          layers={layers}
          onMapClick={handleMapClick}
          flyTo={flyTo}
          initialViewState={{ pitch: 0, bearing: 0, zoom: 5 }}
        />

        {/* Legend overlay */}
        <div
          className="absolute left-4 top-4 z-10 rounded-lg p-3"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}
        >
          <p className="mb-2 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
            Legenda
          </p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: 'rgb(34, 197, 94)' }} />
              Ponto de partida
            </div>
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: 'rgb(239, 68, 68)' }} />
              Ponto de chegada
            </div>
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <span className="inline-block h-3 w-1 rounded" style={{ background: 'rgb(59, 130, 246)' }} />
              Rota de fibra
            </div>
          </div>
        </div>

        {/* Quick stats overlay (when route is computed) */}
        {routeData && !panelOpen && (
          <button
            onClick={() => setPanelOpen(true)}
            className="absolute bottom-4 right-4 z-10 flex items-center gap-3 rounded-lg p-3 transition-transform hover:scale-[1.02]"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: '0 2px 12px rgba(0,0,0,0.1)',
              cursor: 'pointer',
            }}
          >
            <div className="text-left">
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Distancia</p>
              <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                {distanceKm.toFixed(1)} km
              </p>
            </div>
            <div
              className="h-8 w-px"
              style={{ background: 'var(--border)' }}
            />
            <div className="text-left">
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Custo Estimado</p>
              <p className="text-sm font-bold" style={{ color: 'var(--accent)' }}>
                {formatBRL(estimatedCost)}
              </p>
            </div>
            <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
          </button>
        )}
      </div>

      {/* Side panel with route details */}
      <SidePanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        title="Resultado da Rota"
        subtitle={routeData ? `${distanceKm.toFixed(1)} km de fibra` : undefined}
        actions={
          <button
            onClick={handleReset}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <RotateCcw size={14} />
            Nova Rota
          </button>
        }
      >
        {routeData && (
          <div className="space-y-5">
            {/* Summary stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <Ruler size={12} />
                  Distancia
                </div>
                <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                  {distanceKm.toFixed(1)} km
                </p>
              </div>
              <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <DollarSign size={12} />
                  Custo Estimado
                </div>
                <p className="mt-1 text-lg font-bold" style={{ color: 'var(--accent)' }}>
                  {formatBRL(estimatedCost)}
                </p>
              </div>
            </div>

            {/* Cost per km */}
            <div
              className="flex items-center justify-between rounded-lg px-3 py-2"
              style={{ backgroundColor: 'var(--bg-subtle)' }}
            >
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Custo por km</span>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {distanceKm > 0 ? formatBRL(estimatedCost / distanceKm) : '--'}
              </span>
            </div>

            {/* Corridor analysis */}
            {corridorLoading && (
              <div className="flex items-center gap-2 py-2">
                <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Analisando corredor...</span>
              </div>
            )}

            {corridorData && (
              <div className="space-y-2">
                <p className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  <Layers size={12} />
                  Analise de Corredor
                </p>
                {corridorData.power_lines_nearby != null && (
                  <div
                    className="flex items-center justify-between rounded-lg px-3 py-2"
                    style={{ backgroundColor: 'var(--bg-subtle)' }}
                  >
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Linhas de energia proximo</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {corridorData.power_lines_nearby}
                    </span>
                  </div>
                )}
                {corridorData.co_location_savings_pct != null && (
                  <div
                    className="flex items-center justify-between rounded-lg px-3 py-2"
                    style={{ backgroundColor: 'color-mix(in srgb, var(--success) 10%, transparent)' }}
                  >
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Economia co-locacao</span>
                    <span className="text-sm font-bold" style={{ color: 'var(--success)' }}>
                      {corridorData.co_location_savings_pct.toFixed(0)}%
                    </span>
                  </div>
                )}
                {corridorData.recommended != null && (
                  <div
                    className="flex items-center justify-between rounded-lg px-3 py-2"
                    style={{ backgroundColor: 'var(--bg-subtle)' }}
                  >
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Corredor recomendado</span>
                    <span
                      className="text-xs font-bold"
                      style={{ color: corridorData.recommended ? 'var(--success)' : 'var(--warning)' }}
                    >
                      {corridorData.recommended ? 'SIM' : 'NAO'}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Segment breakdown */}
            {segmentCount > 0 && (
              <div className="space-y-2">
                <p className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  <MapPin size={12} />
                  Segmentos ({segmentCount})
                </p>
                <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
                  {routeData.segments!.map((seg, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded-md px-3 py-2 text-xs"
                      style={{ backgroundColor: 'var(--bg-subtle)' }}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                          style={{
                            background: 'var(--accent)',
                            color: '#fff',
                          }}
                        >
                          {idx + 1}
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>
                          {seg.road_name || seg.highway_class || `Segmento ${idx + 1}`}
                        </span>
                      </div>
                      {seg.distance_m != null && (
                        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                          {seg.distance_m >= 1000
                            ? `${(seg.distance_m / 1000).toFixed(1)} km`
                            : `${seg.distance_m.toFixed(0)} m`}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* BOM table */}
            {bomLoading && (
              <div className="flex items-center gap-2 py-2">
                <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando BOM...</span>
              </div>
            )}

            {bomItems.length > 0 && (
              <div className="space-y-2">
                <p className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  <Package size={12} />
                  Bill of Materials (BOM)
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="pb-1.5 text-left font-medium" style={{ color: 'var(--text-muted)' }}>Item</th>
                        <th className="pb-1.5 text-right font-medium" style={{ color: 'var(--text-muted)' }}>Qtd</th>
                        <th className="pb-1.5 text-right font-medium" style={{ color: 'var(--text-muted)' }}>Un.</th>
                        <th className="pb-1.5 text-right font-medium" style={{ color: 'var(--text-muted)' }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bomItems.map((item, idx) => (
                        <tr
                          key={idx}
                          style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}
                        >
                          <td className="py-1.5" style={{ color: 'var(--text-secondary)' }}>
                            {item.item}
                            {item.description && (
                              <span className="block text-[10px]" style={{ color: 'var(--text-muted)' }}>
                                {item.description}
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 text-right font-medium" style={{ color: 'var(--text-primary)' }}>
                            {formatNumber(item.quantity)}
                          </td>
                          <td className="py-1.5 text-right" style={{ color: 'var(--text-muted)' }}>
                            {item.unit}
                          </td>
                          <td className="py-1.5 text-right font-medium" style={{ color: 'var(--text-primary)' }}>
                            {item.total_cost_brl != null ? formatBRL(item.total_cost_brl) : '--'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    {bomTotal > 0 && (
                      <tfoot>
                        <tr style={{ borderTop: '2px solid var(--border)' }}>
                          <td
                            colSpan={3}
                            className="pt-2 text-xs font-semibold"
                            style={{ color: 'var(--text-secondary)' }}
                          >
                            Total BOM
                          </td>
                          <td
                            className="pt-2 text-right text-sm font-bold"
                            style={{ color: 'var(--accent)' }}
                          >
                            {formatBRL(bomTotal)}
                          </td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
            )}

            {/* Coordinates */}
            <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
              <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                Coordenadas
              </p>
              {startPoint && (
                <div
                  className="flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ backgroundColor: 'var(--bg-subtle)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'rgb(34, 197, 94)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Partida</span>
                  </div>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>
                    {startPoint.lat.toFixed(5)}, {startPoint.lng.toFixed(5)}
                  </span>
                </div>
              )}
              {endPoint && (
                <div
                  className="flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ backgroundColor: 'var(--bg-subtle)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'rgb(239, 68, 68)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Chegada</span>
                  </div>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>
                    {endPoint.lat.toFixed(5)}, {endPoint.lng.toFixed(5)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state while loading */}
        {routeLoading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
            <p className="mt-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
              Calculando rota de fibra...
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              Dijkstra sobre 6,4M segmentos de estrada
            </p>
          </div>
        )}
      </SidePanel>
    </div>
  );
}
