'use client';

import { useState } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi, useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { FundingProgram } from '@/lib/types';
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

// Demo funding programs
const demoPrograms: FundingProgram[] = [
  {
    id: 1,
    name: 'FUST Universal Service Fund',
    agency: 'Anatel',
    max_amount: 5000000,
    eligibility_criteria: 'Municipalities under 30,000 inhabitants with less than 40% broadband penetration',
    deadline: '2026-06-30',
    status: 'open',
  },
  {
    id: 2,
    name: 'BNDES Rural Connectivity',
    agency: 'BNDES',
    max_amount: 10000000,
    eligibility_criteria: 'Licensed ISPs expanding to underserved rural areas',
    deadline: '2026-09-15',
    status: 'open',
  },
  {
    id: 3,
    name: 'Norte Conectado',
    agency: 'MCOM',
    max_amount: 25000000,
    eligibility_criteria: 'Projects in the Amazon region using satellite or river-based connectivity',
    deadline: '2026-12-31',
    status: 'upcoming',
  },
  {
    id: 4,
    name: 'Gesac Community WiFi',
    agency: 'MCOM',
    max_amount: 500000,
    eligibility_criteria: 'Community centers and schools in municipalities without broadband access',
    status: 'open',
  },
];

interface DesignResult {
  technology: string;
  cost: number;
  solar_kw: number;
  battery_kwh: number;
  coverage: number;
}

export default function RuralPage() {
  // Form state
  const [communityName, setCommunityName] = useState('');
  const [latitude, setLatitude] = useState('-12.9714');
  const [longitude, setLongitude] = useState('-38.5124');
  const [population, setPopulation] = useState('2500');
  const [area, setArea] = useState('150');
  const [hasPower, setHasPower] = useState(true);

  // Design results (demo)
  const [designResult, setDesignResult] = useState<DesignResult | null>(null);

  // Fetch funding programs
  const { data: programs } = useApi(() => api.rural.programs(), []);
  const displayPrograms = programs || demoPrograms;

  const handleDesign = () => {
    // Simulate design calculation when API is unavailable
    const pop = parseInt(population) || 0;
    const areaKm2 = parseFloat(area) || 0;
    const density = pop / Math.max(areaKm2, 1);

    let technology = 'FTTH + Wireless';
    if (density < 5) technology = 'Satellite + WiFi Hotspot';
    else if (density < 20) technology = 'Fixed Wireless + Solar';
    else if (density < 50) technology = 'FTTH/FTTB Hybrid';

    const baseCost = pop * 450;
    const solarKw = hasPower ? 0 : Math.ceil(pop * 0.05);
    const batteryKwh = hasPower ? 0 : Math.ceil(solarKw * 4);

    setDesignResult({
      technology,
      cost: baseCost + solarKw * 3200,
      solar_kw: solarKw,
      battery_kwh: batteryKwh,
      coverage: Math.min(95, 70 + density * 0.5),
    });
  };

  const costBreakdown = designResult
    ? [
        { name: 'Infrastructure', value: Math.round(designResult.cost * 0.45) },
        { name: 'Equipment', value: Math.round(designResult.cost * 0.25) },
        { name: 'Installation', value: Math.round(designResult.cost * 0.15) },
        { name: 'Solar/Power', value: Math.round(designResult.cost * 0.1) },
        { name: 'Contingency', value: Math.round(designResult.cost * 0.05) },
      ]
    : [];

  return (
    <div className="space-y-6 p-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatsCard
          title="Unserved Communities"
          value="12,450"
          icon={<MapPin size={18} />}
          subtitle="No broadband access"
        />
        <StatsCard
          title="Rural Population"
          value="29.3M"
          icon={<Users size={18} />}
          subtitle="Underserved"
        />
        <StatsCard
          title="Available Funding"
          value="R$ 40.5M"
          icon={<DollarSign size={18} />}
          subtitle="Active programs"
        />
        <StatsCard
          title="Avg Cost/Household"
          value="R$ 1,850"
          icon={<Zap size={18} />}
          subtitle="Rural deployment"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Design input form */}
        <div className="enlace-card">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Mountain size={16} className="text-blue-400" />
            Community Design Input
          </h2>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Community Name
              </label>
              <input
                type="text"
                value={communityName}
                onChange={(e) => setCommunityName(e.target.value)}
                placeholder="e.g., Vila Nova do Norte"
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
                  Population
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
                Grid Power Available
              </span>
            </div>

            <button
              onClick={handleDesign}
              className="enlace-btn-primary w-full flex items-center justify-center gap-2"
            >
              <Send size={16} />
              Generate Design
            </button>
          </div>

          {/* Design results */}
          {designResult && (
            <div className="mt-4 space-y-3 rounded-lg bg-slate-900 p-4">
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Recommended Design
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Technology</span>
                  <span className="font-semibold text-blue-400">
                    {designResult.technology}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Estimated Cost</span>
                  <span className="font-semibold text-slate-200">
                    R${' '}
                    {designResult.cost.toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Coverage</span>
                  <span className="font-semibold text-green-400">
                    {designResult.coverage.toFixed(1)}%
                  </span>
                </div>
                {designResult.solar_kw > 0 && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Sun size={14} /> Solar Capacity
                      </span>
                      <span className="font-semibold text-yellow-400">
                        {designResult.solar_kw} kW
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Battery Storage</span>
                      <span className="font-semibold text-slate-200">
                        {designResult.battery_kwh} kWh
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Results and funding */}
        <div className="lg:col-span-2 space-y-6">
          {/* Cost breakdown chart */}
          {designResult && (
            <SimpleChart
              data={costBreakdown}
              type="bar"
              xKey="name"
              yKey="value"
              title="Cost Breakdown (BRL)"
              height={200}
            />
          )}

          {/* Funding programs */}
          <div>
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
              <DollarSign size={16} className="text-blue-400" />
              Matching Funding Programs
            </h2>

            <div className="space-y-3">
              {displayPrograms.map((program) => (
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
                          {program.status}
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
                        Up to R${' '}
                        {(program.max_amount / 1e6).toFixed(1)}M
                      </p>
                      {program.deadline && (
                        <p className="text-xs text-slate-500">
                          Deadline: {program.deadline}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
