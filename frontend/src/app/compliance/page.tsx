'use client';

import { useState } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Calculator,
  FileCheck,
} from 'lucide-react';
import { clsx } from 'clsx';

interface ComplianceResult {
  regulation: string;
  status: 'compliant' | 'warning' | 'non_compliant';
  message: string;
}

// Demo compliance checks
const demoChecks: ComplianceResult[] = [
  {
    regulation: 'Norma No. 4 - FUST Contribution',
    status: 'compliant',
    message: 'Fund contributions up to date for the current fiscal year.',
  },
  {
    regulation: 'SCM Authorization',
    status: 'compliant',
    message: 'Multimedia Communication Service license is active and valid.',
  },
  {
    regulation: 'Quality of Service (RGQ)',
    status: 'warning',
    message: 'Latency metrics approaching threshold in 2 municipalities.',
  },
  {
    regulation: 'Consumer Rights (RGC)',
    status: 'compliant',
    message: 'Customer complaint resolution within regulated timeframes.',
  },
  {
    regulation: 'Infrastructure Sharing',
    status: 'non_compliant',
    message: 'Missing sharing agreement for 3 tower sites in MG.',
  },
  {
    regulation: 'Data Protection (LGPD)',
    status: 'warning',
    message: 'Data processing impact assessment due for renewal.',
  },
];

const states = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
  'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
  'SP', 'SE', 'TO',
];

export default function CompliancePage() {
  const [providerName, setProviderName] = useState('');
  const [state, setState] = useState('SP');
  const [subscribers, setSubscribers] = useState('50000');
  const [revenue, setRevenue] = useState('2500000');
  const [checks, setChecks] = useState<ComplianceResult[]>(demoChecks);

  const {
    data: norma4Data,
    loading: norma4Loading,
    execute: fetchNorma4,
  } = useLazyApi(
    (params: { state: string; subs: number; revenue: number }) =>
      api.compliance.norma4Impact(params.state, params.subs, params.revenue)
  );

  const handleCalculateImpact = () => {
    fetchNorma4({
      state,
      subs: parseInt(subscribers) || 0,
      revenue: parseFloat(revenue) || 0,
    });
  };

  const statusCounts = {
    compliant: checks.filter((c) => c.status === 'compliant').length,
    warning: checks.filter((c) => c.status === 'warning').length,
    non_compliant: checks.filter((c) => c.status === 'non_compliant').length,
  };

  const chartData = [
    { name: 'Compliant', value: statusCounts.compliant },
    { name: 'Warning', value: statusCounts.warning },
    { name: 'Non-Compliant', value: statusCounts.non_compliant },
  ];

  const statusIcon = {
    compliant: <CheckCircle2 size={16} className="text-green-400" />,
    warning: <AlertTriangle size={16} className="text-yellow-400" />,
    non_compliant: <XCircle size={16} className="text-red-400" />,
  };

  const statusBadge = {
    compliant: 'enlace-badge-green',
    warning: 'enlace-badge-yellow',
    non_compliant: 'enlace-badge-red',
  };

  return (
    <div className="space-y-6 p-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Compliant"
          value={statusCounts.compliant}
          icon={<CheckCircle2 size={18} className="text-green-400" />}
          subtitle="Regulations met"
          className="border-green-900/30"
        />
        <StatsCard
          title="Warnings"
          value={statusCounts.warning}
          icon={<AlertTriangle size={18} className="text-yellow-400" />}
          subtitle="Approaching limits"
          className="border-yellow-900/30"
        />
        <StatsCard
          title="Non-Compliant"
          value={statusCounts.non_compliant}
          icon={<XCircle size={18} className="text-red-400" />}
          subtitle="Requires action"
          className="border-red-900/30"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Provider input form */}
        <div className="enlace-card lg:col-span-1">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Shield size={16} className="text-blue-400" />
            Provider Information
          </h2>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Provider Name
              </label>
              <input
                type="text"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                placeholder="Enter provider name"
                className="enlace-input w-full"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">State</label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="enlace-input w-full"
              >
                {states.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Subscribers
              </label>
              <input
                type="number"
                value={subscribers}
                onChange={(e) => setSubscribers(e.target.value)}
                placeholder="Number of subscribers"
                className="enlace-input w-full"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Monthly Revenue (BRL)
              </label>
              <input
                type="number"
                value={revenue}
                onChange={(e) => setRevenue(e.target.value)}
                placeholder="Monthly revenue"
                className="enlace-input w-full"
              />
            </div>

            <button
              onClick={handleCalculateImpact}
              disabled={norma4Loading}
              className="enlace-btn-primary w-full flex items-center justify-center gap-2"
            >
              <Calculator size={16} />
              {norma4Loading ? 'Calculating...' : 'Calculate Norma 4 Impact'}
            </button>
          </div>

          {/* Norma 4 results */}
          {norma4Data && (
            <div className="mt-4 space-y-2 rounded-lg bg-slate-900 p-4">
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Norma No. 4 Impact
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Fund Contribution</span>
                  <span className="font-semibold text-slate-200">
                    R${' '}
                    {(
                      norma4Data.estimated_fund_contribution || 0
                    ).toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Risk Level</span>
                  <span
                    className={clsx(
                      'font-semibold',
                      norma4Data.risk_level === 'low'
                        ? 'text-green-400'
                        : norma4Data.risk_level === 'medium'
                          ? 'text-yellow-400'
                          : 'text-red-400'
                    )}
                  >
                    {norma4Data.risk_level?.toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Static estimate when API is not connected */}
          {!norma4Data && (
            <div className="mt-4 space-y-2 rounded-lg bg-slate-900 p-4">
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Estimated Impact (Demo)
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">FUST Contribution</span>
                  <span className="font-semibold text-slate-200">
                    R${' '}
                    {((parseFloat(revenue) || 0) * 0.01).toLocaleString(
                      'pt-BR',
                      { minimumFractionDigits: 2, maximumFractionDigits: 2 }
                    )}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">FUNTTEL Contribution</span>
                  <span className="font-semibold text-slate-200">
                    R${' '}
                    {((parseFloat(revenue) || 0) * 0.005).toLocaleString(
                      'pt-BR',
                      { minimumFractionDigits: 2, maximumFractionDigits: 2 }
                    )}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Compliance checks list */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
              <FileCheck size={16} className="text-blue-400" />
              Compliance Checks
            </h2>
          </div>

          <div className="space-y-3">
            {checks.map((check, idx) => (
              <div
                key={idx}
                className="enlace-card flex items-start gap-4"
              >
                <div className="mt-0.5">{statusIcon[check.status]}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-slate-200">
                      {check.regulation}
                    </h3>
                    <span className={statusBadge[check.status]}>
                      {check.status === 'non_compliant'
                        ? 'Non-Compliant'
                        : check.status.charAt(0).toUpperCase() +
                          check.status.slice(1)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{check.message}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <SimpleChart
            data={chartData}
            type="pie"
            xKey="name"
            yKey="value"
            title="Compliance Overview"
            height={250}
          />
        </div>
      </div>
    </div>
  );
}
