// TypeScript types matching ENLACE backend schemas

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
  municipality_name: string;
  state_abbrev: string;
  total_subscribers: number;
  fiber_subscribers: number;
  provider_count: number;
  broadband_penetration_pct: number;
  median_speed_mbps?: number;
  avg_arpu?: number;
}

export interface HeatmapCell {
  lat: number;
  lng: number;
  value: number;
  municipality_code?: string;
}

export interface ComplianceRegulation {
  id: number;
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

export interface Norma4Impact {
  state: string;
  subscribers: number;
  revenue_monthly: number;
  estimated_fund_contribution: number;
  compliance_requirements: string[];
  risk_level: 'low' | 'medium' | 'high';
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
  technology_mix: string[];
  estimated_cost: number;
  solar_capacity_kw?: number;
  battery_kwh?: number;
  coverage_pct: number;
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

export interface ReportRequest {
  report_type: 'market' | 'expansion' | 'compliance' | 'rural';
  parameters: Record<string, string | number | boolean>;
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

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}
