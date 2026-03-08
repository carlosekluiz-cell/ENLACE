'use client';

import { useState } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { FundingProgram, RuralDesign } from '@/lib/types';
import {
  Mountain,
  Sun,
  Wifi,
  DollarSign,
  MapPin,
  Users,
  Zap,
  Send,
} from 'lucide-react';
import { clsx } from 'clsx';

interface DesignFormParams {
  latitude: number;
  longitude: number;
  population: number;
  area_km2: number;
  has_grid_power: boolean;
  community_name?: string;
}

export default function RuralPage() {
  // Form state
  const [communityName, setCommunityName] = useState('');
  const [latitude, setLatitude] = useState('-12.9714');
  const [longitude, setLongitude] = useState('-38.5124');
  const [population, setPopulation] = useState('2500');
  const [area, setArea] = useState('150');
  const [hasPower, setHasPower] = useState(true);

  // Real API: fetch funding programs on mount
  const {
    data: programs,
    loading: programsLoading,
    error: programsError,
  } = useApi(() => api.rural.programs(), []);

  // Real API: lazy design call
  const {
    data: designResult,
    loading: designLoading,
    error: designError,
    execute: executeDesign,
  } = useLazyApi<RuralDesign, DesignFormParams>((params) =>
    api.rural.design(params)
  );

  // Derive stats from programs data
  const totalFunding = programs
    ? programs.reduce((sum, p) => sum + p.max_amount, 0)
    : null;
  const activeCount = programs
    ? programs.filter((p) => p.status === 'open').length
    : null;

  const handleDesign = async () => {
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    const pop = parseInt(population, 10);
    const areaKm2 = parseFloat(area);

    if (isNaN(lat) || isNaN(lon) || isNaN(pop) || isNaN(areaKm2)) {
      return;
    }

    await executeDesign({
      latitude: lat,
      longitude: lon,
      population: pop,
      area_km2: areaKm2,
      has_grid_power: hasPower,
      community_name: communityName || undefined,
    });
  };

  // Build cost breakdown chart data from real result
  const costBreakdown: { name: string; value: number }[] = designResult
    ? [
        { name: 'Backhaul', value: designResult.backhaul.cost_brl },
        { name: 'Ultima Milha', value: designResult.last_mile.cost_brl },
        { name: 'Energia', value: designResult.power.cost_brl },
      ]
    : [];

  const statusLabel: Record<string, string> = {
    open: 'aberto',
    upcoming: 'em breve',
    closed: 'encerrado',
  };

  return (
    <div className="space-y-6 p-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatsCard
          title="Comunidades Não Atendidas"
          value={programs ? `${programs.length}` : '---'}
          icon={<MapPin size={18} />}
          subtitle="Programas cadastrados"
          loading={programsLoading}
        />
        <StatsCard
          title="População Rural"
          value={
            designResult
              ? designResult.coverage_pct.toFixed(1) + '% cobertura'
              : '---'
          }
          icon={<Users size={18} />}
          subtitle={designResult ? 'Do projeto gerado' : 'Gere um projeto'}
          loading={programsLoading}
        />
        <StatsCard
          title="Financiamento Disponivel"
          value={
            totalFunding !== null
              ? `R$ ${(totalFunding / 1e6).toFixed(1)}M`
              : '---'
          }
          icon={<DollarSign size={18} />}
          subtitle={
            activeCount !== null
              ? `${activeCount} programas ativos`
              : 'Programas ativos'
          }
          loading={programsLoading}
        />
        <StatsCard
          title="Custo Médio/Domicílio"
          value={
            designResult
              ? `R$ ${Math.round(designResult.total_cost_brl / Math.max(parseInt(population) || 1, 1)).toLocaleString('pt-BR')}`
              : '---'
          }
          icon={<Zap size={18} />}
          subtitle={designResult ? 'Calculado do projeto' : 'Fonte: Anatel'}
          loading={programsLoading}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Design input form */}
        <div className="enlace-card">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Mountain size={16} className="text-blue-400" />
            Dados da Comunidade
          </h2>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Nome da Comunidade
              </label>
              <input
                type="text"
                value={communityName}
                onChange={(e) => setCommunityName(e.target.value)}
                placeholder="Ex.: Vila Nova do Norte"
                className="enlace-input w-full"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Latitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Longitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Populacao
                </label>
                <input
                  type="number"
                  value={population}
                  onChange={(e) => setPopulation(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Area (km2)
                </label>
                <input
                  type="number"
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  className="enlace-input w-full"
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  checked={hasPower}
                  onChange={(e) => setHasPower(e.target.checked)}
                  className="peer sr-only"
                />
                <div className="h-5 w-9 rounded-full bg-slate-600 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-slate-300 after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full" />
              </label>
              <span className="text-sm text-slate-400">
                Rede Eletrica Disponivel
              </span>
            </div>

            <button
              onClick={handleDesign}
              disabled={designLoading}
              className={clsx(
                'enlace-btn-primary flex w-full items-center justify-center gap-2',
                designLoading && 'cursor-wait opacity-70'
              )}
            >
              {designLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
              ) : (
                <Send size={16} />
              )}
              {designLoading ? 'Gerando...' : 'Gerar Projeto'}
            </button>

            {designError && (
              <div className="rounded-lg bg-red-900/30 p-3 text-sm text-red-400">
                Erro ao gerar projeto: {designError}
              </div>
            )}
          </div>
        </div>

        {/* Results and funding */}
        <div className="space-y-6 lg:col-span-2">
          {/* Design results */}
          {designResult && (
            <div className="enlace-card">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <Wifi size={16} className="text-blue-400" />
                Projeto Recomendado
              </h3>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* Backhaul */}
                <div className="rounded-lg bg-slate-900 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-500">
                    Backhaul
                  </p>
                  <p className="text-sm font-semibold text-blue-400">
                    {designResult.backhaul.technology}
                  </p>
                  <p className="mt-1 text-lg font-bold text-slate-200">
                    R${' '}
                    {designResult.backhaul.cost_brl.toLocaleString('pt-BR')}
                  </p>
                </div>

                {/* Last Mile */}
                <div className="rounded-lg bg-slate-900 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-500">
                    Ultima Milha
                  </p>
                  <p className="text-sm font-semibold text-blue-400">
                    {designResult.last_mile.technology}
                  </p>
                  <p className="mt-1 text-lg font-bold text-slate-200">
                    R${' '}
                    {designResult.last_mile.cost_brl.toLocaleString('pt-BR')}
                  </p>
                </div>

                {/* Power */}
                <div className="rounded-lg bg-slate-900 p-4">
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-500">
                    Energia
                  </p>
                  <p className="text-sm font-semibold text-yellow-400">
                    <Sun size={14} className="mr-1 inline" />
                    {designResult.power.source}
                  </p>
                  <p className="mt-1 text-lg font-bold text-slate-200">
                    R${' '}
                    {designResult.power.cost_brl.toLocaleString('pt-BR')}
                  </p>
                </div>
              </div>

              {/* Summary row */}
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex items-center justify-between rounded-lg bg-slate-900 p-3">
                  <span className="text-sm text-slate-400">Custo Total</span>
                  <span className="text-sm font-bold text-slate-100">
                    R${' '}
                    {designResult.total_cost_brl.toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-slate-900 p-3">
                  <span className="text-sm text-slate-400">OPEX Mensal</span>
                  <span className="text-sm font-bold text-slate-100">
                    R${' '}
                    {designResult.monthly_opex_brl.toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-slate-900 p-3">
                  <span className="text-sm text-slate-400">Cobertura</span>
                  <span className="text-sm font-bold text-green-400">
                    {designResult.coverage_pct.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Notes */}
              {designResult.notes && designResult.notes.length > 0 && (
                <div className="mt-4 rounded-lg bg-slate-900 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                    Observacoes
                  </p>
                  <ul className="space-y-1">
                    {designResult.notes.map((note, idx) => (
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
            </div>
          )}

          {/* Cost breakdown chart */}
          {designResult && (
            <SimpleChart
              data={costBreakdown}
              type="bar"
              xKey="name"
              yKey="value"
              title="Detalhamento de Custos (R$)"
              height={200}
            />
          )}

          {/* Funding programs */}
          <div>
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <DollarSign size={16} className="text-blue-400" />
              Programas de Financiamento Compativeis
            </h2>

            {programsError && (
              <div className="enlace-card mb-3 text-sm text-red-400">
                Erro ao carregar programas: {programsError}
              </div>
            )}

            {programsLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="enlace-card animate-pulse">
                    <div className="h-4 w-48 rounded bg-slate-700" />
                    <div className="mt-2 h-3 w-32 rounded bg-slate-700" />
                    <div className="mt-2 h-3 w-full rounded bg-slate-700" />
                  </div>
                ))}
              </div>
            )}

            {!programsLoading && programs && programs.length === 0 && (
              <div className="enlace-card text-sm text-slate-500">
                Nenhum programa de financiamento encontrado.
              </div>
            )}

            {!programsLoading && programs && programs.length > 0 && (
              <div className="space-y-3">
                {programs.map((program) => (
                  <div key={program.id} className="enlace-card">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-medium text-slate-200">
                            {program.name}
                          </h3>
                          <span
                            className={clsx(
                              program.status === 'open'
                                ? 'enlace-badge-green'
                                : program.status === 'upcoming'
                                  ? 'enlace-badge-yellow'
                                  : 'enlace-badge-red'
                            )}
                          >
                            {statusLabel[program.status] || program.status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {program.agency}
                        </p>
                        <p className="mt-2 text-sm text-slate-400">
                          {program.eligibility_criteria}
                        </p>
                      </div>
                      <div className="ml-4 text-right">
                        <p className="text-sm font-semibold text-slate-200">
                          Ate R${' '}
                          {(program.max_amount / 1e6).toFixed(1)}M
                        </p>
                        {program.deadline && (
                          <p className="text-xs text-slate-500">
                            Prazo: {program.deadline}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
