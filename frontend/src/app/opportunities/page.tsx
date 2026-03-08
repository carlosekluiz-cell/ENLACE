'use client';

import { useState } from 'react';
import DataTable from '@/components/dashboard/DataTable';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { OpportunityScore } from '@/lib/types';
import { TrendingUp, Target, BarChart3, X, AlertTriangle } from 'lucide-react';

const columns = [
  {
    key: 'municipality_name',
    label: 'Município',
    sortable: true,
    render: (value: string, row: OpportunityScore) => (
      <div>
        <span className="font-medium text-slate-100">{value}</span>
        <span className="ml-2 text-xs text-slate-500">{row.state_abbrev}</span>
      </div>
    ),
  },
  {
    key: 'score',
    label: 'Pontuação',
    sortable: true,
    render: (value: number) => (
      <div className="flex items-center gap-2">
        <div className="h-2 w-16 overflow-hidden rounded-full bg-slate-700">
          <div
            className="h-full rounded-full bg-blue-500"
            style={{ width: `${value}%` }}
          />
        </div>
        <span className="text-sm font-semibold text-blue-400">
          {value.toFixed(1)}
        </span>
      </div>
    ),
  },
  {
    key: 'households',
    label: 'Domicílios',
    sortable: true,
    render: (value: number) => value.toLocaleString('pt-BR'),
  },
  {
    key: 'broadband_penetration_pct',
    label: 'Penetração',
    sortable: true,
    render: (value: number) => `${value.toFixed(1)}%`,
  },
  {
    key: 'fiber_share_pct',
    label: '% Fibra',
    sortable: true,
    render: (value: number) => (
      <span
        className={
          value > 40
            ? 'text-green-400'
            : value > 25
              ? 'text-yellow-400'
              : 'text-red-400'
        }
      >
        {value.toFixed(1)}%
      </span>
    ),
  },
  {
    key: 'provider_count',
    label: 'Provedores',
    sortable: true,
  },
];

export default function OpportunitiesPage() {
  const [selectedRow, setSelectedRow] = useState<OpportunityScore | null>(null);

  const {
    data: opportunities,
    loading,
    error,
  } = useApi(() => api.opportunities.top({ limit: '50' }), []);

  const topScore =
    opportunities && opportunities.length > 0
      ? opportunities[0].score.toFixed(1)
      : '—';

  const topMunicipality =
    opportunities && opportunities.length > 0
      ? opportunities[0].municipality_name
      : undefined;

  const avgScore =
    opportunities && opportunities.length > 0
      ? (
          opportunities.reduce((s, o) => s + o.score, 0) /
          opportunities.length
        ).toFixed(1)
      : '—';

  const municipalityCount =
    opportunities && opportunities.length > 0
      ? `${opportunities.length} municípios`
      : undefined;

  const lowPenetrationCount =
    opportunities && opportunities.length > 0
      ? opportunities.filter((o) => o.broadband_penetration_pct < 50).length
      : '—';

  const chartData =
    opportunities && opportunities.length > 0
      ? opportunities.slice(0, 8).map((o) => ({
          name: o.municipality_name.substring(0, 12),
          score: o.score,
          penetration: o.broadband_penetration_pct,
        }))
      : [];

  return (
    <div className="space-y-6 p-6">
      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
          <AlertTriangle size={18} className="shrink-0 text-red-400" />
          <p className="text-sm text-red-300">
            Erro ao carregar dados. Verifique sua conexão e tente novamente.
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Maior Pontuação"
          value={topScore}
          icon={<TrendingUp size={18} />}
          subtitle={topMunicipality}
          loading={loading}
        />
        <StatsCard
          title="Pontuação Média"
          value={avgScore}
          icon={<Target size={18} />}
          subtitle={municipalityCount}
          loading={loading}
        />
        <StatsCard
          title="Baixa Penetração"
          value={lowPenetrationCount}
          icon={<BarChart3 size={18} />}
          subtitle="Abaixo de 50% banda larga"
          loading={loading}
        />
      </div>

      {/* Chart */}
      <SimpleChart
        data={chartData}
        type="bar"
        xKey="name"
        yKeys={['score', 'penetration']}
        title="Top Oportunidades: Pontuação vs Penetração"
        height={250}
        loading={loading}
      />

      {/* Table */}
      <div className="flex gap-6">
        <div className="flex-1">
          <h2 className="mb-4 text-lg font-semibold text-slate-200">
            Scoring de Oportunidades
          </h2>
          <DataTable
            columns={columns}
            data={opportunities || []}
            loading={loading}
            searchable
            searchKeys={['municipality_name', 'state_abbrev']}
            onRowClick={(row) => setSelectedRow(row)}
            emptyMessage="Nenhuma oportunidade encontrada"
          />
        </div>

        {/* Detail panel */}
        {selectedRow && (
          <div className="w-72 shrink-0">
            <div className="enlace-card">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-200">
                  Detalhes
                </h3>
                <button
                  onClick={() => setSelectedRow(null)}
                  className="text-slate-400 hover:text-slate-200"
                  aria-label="Fechar detalhes"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <h4 className="text-lg font-bold text-slate-100">
                    {selectedRow.municipality_name}
                  </h4>
                  <p className="text-sm text-slate-400">
                    {selectedRow.state_abbrev} - {selectedRow.municipality_code}
                  </p>
                </div>

                <div className="space-y-2">
                  <DetailRow
                    label="Pontuação"
                    value={selectedRow.score.toFixed(1)}
                  />
                  <DetailRow
                    label="Domicílios"
                    value={selectedRow.households.toLocaleString('pt-BR')}
                  />
                  <DetailRow
                    label="Penetração"
                    value={`${selectedRow.broadband_penetration_pct.toFixed(1)}%`}
                  />
                  <DetailRow
                    label="% Fibra"
                    value={`${selectedRow.fiber_share_pct.toFixed(1)}%`}
                  />
                  <DetailRow
                    label="Provedores"
                    value={String(selectedRow.provider_count)}
                  />
                </div>

                <button className="enlace-btn-primary mt-4 w-full">
                  Ver Análise Completa
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-900 px-3 py-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-200">{value}</span>
    </div>
  );
}
