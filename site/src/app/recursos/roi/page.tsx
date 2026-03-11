import type { Metadata } from 'next';
import Section from '@/components/ui/Section';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Calculadora de ROI — Pulso Network',
  description: 'Retorno sobre investimento para provedores de internet: 3 casos de uso com ROI de 3,3x a 111x.',
};

export default function ROIPage() {
  return (
    <>
      {/* Header — Dark */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Calculadora de ROI
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-5xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Retorno mensurável.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>3 casos de uso reais.</span>
          </h1>
          <p className="mt-5 text-base leading-relaxed max-w-2xl" style={{ color: 'var(--text-on-dark-secondary)' }}>
            Cada caso compara o custo da assinatura com o valor gerado ou perda evitada.
            Dados reais: 13.534 provedores, 5.572 municípios, 4,1M registros de assinantes.
          </p>
        </div>
      </Section>

      {/* Case 1: ISP Expansion — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Caso 1
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Expansão de ISP de médio porte
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          Um ISP com 8.000 assinantes no interior de São Paulo planeja investir R$2.000.000 em expansão de fibra para um novo município.
        </p>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          {/* Without Pulso */}
          <div className="p-6" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Sem Pulso (decisão tradicional)
            </h3>
            <ul className="space-y-3">
              {[
                { step: 'Pesquisa de mercado', detail: 'Planilhas manuais, dados desatualizados — 40h' },
                { step: 'Análise competitiva', detail: 'Ligações para conhecidos — incompleta' },
                { step: 'Projeto de rede', detail: 'Google Maps — sem terreno real, sem BOM' },
                { step: 'Viabilidade', detail: 'Excel com premissas otimistas — viés de confirmação' },
              ].map((item) => (
                <li key={item.step} className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{item.step}:</span>{' '}
                  {item.detail}
                </li>
              ))}
            </ul>
            <div className="mt-4 p-3 text-sm font-medium" style={{ background: 'var(--bg-surface)', color: 'var(--error, #dc2626)' }}>
              Risco: R$2.000.000 em CAPEX comprometido em município saturado
            </div>
          </div>

          {/* With Pulso */}
          <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--accent)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Com Pulso (Tier Provedor — R$1.500/mes)
            </h3>
            <ul className="space-y-3">
              {[
                { step: 'Ranking de municípios', detail: '5.572 municípios por composite score' },
                { step: 'Validação de mercado', detail: 'HHI, shares, tendência — confirmar oportunidade' },
                { step: 'Rota de fibra', detail: 'Dijkstra sobre 6,4M segmentos + BOM' },
                { step: 'Análise financeira', detail: 'NPV, IRR, payback com 3 cenários' },
              ].map((item) => (
                <li key={item.step} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                  <span><span className="font-medium" style={{ color: 'var(--text-primary)' }}>{item.step}:</span> {item.detail}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 p-3 text-sm font-medium" style={{ background: 'var(--bg-primary)', color: 'var(--success)' }}>
              Resultado: R$2M de CAPEX protegido
            </div>
          </div>
        </div>

        {/* ROI Table */}
        <div className="mt-10 overflow-x-auto max-w-2xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <tbody>
              {[
                { metric: 'Custo anual (Provedor)', value: 'R$18.000', highlight: false },
                { metric: 'Perda evitada (CAPEX em município errado)', value: 'R$2.000.000', highlight: false },
                { metric: 'ROI máximo', value: '111x', highlight: true },
                { metric: 'ROI conservador (10% do CAPEX)', value: '11x', highlight: true },
                { metric: 'ROI ultra-conservador (3% do CAPEX)', value: '3,3x', highlight: true },
              ].map((row) => (
                <tr key={row.metric} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.metric}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: row.highlight ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {row.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Time savings */}
        <div className="mt-8 overflow-x-auto max-w-3xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Atividade</th>
                <th className="px-4 py-3 text-right font-medium" style={{ color: 'var(--text-muted)' }}>Sem Pulso</th>
                <th className="px-4 py-3 text-right font-medium" style={{ color: 'var(--accent)' }}>Com Pulso</th>
                <th className="px-4 py-3 text-right font-medium" style={{ color: 'var(--text-primary)' }}>Economia</th>
              </tr>
            </thead>
            <tbody>
              {[
                { activity: 'Pesquisa de mercado', without: '40h', with: '2h', savings: '38h' },
                { activity: 'Análise competitiva', without: '16h', with: '0,5h', savings: '15,5h' },
                { activity: 'Projeto de rede', without: '24h', with: '1h', savings: '23h' },
                { activity: 'Viabilidade financeira', without: '16h', with: '0,5h', savings: '15,5h' },
                { activity: 'Total', without: '96h', with: '4h', savings: '92h (96%)' },
              ].map((row) => (
                <tr
                  key={row.activity}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: row.activity === 'Total' ? 'var(--bg-surface)' : undefined,
                  }}
                >
                  <td className="px-4 py-3" style={{ color: row.activity === 'Total' ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {row.activity === 'Total' ? <strong>{row.activity}</strong> : row.activity}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{row.without}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--accent)' }}>{row.with}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: 'var(--success)' }}>{row.savings}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Case 2: Regulatory Compliance — Subtle */}
      <Section background="subtle">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Caso 2
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Conformidade regulatória
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          ISP com 4.800 assinantes próximo ao threshold de 5.000 da Anatel. Opera em 3 estados (SP, MG, PR) com receita mensal de R$480.000.
        </p>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Riscos sem Pulso
            </h3>
            <ul className="space-y-3">
              {[
                { risk: 'Multa por operar sem autorização', impact: 'R$50.000 - R$100.000' },
                { risk: 'Impacto ICMS Norma no. 4', impact: 'R$57.600/ano' },
                { risk: 'Multa por não cumprimento RQual', impact: 'R$20.000 - R$50.000' },
                { risk: 'Perda de deadline regulatório', impact: 'R$30.000 + advocatícios' },
              ].map((item) => (
                <li key={item.risk} className="flex justify-between text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span>{item.risk}</span>
                  <span className="font-mono shrink-0 ml-4" style={{ color: 'var(--error, #dc2626)' }}>{item.impact}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="flex justify-between text-sm font-bold">
                <span style={{ color: 'var(--text-primary)' }}>Exposição total anual</span>
                <span className="font-mono" style={{ color: 'var(--error, #dc2626)' }}>R$100K - R$260K</span>
              </div>
            </div>
          </div>

          <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--accent)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Prevenção com Pulso (Provedor — R$1.500/mes)
            </h3>
            <ul className="space-y-3">
              {[
                { feature: 'Licensing check (threshold 5K)', result: 'Alerta 6 meses antes' },
                { feature: 'Norma no. 4 multi-estado', result: 'Otimização ICMS blended' },
                { feature: 'Quality check vs. thresholds', result: 'Identificação prévia de gaps' },
                { feature: 'Calendário de deadlines', result: 'Alertas com urgência categorizada' },
              ].map((item) => (
                <li key={item.feature} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                  <span><span className="font-medium" style={{ color: 'var(--text-primary)' }}>{item.feature}:</span> {item.result}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 overflow-x-auto max-w-2xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <tbody>
              {[
                { metric: 'Custo anual (Provedor)', value: 'R$18.000', highlight: false },
                { metric: 'Multa evitada (cenário base)', value: 'R$100.000', highlight: false },
                { metric: 'ROI (multa evitada)', value: '5,5x', highlight: true },
                { metric: 'ROI total (multa + ICMS + tempo)', value: '7,5x', highlight: true },
              ].map((row) => (
                <tr key={row.metric} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.metric}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: row.highlight ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {row.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Case 3: M&A — Surface */}
      <Section background="surface">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Caso 3
        </div>
        <h2 className="font-serif text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Avaliação de targets para M&A
        </h2>
        <p className="text-sm leading-relaxed mb-8 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
          ISP grande (50.000 assinantes, SP) busca adquirir ISPs regionais em SP, MG e PR.
        </p>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div className="p-6" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Due diligence tradicional
            </h3>
            <ul className="space-y-3">
              {[
                { item: 'Consultoria para 1 target', cost: 'R$80K - R$150K' },
                { item: 'Dados de mercado (por target)', cost: 'R$15K' },
                { item: 'Avaliação financeira (por target)', cost: 'R$25K' },
                { item: 'Due diligence técnica (por target)', cost: 'R$30K' },
              ].map((row) => (
                <li key={row.item} className="flex justify-between text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span>{row.item}</span>
                  <span className="font-mono shrink-0 ml-4" style={{ color: 'var(--text-muted)' }}>{row.cost}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="flex justify-between text-sm font-bold">
                <span style={{ color: 'var(--text-primary)' }}>Para 10 targets</span>
                <span className="font-mono" style={{ color: 'var(--error, #dc2626)' }}>R$1,5M - R$2,2M</span>
              </div>
            </div>
          </div>

          <div className="p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--accent)' }}>
            <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Com Pulso (Profissional — R$5.000/mes)
            </h3>
            <ul className="space-y-3">
              {[
                { feature: 'Target discovery', result: '50+ targets rankeados — 30 segundos' },
                { feature: '3 métodos de valuation', result: 'Subscriber, revenue, DCF — 5s/target' },
                { feature: 'Enriquecimento CNPJ', result: 'Capital social, socios, CNAE — automático' },
                { feature: 'Contratos + BNDES', result: 'Histórico governamental integrado' },
              ].map((item) => (
                <li key={item.feature} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <span className="mt-0.5 text-xs" style={{ color: 'var(--success)' }}>&#10003;</span>
                  <span><span className="font-medium" style={{ color: 'var(--text-primary)' }}>{item.feature}:</span> {item.result}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 p-3 text-sm font-medium" style={{ background: 'var(--bg-primary)', color: 'var(--success)' }}>
              10 targets avaliados em 1 hora
            </div>
          </div>
        </div>

        <div className="mt-10 overflow-x-auto max-w-2xl" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <tbody>
              {[
                { metric: 'Custo anual (Profissional)', value: 'R$60.000', highlight: false },
                { metric: 'Due diligence manual (10 targets)', value: 'R$1.500.000', highlight: false },
                { metric: 'Economia direta', value: 'R$1.439.500', highlight: false },
                { metric: 'Múltiplo de retorno', value: '24x', highlight: true },
              ].map((row) => (
                <tr key={row.metric} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.metric}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: row.highlight ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {row.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Quality comparison */}
        <div className="mt-8 overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Aspecto</th>
                <th className="px-4 py-3 text-center font-medium" style={{ color: 'var(--text-muted)' }}>DD Manual</th>
                <th className="px-4 py-3 text-center font-medium" style={{ color: 'var(--accent)' }}>Pulso</th>
              </tr>
            </thead>
            <tbody>
              {[
                { aspect: 'Targets avaliados', manual: '1-3', pulso: '50+' },
                { aspect: 'Dados de mercado', manual: 'Snapshot pontual', pulso: 'Atualizados mensalmente' },
                { aspect: 'Cobertura geográfica', manual: 'Estado único', pulso: 'Nacional (27 UFs)' },
                { aspect: 'Métodos de avaliação', manual: '1 método', pulso: '3 métodos' },
                { aspect: 'Enriquecimento CNPJ', manual: 'Manual, 5 dias', pulso: 'Automático' },
                { aspect: 'Risco de perder melhor target', manual: 'Alto', pulso: 'Mínimo' },
              ].map((row) => (
                <tr key={row.aspect} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.aspect}</td>
                  <td className="px-4 py-3 text-center" style={{ color: 'var(--text-muted)' }}>{row.manual}</td>
                  <td className="px-4 py-3 text-center font-medium" style={{ color: 'var(--accent)' }}>{row.pulso}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Summary — Primary */}
      <Section background="primary">
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
          Resumo
        </div>
        <h2 className="font-serif text-2xl font-bold mb-8" style={{ color: 'var(--text-primary)' }}>
          Comparativo dos 3 casos
        </h2>
        <div className="overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Caso de uso</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: 'var(--text-primary)' }}>Tier</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Custo anual</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--text-primary)' }}>Valor protegido</th>
                <th className="px-4 py-3 text-right font-mono font-medium" style={{ color: 'var(--accent)' }}>ROI</th>
              </tr>
            </thead>
            <tbody>
              {[
                { case: 'Expansão', tier: 'Provedor', cost: 'R$18K', value: 'R$60K - R$2M', roi: '3,3x - 111x' },
                { case: 'Conformidade', tier: 'Provedor', cost: 'R$18K', value: 'R$100K - R$136K', roi: '5,5x - 7,5x' },
                { case: 'M&A', tier: 'Profissional', cost: 'R$60K', value: 'R$1.440K', roi: '24x' },
              ].map((row) => (
                <tr key={row.case} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{row.case}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{row.tier}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{row.cost}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{row.value}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: 'var(--accent)' }}>{row.roi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-8 max-w-2xl">
          <h3 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Payback period</h3>
          <div className="space-y-2">
            {[
              { tier: 'Provedor (R$1.500/mes)', payback: '< 1 mes (evitando 1 erro de R$60K)' },
              { tier: 'Profissional (R$5.000/mes)', payback: '< 1 mes (substituindo 1 consultoria de R$150K)' },
            ].map((row) => (
              <div key={row.tier} className="flex items-baseline gap-3 text-sm">
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{row.tier}:</span>
                <span style={{ color: 'var(--text-secondary)' }}>{row.payback}</span>
              </div>
            ))}
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
            Payback em menos de 1 mes.{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>Comece gratuitamente.</span>
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/cadastro" className="pulso-btn-dark">
              Criar conta gratuita
            </Link>
            <Link href="/recursos" className="pulso-btn-ghost">
              Voltar a recursos
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
