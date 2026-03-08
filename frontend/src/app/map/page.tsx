'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import StatsCard from '@/components/dashboard/StatsCard';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  MapPin,
  Users,
  Radio,
  Wifi,
  X,
} from 'lucide-react';

// Dynamic import for MapView to avoid SSR issues with WebGL
const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[600px] items-center justify-center rounded-lg bg-slate-800 border border-slate-700">
      <div className="text-center">
        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <p className="text-sm text-slate-400">Loading map...</p>
      </div>
    </div>
  ),
});

// Demo data for when API is unavailable
const demoStats = {
  municipalities: 5570,
  subscribers: 48200000,
  providers: 12400,
  avgPenetration: 62.3,
};

interface SelectedMunicipality {
  name: string;
  state: string;
  population: number;
  subscribers: number;
  penetration: number;
  providers: number;
}

export default function MapPage() {
  const [selectedMunicipality, setSelectedMunicipality] =
    useState<SelectedMunicipality | null>(null);

  // Try to fetch real data; gracefully fallback to demo data
  const { data: healthData } = useApi(() => api.health(), []);
  const isApiConnected = !!healthData;

  const handleMapClick = (info: any) => {
    if (info?.object) {
      setSelectedMunicipality({
        name: info.object.name || 'Unknown',
        state: info.object.state_abbrev || 'N/A',
        population: info.object.population || 0,
        subscribers: info.object.subscribers || 0,
        penetration: info.object.penetration || 0,
        providers: info.object.provider_count || 0,
      });
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Stats bar */}
      <div className="grid grid-cols-2 gap-4 p-4 md:grid-cols-4">
        <StatsCard
          title="Municipalities"
          value={demoStats.municipalities}
          icon={<MapPin size={18} />}
          subtitle="Total tracked"
        />
        <StatsCard
          title="Subscribers"
          value={`${(demoStats.subscribers / 1e6).toFixed(1)}M`}
          icon={<Users size={18} />}
          change={3.2}
          subtitle="vs last quarter"
        />
        <StatsCard
          title="Providers"
          value={demoStats.providers.toLocaleString('pt-BR')}
          icon={<Radio size={18} />}
          subtitle="Active ISPs"
        />
        <StatsCard
          title="Avg Penetration"
          value={`${demoStats.avgPenetration}%`}
          icon={<Wifi size={18} />}
          change={1.8}
          subtitle="Broadband"
        />
      </div>

      {/* Map + Side panel */}
      <div className="flex flex-1 gap-4 px-4 pb-4">
        {/* Map */}
        <div className="flex-1">
          <MapView
            className="h-full"
            onMapClick={handleMapClick}
          />

          {/* API status indicator */}
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <span
              className={`h-2 w-2 rounded-full ${isApiConnected ? 'bg-green-500' : 'bg-yellow-500'}`}
            />
            {isApiConnected ? 'API Connected' : 'Demo Mode - API Unavailable'}
          </div>
        </div>

        {/* Side panel - municipality details */}
        {selectedMunicipality && (
          <div className="w-80 shrink-0 overflow-y-auto rounded-lg border border-slate-700 bg-slate-800">
            <div className="flex items-center justify-between border-b border-slate-700 p-4">
              <h2 className="text-sm font-semibold text-slate-200">
                Municipality Details
              </h2>
              <button
                onClick={() => setSelectedMunicipality(null)}
                className="text-slate-400 hover:text-slate-200"
                aria-label="Close panel"
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-4 p-4">
              <div>
                <h3 className="text-lg font-bold text-slate-100">
                  {selectedMunicipality.name}
                </h3>
                <p className="text-sm text-slate-400">
                  {selectedMunicipality.state}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-900 p-3">
                  <p className="text-xs text-slate-500">Population</p>
                  <p className="text-sm font-semibold text-slate-200">
                    {selectedMunicipality.population.toLocaleString('pt-BR')}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900 p-3">
                  <p className="text-xs text-slate-500">Subscribers</p>
                  <p className="text-sm font-semibold text-slate-200">
                    {selectedMunicipality.subscribers.toLocaleString('pt-BR')}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900 p-3">
                  <p className="text-xs text-slate-500">Penetration</p>
                  <p className="text-sm font-semibold text-slate-200">
                    {selectedMunicipality.penetration.toFixed(1)}%
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900 p-3">
                  <p className="text-xs text-slate-500">Providers</p>
                  <p className="text-sm font-semibold text-slate-200">
                    {selectedMunicipality.providers}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
