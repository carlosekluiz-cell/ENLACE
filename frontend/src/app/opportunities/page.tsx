'use client';

import { useState } from 'react';
import DataTable from '@/components/dashboard/DataTable';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { OpportunityScore } from '@/lib/types';
import { TrendingUp, Target, BarChart3, X } from 'lucide-react';

// Demo data for when API is unavailable
const demoOpportunities: OpportunityScore[] = [
  {
    municipality_code: '3550308',
    municipality_name: 'Sao Paulo',
    state_abbrev: 'SP',
    score: 92.5,
    households: 4200000,
    broadband_penetration_pct: 78.3,
    fiber_share_pct: 45.2,
    provider_count: 85,
  },
  {
    municipality_code: '3304557',
    municipality_name: 'Rio de Janeiro',
    state_abbrev: 'RJ',
    score: 88.1,
    households: 2300000,
    broadband_penetration_pct: 72.1,
    fiber_share_pct: 38.7,
    provider_count: 62,
  },
  {
    municipality_code: '2927408',
    municipality_name: 'Salvador',
    state_abbrev: 'BA',
    score: 85.3,
    households: 980000,
    broadband_penetration_pct: 58.4,
    fiber_share_pct: 32.1,
    provider_count: 28,
  },
  {
    municipality_code: '4106902',
    municipality_name: 'Curitiba',
    state_abbrev: 'PR',
    score: 83.7,
    households: 650000,
    broadband_penetration_pct: 74.2,
    fiber_share_pct: 52.8,
    provider_count: 45,
  },
  {
    municipality_code: '2304400',
    municipality_name: 'Fortaleza',
    state_abbrev: 'CE',
    score: 81.2,
    households: 880000,
    broadband_penetration_pct: 55.6,
    fiber_share_pct: 28.9,
    provider_count: 31,
  },
  {
    municipality_code: '1302603',
    municipality_name: 'Manaus',
    state_abbrev: 'AM',
    score: 79.8,
    households: 620000,
    broadband_penetration_pct: 48.3,
    fiber_share_pct: 22.1,
    provider_count: 18,
  },
  {
    municipality_code: '2611606',
    municipality_name: 'Recife',
    state_abbrev: 'PE',
    score: 78.4,
    households: 540000,
    broadband_penetration_pct: 61.7,
    fiber_share_pct: 35.4,
    provider_count: 34,
  },
  {
    municipality_code: '5300108',
    municipality_name: 'Brasilia',
    state_abbrev: 'DF',
    score: 77.9,
    households: 950000,
    broadband_penetration_pct: 76.8,
    fiber_share_pct: 48.3,
    provider_count: 52,
  },
  {
    municipality_code: '3106200',
    municipality_name: 'Belo Horizonte',
    state_abbrev: 'MG',
    score: 76.5,
    households: 870000,
    broadband_penetration_pct: 68.9,
    fiber_share_pct: 41.6,
    provider_count: 42,
  },
  {
    municipality_code: '4314902',
    municipality_name: 'Porto Alegre',
    state_abbrev: 'RS',
    score: 75.1,
    households: 520000,
    broadband_penetration_pct: 71.4,
    fiber_share_pct: 44.7,
    provider_count: 38,
  },
];

const columns = [
  {
    key: 'municipality_name',
    label: 'Municipality',
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
    label: 'Score',
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
    label: 'Households',
    sortable: true,
    render: (value: number) => value.toLocaleString('pt-BR'),
  },
  {
    key: 'broadband_penetration_pct',
    label: 'Penetration',
    sortable: true,
    render: (value: number) => `${value.toFixed(1)}%`,
  },
  {
    key: 'fiber_share_pct',
    label: 'Fiber Share',
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
    label: 'Providers',
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

  const displayData = opportunities || demoOpportunities;

  const chartData = displayData.slice(0, 8).map((o) => ({
    name: o.municipality_name.substring(0, 12),
    score: o.score,
    penetration: o.broadband_penetration_pct,
  }));

  return (
    <div className="space-y-6 p-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Top Score"
          value={displayData[0]?.score.toFixed(1) || '0'}
          icon={<TrendingUp size={18} />}
          subtitle={displayData[0]?.municipality_name}
        />
        <StatsCard
          title="Avg Score"
          value={(
            displayData.reduce((s, o) => s + o.score, 0) / displayData.length
          ).toFixed(1)}
          icon={<Target size={18} />}
          subtitle={`${displayData.length} municipalities`}
        />
        <StatsCard
          title="Low Penetration"
          value={displayData.filter((o) => o.broadband_penetration_pct < 50).length}
          icon={<BarChart3 size={18} />}
          subtitle="Under 50% broadband"
        />
      </div>

      {/* Chart */}
      <SimpleChart
        data={chartData}
        type="bar"
        xKey="name"
        yKeys={['score', 'penetration']}
        title="Top Opportunities: Score vs Penetration"
        height={250}
      />

      {/* Table */}
      <div className="flex gap-6">
        <div className="flex-1">
          <h2 className="mb-4 text-lg font-semibold text-slate-200">
            Opportunity Scoring
            {error && (
              <span className="ml-3 text-xs font-normal text-yellow-500">
                (Demo data - API unavailable)
              </span>
            )}
          </h2>
          <DataTable
            columns={columns}
            data={displayData}
            loading={loading}
            searchable
            searchKeys={['municipality_name', 'state_abbrev']}
            onRowClick={(row) => setSelectedRow(row)}
            emptyMessage="No opportunities found"
          />
        </div>

        {/* Detail panel */}
        {selectedRow && (
          <div className="w-72 shrink-0">
            <div className="enlace-card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-200">
                  Details
                </h3>
                <button
                  onClick={() => setSelectedRow(null)}
                  className="text-slate-400 hover:text-slate-200"
                  aria-label="Close details"
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
                  <DetailRow label="Score" value={selectedRow.score.toFixed(1)} />
                  <DetailRow
                    label="Households"
                    value={selectedRow.households.toLocaleString('pt-BR')}
                  />
                  <DetailRow
                    label="Penetration"
                    value={`${selectedRow.broadband_penetration_pct.toFixed(1)}%`}
                  />
                  <DetailRow
                    label="Fiber Share"
                    value={`${selectedRow.fiber_share_pct.toFixed(1)}%`}
                  />
                  <DetailRow
                    label="Providers"
                    value={String(selectedRow.provider_count)}
                  />
                </div>

                <button className="enlace-btn-primary w-full mt-4">
                  View Full Analysis
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
