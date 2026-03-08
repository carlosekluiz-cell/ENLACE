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
const TOKEN_KEY = 'enlace_access_token';

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

/** Read the stored JWT token from localStorage (client-side only). */
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** Store a JWT token after login/register. */
export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

/** Remove the stored JWT token (logout). */
export function clearToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper — attaches Authorization header automatically
// ---------------------------------------------------------------------------

export async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;

  // Build headers: always include Content-Type, attach Bearer token if available
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 — token expired or invalid: clear token and redirect to login
  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new ApiError('Session expired. Please log in again.', 401);
  }

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
