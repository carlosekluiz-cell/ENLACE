'use client';

import { useState } from 'react';
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
    ? programs.reduce((sum, p) => sum + (p.max_funding_brl ?? 0), 0)
    : null;
  const programCount = programs ? programs.length : null;

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
        { name: 'Backhaul', value: designResult.backhaul_details?.total_estimated_cost_brl ?? 0 },
        { name: 'Ultima Milha', value: designResult.last_mile_details?.total_estimated_cost_brl ?? 0 },
        { name: 'Energia', value: designResult.power_details?.total_estimated_cost_brl ?? 0 },
      ]
    : [];

  const fundingTypeLabel: Record<string, string> = {
    credit: 'Credito',
    grant: 'Fundo perdido',
    subsidy: 'Subsidio',
    mixed: 'Misto',
  };

  return (
    <div className="space-y-6 p-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Comunidades Nao Atendidas</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {programsLoading ? 'Carregando...' : programs ? `${programs.length}` : '---'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Programas cadastrados</p>
            </div>
            <MapPin size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Populacao Rural</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {programsLoading
                  ? 'Carregando...'
                  : designResult
                    ? `${designResult.coverage_estimate_km2?.toFixed(0) ?? 0} km²`
                    : '---'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {designResult ? 'Do projeto gerado' : 'Gere um projeto'}
              </p>
            </div>
            <Users size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Financiamento Disponivel</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {programsLoading
                  ? 'Carregando...'
                  : totalFunding !== null
                    ? `R$ ${(totalFunding / 1e6).toFixed(1)}M`
                    : '---'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {programCount !== null
                  ? `${programCount} programas`
                  : 'Programas ativos'}
              </p>
            </div>
            <DollarSign size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Custo Medio/Domicilio</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {programsLoading
                  ? 'Carregando...'
                  : designResult
                    ? `R$ ${Math.round((designResult.estimated_capex_brl ?? 0) / Math.max(designResult.max_subscribers || 1, 1)).toLocaleString('pt-BR')}`
                    : '---'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {designResult ? 'Calculado do projeto' : 'Fonte: Anatel'}
              </p>
            </div>
            <Zap size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Design input form */}
        <div className="pulso-card">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            <Mountain size={16} style={{ color: 'var(--accent)' }} />
            Dados da Comunidade
          </h2>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                Nome da Comunidade
              </label>
              <input
                type="text"
                value={communityName}
                onChange={(e) => setCommunityName(e.target.value)}
                placeholder="Ex.: Vila Nova do Norte"
                className="pulso-input w-full"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Latitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  className="pulso-input w-full"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Longitude
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  className="pulso-input w-full"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Populacao
                </label>
                <input
                  type="number"
                  value={population}
                  onChange={(e) => setPopulation(e.target.value)}
                  className="pulso-input w-full"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Area (km2)
                </label>
                <input
                  type="number"
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  className="pulso-input w-full"
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
                <div
                  className="h-5 w-9 rounded-full after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:transition-all peer-checked:after:translate-x-full"
                  style={{
                    backgroundColor: hasPower ? 'var(--accent)' : 'var(--bg-subtle)',
                  }}
                >
                  <div className="absolute left-[2px] top-[2px] h-4 w-4 rounded-full bg-white transition-all" style={{ transform: hasPower ? 'translateX(100%)' : 'translateX(0)' }} />
                </div>
              </label>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Rede Eletrica Disponivel
              </span>
            </div>

            <button
              onClick={handleDesign}
              disabled={designLoading}
              className={clsx(
                'pulso-btn-primary flex w-full items-center justify-center gap-2',
                designLoading && 'cursor-wait opacity-70'
              )}
            >
              <Send size={16} />
              {designLoading ? 'Gerando...' : 'Gerar Projeto'}
            </button>

            {designError && (
              <div
                className="rounded-lg p-3 text-sm"
                style={{
                  backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  color: 'var(--danger)',
                }}
              >
                Erro ao gerar projeto: {designError}
              </div>
            )}
          </div>
        </div>

        {/* Results and funding */}
        <div className="space-y-6 lg:col-span-2">
          {/* Design results */}
          {designResult && (
            <div className="pulso-card">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <Wifi size={16} style={{ color: 'var(--accent)' }} />
                Projeto Recomendado
              </h3>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* Backhaul */}
                <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="mb-1 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
                    Backhaul
                  </p>
                  <p className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>
                    {designResult.backhaul_technology?.replace(/_/g, ' ')}
                  </p>
                  <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                    R${' '}
                    {(designResult.backhaul_details?.total_estimated_cost_brl ?? 0).toLocaleString('pt-BR')}
                  </p>
                  <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {designResult.backhaul_details?.capacity_mbps}Mbps / {designResult.backhaul_details?.latency_ms}ms
                  </p>
                </div>

                {/* Last Mile */}
                <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="mb-1 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
                    Ultima Milha
                  </p>
                  <p className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>
                    {designResult.last_mile_technology?.toUpperCase()}
                  </p>
                  <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                    R${' '}
                    {(designResult.last_mile_details?.total_estimated_cost_brl ?? 0).toLocaleString('pt-BR')}
                  </p>
                  <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {designResult.last_mile_details?.sites} sites / {designResult.last_mile_details?.cpes} CPEs
                  </p>
                </div>

                {/* Power */}
                <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="mb-1 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
                    Energia
                  </p>
                  <p className="text-sm font-semibold" style={{ color: 'var(--warning)' }}>
                    <Sun size={14} className="mr-1 inline" />
                    {designResult.power_solution?.replace(/_/g, ' ')}
                  </p>
                  <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                    R${' '}
                    {(designResult.power_details?.total_estimated_cost_brl ?? 0).toLocaleString('pt-BR')}
                  </p>
                  <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {designResult.power_details?.estimated_power_kw}kW / {designResult.power_details?.battery_kwh}kWh
                  </p>
                </div>
              </div>

              {/* Summary row */}
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-4">
                <div className="flex items-center justify-between rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>CAPEX Total</span>
                  <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                    R${' '}
                    {(designResult.estimated_capex_brl ?? 0).toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>OPEX Mensal</span>
                  <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                    R${' '}
                    {(designResult.estimated_monthly_opex_brl ?? 0).toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Cobertura</span>
                  <span className="text-sm font-bold" style={{ color: 'var(--success)' }}>
                    {(designResult.coverage_estimate_km2 ?? 0).toFixed(0)} km²
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Max Assinantes</span>
                  <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>
                    {(designResult.max_subscribers ?? 0).toLocaleString('pt-BR')}
                  </span>
                </div>
              </div>

              {/* Equipment list */}
              {designResult.equipment_list && designResult.equipment_list.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
                    Equipamentos
                  </p>
                  <div className="space-y-1">
                    {designResult.equipment_list.map((eq, idx) => (
                      <div key={idx} className="flex items-center justify-between rounded px-3 py-2 text-sm" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{eq.item} x{eq.quantity}</span>
                        <span className="font-medium" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                          R$ {(eq.total_cost_brl ?? 0).toLocaleString('pt-BR')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Notes */}
              {designResult.design_notes && designResult.design_notes.length > 0 && (
                <div className="mt-4 rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
                    Observacoes
                  </p>
                  <ul className="space-y-1">
                    {designResult.design_notes.map((note, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-sm"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
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
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <DollarSign size={16} style={{ color: 'var(--accent)' }} />
              Programas de Financiamento Compativeis
            </h2>

            {programsError && (
              <div className="pulso-card mb-3 text-sm" style={{ color: 'var(--danger)' }}>
                Erro ao carregar programas: {programsError}
              </div>
            )}

            {programsLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="pulso-card animate-pulse">
                    <div className="h-4 w-48 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="mt-2 h-3 w-32 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                    <div className="mt-2 h-3 w-full rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                  </div>
                ))}
              </div>
            )}

            {!programsLoading && programs && programs.length === 0 && (
              <div className="pulso-card text-sm" style={{ color: 'var(--text-muted)' }}>
                Nenhum programa de financiamento encontrado.
              </div>
            )}

            {!programsLoading && programs && programs.length > 0 && (
              <div className="space-y-3">
                {programs.map((program) => (
                  <div key={program.id} className="pulso-card">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                            {program.name}
                          </h3>
                          <span className="pulso-badge-green">
                            {fundingTypeLabel[program.funding_type] || program.funding_type}
                          </span>
                        </div>
                        <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                          {program.full_name}
                        </p>
                        <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {program.description}
                        </p>
                        {Array.isArray(program.eligibility_criteria) && program.eligibility_criteria.length > 0 && (
                          <ul className="mt-2 space-y-1">
                            {program.eligibility_criteria.map((c, i) => (
                              <li key={i} className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                                <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
                                {c}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div className="ml-4 text-right">
                        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                          Ate R${' '}
                          {((program.max_funding_brl ?? 0) / 1e6).toFixed(1)}M
                        </p>
                        {program.deadline && (
                          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
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
