'use client';

import { useState } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type {
  CoverageRequest,
  CoverageResult,
  OptimizeRequest,
  LinkBudgetRequest,
} from '@/lib/types';
import {
  Antenna,
  Radio,
  Mountain,
  Zap,
  MapPin,
  Signal,
  Ruler,
  Maximize2,
  Send,
} from 'lucide-react';
import { clsx } from 'clsx';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type TabKey = 'coverage' | 'optimize' | 'linkbudget' | 'terrain';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'coverage', label: 'Cobertura RF', icon: <Signal size={16} /> },
  { key: 'optimize', label: 'Otimizacao de Torres', icon: <Antenna size={16} /> },
  { key: 'linkbudget', label: 'Link Budget', icon: <Radio size={16} /> },
  { key: 'terrain', label: 'Perfil de Terreno', icon: <Mountain size={16} /> },
];

const FREQ_OPTIONS = ['700', '850', '1800', '2100', '2600', '3500'];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function DesignPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('coverage');

  // ── Tab 1: Cobertura RF ─────────────────────────────────────────────────
  const [covLat, setCovLat] = useState('-15.7939');
  const [covLon, setCovLon] = useState('-47.8828');
  const [covHeight, setCovHeight] = useState('30');
  const [covFreq, setCovFreq] = useState('700');
  const [covPower, setCovPower] = useState('43');
  const [covGain, setCovGain] = useState('15');
  const [covRadius, setCovRadius] = useState('5000');
  const [covResolution, setCovResolution] = useState('50');
  const [covVegetation, setCovVegetation] = useState(true);

  const {
    data: coverageData,
    loading: coverageLoading,
    error: coverageError,
    execute: executeCoverage,
  } = useLazyApi<CoverageResult, CoverageRequest>((params) =>
    api.design.coverage(params)
  );

  const handleCoverage = () => {
    const params: CoverageRequest = {
      tower_lat: parseFloat(covLat),
      tower_lon: parseFloat(covLon),
      tower_height_m: parseFloat(covHeight),
      frequency_mhz: parseInt(covFreq, 10),
      tx_power_dbm: parseFloat(covPower),
      antenna_gain_dbi: parseFloat(covGain),
      radius_m: parseFloat(covRadius),
      grid_resolution_m: parseFloat(covResolution),
      apply_vegetation: covVegetation,
      country_code: 'BRA',
    };
    executeCoverage(params);
  };

  // ── Tab 2: Otimizacao de Torres ─────────────────────────────────────────
  const [optLat, setOptLat] = useState('-15.7939');
  const [optLon, setOptLon] = useState('-47.8828');
  const [optRadius, setOptRadius] = useState('5000');
  const [optTarget, setOptTarget] = useState('95');
  const [optMinSignal, setOptMinSignal] = useState('-95');
  const [optMaxTowers, setOptMaxTowers] = useState('20');
  const [optFreq, setOptFreq] = useState('700');
  const [optPower, setOptPower] = useState('43');
  const [optGain, setOptGain] = useState('15');
  const [optAntennaHeight, setOptAntennaHeight] = useState('30');

  const {
    data: optimizeData,
    loading: optimizeLoading,
    error: optimizeError,
    execute: executeOptimize,
  } = useLazyApi<any, OptimizeRequest>((params) =>
    api.design.optimize(params)
  );

  const handleOptimize = () => {
    const params: OptimizeRequest = {
      center_lat: parseFloat(optLat),
      center_lon: parseFloat(optLon),
      radius_m: parseFloat(optRadius),
      coverage_target_pct: parseFloat(optTarget),
      min_signal_dbm: parseFloat(optMinSignal),
      max_towers: parseInt(optMaxTowers, 10),
      frequency_mhz: parseInt(optFreq, 10),
      tx_power_dbm: parseFloat(optPower),
      antenna_gain_dbi: parseFloat(optGain),
      antenna_height_m: parseFloat(optAntennaHeight),
    };
    executeOptimize(params);
  };

  // ── Tab 3: Link Budget ──────────────────────────────────────────────────
  const [lbFreq, setLbFreq] = useState('18');
  const [lbDist, setLbDist] = useState('10');
  const [lbPower, setLbPower] = useState('20');
  const [lbTxGain, setLbTxGain] = useState('38');
  const [lbRxGain, setLbRxGain] = useState('38');
  const [lbThreshold, setLbThreshold] = useState('-70');
  const [lbRain, setLbRain] = useState('145');

  const {
    data: linkData,
    loading: linkLoading,
    error: linkError,
    execute: executeLink,
  } = useLazyApi<any, LinkBudgetRequest>((params) =>
    api.design.linkBudget(params)
  );

  const handleLinkBudget = () => {
    const params: LinkBudgetRequest = {
      frequency_ghz: parseFloat(lbFreq),
      distance_km: parseFloat(lbDist),
      tx_power_dbm: parseFloat(lbPower),
      tx_antenna_gain_dbi: parseFloat(lbTxGain),
      rx_antenna_gain_dbi: parseFloat(lbRxGain),
      rx_threshold_dbm: parseFloat(lbThreshold),
      rain_rate_mmh: parseFloat(lbRain),
    };
    executeLink(params);
  };

  // ── Tab 4: Perfil de Terreno ────────────────────────────────────────────
  const [tpStartLat, setTpStartLat] = useState('-15.7939');
  const [tpStartLon, setTpStartLon] = useState('-47.8828');
  const [tpEndLat, setTpEndLat] = useState('-15.8200');
  const [tpEndLon, setTpEndLon] = useState('-47.9100');
  const [tpStep, setTpStep] = useState('30');

  const {
    data: terrainData,
    loading: terrainLoading,
    error: terrainError,
    execute: executeTerrain,
  } = useLazyApi<any, { startLat: number; startLon: number; endLat: number; endLon: number; stepM: number }>(
    (p) => api.design.terrainProfile(p.startLat, p.startLon, p.endLat, p.endLon, p.stepM)
  );

  const handleTerrain = () => {
    executeTerrain({
      startLat: parseFloat(tpStartLat),
      startLon: parseFloat(tpStartLon),
      endLat: parseFloat(tpEndLat),
      endLon: parseFloat(tpEndLon),
      stepM: parseFloat(tpStep),
    });
  };

  // ── Helpers ─────────────────────────────────────────────────────────────

  const fmtNum = (v: number, decimals = 1) =>
    v.toLocaleString('pt-BR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });

  // Build terrain chart data
  const terrainChartData: { name: string; elevacao: number }[] = [];
  if (terrainData?.profile) {
    const profile = terrainData.profile as { distance_m: number; elevation_m: number }[];
    for (const pt of profile) {
      terrainChartData.push({
        name: `${(pt.distance_m / 1000).toFixed(1)} km`,
        elevacao: pt.elevation_m,
      });
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 p-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100">
          Projeto de Cobertura RF
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Simulacao de cobertura, otimizacao de torres, link budget e perfil de terreno
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-800/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-blue-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ================================================================== */}
      {/* TAB 1 — Cobertura RF                                                */}
      {/* ================================================================== */}
      {activeTab === 'coverage' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Form panel */}
          <div className="enlace-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Signal size={16} className="text-blue-400" />
              Parametros de Cobertura
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Latitude da Torre
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={covLat}
                    onChange={(e) => setCovLat(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Longitude da Torre
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={covLon}
                    onChange={(e) => setCovLon(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Altura da Torre (m)
                </label>
                <input
                  type="number"
                  value={covHeight}
                  onChange={(e) => setCovHeight(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Frequencia (MHz)
                </label>
                <select
                  value={covFreq}
                  onChange={(e) => setCovFreq(e.target.value)}
                  className="enlace-input w-full"
                >
                  {FREQ_OPTIONS.map((f) => (
                    <option key={f} value={f}>
                      {f} MHz
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Potencia TX (dBm)
                  </label>
                  <input
                    type="number"
                    value={covPower}
                    onChange={(e) => setCovPower(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Ganho da Antena (dBi)
                  </label>
                  <input
                    type="number"
                    value={covGain}
                    onChange={(e) => setCovGain(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Raio (m)
                  </label>
                  <input
                    type="number"
                    value={covRadius}
                    onChange={(e) => setCovRadius(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Resolucao (m)
                  </label>
                  <input
                    type="number"
                    value={covResolution}
                    onChange={(e) => setCovResolution(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    checked={covVegetation}
                    onChange={(e) => setCovVegetation(e.target.checked)}
                    className="peer sr-only"
                  />
                  <div className="h-5 w-9 rounded-full bg-slate-600 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-slate-300 after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full" />
                </label>
                <span className="text-sm text-slate-400">
                  Correcao de Vegetacao
                </span>
              </div>

              <button
                onClick={handleCoverage}
                disabled={coverageLoading}
                className={clsx(
                  'enlace-btn-primary flex w-full items-center justify-center gap-2',
                  coverageLoading && 'cursor-wait opacity-70'
                )}
              >
                {coverageLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
                ) : (
                  <Send size={16} />
                )}
                {coverageLoading ? 'Calculando...' : 'Calcular Cobertura'}
              </button>

              {coverageError && (
                <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                  <span className="font-medium">Erro:</span> {coverageError}
                </div>
              )}
            </div>
          </div>

          {/* Results panel */}
          <div className="space-y-4 lg:col-span-2">
            {!coverageData && !coverageLoading && (
              <div className="enlace-card flex items-center justify-center py-16 text-sm text-slate-500">
                Defina os parametros e clique em &quot;Calcular Cobertura&quot; para visualizar os resultados.
              </div>
            )}

            {coverageLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <StatsCard key={i} title="" value="" loading />
                ))}
              </div>
            )}

            {coverageData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatsCard
                    title="Cobertura"
                    value={`${fmtNum(coverageData.coverage_pct)}%`}
                    icon={<Signal size={18} className="text-blue-400" />}
                    subtitle="Percentual coberto"
                  />
                  <StatsCard
                    title="Area de Cobertura"
                    value={`${fmtNum(coverageData.coverage_area_km2, 2)} km2`}
                    icon={<Maximize2 size={18} className="text-green-400" />}
                    subtitle="Area total"
                  />
                  <StatsCard
                    title="Sinal Medio"
                    value={`${fmtNum(coverageData.avg_signal_dbm)} dBm`}
                    icon={<Radio size={18} className="text-cyan-400" />}
                    subtitle="Media na area"
                  />
                  <StatsCard
                    title="Sinal Minimo"
                    value={`${fmtNum(coverageData.min_signal_dbm)} dBm`}
                    icon={<Zap size={18} className="text-yellow-400" />}
                    subtitle="Pior caso"
                  />
                </div>

                {/* Grid points summary */}
                <div className="enlace-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                    <MapPin size={16} className="text-blue-400" />
                    Grade de Cobertura
                  </h3>
                  <div className="space-y-3">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div className="rounded-lg bg-slate-900 p-3">
                        <p className="text-xs font-semibold uppercase text-slate-500">
                          Pontos da Grade
                        </p>
                        <p className="mt-1 text-lg font-bold text-slate-200">
                          {coverageData.grid.length.toLocaleString('pt-BR')}
                        </p>
                      </div>
                      <div className="rounded-lg bg-slate-900 p-3">
                        <p className="text-xs font-semibold uppercase text-slate-500">
                          Sinal Maximo
                        </p>
                        <p className="mt-1 text-lg font-bold text-green-400">
                          {fmtNum(coverageData.max_signal_dbm)} dBm
                        </p>
                      </div>
                      <div className="rounded-lg bg-slate-900 p-3">
                        <p className="text-xs font-semibold uppercase text-slate-500">
                          Resolucao da Grade
                        </p>
                        <p className="mt-1 text-lg font-bold text-slate-200">
                          {covResolution} m
                        </p>
                      </div>
                    </div>

                    {/* Signal distribution summary */}
                    {coverageData.grid.length > 0 && (
                      <div className="rounded-lg bg-slate-900 p-4">
                        <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                          Distribuicao do Sinal
                        </p>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                          {[
                            { label: 'Excelente (> -65 dBm)', count: coverageData.grid.filter(p => p.signal_dbm > -65).length, color: 'text-green-400' },
                            { label: 'Bom (-65 a -75 dBm)', count: coverageData.grid.filter(p => p.signal_dbm <= -65 && p.signal_dbm > -75).length, color: 'text-blue-400' },
                            { label: 'Regular (-75 a -85 dBm)', count: coverageData.grid.filter(p => p.signal_dbm <= -75 && p.signal_dbm > -85).length, color: 'text-yellow-400' },
                            { label: 'Fraco (< -85 dBm)', count: coverageData.grid.filter(p => p.signal_dbm <= -85).length, color: 'text-red-400' },
                          ].map((band) => (
                            <div key={band.label} className="text-center">
                              <p className={clsx('text-lg font-bold', band.color)}>
                                {band.count.toLocaleString('pt-BR')}
                              </p>
                              <p className="text-xs text-slate-500">{band.label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ================================================================== */}
      {/* TAB 2 — Otimizacao de Torres                                        */}
      {/* ================================================================== */}
      {activeTab === 'optimize' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Form panel */}
          <div className="enlace-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Antenna size={16} className="text-blue-400" />
              Parametros de Otimizacao
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Latitude Central
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={optLat}
                    onChange={(e) => setOptLat(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Longitude Central
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={optLon}
                    onChange={(e) => setOptLon(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Raio (m)
                  </label>
                  <input
                    type="number"
                    value={optRadius}
                    onChange={(e) => setOptRadius(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Cobertura Alvo (%)
                  </label>
                  <input
                    type="number"
                    value={optTarget}
                    onChange={(e) => setOptTarget(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Sinal Minimo (dBm)
                  </label>
                  <input
                    type="number"
                    value={optMinSignal}
                    onChange={(e) => setOptMinSignal(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Max. Torres
                  </label>
                  <input
                    type="number"
                    value={optMaxTowers}
                    onChange={(e) => setOptMaxTowers(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Frequencia (MHz)
                </label>
                <input
                  type="number"
                  value={optFreq}
                  onChange={(e) => setOptFreq(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Potencia TX (dBm)
                  </label>
                  <input
                    type="number"
                    value={optPower}
                    onChange={(e) => setOptPower(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Ganho da Antena (dBi)
                  </label>
                  <input
                    type="number"
                    value={optGain}
                    onChange={(e) => setOptGain(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Altura da Antena (m)
                </label>
                <input
                  type="number"
                  value={optAntennaHeight}
                  onChange={(e) => setOptAntennaHeight(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <button
                onClick={handleOptimize}
                disabled={optimizeLoading}
                className={clsx(
                  'enlace-btn-primary flex w-full items-center justify-center gap-2',
                  optimizeLoading && 'cursor-wait opacity-70'
                )}
              >
                {optimizeLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
                ) : (
                  <Antenna size={16} />
                )}
                {optimizeLoading ? 'Otimizando...' : 'Otimizar Posicionamento'}
              </button>

              {optimizeError && (
                <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                  <span className="font-medium">Erro:</span> {optimizeError}
                </div>
              )}
            </div>
          </div>

          {/* Results panel */}
          <div className="space-y-4 lg:col-span-2">
            {!optimizeData && !optimizeLoading && (
              <div className="enlace-card flex items-center justify-center py-16 text-sm text-slate-500">
                Defina os parametros e clique em &quot;Otimizar Posicionamento&quot; para visualizar os resultados.
              </div>
            )}

            {optimizeLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <StatsCard key={i} title="" value="" loading />
                ))}
              </div>
            )}

            {optimizeData && (
              <>
                {/* Summary stats */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatsCard
                    title="Torres Necessarias"
                    value={optimizeData.tower_count ?? optimizeData.towers?.length ?? '---'}
                    icon={<Antenna size={18} className="text-blue-400" />}
                    subtitle="Posicoes otimizadas"
                  />
                  <StatsCard
                    title="Cobertura Alcancada"
                    value={
                      optimizeData.coverage_achieved_pct != null
                        ? `${fmtNum(optimizeData.coverage_achieved_pct)}%`
                        : '---'
                    }
                    icon={<Signal size={18} className="text-green-400" />}
                    subtitle={`Meta: ${optTarget}%`}
                  />
                  <StatsCard
                    title="Area Coberta"
                    value={
                      optimizeData.coverage_area_km2 != null
                        ? `${fmtNum(optimizeData.coverage_area_km2, 2)} km2`
                        : '---'
                    }
                    icon={<Maximize2 size={18} className="text-cyan-400" />}
                    subtitle="Estimativa"
                  />
                  <StatsCard
                    title="CAPEX Estimado"
                    value={
                      optimizeData.estimated_capex_brl != null
                        ? `R$ ${(optimizeData.estimated_capex_brl / 1000).toFixed(0)}k`
                        : '---'
                    }
                    icon={<Zap size={18} className="text-yellow-400" />}
                    subtitle="Investimento total"
                  />
                </div>

                {/* Tower positions */}
                {optimizeData.towers && optimizeData.towers.length > 0 && (
                  <div className="enlace-card">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                      <MapPin size={16} className="text-blue-400" />
                      Posicoes das Torres
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-700 text-left text-xs uppercase text-slate-400">
                            <th className="pb-2 pr-4 font-medium">#</th>
                            <th className="pb-2 pr-4 font-medium">Latitude</th>
                            <th className="pb-2 pr-4 font-medium">Longitude</th>
                            <th className="pb-2 pr-4 font-medium">Altura (m)</th>
                            <th className="pb-2 font-medium">Cobertura (%)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50">
                          {optimizeData.towers.map((tower: any, idx: number) => (
                            <tr key={idx} className="text-slate-300">
                              <td className="py-2 pr-4 font-medium text-slate-200">
                                {idx + 1}
                              </td>
                              <td className="py-2 pr-4">
                                {tower.lat?.toFixed(4) ?? tower.latitude?.toFixed(4) ?? '---'}
                              </td>
                              <td className="py-2 pr-4">
                                {tower.lon?.toFixed(4) ?? tower.longitude?.toFixed(4) ?? '---'}
                              </td>
                              <td className="py-2 pr-4">
                                {tower.height_m ?? tower.antenna_height_m ?? optAntennaHeight}
                              </td>
                              <td className="py-2">
                                {tower.coverage_pct != null ? (
                                  <span className="font-semibold text-green-400">
                                    {fmtNum(tower.coverage_pct)}%
                                  </span>
                                ) : (
                                  '---'
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Notes / recommendations */}
                {optimizeData.notes && optimizeData.notes.length > 0 && (
                  <div className="enlace-card">
                    <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                      Observacoes
                    </h3>
                    <ul className="space-y-1">
                      {optimizeData.notes.map((note: string, idx: number) => (
                        <li
                          key={idx}
                          className="flex items-start gap-2 text-sm text-slate-400"
                        >
                          <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-400" />
                          {note}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ================================================================== */}
      {/* TAB 3 — Link Budget                                                 */}
      {/* ================================================================== */}
      {activeTab === 'linkbudget' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Form panel */}
          <div className="enlace-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Radio size={16} className="text-blue-400" />
              Parametros do Link Budget
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Frequencia (GHz)
                  </label>
                  <input
                    type="number"
                    value={lbFreq}
                    onChange={(e) => setLbFreq(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Distancia (km)
                  </label>
                  <input
                    type="number"
                    value={lbDist}
                    onChange={(e) => setLbDist(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Potencia TX (dBm)
                </label>
                <input
                  type="number"
                  value={lbPower}
                  onChange={(e) => setLbPower(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Ganho Antena TX (dBi)
                  </label>
                  <input
                    type="number"
                    value={lbTxGain}
                    onChange={(e) => setLbTxGain(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Ganho Antena RX (dBi)
                  </label>
                  <input
                    type="number"
                    value={lbRxGain}
                    onChange={(e) => setLbRxGain(e.target.value)}
                    className="enlace-input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Limiar RX (dBm)
                </label>
                <input
                  type="number"
                  value={lbThreshold}
                  onChange={(e) => setLbThreshold(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Taxa de Chuva (mm/h)
                </label>
                <input
                  type="number"
                  value={lbRain}
                  onChange={(e) => setLbRain(e.target.value)}
                  className="enlace-input w-full"
                />
                <p className="mt-1 text-xs text-slate-500">
                  Padrao tropical Brasil
                </p>
              </div>

              <button
                onClick={handleLinkBudget}
                disabled={linkLoading}
                className={clsx(
                  'enlace-btn-primary flex w-full items-center justify-center gap-2',
                  linkLoading && 'cursor-wait opacity-70'
                )}
              >
                {linkLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
                ) : (
                  <Ruler size={16} />
                )}
                {linkLoading ? 'Calculando...' : 'Calcular Link Budget'}
              </button>

              {linkError && (
                <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                  <span className="font-medium">Erro:</span> {linkError}
                </div>
              )}
            </div>
          </div>

          {/* Results panel */}
          <div className="space-y-4 lg:col-span-2">
            {!linkData && !linkLoading && (
              <div className="enlace-card flex items-center justify-center py-16 text-sm text-slate-500">
                Defina os parametros e clique em &quot;Calcular Link Budget&quot; para visualizar os resultados.
              </div>
            )}

            {linkLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <StatsCard key={i} title="" value="" loading />
                ))}
              </div>
            )}

            {linkData && (
              <>
                {/* Key metrics */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <StatsCard
                    title="EIRP"
                    value={
                      linkData.eirp_dbm != null
                        ? `${fmtNum(linkData.eirp_dbm)} dBm`
                        : '---'
                    }
                    icon={<Zap size={18} className="text-blue-400" />}
                    subtitle="Potencia efetiva irradiada"
                  />
                  <StatsCard
                    title="Perda no Espaco Livre"
                    value={
                      linkData.free_space_loss_db != null
                        ? `${fmtNum(linkData.free_space_loss_db)} dB`
                        : '---'
                    }
                    icon={<Ruler size={18} className="text-cyan-400" />}
                    subtitle="FSL"
                  />
                  <StatsCard
                    title="Atenuacao por Chuva"
                    value={
                      linkData.rain_attenuation_db != null
                        ? `${fmtNum(linkData.rain_attenuation_db)} dB`
                        : '---'
                    }
                    icon={<Mountain size={18} className="text-yellow-400" />}
                    subtitle={`${lbRain} mm/h`}
                  />
                  <StatsCard
                    title="Sinal Recebido"
                    value={
                      linkData.received_power_dbm != null
                        ? `${fmtNum(linkData.received_power_dbm)} dBm`
                        : '---'
                    }
                    icon={<Signal size={18} className="text-green-400" />}
                    subtitle="Nivel no receptor"
                  />
                  <StatsCard
                    title="Margem de Desvanecimento"
                    value={
                      linkData.fade_margin_db != null
                        ? `${fmtNum(linkData.fade_margin_db)} dB`
                        : '---'
                    }
                    icon={<Radio size={18} className={clsx(
                      linkData.fade_margin_db != null && linkData.fade_margin_db > 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    )} />}
                    subtitle={
                      linkData.fade_margin_db != null
                        ? linkData.fade_margin_db > 0
                          ? 'Link viavel'
                          : 'Link inviavel'
                        : ''
                    }
                  />
                  <StatsCard
                    title="Disponibilidade"
                    value={
                      linkData.availability_pct != null
                        ? `${fmtNum(linkData.availability_pct, 4)}%`
                        : '---'
                    }
                    icon={<Maximize2 size={18} className="text-purple-400" />}
                    subtitle="Estimativa anual"
                  />
                </div>

                {/* Detailed breakdown */}
                <div className="enlace-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                    <Radio size={16} className="text-blue-400" />
                    Detalhamento do Link
                  </h3>
                  <div className="space-y-2">
                    {[
                      { label: 'Frequencia', value: `${lbFreq} GHz` },
                      { label: 'Distancia', value: `${lbDist} km` },
                      { label: 'Potencia TX', value: `${lbPower} dBm` },
                      { label: 'Ganho Antena TX', value: `${lbTxGain} dBi` },
                      { label: 'Ganho Antena RX', value: `${lbRxGain} dBi` },
                      { label: 'EIRP', value: linkData.eirp_dbm != null ? `${fmtNum(linkData.eirp_dbm)} dBm` : '---' },
                      { label: 'Perda no Espaco Livre (FSL)', value: linkData.free_space_loss_db != null ? `${fmtNum(linkData.free_space_loss_db)} dB` : '---' },
                      { label: 'Atenuacao por Chuva', value: linkData.rain_attenuation_db != null ? `${fmtNum(linkData.rain_attenuation_db)} dB` : '---' },
                      { label: 'Perdas Totais', value: linkData.total_loss_db != null ? `${fmtNum(linkData.total_loss_db)} dB` : '---' },
                      { label: 'Sinal Recebido', value: linkData.received_power_dbm != null ? `${fmtNum(linkData.received_power_dbm)} dBm` : '---' },
                      { label: 'Limiar RX', value: `${lbThreshold} dBm` },
                      { label: 'Margem de Desvanecimento', value: linkData.fade_margin_db != null ? `${fmtNum(linkData.fade_margin_db)} dB` : '---', highlight: true },
                      { label: 'Disponibilidade', value: linkData.availability_pct != null ? `${fmtNum(linkData.availability_pct, 4)}%` : '---', highlight: true },
                    ].map((row) => (
                      <div
                        key={row.label}
                        className={clsx(
                          'flex justify-between text-sm',
                          row.highlight
                            ? 'border-t border-slate-700 pt-2'
                            : ''
                        )}
                      >
                        <span className={clsx(
                          row.highlight ? 'font-medium text-slate-300' : 'text-slate-400'
                        )}>
                          {row.label}
                        </span>
                        <span className={clsx(
                          'font-semibold',
                          row.highlight ? 'text-blue-400' : 'text-slate-200'
                        )}>
                          {row.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Link viability badge */}
                <div className="enlace-card flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-300">
                    Status do Enlace
                  </span>
                  {linkData.fade_margin_db != null ? (
                    linkData.fade_margin_db > 0 ? (
                      <span className="enlace-badge-green flex items-center gap-1">
                        <Signal size={14} />
                        Enlace Viavel - Margem de {fmtNum(linkData.fade_margin_db)} dB
                      </span>
                    ) : (
                      <span className="enlace-badge-red flex items-center gap-1">
                        <Zap size={14} />
                        Enlace Inviavel - Margem insuficiente
                      </span>
                    )
                  ) : (
                    <span className="text-sm text-slate-500">---</span>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ================================================================== */}
      {/* TAB 4 — Perfil de Terreno                                           */}
      {/* ================================================================== */}
      {activeTab === 'terrain' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Form panel */}
          <div className="enlace-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <Mountain size={16} className="text-blue-400" />
              Parametros do Perfil
            </h2>

            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  Ponto de Inicio
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">
                      Latitude Inicio
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={tpStartLat}
                      onChange={(e) => setTpStartLat(e.target.value)}
                      className="enlace-input w-full"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">
                      Longitude Inicio
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={tpStartLon}
                      onChange={(e) => setTpStartLon(e.target.value)}
                      className="enlace-input w-full"
                    />
                  </div>
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  Ponto Final
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">
                      Latitude Fim
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={tpEndLat}
                      onChange={(e) => setTpEndLat(e.target.value)}
                      className="enlace-input w-full"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">
                      Longitude Fim
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={tpEndLon}
                      onChange={(e) => setTpEndLon(e.target.value)}
                      className="enlace-input w-full"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Passo (m)
                </label>
                <input
                  type="number"
                  value={tpStep}
                  onChange={(e) => setTpStep(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>

              <button
                onClick={handleTerrain}
                disabled={terrainLoading}
                className={clsx(
                  'enlace-btn-primary flex w-full items-center justify-center gap-2',
                  terrainLoading && 'cursor-wait opacity-70'
                )}
              >
                {terrainLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
                ) : (
                  <Mountain size={16} />
                )}
                {terrainLoading ? 'Calculando...' : 'Extrair Perfil'}
              </button>

              {terrainError && (
                <div className="rounded-lg bg-red-900/20 p-3 text-sm text-red-400">
                  <span className="font-medium">Erro:</span> {terrainError}
                </div>
              )}
            </div>
          </div>

          {/* Results panel */}
          <div className="space-y-4 lg:col-span-2">
            {!terrainData && !terrainLoading && (
              <div className="enlace-card flex items-center justify-center py-16 text-sm text-slate-500">
                Defina os pontos de inicio e fim e clique em &quot;Extrair Perfil&quot; para visualizar o terreno.
              </div>
            )}

            {terrainLoading && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  {[1, 2, 3].map((i) => (
                    <StatsCard key={i} title="" value="" loading />
                  ))}
                </div>
                <SimpleChart data={[]} type="line" title="Perfil de Elevacao" loading height={300} />
              </div>
            )}

            {terrainData && (
              <>
                {/* Terrain stats */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatsCard
                    title="Distancia Total"
                    value={
                      terrainData.total_distance_km != null
                        ? `${fmtNum(terrainData.total_distance_km, 2)} km`
                        : terrainData.profile?.length
                          ? `${fmtNum((terrainData.profile[terrainData.profile.length - 1].distance_m || 0) / 1000, 2)} km`
                          : '---'
                    }
                    icon={<Ruler size={18} className="text-blue-400" />}
                    subtitle="Entre os pontos"
                  />
                  <StatsCard
                    title="Elevacao Maxima"
                    value={
                      terrainData.max_elevation_m != null
                        ? `${fmtNum(terrainData.max_elevation_m, 0)} m`
                        : terrainData.profile?.length
                          ? `${fmtNum(Math.max(...terrainData.profile.map((p: any) => p.elevation_m)), 0)} m`
                          : '---'
                    }
                    icon={<Mountain size={18} className="text-green-400" />}
                    subtitle="Ponto mais alto"
                  />
                  <StatsCard
                    title="Elevacao Minima"
                    value={
                      terrainData.min_elevation_m != null
                        ? `${fmtNum(terrainData.min_elevation_m, 0)} m`
                        : terrainData.profile?.length
                          ? `${fmtNum(Math.min(...terrainData.profile.map((p: any) => p.elevation_m)), 0)} m`
                          : '---'
                    }
                    icon={<MapPin size={18} className="text-yellow-400" />}
                    subtitle="Ponto mais baixo"
                  />
                  <StatsCard
                    title="Pontos Amostrados"
                    value={terrainData.profile?.length?.toLocaleString('pt-BR') ?? '---'}
                    icon={<Maximize2 size={18} className="text-cyan-400" />}
                    subtitle={`Passo: ${tpStep} m`}
                  />
                </div>

                {/* Elevation profile chart */}
                {terrainChartData.length > 0 && (
                  <SimpleChart
                    data={terrainChartData}
                    type="line"
                    xKey="name"
                    yKey="elevacao"
                    title="Perfil de Elevacao (m)"
                    height={350}
                  />
                )}

                {/* Elevation difference */}
                {terrainData.profile && terrainData.profile.length > 1 && (
                  <div className="enlace-card">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                      <Mountain size={16} className="text-blue-400" />
                      Resumo do Terreno
                    </h3>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      {(() => {
                        const elevations = terrainData.profile.map((p: any) => p.elevation_m);
                        const maxElev = Math.max(...elevations);
                        const minElev = Math.min(...elevations);
                        const avgElev = elevations.reduce((a: number, b: number) => a + b, 0) / elevations.length;
                        const startElev = elevations[0];
                        const endElev = elevations[elevations.length - 1];
                        return (
                          <>
                            <div className="rounded-lg bg-slate-900 p-3">
                              <p className="text-xs font-semibold uppercase text-slate-500">
                                Desnivel Total
                              </p>
                              <p className="mt-1 text-lg font-bold text-slate-200">
                                {fmtNum(maxElev - minElev, 0)} m
                              </p>
                            </div>
                            <div className="rounded-lg bg-slate-900 p-3">
                              <p className="text-xs font-semibold uppercase text-slate-500">
                                Elevacao Media
                              </p>
                              <p className="mt-1 text-lg font-bold text-slate-200">
                                {fmtNum(avgElev, 0)} m
                              </p>
                            </div>
                            <div className="rounded-lg bg-slate-900 p-3">
                              <p className="text-xs font-semibold uppercase text-slate-500">
                                Diferenca Inicio/Fim
                              </p>
                              <p className={clsx(
                                'mt-1 text-lg font-bold',
                                endElev >= startElev ? 'text-green-400' : 'text-red-400'
                              )}>
                                {endElev >= startElev ? '+' : ''}{fmtNum(endElev - startElev, 0)} m
                              </p>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
