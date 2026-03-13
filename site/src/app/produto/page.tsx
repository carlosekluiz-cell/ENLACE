import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';
import {
  Map, BarChart3, Radio, Shield, CloudRain, TreePine,
  Satellite, Building2, Brain, Layers, Wifi, Globe, Award, GitCompareArrows,
  Cable, Gauge, ShieldCheck, Radiation, CreditCard, TowerControl, FileSearch, Hexagon, History,
} from 'lucide-react';

export const metadata: Metadata = {
  title: 'Produto — Pulso Network',
  description: '25 módulos de inteligência telecom para provedores de internet brasileiros. Expansão, M&A, RF, conformidade, análise espacial e mais.',
  alternates: { canonical: 'https://pulso.network/produto' },
};

const modules = [
  {
    icon: Map,
    title: 'Expansão',
    description: 'Scoring de oportunidade por município. Identifique onde expandir com base em variáveis demográficas, econômicas, competitivas e geográficas cruzadas automaticamente.',
    metric: '5.572 municípios ranqueados',
    highlights: ['Score proprietário com 15+ variáveis', 'Filtros por estado, população, HHI', 'Projeção de assinantes potenciais'],
  },
  {
    icon: BarChart3,
    title: 'Concorrência',
    description: 'Análise competitiva real por município. Mapeamento de market share por provedor, índice HHI e tendências de concentração de mercado.',
    metric: '13.534 provedores rastreados',
    highlights: ['Market share por provedor (Anatel STEL)', 'Índice HHI de concentração', 'Mapeamento de ERBs e outorgas'],
  },
  {
    icon: Radio,
    title: 'Projeto RF',
    description: 'Planejamento de enlaces wireless com dados de elevação reais. Link budget, perfil de terreno e conformidade com limites de potência.',
    metric: 'Resolução de 30m (SRTM/NASA)',
    highlights: ['Perfil de terreno entre pontos', 'Clearance de zona de Fresnel', 'Conformidade EIRP automática'],
  },
  {
    icon: Shield,
    title: 'Conformidade',
    description: 'Monitoramento de obrigações regulatórias Anatel. Prazos, documentação e indicadores de qualidade por faixa de assinantes.',
    metric: 'Alertas automáticos de prazo',
    highlights: ['Norma n.4 SCM por faixa', 'Prazos de licenciamento', 'Indicadores ABNT/Anatel'],
  },
  {
    icon: CloudRain,
    title: 'Saúde da Rede',
    description: 'Correlação climática com dados de 671 estações INMET, benchmarking de qualidade vs peers e priorização de manutenção.',
    metric: '671 estações meteo integradas',
    highlights: ['Risco climático por região', 'Qualidade vs concorrentes', 'Priorização por impacto em receita'],
  },
  {
    icon: TreePine,
    title: 'Rural',
    description: 'Elegibilidade para programas de financiamento público, scoring de infraestrutura rural e identificação de áreas desatendidas.',
    metric: '2.700+ municípios rurais mapeados',
    highlights: ['Elegibilidade PNBL/PGMU', 'Áreas desatendidas Anatel', 'Scoring de infraestrutura'],
  },
  {
    icon: Satellite,
    title: 'Satélite',
    description: 'Índices urbanos derivados de imagens Sentinel-2 da ESA. Análise de uso do solo, cobertura vegetal, expansão urbana e correlação com demanda de conectividade.',
    metric: 'Resolução de 10m (Sentinel-2)',
    highlights: ['NDVI e índices de vegetação', 'Detecção de expansão urbana', 'Correlação com demanda de banda larga'],
  },
  {
    icon: Building2,
    title: 'M&A',
    description: 'Valuation de provedores com due diligence automatizada: dívidas PGFN, grafo societário (Receita Federal), sanções e reclamações. Simulação de aquisições e projeções.',
    metric: '13.534 ISPs avaliados',
    highlights: ['Due diligence: dívidas, sócios, sanções', 'Grafo de propriedade cruzada (783K vínculos)', 'Valuation + projeções financeiras 5 anos'],
  },
  {
    icon: Brain,
    title: 'Inteligência',
    description: 'Análise preditiva de mercado combinando todas as fontes de dados. Alertas automáticos de oportunidade, risco e tendências de mercado.',
    metric: 'Machine learning sobre 38+ fontes',
    highlights: ['Alertas de oportunidade', 'Predição de churn por município', 'Tendências de mercado automatizadas'],
  },
  {
    icon: Layers,
    title: 'Análise Espacial',
    description: 'Clustering espacial DBSCAN, detecção de hotspots Getis-Ord e autocorrelação Moran\'s I sobre dados georreferenciados de telecomunicações.',
    metric: 'Clustering + Hotspots',
    highlights: ['DBSCAN clustering espacial', 'Hotspot detection Getis-Ord', 'Autocorrelação Moran\'s I'],
  },
  {
    icon: Wifi,
    title: 'Índice Starlink',
    description: 'Score de vulnerabilidade por município e provedor frente à expansão da Starlink no mercado brasileiro de banda larga.',
    metric: 'Threat scoring por município',
    highlights: ['Índice de ameaça municipal', 'Vulnerabilidade por provedor', 'Recomendações de mitigação'],
  },
  {
    icon: Radio,
    title: 'FWA vs Fibra',
    description: 'Calculadora de decisão tecnológica comparando FWA e fibra óptica com análise de TCO, ROI e cenários por densidade.',
    metric: 'Decisão tecnológica',
    highlights: ['Comparação TCO 5 anos', 'Análise por densidade demográfica', 'Cenários de ROI automatizados'],
  },
  {
    icon: Globe,
    title: 'Peering & IX.br',
    description: 'Inteligência de interconexão com dados de 34K+ redes PeeringDB e 37 IXPs brasileiros (IX.br/NIC.br).',
    metric: '34K+ redes mapeadas',
    highlights: ['34K+ redes PeeringDB', '37 IXPs brasileiros', 'Histórico de tráfego'],
  },
  {
    icon: Award,
    title: 'Pulso Score',
    description: 'Scoring proprietário de saúde do provedor combinando crescimento, qualidade de serviço, cobertura e indicadores financeiros.',
    metric: '13.534 provedores scored',
    highlights: ['Score 0-100 multi-fator', 'Benchmarking vs pares', 'Tendência histórica'],
  },
  {
    icon: GitCompareArrows,
    title: 'Análise Cruzada',
    description: 'Correlações multi-dimensionais entre competição, cobertura, emprego e clima. Detecção de anomalias com pyod e scoring de investimento.',
    metric: '10 endpoints analíticos',
    highlights: ['HHI e gaps de cobertura', 'Detecção de anomalias (pyod)', 'Score de prioridade de investimento'],
  },
  {
    icon: Cable,
    title: 'Backhaul',
    description: 'Modelagem de capacidade de backhaul e previsão de congestionamento para planejamento de rede com projeções de demanda e simulação de cenários.',
    metric: 'Modelagem de capacidade',
    highlights: ['Modelagem de capacidade de link', 'Previsão de congestionamento', 'Simulação de cenários de upgrade'],
  },
  {
    icon: Gauge,
    title: 'Velocidade',
    description: 'Rankings de velocidade Ookla por município com dados de download, upload e latência. Benchmarking de performance contra concorrentes por região.',
    metric: 'Rankings por município',
    highlights: ['Download, upload e latência', 'Rankings Ookla por município', 'Benchmarking vs concorrentes'],
  },
  {
    icon: ShieldCheck,
    title: 'Obrigações 5G',
    description: 'Rastreamento de obrigações de cobertura 5G com prazos regulatórios, acompanhamento de metas e status de conformidade por operadora.',
    metric: 'Rastreamento de prazos',
    highlights: ['Rastreamento de cobertura 5G', 'Prazos regulatórios Anatel', 'Status de conformidade por operadora'],
  },
  {
    icon: Radiation,
    title: 'Espectro',
    description: 'Valuation de licenças de espectro e mapeamento de holdings por operadora. Análise de oportunidades em faixas de frequência para estratégia de M&A.',
    metric: 'Valuation de licenças',
    highlights: ['Valuation de licenças de espectro', 'Holdings por operadora', 'Análise de faixas de frequência'],
  },
  {
    icon: CreditCard,
    title: 'Crédito ISP',
    description: 'Credit scoring de provedores com classificação AAA a CCC e modelo de probabilidade de default (PD). Avaliação de risco para financiamento e parcerias.',
    metric: 'Scoring AAA–CCC',
    highlights: ['Classificação AAA a CCC', 'Modelo de probabilidade de default', 'Avaliação de risco financeiro'],
  },
  {
    icon: TowerControl,
    title: 'Compartilhamento de Torres',
    description: 'Identificação de oportunidades de colocation em torres existentes. Análise de proximidade, capacidade disponível e potencial de compartilhamento de infraestrutura.',
    metric: 'Oportunidades de colocation',
    highlights: ['Colocation em torres existentes', 'Análise de proximidade', 'Potencial de compartilhamento'],
  },
  {
    icon: FileSearch,
    title: 'Raio-X do Provedor',
    description: 'Relatório completo por provedor com posição competitiva, dívidas fiscais, selos Anatel, publicações em diário oficial, BNDES e espectro. Gratuito + premium.',
    metric: 'Relatório gratuito + premium',
    highlights: ['Posição competitiva nacional + dívidas PGFN', 'Selos de qualidade Anatel + diário oficial', 'BNDES, espectro e reclamações'],
  },
  {
    icon: Hexagon,
    title: 'Hex Grid',
    description: 'Visualização hexagonal H3 com métricas por célula. Análise granular de cobertura, demanda e infraestrutura em resolução espacial superior ao município.',
    metric: 'Resolução H3 hexagonal',
    highlights: ['Grid H3 com métricas por célula', 'Análise granular de cobertura', 'Resolução superior ao município'],
  },
  {
    icon: History,
    title: 'Histórico',
    description: 'Evolução de 37 meses de dados por provedor e município. Tendências de crescimento, sazonalidade e análise temporal de market share e assinantes.',
    metric: '37 meses de evolução',
    highlights: ['Evolução por provedor e município', 'Tendências de crescimento', 'Análise de sazonalidade'],
  },
];

