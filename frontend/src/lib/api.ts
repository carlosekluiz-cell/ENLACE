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
  MunicipalityFusion,
  FundingEligibility,
  GazetteAlert,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network';
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

/** POST que baixa HTML como arquivo (relatórios). */
export async function fetchReportDownload(
  path: string,
  body: Record<string, any>,
): Promise<{ blob: Blob; filename: string }> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(`Erro ${res.status}: ${text || res.statusText}`, res.status);
  }

  const disposition = res.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";\s]+)"?/);
  const filename = match?.[1] || `relatorio-${Date.now()}.html`;

  const blob = await res.blob();
  return { blob, filename };
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
    rgst777: (providerId: number) => fetchApi<any>(`/api/v1/compliance/rgst777/${providerId}`),
    rgst777Overview: () => fetchApi<any>('/api/v1/compliance/rgst777/overview'),
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

  // ── Inteligência Agregada ────────────────────────────────────────────
  intelligence: {
    fusion: (municipalityId: number) =>
      fetchApi<MunicipalityFusion>(`/api/v1/intelligence/${municipalityId}/fusion`),
    profile: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/intelligence/${municipalityId}/profile`),
    infrastructureGaps: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/intelligence/${municipalityId}/infrastructure-gaps`),
    fundingEligibility: (municipalityId: number) =>
      fetchApi<FundingEligibility>(`/api/v1/intelligence/${municipalityId}/funding-eligibility`),
    contracts: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<any[]>(`/api/v1/intelligence/contracts${qs}`);
    },
    gazetteAlerts: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<GazetteAlert[]>(`/api/v1/intelligence/gazette-alerts${qs}`);
    },
    regulatoryFeed: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<any[]>(`/api/v1/intelligence/regulatory-feed${qs}`);
    },
    bndes: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<any[]>(`/api/v1/intelligence/bndes${qs}`);
    },
    gazetteMentions: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : '';
      return fetchApi<any[]>(`/api/v1/intelligence/gazette-mentions${qs}`);
    },
  },

  // ── Geográfico ──────────────────────────────────────────────────────
  geo: {
    search: (q: string, limit = 20) =>
      fetchApi<Array<{
        id: number;
        code: string;
        name: string;
        state_abbrev: string;
        country_code: string;
        area_km2: number | null;
        latitude: number;
        longitude: number;
      }>>(`/api/v1/geo/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  },

  // ── Fiber Route Planning ────────────────────────────────────────────
  fiber: {
    route: (data: { start_lat: number; start_lon: number; end_lat: number; end_lon: number }) =>
      fetchApi<any>('/api/v1/fiber/route', { method: 'POST', body: JSON.stringify(data) }),
    corridor: (data: { start_lat: number; start_lon: number; end_lat: number; end_lon: number; width_m?: number }) =>
      fetchApi<any>('/api/v1/fiber/corridor', { method: 'POST', body: JSON.stringify(data) }),
    bom: (params: { distance_km: number; terrain?: string }) => {
      const qs = new URLSearchParams({ distance_km: String(params.distance_km), ...(params.terrain ? { terrain: params.terrain } : {}) });
      return fetchApi<any>(`/api/v1/fiber/bom?${qs}`);
    },
  },

  // ── H3 Hexagonal Grid ──────────────────────────────────────────────
  h3: {
    cells: (params: { bbox: string; resolution?: number; metric?: string }) => {
      const qs = new URLSearchParams({ bbox: params.bbox, ...(params.resolution ? { resolution: String(params.resolution) } : {}), ...(params.metric ? { metric: params.metric } : {}) });
      return fetchApi<any>(`/api/v1/h3/cells?${qs}`);
    },
    analysis: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/h3/${municipalityId}/analysis`),
    compute: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/h3/${municipalityId}/compute`, { method: 'POST' }),
  },

  // ── Time Series ────────────────────────────────────────────────────
  timeseries: {
    subscribers: (params: { municipality_id?: number; interval?: string }) => {
      const qs = new URLSearchParams();
      if (params.municipality_id) qs.set('municipality_id', String(params.municipality_id));
      if (params.interval) qs.set('interval', params.interval);
      return fetchApi<any>(`/api/v1/timeseries/subscribers?${qs}`);
    },
    growth: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/timeseries/growth?${qs}`);
    },
    forecast: (params: { municipality_id: number; months_ahead?: number }) => {
      const qs = new URLSearchParams({ municipality_id: String(params.municipality_id) });
      if (params.months_ahead) qs.set('months_ahead', String(params.months_ahead));
      return fetchApi<any>(`/api/v1/timeseries/forecast?${qs}`);
    },
  },

  // ── Speedtest ──────────────────────────────────────────────────────
  speedtest: {
    municipality: (id: number) => fetchApi<any>(`/api/v1/speedtest/${id}`),
    ranking: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any[]>(`/api/v1/speedtest/ranking/?${qs}`);
    },
    heatmap: (params: { bbox: string; metric?: string }) => {
      const qs = new URLSearchParams({ bbox: params.bbox });
      if (params.metric) qs.set('metric', params.metric);
      return fetchApi<any>(`/api/v1/speedtest/heatmap/?${qs}`);
    },
    history: (id: number) => fetchApi<any[]>(`/api/v1/speedtest/history/${id}`),
  },

  // ── Coverage Validation ────────────────────────────────────────────
  coverage: {
    validation: (id: number) => fetchApi<any>(`/api/v1/coverage/${id}/validation`),
    gaps: (params?: { state?: string; min_gap?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.min_gap) qs.set('min_gap', String(params.min_gap));
      return fetchApi<any[]>(`/api/v1/coverage/gaps?${qs}`);
    },
    towers: (id: number) => fetchApi<any>(`/api/v1/coverage/${id}/towers`),
  },

  // ── Tower Co-location ──────────────────────────────────────────────
  colocation: {
    opportunities: (params?: { state?: string; min_score?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.min_score) qs.set('min_score', String(params.min_score));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any[]>(`/api/v1/colocation/opportunities?${qs}`);
    },
    analysis: (baseStationId: number, recompute = false) =>
      fetchApi<any>(`/api/v1/colocation/${baseStationId}/analysis?recompute=${recompute}`),
    compute: (municipalityId: number) =>
      fetchApi<any>(`/api/v1/colocation/compute/${municipalityId}`, { method: 'POST' }),
    summary: (params?: { state?: string }) => {
      const qs = params?.state ? `?state=${params.state}` : '';
      return fetchApi<any>(`/api/v1/colocation/summary${qs}`);
    },
  },

  // ── Smart Alerts ───────────────────────────────────────────────────
  alerts: {
    rules: () => fetchApi<any[]>('/api/v1/alerts/rules'),
    createRule: (data: any) => fetchApi<any>('/api/v1/alerts/rules', { method: 'POST', body: JSON.stringify(data) }),
    deleteRule: (id: number) => fetchApi<any>(`/api/v1/alerts/rules/${id}`, { method: 'DELETE' }),
    events: (params?: { unread?: boolean; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.unread != null) qs.set('unread', String(params.unread));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any[]>(`/api/v1/alerts/events?${qs}`);
    },
    eventCount: (unread = true) =>
      fetchApi<{ count: number }>(`/api/v1/alerts/events/count?unread=${unread}`),
    acknowledge: (eventId: number) =>
      fetchApi<any>(`/api/v1/alerts/events/${eventId}/acknowledge`, { method: 'POST' }),
    evaluate: () =>
      fetchApi<any>('/api/v1/alerts/evaluate', { method: 'POST' }),
  },

  // ── Enhanced M&A ───────────────────────────────────────────────────
  mnaEnhanced: {
    comparableAnalysis: (data: { provider_id: number; subscriber_range?: [number, number]; fiber_range?: [number, number]; states?: string[] }) =>
      fetchApi<any>('/api/v1/mna/comparable-analysis', { method: 'POST', body: JSON.stringify(data) }),
    synergyModel: (data: { acquirer_id: number; target_id: number }) =>
      fetchApi<any>('/api/v1/mna/synergy-model', { method: 'POST', body: JSON.stringify(data) }),
    dueDiligence: (data: { target_provider_name: string; state_codes?: string[] }) =>
      fetchApi<any>('/api/v1/mna/due-diligence', { method: 'POST', body: JSON.stringify(data) }),
    integrationTimeline: (acquirerSubs: number, targetSubs: number) =>
      fetchApi<any>(`/api/v1/mna/integration-timeline?acquirer_subs=${acquirerSubs}&target_subs=${targetSubs}`),
  },

  // ── Pulso Score ────────────────────────────────────────────────────
  pulsoScore: {
    provider: (id: number) => fetchApi<any>(`/api/v1/score/provider/${id}`),
    ranking: (params?: { state?: string; tier?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.tier) qs.set('tier', params.tier);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any[]>(`/api/v1/score/ranking?${qs}`);
    },
    distribution: () => fetchApi<any>('/api/v1/score/distribution'),
    compute: (id: number) => fetchApi<any>(`/api/v1/score/compute/${id}`, { method: 'POST' }),
  },

  // ── ISP Credit Scoring ─────────────────────────────────────────────
  credit: {
    score: (id: number) => fetchApi<any>(`/api/v1/credit/${id}`),
    ranking: (params?: { state?: string; min_rating?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.min_rating) qs.set('min_rating', params.min_rating);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any[]>(`/api/v1/credit/ranking?${qs}`);
    },
    distribution: () => fetchApi<any>('/api/v1/credit/distribution'),
    compute: (id: number) => fetchApi<any>(`/api/v1/credit/compute/${id}`, { method: 'POST' }),
  },

  // ── Buildings ──────────────────────────────────────────────────────
  buildings: {
    stats: (municipalityId: number) => fetchApi<any>(`/api/v1/buildings/geo/${municipalityId}/buildings/stats`),
    list: (municipalityId: number, bbox?: string) => {
      const qs = bbox ? `?bbox=${bbox}` : '';
      return fetchApi<any>(`/api/v1/buildings/geo/${municipalityId}/buildings${qs}`);
    },
  },

  // ── Spatial Analytics ───────────────────────────────────────────────
  spatial: {
    clusters: (params?: { num_clusters?: number; state?: string }) => {
      const qs = new URLSearchParams();
      if (params?.num_clusters) qs.set('num_clusters', String(params.num_clusters));
      if (params?.state) qs.set('state', params.state);
      return fetchApi<any>(`/api/v1/spatial/clusters?${qs}`);
    },
    voronoi: (params?: { state?: string; provider_id?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.provider_id) qs.set('provider_id', String(params.provider_id));
      return fetchApi<any>(`/api/v1/spatial/voronoi?${qs}`);
    },
    footprint: (providerId: number) =>
      fetchApi<any>(`/api/v1/spatial/footprint/${providerId}`),
  },

  // ── Starlink Threat Index ───────────────────────────────────────────
  starlink: {
    threat: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/starlink/threat?${qs}`);
    },
    municipality: (l2Id: number) =>
      fetchApi<any>(`/api/v1/starlink/threat/${l2Id}`),
  },

  // ── FWA vs Fiber Calculator ─────────────────────────────────────────
  fwaFiber: {
    compare: (params: { l2_id: number; target_subscribers?: number }) =>
      fetchApi<any>('/api/v1/fwa-fiber/compare', { method: 'POST', body: JSON.stringify(params) }),
    presets: () => fetchApi<any[]>('/api/v1/fwa-fiber/presets'),
  },

  // ── Backhaul Utilization ────────────────────────────────────────────
  backhaul: {
    utilization: (params?: { state?: string }) => {
      const qs = params?.state ? `?state=${params.state}` : '';
      return fetchApi<any>(`/api/v1/backhaul/utilization${qs}`);
    },
    forecast: (l2Id: number) =>
      fetchApi<any>(`/api/v1/backhaul/forecast/${l2Id}`),
  },

  // ── Weather Risk ────────────────────────────────────────────────────
  weatherRisk: {
    risk: (params?: { state?: string }) => {
      const qs = params?.state ? `?state=${params.state}` : '';
      return fetchApi<any>(`/api/v1/weather-risk/risk${qs}`);
    },
    seasonal: (params?: { state?: string }) => {
      const qs = params?.state ? `?state=${params.state}` : '';
      return fetchApi<any>(`/api/v1/weather-risk/seasonal${qs}`);
    },
    municipality: (l2Id: number) =>
      fetchApi<any>(`/api/v1/weather-risk/${l2Id}`),
  },

  // ── Peering ─────────────────────────────────────────────────────────
  peering: {
    networks: () => fetchApi<any>('/api/v1/peering/networks'),
    ixps: () => fetchApi<any>('/api/v1/peering/ixps'),
    stats: () => fetchApi<any>('/api/v1/peering/stats'),
  },

  // ── IXP ─────────────────────────────────────────────────────────────
  ixp: {
    locations: (params?: { state?: string }) => {
      const qs = params?.state ? `?state=${params.state}` : '';
      return fetchApi<any>(`/api/v1/ixp/locations${qs}`);
    },
    traffic: () => fetchApi<any>('/api/v1/ixp/traffic'),
    trafficHistory: (code: string) => fetchApi<any>(`/api/v1/ixp/traffic/${code}`),
  },

  // ── 5G Obligations ──────────────────────────────────────────────────
  obligations: {
    fiveG: () => fetchApi<any>('/api/v1/obligations/5g'),
    provider: (name: string) => fetchApi<any>(`/api/v1/obligations/5g/${encodeURIComponent(name)}`),
    gapAnalysis: () => fetchApi<any>('/api/v1/obligations/5g/gap-analysis'),
  },

  // ── Cross-Reference Analytics ──────────────────────────────────────
  analytics: {
    hhi: (params?: { state?: string; year_month?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.year_month) qs.set('year_month', params.year_month);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/hhi?${qs}`);
    },
    coverageGaps: (params?: { state?: string; min_population?: number; max_towers_per_1000?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.min_population) qs.set('min_population', String(params.min_population));
      if (params?.max_towers_per_1000) qs.set('max_towers_per_1000', String(params.max_towers_per_1000));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/coverage-gaps?${qs}`);
    },
    providerOverlap: (providerA: number, providerB: number) =>
      fetchApi<any>(`/api/v1/analytics/provider-overlap?provider_a=${providerA}&provider_b=${providerB}`),
    towerDensity: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/tower-density?${qs}`);
    },
    weatherCorrelation: (params?: { state?: string; months?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.months) qs.set('months', String(params.months));
      return fetchApi<any>(`/api/v1/analytics/weather-correlation?${qs}`);
    },
    employmentCorrelation: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/employment-correlation?${qs}`);
    },
    schoolGaps: (params?: { state?: string; max_distance_km?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.max_distance_km) qs.set('max_distance_km', String(params.max_distance_km));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/school-gaps?${qs}`);
    },
    healthGaps: (params?: { state?: string; max_distance_km?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.max_distance_km) qs.set('max_distance_km', String(params.max_distance_km));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/health-gaps?${qs}`);
    },
    investmentPriority: (params?: { state?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/investment-priority?${qs}`);
    },
    anomalies: (params?: { state?: string; lookback_months?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.state) qs.set('state', params.state);
      if (params?.lookback_months) qs.set('lookback_months', String(params.lookback_months));
      if (params?.limit) qs.set('limit', String(params.limit));
      return fetchApi<any>(`/api/v1/analytics/anomalies?${qs}`);
    },
  },

  // ── Spectrum Valuation (M&A) ────────────────────────────────────────
  spectrum: {
    holdings: (providerId: number) => fetchApi<any>(`/api/v1/mna/spectrum/${providerId}`),
    valuation: (providerId: number) => fetchApi<any>(`/api/v1/mna/spectrum/valuation/${providerId}`),
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
  try {
    return await fetchApi(
      `/api/v1/satellite/${municipalityCode}/indices?from_year=${fromYear}&to_year=${toYear}`,
    );
  } catch {
    return [];
  }
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
  try {
    const params = new URLSearchParams({ metric, years: String(years), limit: String(limit) });
    if (state) params.append('state', state);
    return await fetchApi(`/api/v1/satellite/ranking?${params}`);
  } catch {
    return [];
  }
}

export function getSatelliteTileUrl(
  municipalityCode: string,
  year: number,
): string {
  return `${API_BASE}/api/v1/satellite/${municipalityCode}/tiles/${year}/{z}/{x}/{y}.png`;
}

export interface SatelliteComputeResult {
  status: 'cached' | 'computed' | 'computing';
  municipality_code: string;
  years_computed?: number;
  message?: string;
  data?: Array<{
    year: number;
    ndvi_mean: number | null;
    ndbi_mean: number | null;
    mndwi_mean: number | null;
    bsi_mean: number | null;
    built_up_area_km2: number | null;
    built_up_pct: number | null;
    built_up_change_km2: number | null;
    built_up_change_pct: number | null;
    ndvi_change_pct: number | null;
  }>;
}

export async function computeSatelliteAnalysis(
  municipalityCode: string,
): Promise<SatelliteComputeResult> {
  return fetchApi(`/api/v1/satellite/${municipalityCode}/compute`, {
    method: 'POST',
  });
}
