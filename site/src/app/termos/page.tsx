import type { Metadata } from 'next';
import Section from '@/components/ui/Section';

export const metadata: Metadata = {
  title: 'Termos de Uso',
  description: 'Termos de uso da plataforma Pulso Network.',
  alternates: { canonical: 'https://pulso.network/termos' },
};

export default function TermosPage() {
  return (
    <>
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
            Legal
          </div>
          <h1
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
          >
            Termos de Uso
          </h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-muted)' }}>
            Ultima atualizacao: 16 de marco de 2026
          </p>
        </div>
      </Section>

      <Section background="primary">
        <div className="max-w-3xl space-y-8">
          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>1. Aceitacao dos Termos</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Ao acessar ou utilizar a plataforma Pulso Network (&quot;Plataforma&quot;), operada por Pulso Network Tecnologia Ltda. (&quot;Pulso&quot;, &quot;nos&quot;), voce concorda com estes Termos de Uso. Se voce nao concordar, nao utilize a Plataforma.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>2. Descricao do Servico</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso e uma plataforma de inteligencia de mercado para o setor de telecomunicacoes brasileiro. Agregamos e processamos dados de fontes publicas — incluindo Anatel, IBGE, INMET, NASA/SRTM, DataSUS, INEP, SNIS, ANP, BNDES, PNCP e OpenStreetMap — para gerar analises, scores e visualizacoes. Os dados apresentados sao publicos e agregados por municipio; nao coletamos nem exibimos dados individuais de assinantes.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>3. Classificacao de Servicos e Niveis de Acesso</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              A Plataforma oferece tres niveis de acesso, cada um com escopo e responsabilidades distintas:
            </p>
            <div className="space-y-4">
              <div className="rounded-lg p-4" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>3.1. Acesso Livre (Publico)</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  Inclui funcionalidades de consulta a dados publicos agregados, como mapa de municipios, Raio-X basico do provedor (com dados anonimizados), qualidade ANATEL, obrigacoes 5G e tendencias historicas nacionais. Nao requer cadastro. Os dados exibidos sao consolidacoes de fontes publicas, sem tratamento individualizado.
                </p>
              </div>
              <div className="rounded-lg p-4" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>3.2. Acesso Autenticado (Planos Pagos)</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  Requer cadastro e assinatura. Inclui analise de concorrencia, ranking de provedores, oportunidades de expansao, projetos de rede, conformidade regulatoria e relatorios exportaveis. Os dados sao apresentados como referencia informativa e nao constituem recomendacao de investimento, parecer tecnico ou consultoria profissional.
                </p>
              </div>
              <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--accent) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)' }}>
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>3.3. Servicos Contratados (Termo Especifico)</h3>
                <p className="text-sm leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>
                  Funcionalidades sensiveis estao disponiveis exclusivamente mediante contratacao especifica, com termo de adesao assinado, identificacao do CNPJ contratante e declaracao de finalidade. Incluem:
                </p>
                <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Valuation de ISPs (modelos DCF, multiplos, por assinante)</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Due Diligence completa (fiscal, societaria, sancoes, reclamacoes)</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Credit Scoring e rating de solvencia (AAA-CCC)</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Targets de aquisicao e analise de sinergias M&amp;A</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Seller intelligence e preparacao para venda</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Detalhamento de divida ativa PGFN e financiamentos BNDES</li>
                  <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Agente Pulso (telemetria operacional de rede)</li>
                </ul>
                <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  Os relatorios e dados gerados neste nivel sao entregues exclusivamente ao CNPJ contratante, com clausula de nao redistribuicao e acordo de confidencialidade (NDA). O acesso e auditado (log de consultas).
                </p>
              </div>
            </div>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>4. Cadastro e Conta</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Para acessar funcionalidades alem do plano gratuito, e necessario criar uma conta com informacoes verdadeiras. Voce e responsavel por manter a confidencialidade das suas credenciais de acesso. Cada conta e de uso pessoal e intransferivel, salvo contas multi-usuario nos planos Profissional e Empresa. Reservamo-nos o direito de suspender contas que violem estes termos ou que apresentem atividade anomala.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>5. Planos e Pagamento</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso oferece planos gratuito e pagos, conforme descrito na pagina de Precos. Planos pagos sao cobrados mensalmente, sem fidelidade. O cancelamento pode ser feito a qualquer momento e tera efeito ao final do ciclo de faturamento vigente. Aceitamos pagamento via PIX, boleto bancario e cartao de credito. Servicos Contratados (secao 3.3) possuem faturamento e termos de pagamento proprios, definidos no respectivo contrato.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>6. Uso dos Dados e Restricoes</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Os dados disponibilizados na Plataforma sao derivados de fontes publicas e apresentados no estado em que se encontram (&quot;as is&quot;). O Pulso nao garante a exatidao, completude ou atualidade dos dados de terceiros.
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Os dados podem ser utilizados para analise interna e tomada de decisao do contratante.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> E expressamente proibida a redistribuicao comercial, revenda, sublicenciamento ou publicacao dos dados sem autorizacao previa por escrito.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Dados importados pelo cliente permanecem de propriedade do cliente e sao tratados conforme nossa Politica de Privacidade.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> E vedado o uso dos dados para praticas de concorrencia desleal, assedio comercial ou targeting abusivo de provedores.</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>7. Natureza dos Scores e Analises</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Os scores, ratings, valuations e analises gerados pela Plataforma sao indicadores baseados em dados publicos e modelos proprietarios. E fundamental observar que:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Nao constituem recomendacao de investimento</strong>, parecer juridico, laudo de avaliacao formal ou consultoria financeira.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>O Credit Scoring nao configura atividade de bureau de credito</strong> nos termos da Lei 12.414/2011 (Cadastro Positivo). Os scores sao indicadores internos para uso do contratante, nao sendo compartilhados com terceiros ou utilizados para concessao de credito.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Valuations sao estimativas indicativas</strong> baseadas em dados publicos e nao substituem laudos de avaliacao elaborados por profissionais habilitados (CVM, CRC).</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Relatorios de Due Diligence consolidam informacoes publicas</strong> e nao substituem due diligence juridica conduzida por advogados ou auditores independentes.</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>8. Propriedade Intelectual</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              A Plataforma, incluindo seu codigo-fonte, algoritmos de scoring, modelos de propagacao RF, interface e marca, sao propriedade do Pulso. Relatorios e analises gerados para o cliente podem ser utilizados livremente pelo cliente, mas a metodologia subjacente permanece propriedade do Pulso.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>9. Limitacao de Responsabilidade</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso nao se responsabiliza por decisoes de negocio, investimento, aquisicao ou desinvestimento tomadas com base nos dados da Plataforma. Os scores de oportunidade, credit ratings, valuations, analises de mercado e projecoes sao indicadores baseados em dados publicos e nao constituem garantia de resultado. Em nenhuma hipotese a responsabilidade do Pulso excedera o valor pago pelo cliente nos 12 meses anteriores ao evento.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>10. Disponibilidade</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Nos esforcamos para manter a Plataforma disponivel 24/7, com SLA de 99,9% para clientes do plano Empresa. Manutencoes programadas serao comunicadas com 48 horas de antecedencia. Nao nos responsabilizamos por indisponibilidades causadas por fatores externos (provedores de infraestrutura, APIs de terceiros, eventos de forca maior).
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>11. Alteracoes</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Podemos atualizar estes Termos periodicamente. Alteracoes materiais serao notificadas por e-mail com 30 dias de antecedencia. O uso continuado da Plataforma apos a notificacao constitui aceitacao dos novos termos.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>12. Foro e Legislacao</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Estes Termos sao regidos pela legislacao brasileira. Fica eleito o foro da comarca de Sao Paulo/SP para dirimir quaisquer controversias.
            </p>
          </div>

          <div className="pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Duvidas sobre os Termos de Uso? Entre em contato pelo e-mail legal@pulso.network.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
