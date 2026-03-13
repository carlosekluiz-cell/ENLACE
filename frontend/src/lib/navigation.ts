import {
  Map,
  TrendingUp,
  Users,
  Antenna,
  Shield,
  Activity,
  Mountain,
  Satellite,
  FileText,
  BookMarked,
  Building2,
  Hexagon,
  Gauge,
  Share2,
  Bell,
  Search,
  LineChart,
  Award,
  CreditCard,
  Layers,
  Wifi,
  Zap,
  Globe,
  CloudRain,
  Radio,
  GitCompareArrows,
  Clock,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string; // "NEW", "BETA", etc.
  minRole?: string;
}

export interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    id: 'market',
    label: 'Inteligência de Mercado',
    items: [
      { label: 'Mapa', href: '/', icon: Map },
      { label: 'Expansão', href: '/expansao', icon: TrendingUp },
      { label: 'Concorrência', href: '/concorrencia', icon: Users },
      { label: 'Research', href: '/research', icon: BookMarked },
      { label: 'Velocidade', href: '/velocidade', icon: Gauge, badge: 'NEW' },
      { label: 'Hex Grid', href: '/hexgrid', icon: Hexagon, badge: 'NEW' },
      { label: 'Análise Espacial', href: '/espacial', icon: Layers, badge: 'NEW' },
      { label: 'Índice Starlink', href: '/starlink', icon: Wifi, badge: 'NEW' },
    ],
  },
  {
    id: 'infra',
    label: 'Infraestrutura',
    items: [
      { label: 'Projeto RF', href: '/projeto', icon: Antenna },
      { label: 'Satélite', href: '/satelite', icon: Satellite },
      { label: 'Fibra', href: '/fibra', icon: Building2, badge: 'NEW' },
      { label: 'Cobertura', href: '/compartilhamento', icon: Share2, badge: 'NEW' },
      { label: 'FWA vs Fibra', href: '/fwa-fiber', icon: Radio, badge: 'NEW' },
      { label: 'Backhaul', href: '/backhaul', icon: Zap, badge: 'NEW' },
      { label: 'Risco Climático', href: '/risco-clima', icon: CloudRain, badge: 'NEW' },
      { label: 'Peering', href: '/peering', icon: Globe, badge: 'NEW' },
      { label: 'IX.br', href: '/ixp', icon: Zap, badge: 'NEW' },
    ],
  },
  {
    id: 'compliance',
    label: 'Conformidade',
    items: [
      { label: 'Conformidade', href: '/conformidade', icon: Shield },
      { label: 'Obrigações 5G', href: '/obrigacoes', icon: Shield, badge: 'NEW' },
    ],
  },
  {
    id: 'mna',
    label: 'M&A & Finanças',
    items: [
      { label: 'M&A', href: '/mna', icon: LineChart },
      { label: 'Pulso Score', href: '/provedor', icon: Award, badge: 'NEW' },
      { label: 'Crédito ISP', href: '/credito', icon: CreditCard, badge: 'NEW' },
    ],
  },
  {
    id: 'rural',
    label: 'Rural & Social',
    items: [
      { label: 'Rural', href: '/rural', icon: Mountain },
      { label: 'Saúde', href: '/saude', icon: Activity },
    ],
  },
  {
    id: 'data',
    label: 'Dados & AI',
    items: [
      { label: 'Relatórios', href: '/relatorios', icon: FileText },
      { label: 'Consulta SQL', href: '/consulta', icon: Search, badge: 'NEW' },
      { label: 'Alertas', href: '/alertas', icon: Bell, badge: 'NEW' },
      { label: 'Análise Cruzada', href: '/analise', icon: GitCompareArrows, badge: 'NEW' },
      { label: 'Histórico', href: '/historico', icon: Clock, badge: 'NEW' },
    ],
  },
];

/**
 * Find which section contains the current path.
 * Returns the section id, or null if not found.
 */
export function findSectionForPath(pathname: string): string | null {
  for (const section of navSections) {
    for (const item of section.items) {
      if (item.href === '/') {
        if (pathname === '/') return section.id;
      } else {
        if (pathname === item.href || pathname.startsWith(item.href + '/')) {
          return section.id;
        }
      }
    }
  }
  return null;
}
