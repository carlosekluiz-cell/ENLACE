// API client for ENLACE backend
import type {
  ApiHealth,
  OpportunityScore,
  MarketSummary,
  HeatmapCell,
  Norma4Impact,
  ComplianceRegulation,
  ComplianceCheck,
  FundingProgram,
  RuralDesign,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new ApiError(
      `API error ${res.status}: ${res.statusText}`,
      res.status
    );
  }

  return res.json();
}

// Typed API functions organized by domain
export const api = {
  // Health check
  health: () => fetchApi<ApiHealth>('/health'),

  // Opportunity endpoints
  opportunities: {
    top: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<OpportunityScore[]>(`/api/v1/opportunity/top${qs}`);
    },
    score: (municipalityCode: string) =>
      fetchApi<OpportunityScore>(
        `/api/v1/opportunity/score/${municipalityCode}`
      ),
  },

  // Market intelligence endpoints
  market: {
    summary: (id: number) =>
      fetchApi<MarketSummary>(`/api/v1/market/${id}/summary`),
    heatmap: (bbox: string, metric: string) =>
      fetchApi<HeatmapCell[]>(
        `/api/v1/market/heatmap?bbox=${bbox}&metric=${metric}`
      ),
    providers: (municipalityId: number) =>
      fetchApi<any[]>(`/api/v1/market/${municipalityId}/providers`),
  },

  // Compliance endpoints
  compliance: {
    norma4Impact: (state: string, subs: number, revenue: number) =>
      fetchApi<Norma4Impact>(
        `/api/v1/compliance/norma4/impact?state=${state}&subscribers=${subs}&revenue_monthly=${revenue}`
      ),
    regulations: () =>
      fetchApi<ComplianceRegulation[]>('/api/v1/compliance/regulations'),
    check: (providerId: number) =>
      fetchApi<ComplianceCheck[]>(
        `/api/v1/compliance/check?provider_id=${providerId}`
      ),
  },

  // Rural connectivity endpoints
  rural: {
    programs: () =>
      fetchApi<FundingProgram[]>('/api/v1/rural/funding/programs'),
    design: (params: {
      latitude: number;
      longitude: number;
      population: number;
      area_km2: number;
      has_power: boolean;
    }) =>
      fetchApi<RuralDesign>('/api/v1/rural/design', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  },

  // Report endpoints
  reports: {
    generate: (reportType: string, params: Record<string, any>) =>
      fetchApi<{ report_url: string }>('/api/v1/report/generate', {
        method: 'POST',
        body: JSON.stringify({ report_type: reportType, parameters: params }),
      }),
  },

  // Coverage endpoints
  coverage: {
    municipality: (code: string) =>
      fetchApi<any>(`/api/v1/coverage/municipality/${code}`),
  },
};
