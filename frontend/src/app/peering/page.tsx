'use client';

import { useState } from 'react';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import { Globe, Network, BarChart3, Search } from 'lucide-react';

export default function PeeringPage() {
  const [searchTerm, setSearchTerm] = useState('');

  const { data: networks, loading: nLoading } = useApi<any>(
    () => api.peering.networks(),
    []
  );

  const { data: ixps, loading: iLoading } = useApi<any>(
    () => api.peering.ixps(),
    []
  );

  const { data: stats, loading: sLoading } = useApi<any>(
    () => api.peering.stats(),
    []
  );

  const filteredNetworks = (networks?.networks ?? []).filter((n: any) =>
    !searchTerm || n.name?.toLowerCase().includes(searchTerm.toLowerCase()) || String(n.asn).includes(searchTerm)
  );

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Globe size={28} style={{ color: 'var(--accent)' }} />
          Peering
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Dados de peering do PeeringDB — redes e pontos de troca de tráfego no Brasil
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Redes BR</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{sLoading ? '...' : formatNumber(stats?.networks?.count)}</p>
        </div>
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Prefixos IPv4</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{sLoading ? '...' : formatNumber(stats?.networks?.total_prefixes4)}</p>
        </div>
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>IXPs</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{sLoading ? '...' : formatNumber(stats?.ixps?.count)}</p>
        </div>
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Participantes IXP</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{sLoading ? '...' : formatNumber(stats?.ixps?.total_participants)}</p>
        </div>
      </div>

      {/* Networks */}
      <div className="pulso-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            <Network size={16} style={{ color: 'var(--accent)' }} />
            Redes ({filteredNetworks.length})
          </h2>
          <div className="relative">
            <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input type="text" placeholder="Buscar ASN ou nome..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
              className="pulso-input pl-7 text-xs" style={{ width: '200px' }} />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <th className="pb-2 pr-4">ASN</th>
                <th className="pb-2 pr-4">Nome</th>
                <th className="pb-2 pr-4">Tipo</th>
                <th className="pb-2 pr-4">IPv4</th>
                <th className="pb-2 pr-4">IPv6</th>
                <th className="pb-2">Política</th>
              </tr>
            </thead>
            <tbody>
              {filteredNetworks.slice(0, 50).map((n: any) => (
                <tr key={n.asn} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}>
                  <td className="py-2 pr-4 font-mono text-xs" style={{ color: 'var(--accent)' }}>AS{n.asn}</td>
                  <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{n.name}</td>
                  <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{n.info_type ?? '--'}</td>
                  <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatNumber(n.info_prefixes4)}</td>
                  <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{formatNumber(n.info_prefixes6)}</td>
                  <td className="py-2">
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-medium" style={{
                      backgroundColor: n.policy_general === 'Open' ? 'color-mix(in srgb, var(--success) 15%, transparent)' : 'var(--bg-subtle)',
                      color: n.policy_general === 'Open' ? 'var(--success)' : 'var(--text-muted)',
                    }}>{n.policy_general ?? '--'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* IXPs */}
      <div className="pulso-card">
        <h2 className="flex items-center gap-2 text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          <BarChart3 size={16} style={{ color: 'var(--accent)' }} />
          IXPs Brasil
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(ixps?.ixps ?? []).slice(0, 12).map((ix: any) => (
            <div key={ix.peeringdb_id} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{ix.name}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{ix.city}</p>
              <p className="text-xs mt-1 font-semibold" style={{ color: 'var(--accent)' }}>{ix.participants_count ?? 0} participantes</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
