// Cliente API para o backend Pulso
import type {
  ApiHealth,
  OpportunityScore,
  BaseStationPoint,
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
  UpdateProfileRequest,
  ChangePasswordRequest,
  AdminUser,
  CreateUserRequest,
  PipelineRun,
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
  WeatherRisk,
  MaintenancePriority,
  SatelliteYearData,
  SatelliteGrowthComparison,
  SatelliteGrowthRanking,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'pulso_access_token';

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

  // 401 — sem permissão. Não redireciona automaticamente;
  // o AuthContext gerencia o estado de sessão via /auth/me.
  if (res.status === 401) {
    throw new ApiError('Sem permissão.', 401);
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
    updateProfile: (data: UpdateProfileRequest) =>
      fetchApi<UserProfile>('/api/v1/auth/me', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    changePassword: (data: ChangePasswordRequest) =>
      fetchApi<{ message: string }>('/api/v1/auth/me/password', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
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
    baseStations: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<BaseStationPoint[]>(`/api/v1/opportunity/base-stations${qs}`);
    },
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
    status: (params: { provider_name: string; state: string; subscribers: number }) =>
      fetchApi<ComplianceStatus>(
        `/api/v1/compliance/status?provider_name=${encodeURIComponent(params.provider_name)}&state=${params.state}&subscribers=${params.subscribers}`
      ),
    norma4Impact: (state: string, subs: number, revenue: number) =>
      fetchApi<Norma4Impact>(
        `/api/v1/compliance/norma4/impact?state=${state}&subscribers=${subs}&revenue_monthly=${revenue}`
      ),
    licensingCheck: (subscriberCount: number) =>
      fetchApi<LicensingCheck>(
        `/api/v1/compliance/licensing/check?subscribers=${subscriberCount}`
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
        body: JSON.stringify({
          community_lat: params.latitude,
          community_lon: params.longitude,
          population: params.population,
          area_km2: params.area_km2,
          has_grid_power: params.has_grid_power,
          community_name: params.community_name,
        }),
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
      fetchApi<ReportResult>('/api/v1/reports/market', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    expansion: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/reports/expansion', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    compliance: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/reports/compliance', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    rural: (params: Record<string, any>) =>
      fetchApi<ReportResult>('/api/v1/reports/rural', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  },

  // ── Administração ─────────────────────────────────────────────────
  admin: {
    listUsers: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<AdminUser[]>(`/api/v1/admin/users${qs}`);
    },
    createUser: (data: CreateUserRequest) =>
      fetchApi<AdminUser>('/api/v1/admin/users', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updateUser: (id: number, data: Partial<AdminUser>) =>
      fetchApi<AdminUser>(`/api/v1/admin/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteUser: (id: number) =>
      fetchApi<{ message: string }>(`/api/v1/admin/users/${id}`, {
        method: 'DELETE',
      }),
    listPipelines: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<PipelineRun[]>(`/api/v1/admin/pipelines${qs}`);
    },
    triggerPipeline: (name: string) =>
      fetchApi<{ message: string; run_id: number }>(
        `/api/v1/admin/pipelines/${name}/run`,
        { method: 'POST' }
      ),
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

  // ── Saúde da rede ───────────────────────────────────────────────────
  networkHealth: {
    weatherRisk: (municipalityId: number) =>
      fetchApi<WeatherRisk>(
        `/api/v1/health/weather-risk?municipality_id=${municipalityId}`
      ),
    maintenancePriorities: (providerId: number) =>
      fetchApi<MaintenancePriority[]>(
        `/api/v1/health/maintenance/priorities?provider_id=${providerId}`
      ),
    quality: (municipalityId: number, providerId: number) =>
      fetchApi<any>(
        `/api/v1/health/quality/${municipalityId}?provider_id=${providerId}`
      ),
    seasonal: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/health/seasonal/${municipalityId}`),
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

// ═══════════════════════════════════════════════════════════════════════════════
// Satellite Intelligence
// ═══════════════════════════════════════════════════════════════════════════════

export async function getSatelliteIndices(
  municipalityCode: string,
  fromYear = 2016,
  toYear = 2026,
): Promise<SatelliteYearData[]> {
  return fetchApi(
    `/api/v1/satellite/${municipalityCode}/indices?from_year=${fromYear}&to_year=${toYear}`,
  );
}

export async function getSatelliteGrowth(
  municipalityCode: string,
): Promise<SatelliteGrowthComparison> {
  return fetchApi(`/api/v1/satellite/${municipalityCode}/growth`);
}

export async function getSatelliteRanking(
  state?: string,
  metric = 'built_up_change_pct',
  years = 3,
  limit = 50,
): Promise<SatelliteGrowthRanking[]> {
  const params = new URLSearchParams({ metric, years: String(years), limit: String(limit) });
  if (state) params.append('state', state);
  return fetchApi(`/api/v1/satellite/ranking?${params}`);
}

export function getSatelliteTileUrl(
  municipalityCode: string,
  year: number,
): string {
  return `${API_BASE}/api/v1/satellite/${municipalityCode}/tiles/${year}/{z}/{x}/{y}.png`;
}