export default function ProdutoPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Plataforma
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            25 módulos.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Uma plataforma.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Cada módulo resolve um problema específico do ciclo de decisão de um provedor
            de internet. Todos operam sobre a mesma base integrada com 38+ fontes de dados públicos.
          </p>
        </div>
      </Section>

      {/* Modules — Light */}
      <Section background="primary">
        <div className="space-y-0">
          {modules.map((mod, i) => {
            const Icon = mod.icon;
            const isEven = i % 2 === 0;
            return (
              <div
                key={mod.title}
                className="grid grid-cols-1 gap-8 py-12 md:grid-cols-2 md:items-start"
                style={{ borderBottom: i < modules.length - 1 ? '1px solid var(--border)' : 'none' }}
              >
                <div className={isEven ? '' : 'md:order-2'}>
                  <div className="flex items-center gap-3 mb-4">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center"
                      style={{ border: '1px solid var(--border-strong)', color: 'var(--accent)' }}
                    >
                      <Icon size={18} />
                    </div>
                    <h3 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {mod.title}
                    </h3>
                  </div>
                  <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {mod.description}
                  </p>
                  <div className="mt-3 font-mono text-xs" style={{ color: 'var(--accent)' }}>
                    {mod.metric}
                  </div>
                </div>
                <div className={isEven ? '' : 'md:order-1'}>
                  {/* Feature highlights */}
                  <div className="p-6" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                    <ul className="space-y-3">
                      {mod.highlights.map((h) => (
                        <li key={h} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                          <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                          {h}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Architecture — Subtle */}
      <Section background="subtle">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-2 md:items-start">
          <div>
            <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Arquitetura
            </div>
            <h2 className="font-serif text-2xl font-bold" style={{ color: 'var(--text-primary)', lineHeight: 1.1 }}>
              Base unificada.{' '}
              <span style={{ color: 'var(--text-muted)' }}>Cruzamento instantâneo.</span>
            </h2>
          </div>
          <div>
            <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Todos os módulos operam sobre uma base indexada pelo código IBGE de 7 dígitos.
              Dados demográficos, regulatórios, geográficos e climáticos cruzados automaticamente.
              Ingestão mensal automatizada.
            </p>
          </div>
        </div>
      </Section>

      {/* CTA — Dark */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-2xl font-bold"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Veja os módulos em ação.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Acesso gratuito ao mapa e dados básicos.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark">
              Entrar na lista de espera
            </Link>
            <Link href="/precos" className="pulso-btn-ghost">
              Ver planos
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
