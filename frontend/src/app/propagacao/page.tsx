'use client';

/**
 * Propagação — planejador nacional de rádio-enlaces e cobertura FWA.
 *
 * Clique em qualquer ponto do Brasil: o backend baixa os tiles de terreno
 * (SRTM 30 m + Copernicus DSM 30 m) sob demanda, extrai o perfil com
 * curvatura da Terra e zona de Fresnel, e calcula cobertura com o motor
 * RF (Hata / ITM / TR 38.901 / P.1812 / P.530).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  Area,
  ComposedChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Loader2, Mountain, Radio, RotateCcw, X } from 'lucide-react';
import { api } from '@/lib/api';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center" style={{ background: 'var(--bg-subtle)' }}>
      <span style={{ color: 'var(--text-muted)' }}>Carregando mapa…</span>
    </div>
  ),
});

type Mode = 'enlace' | 'cobertura';
type Surface = 'dtm' | 'dsm' | 'ground';
interface Pt { lat: number; lng: number }

const EARTH_R = 6371000;
const K_FACTOR = 4 / 3;

function haversineM(a: Pt, b: Pt): number {
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lng - a.lng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return EARTH_R * 2 * Math.asin(Math.sqrt(s));
}

function signalColor(dbm: number): [number, number, number, number] {
  if (dbm >= -70) return [16, 185, 129, 190]; // excelente
  if (dbm >= -85) return [234, 179, 8, 190]; // bom
  if (dbm >= -95) return [249, 115, 22, 190]; // regular
  return [239, 68, 68, 150]; // fraco
}

export default function PropagacaoPage() {
  const [mode, setMode] = useState<Mode>('enlace');
  const [surface, setSurface] = useState<Surface>('dsm');
  const [useBuildings, setUseBuildings] = useState(false);
  const [tx, setTx] = useState<Pt | null>(null);
  const [rx, setRx] = useState<Pt | null>(null);

  // Parâmetros do enlace / cobertura
  const [freqMhz, setFreqMhz] = useState(5800);
  const [txHeight, setTxHeight] = useState(30);
  const [rxHeight, setRxHeight] = useState(15);
  const [txPower, setTxPower] = useState(43);
  const [antGain, setAntGain] = useState(16);
  const [radiusM, setRadiusM] = useState(5000);
  const [gridRes, setGridRes] = useState(100);

  const [profile, setProfile] = useState<any>(null);
  const [coverage, setCoverage] = useState<any>(null);
  const [linkBudget, setLinkBudget] = useState<any>(null);
  const [clickInfo, setClickInfo] = useState<any>(null);
  const [terrainStatus, setTerrainStatus] = useState<any>(null);
  const [calibration, setCalibration] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [showProjects, setShowProjects] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [covLoading, setCovLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(true);

  const [deckReady, setDeckReady] = useState(false);
  const deckRef = useRef<any>(null);

  // Vista inicial via URL (?lat=&lon=&zoom=) — permite deep-link para uma região
  const [initialView] = useState(() => {
    if (typeof window === 'undefined') return undefined;
    const q = new URLSearchParams(window.location.search);
    const lat = parseFloat(q.get('lat') || '');
    const lon = parseFloat(q.get('lon') || '');
    const zoom = parseFloat(q.get('zoom') || '');
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      return {
        latitude: lat,
        longitude: lon,
        zoom: Number.isFinite(zoom) ? zoom : 11,
        pitch: 0,
        bearing: 0,
      };
    }
    return undefined;
  });

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = {
        ScatterplotLayer: mod.ScatterplotLayer,
        GridCellLayer: mod.GridCellLayer,
        LineLayer: mod.LineLayer,
        TextLayer: mod.TextLayer,
      };
      setDeckReady(true);
    });
  }, []);

  useEffect(() => {
    api.design.terrainStatus().then(setTerrainStatus).catch(() => {});
    api.design.calibrationStatus().then(setCalibration).catch(() => {});
    api.rfProjects.list().then((r) => setProjects(r.projects || [])).catch(() => {});
  }, []);

  // ── Perfil de terreno (auto ao definir TX+RX ou trocar superfície) ──
  const fetchProfile = useCallback(
    async (a: Pt, b: Pt, surf: Surface) => {
      setLoading(true);
      setError(null);
      try {
        const distM = haversineM(a, b);
        const step = Math.max(30, Math.round(distM / 400));
        const [prof, budget] = await Promise.all([
          api.design.terrainProfile(a.lat, a.lng, b.lat, b.lng, step, {
            surface: surf,
            txHeightM: txHeight,
            rxHeightM: rxHeight,
            frequencyMhz: freqMhz,
            buildings: useBuildings,
          }),
          api.design
            .linkBudget({
              frequency_ghz: freqMhz / 1000,
              distance_km: distM / 1000,
              tx_power_dbm: txPower,
              tx_antenna_gain_dbi: antGain,
              rx_antenna_gain_dbi: antGain,
              rx_threshold_dbm: -70,
              // rain resolved from ITU-R P.837 at the path midpoint
              mid_lat: (a.lat + b.lat) / 2,
              mid_lon: (a.lng + b.lng) / 2,
            } as any)
            .catch(() => null),
        ]);
        setProfile(prof);
        setLinkBudget(budget);
        setShowResults(true);
      } catch (e: any) {
        setError(e?.message || 'Falha ao extrair perfil de terreno');
      } finally {
        setLoading(false);
      }
    },
    [freqMhz, txHeight, rxHeight, txPower, antGain, useBuildings]
  );

  useEffect(() => {
    if (mode === 'enlace' && tx && rx) fetchProfile(tx, rx, surface);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tx, rx, surface, mode, useBuildings]);

  const runCoverage = useCallback(async () => {
    if (!tx) return;
    setCovLoading(true);
    setError(null);
    try {
      const result = await api.design.coverage({
        tower_lat: tx.lat,
        tower_lon: tx.lng,
        tower_height_m: txHeight,
        frequency_mhz: freqMhz,
        tx_power_dbm: txPower,
        antenna_gain_dbi: antGain,
        radius_m: radiusM,
        grid_resolution_m: gridRes,
        apply_vegetation: true,
        country_code: 'BR',
      });
      setCoverage(result);
      setShowResults(true);
    } catch (e: any) {
      setError(e?.message || 'Falha no cálculo de cobertura');
    } finally {
      setCovLoading(false);
    }
  }, [tx, txHeight, freqMhz, txPower, antGain, radiusM, gridRes]);

  const handleMapClick = useCallback(
    (info: any) => {
      if (!info?.coordinate) return;
      const [lng, lat] = info.coordinate;
      const pt = { lat, lng };
      if (mode === 'cobertura') {
        setTx(pt);
        setCoverage(null);
      } else if (!tx || (tx && rx)) {
        setTx(pt);
        setRx(null);
        setProfile(null);
        setLinkBudget(null);
      } else {
        setRx(pt);
      }
      setClickInfo({ lat, lng, loading: true });
      api.design
        .elevation(lat, lng)
        .then((e) => setClickInfo({ ...e, loading: false }))
        .catch(() => setClickInfo(null));
    },
    [mode, tx, rx]
  );

  const reset = useCallback(() => {
    setTx(null);
    setRx(null);
    setProfile(null);
    setCoverage(null);
    setLinkBudget(null);
    setClickInfo(null);
    setError(null);
    setProjectId(null);
  }, []);

  // ── Projetos salvos ─────────────────────────────────────────────────
  const snapshotState = useCallback(
    () => ({
      mode, tx, rx, surface, useBuildings,
      freqMhz, txHeight, rxHeight, txPower, antGain, radiusM, gridRes,
    }),
    [mode, tx, rx, surface, useBuildings, freqMhz, txHeight, rxHeight, txPower, antGain, radiusM, gridRes]
  );

  const refreshProjects = useCallback(() => {
    api.rfProjects.list().then((r) => setProjects(r.projects || [])).catch(() => {});
  }, []);

  const saveProject = useCallback(async () => {
    const state = snapshotState();
    try {
      if (projectId) {
        await api.rfProjects.update(projectId, { state });
        setSaveMsg('Projeto atualizado');
      } else {
        const name = window.prompt('Nome do projeto:', mode === 'enlace' ? 'Enlace' : 'Cobertura');
        if (!name) return;
        const r = await api.rfProjects.create(name, mode, state);
        setProjectId(r.id);
        setSaveMsg(`Salvo: ${name}`);
      }
      refreshProjects();
      setTimeout(() => setSaveMsg(null), 2500);
    } catch (e: any) {
      setSaveMsg('Falha ao salvar');
      setTimeout(() => setSaveMsg(null), 2500);
    }
  }, [projectId, snapshotState, mode, refreshProjects]);

  const exportStudy = useCallback(
    async (fmt: 'pdf' | 'kmz' | 'geojson') => {
      const study = {
        kind: mode,
        tx, rx,
        params: { freqMhz, txHeight, rxHeight, txPower, antGain, radiusM, gridRes, surface, useBuildings },
        profile, linkBudget, coverage,
      };
      try {
        const base = (process.env.NEXT_PUBLIC_API_URL || 'https://api.enlace.network');
        const token = typeof window !== 'undefined' ? localStorage.getItem('pulso_access_token') : null;
        const r = await fetch(`${base}/api/v1/design/study/export/${fmt}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify(study),
        });
        if (!r.ok) throw new Error(String(r.status));
        const blob = await r.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `estudo-${mode}.${fmt === 'geojson' ? 'geojson' : fmt}`;
        a.click();
        URL.revokeObjectURL(a.href);
      } catch {
        setSaveMsg('Falha ao exportar');
        setTimeout(() => setSaveMsg(null), 2500);
      }
    },
    [mode, tx, rx, freqMhz, txHeight, rxHeight, txPower, antGain, radiusM, gridRes, surface, useBuildings, profile, linkBudget, coverage]
  );

  const loadProject = useCallback(async (id: number) => {
    try {
      const p = await api.rfProjects.get(id);
      const s = p.state || {};
      setMode(s.mode ?? 'enlace');
      setSurface(s.surface ?? 'dsm');
      setUseBuildings(!!s.useBuildings);
      setFreqMhz(s.freqMhz ?? 5800);
      setTxHeight(s.txHeight ?? 30);
      setRxHeight(s.rxHeight ?? 15);
      setTxPower(s.txPower ?? 43);
      setAntGain(s.antGain ?? 16);
      setRadiusM(s.radiusM ?? 5000);
      setGridRes(s.gridRes ?? 100);
      setCoverage(null); setProfile(null); setLinkBudget(null);
      setTx(s.tx ?? null); setRx(s.rx ?? null);
      setProjectId(id);
      setShowProjects(false);
    } catch { setSaveMsg('Falha ao carregar'); setTimeout(() => setSaveMsg(null), 2500); }
  }, []);

  // ── Camadas deck.gl ─────────────────────────────────────────────────
  const layers = useMemo(() => {
    if (!deckReady || !deckRef.current) return [];
    const { ScatterplotLayer, GridCellLayer, LineLayer, TextLayer } = deckRef.current;
    const out: any[] = [];

    if (coverage?.grid?.length) {
      out.push(
        new GridCellLayer({
          id: 'coverage-grid',
          data: coverage.grid,
          cellSize: gridRes,
          extruded: false,
          getPosition: (d: any) => [d.lon, d.lat],
          getFillColor: (d: any) => signalColor(d.signal_dbm),
          pickable: true,
          opacity: 0.35,
        })
      );
    }

    if (tx && rx && mode === 'enlace') {
      out.push(
        new LineLayer({
          id: 'link-line',
          data: [{ from: [tx.lng, tx.lat], to: [rx.lng, rx.lat] }],
          getSourcePosition: (d: any) => d.from,
          getTargetPosition: (d: any) => d.to,
          getColor: profile?.link_analysis
            ? profile.link_analysis.fresnel_clear
              ? [16, 185, 129, 220]
              : profile.link_analysis.line_of_sight
                ? [234, 179, 8, 220]
                : [239, 68, 68, 220]
            : [148, 163, 184, 180],
          getWidth: 3,
        })
      );
    }

    const pts = [
      ...(tx ? [{ ...tx, label: mode === 'cobertura' ? 'TORRE' : 'TX', color: [15, 118, 110, 255] }] : []),
      ...(rx && mode === 'enlace' ? [{ ...rx, label: 'RX', color: [124, 58, 237, 255] }] : []),
    ];
    if (pts.length) {
      out.push(
        new ScatterplotLayer({
          id: 'endpoints',
          data: pts,
          getPosition: (d: any) => [d.lng, d.lat],
          getFillColor: (d: any) => d.color,
          getRadius: 60,
          radiusMinPixels: 7,
          radiusMaxPixels: 14,
          stroked: true,
          getLineColor: [255, 255, 255, 230],
          lineWidthMinPixels: 2,
        }),
        new TextLayer({
          id: 'endpoint-labels',
          data: pts,
          getPosition: (d: any) => [d.lng, d.lat],
          getText: (d: any) => d.label,
          getSize: 13,
          getColor: [255, 255, 255, 255],
          getPixelOffset: [0, -18],
          background: true,
          getBackgroundColor: [15, 23, 42, 200],
        })
      );
    }
    return out;
  }, [deckReady, tx, rx, mode, coverage, gridRes, profile]);

  // ── Dados do gráfico de perfil ──────────────────────────────────────
  const chartData = useMemo(() => {
    if (!profile?.points?.length) return [];
    const total = profile.total_distance_m;
    const la = profile.link_analysis;
    return profile.points.map((p: any, i: number) => {
      const d = p.distance_m;
      const curved =
        p.curved_elevation_m ?? p.elevation_m + (d * (total - d)) / (2 * K_FACTOR * EARTH_R);
      const f = la?.fresnel?.[i];
      return {
        km: +(d / 1000).toFixed(2),
        terreno: +curved.toFixed(1),
        los: f ? f.los_m : undefined,
        fresnelInf: f ? +(f.los_m - f.fresnel_radius_m).toFixed(1) : undefined,
      };
    });
  }, [profile]);

  const la = profile?.link_analysis;
  const isMockProfile = Boolean(profile?._mock);
  const isMockCoverage = Boolean(coverage?._mock);
  const distKm = tx && rx ? haversineM(tx, rx) / 1000 : 0;

  const inputCls = 'pulso-input w-full';
  const lblCls = 'mb-1 block text-xs font-medium';

  return (
    <div className="relative h-full w-full overflow-hidden">
      <MapView className="h-full w-full" layers={layers} onMapClick={handleMapClick} initialViewState={initialView} />

      {(loading || covLoading) && (
        <div className="absolute left-0 right-0 top-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      {/* ── Painel de controle ── */}
      <div
        className="absolute left-4 top-4 z-10 w-72 rounded-lg p-4"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
      >
        <div className="mb-1 flex items-center gap-2">
          <Radio size={16} style={{ color: 'var(--accent)' }} />
          <h1 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            Propagação — Brasil inteiro
          </h1>
        </div>
        <p className="mb-3 text-xs" style={{ color: 'var(--text-muted)' }}>
          {mode === 'enlace'
            ? !tx
              ? 'Clique no mapa para posicionar o TX.'
              : !rx
                ? 'Agora clique para posicionar o RX.'
                : 'Enlace definido — clique de novo para recomeçar.'
            : 'Clique no mapa para posicionar a torre.'}
        </p>

        <div className="mb-3 grid grid-cols-2 gap-1 rounded-md p-1" style={{ background: 'var(--bg-subtle)' }}>
          {(['enlace', 'cobertura'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                reset();
              }}
              className="rounded px-2 py-1.5 text-xs font-medium capitalize"
              style={
                mode === m
                  ? { background: 'var(--accent)', color: '#fff' }
                  : { color: 'var(--text-secondary)' }
              }
            >
              {m === 'enlace' ? 'Enlace P2P' : 'Cobertura'}
            </button>
          ))}
        </div>

        <div className="mb-3 grid grid-cols-2 gap-2">
          <div>
            <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Freq. (MHz)</label>
            <input type="number" className={inputCls} value={freqMhz} onChange={(e) => setFreqMhz(+e.target.value)} />
          </div>
          <div>
            <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>
              {mode === 'enlace' ? 'Alt. TX (m)' : 'Alt. torre (m)'}
            </label>
            <input type="number" className={inputCls} value={txHeight} onChange={(e) => setTxHeight(+e.target.value)} />
          </div>
          {mode === 'enlace' ? (
            <div>
              <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Alt. RX (m)</label>
              <input type="number" className={inputCls} value={rxHeight} onChange={(e) => setRxHeight(+e.target.value)} />
            </div>
          ) : (
            <>
              <div>
                <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Potência (dBm)</label>
                <input type="number" className={inputCls} value={txPower} onChange={(e) => setTxPower(+e.target.value)} />
              </div>
              <div>
                <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Ganho (dBi)</label>
                <input type="number" className={inputCls} value={antGain} onChange={(e) => setAntGain(+e.target.value)} />
              </div>
              <div>
                <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Raio (m)</label>
                <input type="number" className={inputCls} value={radiusM} onChange={(e) => setRadiusM(+e.target.value)} />
              </div>
              <div>
                <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Grade (m)</label>
                <input type="number" className={inputCls} value={gridRes} onChange={(e) => setGridRes(+e.target.value)} />
              </div>
            </>
          )}
        </div>

        {mode === 'enlace' && (
          <div className="mb-3">
            <label className="mb-2 flex cursor-pointer items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={useBuildings}
                onChange={(e) => setUseBuildings(e.target.checked)}
              />
              Edifícios 0,5 m em pontos urbanos (Open Buildings)
            </label>
            <label className={lblCls} style={{ color: 'var(--text-secondary)' }}>Superfície</label>
            <div className="grid grid-cols-3 gap-1 rounded-md p-1" style={{ background: 'var(--bg-subtle)' }}>
              {(['dsm', 'dtm', 'ground'] as Surface[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSurface(s)}
                  title={
                    s === 'dsm'
                      ? 'Superfície: inclui edifícios e vegetação (Copernicus GLO-30)'
                      : s === 'dtm'
                        ? 'SRTM GL1 (radar banda C: inclui parte do dossel)'
                        : 'Solo nu ANADEM (viés de vegetação/edifícios removido por ML)'
                  }
                  className="rounded px-2 py-1 text-xs font-medium uppercase"
                  style={
                    surface === s
                      ? { background: 'var(--accent)', color: '#fff' }
                      : { color: 'var(--text-secondary)' }
                  }
                >
                  {s === 'ground' ? 'solo' : s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          {mode === 'cobertura' && (
            <button className="pulso-btn-primary flex-1 text-xs" onClick={runCoverage} disabled={!tx || covLoading}>
              {covLoading ? <Loader2 size={14} className="mx-auto animate-spin" /> : 'Calcular cobertura'}
            </button>
          )}
          {mode === 'enlace' && tx && rx && (
            <button className="pulso-btn-primary flex-1 text-xs" onClick={() => fetchProfile(tx, rx, surface)} disabled={loading}>
              {loading ? <Loader2 size={14} className="mx-auto animate-spin" /> : 'Recalcular'}
            </button>
          )}
          <button
            className="rounded-md px-3 py-1.5 text-xs"
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            onClick={reset}
          >
            <RotateCcw size={13} className="mr-1 inline" />
            Limpar
          </button>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <button
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ border: '1px solid var(--accent)', color: 'var(--accent)' }}
            onClick={saveProject}
            disabled={!tx}
            title={projectId ? 'Atualizar projeto salvo' : 'Salvar como novo projeto'}
          >
            {projectId ? 'Salvar alterações' : 'Salvar projeto'}
          </button>
          <button
            className="rounded-md px-3 py-1.5 text-xs"
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            onClick={() => { setShowProjects((v) => !v); refreshProjects(); }}
          >
            Meus projetos ({projects.length})
          </button>
        </div>
        {saveMsg && (
          <p className="mt-1 text-[11px]" style={{ color: 'var(--accent)' }}>{saveMsg}</p>
        )}
        {showProjects && (
          <div className="mt-2 max-h-44 overflow-y-auto rounded-md" style={{ border: '1px solid var(--border)' }}>
            {projects.length === 0 && (
              <p className="p-2 text-[11px]" style={{ color: 'var(--text-muted)' }}>Nenhum projeto salvo ainda.</p>
            )}
            {projects.map((p) => (
              <div key={p.id} className="flex items-center justify-between px-2 py-1.5 text-xs" style={{ borderBottom: '1px solid var(--border)' }}>
                <button className="truncate text-left" style={{ color: 'var(--text-primary)' }} onClick={() => loadProject(p.id)}>
                  {p.name} <span style={{ color: 'var(--text-muted)' }}>· {p.kind}</span>
                </button>
                <button
                  title="Excluir"
                  style={{ color: 'var(--text-muted)' }}
                  onClick={() => api.rfProjects.remove(p.id).then(refreshProjects)}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {loading && (
          <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            Extraindo perfil… tiles de terreno novos são baixados sob demanda (~26 MB/tile, pode levar ~1 min).
          </p>
        )}
        {error && (
          <p className="mt-2 text-xs" style={{ color: 'var(--danger)' }}>{error}</p>
        )}

        <p className="mt-3 text-[10px] leading-snug" style={{ color: 'var(--text-muted)' }}>
          Estimativa por modelos ITU-R/3GPP sobre terreno 30 m (SRTM + Copernicus DSM). Não substitui
          projeto técnico assinado (Lei 5.194/66) nem site survey.
        </p>
      </div>

      {/* ── Ponto clicado / status do terreno ── */}
      <div className="absolute right-4 top-4 z-10 w-64 space-y-2">
        {clickInfo && (
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Mountain size={13} /> Elevação no ponto
              </span>
              <button onClick={() => setClickInfo(null)}>
                <X size={13} style={{ color: 'var(--text-muted)' }} />
              </button>
            </div>
            {clickInfo.loading ? (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>consultando…</p>
            ) : (
              <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                <div className="flex justify-between"><span>Terreno (DTM)</span><b>{clickInfo.elevation_dtm_m ?? '—'} m</b></div>
                <div className="flex justify-between"><span>Superfície (DSM)</span><b>{clickInfo.elevation_dsm_m ?? '—'} m</b></div>
                <div className="flex justify-between"><span>Clutter (DSM−DTM)</span><b>{clickInfo.clutter_height_m ?? '—'} m</b></div>
                {clickInfo.elevation_ground_m != null && (
                  <div className="flex justify-between"><span>Solo nu (ANADEM)</span><b>{clickInfo.elevation_ground_m} m</b></div>
                )}
                {clickInfo.surface_height_m != null && (
                  <div className="flex justify-between"><span>Altura sobre solo</span><b>{clickInfo.surface_height_m} m</b></div>
                )}
                {clickInfo.building_height_m != null && clickInfo.building_height_m > 0 && (
                  <div className="flex justify-between"><span>Edifício (0,5 m)</span><b>{clickInfo.building_height_m} m</b></div>
                )}
                {clickInfo.landcover && (
                  <div className="flex justify-between"><span>Uso do solo</span><b>{clickInfo.landcover.name_pt}</b></div>
                )}
                <div className="flex justify-between" style={{ color: 'var(--text-muted)' }}>
                  <span>{Number(clickInfo.lat).toFixed(4)}, {Number(clickInfo.lon).toFixed(4)}</span>
                  <span>tile {clickInfo.tile}</span>
                </div>
              </div>
            )}
          </div>
        )}
        {terrainStatus && (
          <div className="rounded-lg px-3 py-2 text-[10px]" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            Tiles em cache: {terrainStatus.surfaces?.dtm?.tiles_cached ?? 0} DTM · {terrainStatus.surfaces?.dsm?.tiles_cached ?? 0} DSM · {terrainStatus.surfaces?.ground?.tiles_cached ?? 0} solo (30 m, download automático)
          </div>
        )}
        {calibration && (
          <div className="rounded-lg px-3 py-2 text-[10px]" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            {calibration.calibrated?.urban
              ? `Calibrado (held-out): RMSE ${calibration.calibrated.urban.rmse_after_db} dB urbano · ${calibration.calibrated.rural?.rmse_after_db ?? '—'} dB rural (${(calibration.residuals_scored / 1e6).toFixed(1)}M medições Anatel)`
              : calibration.benchmark_valid
                ? `Benchmark v1: σ ${calibration.overall?.std_db} dB · viés ${calibration.overall?.bias_db} dB (${(calibration.residuals_scored / 1e6).toFixed(1)}M medições Anatel)`
                : `Modelo não calibrado — previsões são física ITU-R/3GPP sem validação de campo (${calibration.residuals_scored ?? 0}/100 medições)`}
          </div>
        )}
      </div>

      {/* ── Resultados: cobertura ── */}
      {coverage && mode === 'cobertura' && showResults && (
        <div
          className="absolute bottom-4 left-4 z-10 w-80 rounded-lg p-3"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>Cobertura RF</span>
            <span className="flex items-center gap-2">
              {(['pdf', 'kmz', 'geojson'] as const).map((f) => (
                <button
                  key={f}
                  className="rounded px-1.5 py-0.5 text-[9px] font-medium uppercase"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  onClick={() => exportStudy(f)}
                >
                  {f}
                </button>
              ))}
              <button onClick={() => setShowResults(false)}><X size={13} style={{ color: 'var(--text-muted)' }} /></button>
            </span>
          </div>
          {isMockCoverage && (
            <div className="mb-2 rounded px-2 py-1 text-[10px]" style={{ background: 'color-mix(in srgb, var(--warning) 15%, transparent)', color: 'var(--warning)' }}>
              Motor RF não conectado — resultado SIMULADO, não usar para planejamento.
            </div>
          )}
          {coverage.environment && (
            <div className="mb-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Ambiente {({ urban: 'urbano', suburban: 'suburbano', rural: 'rural', open: 'aberto' } as Record<string, string>)[coverage.environment] || coverage.environment} (MapBiomas) · sombreamento por terreno SRTM · difração ITU-R P.526
            </div>
          )}
          <div className="grid grid-cols-4 gap-2 text-center">
            <div><div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{coverage.coverage_pct?.toFixed(0)}%</div><div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>cobertura P50</div></div>
            {coverage.coverage_pct_p90 != null && (
              <div><div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{coverage.coverage_pct_p90.toFixed(0)}%</div><div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>P90 (σ {coverage.sigma_db?.toFixed(0)} dB)</div></div>
            )}
            <div><div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{coverage.coverage_area_km2?.toFixed(1)}</div><div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>km²</div></div>
            <div><div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{coverage.avg_signal_dbm?.toFixed(0)}</div><div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>dBm médio</div></div>
          </div>
          <div className="mt-2 flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: 'rgb(16,185,129)' }} /> ≥−70
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: 'rgb(234,179,8)' }} /> ≥−85
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: 'rgb(249,115,22)' }} /> ≥−95
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: 'rgb(239,68,68)' }} /> &lt;−95 dBm
          </div>
        </div>
      )}

      {/* ── Resultados: perfil do enlace ── */}
      {profile && mode === 'enlace' && showResults && (
        <div
          className="absolute bottom-4 left-4 right-4 z-10 rounded-lg p-3"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
              Perfil {surface.toUpperCase()} — {distKm.toFixed(1)} km
            </span>
            {la && (
              <>
                <span className={la.line_of_sight ? 'pulso-badge-green' : 'pulso-badge-red'}>
                  {la.line_of_sight ? 'LOS livre' : 'LOS obstruído'}
                </span>
                <span className={la.fresnel_clear ? 'pulso-badge-green' : 'pulso-badge-yellow'}>
                  Fresnel {la.fresnel_clear ? '≥60% livre' : `${(la.worst_clearance_ratio * 100).toFixed(0)}% no pior ponto`}
                </span>
              </>
            )}
            {linkBudget && (
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                Rx {linkBudget.received_power_dbm?.toFixed(1)} dBm · margem {linkBudget.fade_margin_db?.toFixed(1)} dB · disp. {linkBudget.availability_pct?.toFixed(3)}%
                {linkBudget.rain_rate_mmh != null && ` · chuva ${linkBudget.rain_rate_mmh} mm/h${linkBudget.rain_rate_source === 'itu_p837' ? ' (P.837)' : ''}`}
              </span>
            )}
            {isMockProfile && (
              <span className="rounded px-2 py-0.5 text-[10px]" style={{ background: 'color-mix(in srgb, var(--warning) 15%, transparent)', color: 'var(--warning)' }}>
                Terreno SIMULADO (tiles indisponíveis)
              </span>
            )}
            {profile.source === 'local_tiles' && (
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>leitor local (motor RF offline)</span>
            )}
            {la?.buildings_used && (
              <span className="rounded px-2 py-0.5 text-[10px]" style={{ background: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}>
                com edifícios ({profile.buildings_sampled ?? 0} pts urbanos)
              </span>
            )}
            {profile.clutter_summary?.fractions && (
              <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                {Object.entries(profile.clutter_summary.fractions as Record<string, number>)
                  .slice(0, 3)
                  .map(([k, v]) => `${Math.round(v * 100)}% ${
                    ({ urban: 'urbano', forest: 'floresta', agriculture: 'agro', water: 'água', wetland: 'úmido', bare: 'solo', open: 'campo', plantation: 'silvic.' } as Record<string, string>)[k] || k
                  }`)
                  .join(' · ')}
                {profile.clutter_summary.vegetation_depth_m > 0 &&
                  ` · veg ${(profile.clutter_summary.vegetation_depth_m / 1000).toFixed(1)} km`}
                {' · amb. '}
                {({ urban: 'urbano', suburban: 'suburbano', rural: 'rural' } as Record<string, string>)[
                  profile.clutter_summary.environment
                ] || profile.clutter_summary.environment}
              </span>
            )}
            <span className="ml-auto flex items-center gap-2">
              {(['pdf', 'kmz', 'geojson'] as const).map((f) => (
                <button
                  key={f}
                  className="rounded px-2 py-0.5 text-[10px] font-medium uppercase"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  onClick={() => exportStudy(f)}
                >
                  {f}
                </button>
              ))}
              <button onClick={() => setShowResults(false)}>
                <X size={14} style={{ color: 'var(--text-muted)' }} />
              </button>
            </span>
          </div>
          <div style={{ height: 190 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis dataKey="km" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} unit=" km" />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} unit=" m" domain={['auto', 'auto']} width={52} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', fontSize: 11 }}
                  formatter={(v: any, name: any) => [`${v} m`, name]}
                  labelFormatter={(v: any) => `${v} km`}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="terreno" name={`Terreno (${surface.toUpperCase()}, curvatura k=4/3)`} stroke="#0f766e" fill="#0f766e" fillOpacity={0.35} isAnimationActive={false} />
                {la && <Line type="monotone" dataKey="los" name="Visada TX→RX" stroke="#7c3aed" dot={false} strokeWidth={2} isAnimationActive={false} />}
                {la && <Line type="monotone" dataKey="fresnelInf" name="1ª zona de Fresnel (limite inferior)" stroke="#eab308" strokeDasharray="5 3" dot={false} isAnimationActive={false} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
