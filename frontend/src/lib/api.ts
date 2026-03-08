// Cliente API para o backend ENLACE
import type {
  ApiHealth,
  OpportunityScore,
  MarketSummary,
  HeatmapFeatureCollection,
  Norma4Impact,
  ComplianceRegulation,
  ComplianceCheck,
  ComplianceStatus,
  ComplianceDeadline,
  LicensingCheck,
  FundingProgram,
  FundingMatch,
  RuralDesign,
  ReportResult,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  UserProfile,
  ValuationRequest,
  ValuationResponse,
  AcquisitionTarget,
  TargetsRequest,
  SellerPrepareRequest,
  SellerReport,
  MnaMarketOverview,
  CoverageRequest,
  CoverageResult,
  OptimizeRequest,
  LinkBudgetRequest,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'enlace_access_token';

// ---------------------------------------------------------------------------
// Helpers de token
// ---------------------------------------------------------------------------

/** Lê o token JWT armazenado no localStorage (client-side only). */
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** Armazena um token JWT após login/registro. */
export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

/** Remove o token JWT armazenado (logout). */
export function clearToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

/** Verifica se o usuário está autenticado. */
export function isAuthenticated(): boolean {
  return !!getToken();
}

// ---------------------------------------------------------------------------
// Classe de erro
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
// Fetch wrapper — anexa Authorization header automaticamente
// ---------------------------------------------------------------------------

export async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;

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

  // 401 — token expirado ou inválido: limpar e redirecionar
  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new ApiError('Sessão expirada. Faça login novamente.', 401);
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new ApiError(
      `Erro na API ${res.status}: ${body || res.statusText}`,
      res.status
    );
  }

  return res.json();
}

/** Fetch que retorna blob (para download de relatórios). */
export async function fetchBlob(path: string): Promise<Blob> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, { headers });
  if (!res.ok) throw new ApiError(`Erro ${res.status}`, res.status);
  return res.blob();
}

// ---------------------------------------------------------------------------
// Funções de API tipadas organizadas por domínio
// ---------------------------------------------------------------------------

export const api = {
  // Health check
  health: () => fetchApi<ApiHealth>('/health'),

  // ── Autenticação ──────────────────────────────────────────────────────
  auth: {
    login: (data: LoginRequest) =>
      fetchApi<LoginResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    register: (data: RegisterRequest) =>
      fetchApi<RegisterResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    me: () => fetchApi<UserProfile>('/api/v1/auth/me'),
  },

  // ── Oportunidades ────────────────────────────────────────────────────
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

  // ── Inteligência de mercado ──────────────────────────────────────────
  market: {
    summary: (id: number) =>
      fetchApi<MarketSummary>(`/api/v1/market/${id}/summary`),
    history: (id: number, months?: number) =>
      fetchApi<any[]>(
        `/api/v1/market/${id}/history${months ? `?months=${months}` : ''}`
      ),
    competitors: (id: number) =>
      fetchApi<any>(`/api/v1/market/${id}/competitors`),
    heatmap: (bbox: string, metric: string) =>
      fetchApi<HeatmapFeatureCollection>(
        `/api/v1/market/heatmap?bbox=${bbox}&metric=${metric}`
      ),
  },

  // ── Conformidade regulatória ─────────────────────────────────────────
  compliance: {
    status: (providerId: number) =>
      fetchApi<ComplianceStatus>(
        `/api/v1/compliance/status?provider_id=${providerId}`
      ),
    norma4Impact: (state: string, subs: number, revenue: number) =>
      fetchApi<Norma4Impact>(
        `/api/v1/compliance/norma4/impact?state=${state}&subscribers=${subs}&revenue_monthly=${revenue}`
      ),
    licensingCheck: (subscriberCount: number) =>
      fetchApi<LicensingCheck>(
        `/api/v1/compliance/licensing/check?subscriber_count=${subscriberCount}`
      ),
    deadlines: (daysAhead?: number) =>
      fetchApi<ComplianceDeadline[]>(
        `/api/v1/compliance/deadlines${daysAhead ? `?days_ahead=${daysAhead}` : ''}`
      ),
    regulations: () =>
      fetchApi<ComplianceRegulation[]>('/api/v1/compliance/regulations'),
    qualityCheck: (providerId: number) =>
      fetchApi<any>(
        `/api/v1/compliance/quality/check?provider_id=${providerId}`
      ),
  },

  // ── Conectividade rural ──────────────────────────────────────────────
  rural: {
    design: (params: {
      latitude: number;
      longitude: number;
      population: number;
      area_km2: number;
      has_grid_power: boolean;
      community_name?: string;
    }) =>
      fetchApi<RuralDesign>('/api/v1/rural/design', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    solar: (latitude: number, longitude: number, load_kw: number) =>
      fetchApi<any>(
        `/api/v1/rural/solar?latitude=${latitude}&longitude=${longitude}&load_kw=${load_kw}`
      ),
    programs: () =>
      fetchApi<FundingProgram[]>('/api/v1/rural/funding/programs'),
    fundingMatch: (params: {
      latitude: number;
      longitude: number;
      population: number;
      subscribers: number;
    }) =>
      fetchApi<FundingMatch>('/api/v1/rural/funding/match', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    communityProfile: (params: {
      latitude: number;
      longitude: number;
      population: number;
      area_km2: number;
    }) =>
      fetchApi<any>('/api/v1/rural/community/profile', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    riverCrossing: (params: {
      start_lat: number;
      start_lon: number;
      end_lat: number;
      end_lon: number;
      river_width_m: number;
    }) =>
      fetchApi<any>('/api/v1/rural/crossing', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  },

  // ── Relatórios ───────────────────────────────────────────────────────
  reports: {
    market: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/report/market', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    expansion: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/report/expansion', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    compliance: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/report/compliance', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    rural: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/report/rural', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  },

  // ── Projeto de cobertura RF ──────────────────────────────────────────
  design: {
    coverage: (params: CoverageRequest) =>
      fetchApi<CoverageResult>('/api/v1/design/coverage', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    optimize: (params: OptimizeRequest) =>
      fetchApi<any>('/api/v1/design/optimize', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    linkBudget: (params: LinkBudgetRequest) =>
      fetchApi<any>('/api/v1/design/linkbudget', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    terrainProfile: (
      startLat: number, startLon: number,
      endLat: number, endLon: number,
      stepM?: number
    ) =>
      fetchApi<any>(
        `/api/v1/design/profile?start_lat=${startLat}&start_lon=${startLon}&end_lat=${endLat}&end_lon=${endLon}${stepM ? `&step_m=${stepM}` : ''}`
      ),
  },

  // ── M&A Intelligence ─────────────────────────────────────────────────
  mna: {
    valuation: (data: ValuationRequest) =>
      fetchApi<ValuationResponse>('/api/v1/mna/valuation', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    targets: (data: TargetsRequest) =>
      fetchApi<AcquisitionTarget[]>('/api/v1/mna/targets', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    sellerPrepare: (data: SellerPrepareRequest) =>
      fetchApi<SellerReport>('/api/v1/mna/seller/prepare', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    marketOverview: (state: string) =>
      fetchApi<MnaMarketOverview>(`/api/v1/mna/market?state=${state}`),
  },
};
