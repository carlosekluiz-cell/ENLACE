// Tipos TypeScript correspondentes aos schemas do backend ENLACE

export interface Municipality {
  id: number;
  code: string;
  name: string;
  state_abbrev?: string;
  country_code: string;
  population?: number;
  area_km2?: number;
  latitude?: number;
  longitude?: number;
}

export interface OpportunityScore {
  municipality_code: string;
  municipality_name: string;
  state_abbrev: string;
  score: number;
  rank?: number;
  households: number;
  broadband_penetration_pct: number;
  fiber_share_pct: number;
  provider_count: number;
  median_income?: number;
  population_density?: number;
  growth_rate?: number;
}

export interface MarketSummary {
  municipality_id: number;
  code?: string;
  name?: string;
  municipality_name?: string;
  state_abbrev: string;
  year_month?: string;
  total_subscribers: number;
  fiber_subscribers: number;
  provider_count: number;
  total_households?: number | null;
  total_population?: number | null;
  broadband_penetration_pct: number | null;
  fiber_share_pct: number | null;
  median_speed_mbps?: number;
  avg_arpu?: number;
}

export interface HeatmapFeatureCollection {
  type: 'FeatureCollection';
  features: HeatmapFeature[];
}

export interface HeatmapFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: {
    municipality_id: number;
    code: string;
    name: string;
    state_abbrev: string;
    metric: string;
    value: number | null;
    total_subscribers: number;
    provider_count: number;
  };
}

export interface ComplianceRegulation {
  id: string;
  name: string;
  agency: string;
  category: string;
  description: string;
  effective_date?: string;
  status: 'active' | 'pending' | 'revoked';
}

export interface ComplianceCheck {
  regulation: string;
  status: 'compliant' | 'warning' | 'non_compliant';
  message: string;
  details?: string;
}

export interface ComplianceStatus {
  provider_id: number;
  overall_status: string;
  checks: ComplianceCheck[];
  last_updated?: string;
}

export interface Norma4Impact {
  state: string;
  icms_rate_pct: number;
  subscribers: number;
  revenue_monthly: number;
  estimated_fund_contribution: number;
  fust_contribution: number;
  funttel_contribution: number;
  total_tax_burden_monthly: number;
  compliance_requirements: string[];
  risk_level: 'low' | 'medium' | 'high';
}

export interface LicensingCheck {
  subscriber_count: number;
  requires_scm_license: boolean;
  threshold: number;
  message: string;
}

export interface ComplianceDeadline {
  regulation: string;
  deadline: string;
  days_remaining: number;
  status: string;
  description: string;
}

export interface RuralCommunity {
  name: string;
  latitude: number;
  longitude: number;
  population: number;
  area_km2: number;
  has_power: boolean;
}

export interface RuralDesign {
  backhaul: { technology: string; cost_brl: number; details: Record<string, any> };
  last_mile: { technology: string; cost_brl: number; details: Record<string, any> };
  power: { source: string; cost_brl: number; details: Record<string, any> };
  total_cost_brl: number;
  monthly_opex_brl: number;
  coverage_pct: number;
  notes: string[];
}

export interface FundingProgram {
  id: number;
  name: string;
  agency: string;
  max_amount: number;
  eligibility_criteria: string;
  deadline?: string;
  status: 'open' | 'closed' | 'upcoming';
}

export interface FundingMatch {
  matched_programs: FundingProgram[];
  total_available: number;
  eligibility_notes: string[];
}

export interface ReportResult {
  report_type: string;
  content: Record<string, any>;
  generated_at: string;
}

export interface ApiHealth {
  status: string;
  version?: string;
  timestamp?: string;
}

export interface Provider {
  id: number;
  name: string;
  cnpj?: string;
  type?: string;
  subscribers?: number;
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  tenant_id: string;
  role: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  organization: string;
  state_code?: string;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  tenant_id: string;
  organization: string;
  access_token: string;
  token_type: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  tenant_id: string;
  role: string;
  anonymous: boolean;
  tenant?: Record<string, any> | null;
}

// ---------------------------------------------------------------------------
// M&A types
// ---------------------------------------------------------------------------

export interface ValuationRequest {
  subscriber_count: number;
  fiber_pct: number;
  monthly_revenue_brl: number;
  ebitda_margin_pct: number;
  state_code: string;
  monthly_churn_pct: number;
  growth_rate_12m: number;
  net_debt_brl: number;
}

export interface ValuationResponse {
  subscriber_multiple: Record<string, any>;
  revenue_multiple: Record<string, any>;
  dcf: Record<string, any>;
  combined_range: { low_brl: number; mid_brl: number; high_brl: number };
}

export interface TargetsRequest {
  acquirer_states: string[];
  acquirer_subscribers: number;
  min_subs: number;
  max_subs: number;
}

export interface AcquisitionTarget {
  provider_id: number;
  provider_name: string;
  state_codes: string[];
  subscriber_count: number;
  fiber_pct: number;
  estimated_revenue_brl: number;
  valuation_subscriber: number;
  valuation_revenue: number;
  valuation_dcf: number;
  strategic_score: number;
  financial_score: number;
  integration_risk: string;
  synergy_estimate_brl: number;
  overall_score: number;
}

export interface SellerPrepareRequest {
  provider_name: string;
  state_codes: string[];
  subscriber_count: number;
  fiber_pct: number;
  monthly_revenue_brl: number;
  ebitda_margin_pct: number;
  net_debt_brl: number;
}

export interface SellerReport {
  provider_name: string;
  subscriber_count: number;
  estimated_value_range: number[];
  valuation_methods: Record<string, any>;
  strengths: string[];
  weaknesses: string[];
  value_enhancement_opportunities: Record<string, any>[];
  preparation_checklist: Record<string, any>[];
  estimated_timeline_months: number;
}

export interface MnaMarketOverview {
  state: string;
  total_isps: number;
  total_subscribers: number;
  avg_valuation_per_sub: number;
  fiber_pct_avg: number;
  recent_transactions: Record<string, any>[];
}

// ---------------------------------------------------------------------------
// Design / RF types
// ---------------------------------------------------------------------------

export interface CoverageRequest {
  tower_lat: number;
  tower_lon: number;
  tower_height_m: number;
  frequency_mhz: number;
  tx_power_dbm: number;
  antenna_gain_dbi: number;
  radius_m: number;
  grid_resolution_m: number;
  apply_vegetation: boolean;
  country_code: string;
}

export interface CoverageResult {
  coverage_pct: number;
  coverage_area_km2: number;
  avg_signal_dbm: number;
  min_signal_dbm: number;
  max_signal_dbm: number;
  grid: { lat: number; lon: number; signal_dbm: number }[];
}

export interface OptimizeRequest {
  center_lat: number;
  center_lon: number;
  radius_m: number;
  coverage_target_pct: number;
  min_signal_dbm: number;
  max_towers: number;
  frequency_mhz: number;
  tx_power_dbm: number;
  antenna_gain_dbi: number;
  antenna_height_m: number;
}

export interface LinkBudgetRequest {
  frequency_ghz: number;
  distance_km: number;
  tx_power_dbm: number;
  tx_antenna_gain_dbi: number;
  rx_antenna_gain_dbi: number;
  rx_threshold_dbm: number;
  rain_rate_mmh: number;
}

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}
