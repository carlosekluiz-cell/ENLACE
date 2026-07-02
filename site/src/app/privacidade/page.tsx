import type { Metadata } from 'next';
import Section from '@/components/ui/Section';

export const metadata: Metadata = {
  title: 'Politica de Privacidade',
  description: 'Politica de privacidade e conformidade LGPD da plataforma Pulso Network.',
  alternates: { canonical: 'https://pulso.network/privacidade' },
};

export default function PrivacidadePage() {
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
            Politica de Privacidade
          </h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-muted)' }}>
            Ultima atualizacao: 16 de marco de 2026
          </p>
        </div>
      </Section>

      <Section background="primary">
        <div className="max-w-3xl space-y-8">
          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>1. Introducao</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Esta Politica de Privacidade descreve como a Pulso Network Tecnologia Ltda. (&quot;Pulso&quot;) coleta, utiliza, armazena e protege dados pessoais em conformidade com a Lei Geral de Protecao de Dados (LGPD — Lei n. 13.709/2018).
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>2. Dados Coletados</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Coletamos os seguintes dados pessoais no momento do cadastro:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Nome completo</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Endereco de e-mail</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Nome da empresa / ISP</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Estado de atuacao</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Faixa de assinantes (dado opcional)</li>
            </ul>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Durante o uso da Plataforma, coletamos dados de navegacao (paginas acessadas, funcionalidades utilizadas) para fins de melhoria do servico. Nao coletamos dados sensiveis conforme definidos pela LGPD.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>3. Finalidade do Tratamento</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Os dados pessoais sao tratados para as seguintes finalidades:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Criacao e gerenciamento da conta de acesso</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Personalizacao da experiencia (dados filtrados por regiao de atuacao)</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Comunicacoes operacionais (atualizacoes de dados, manutencoes, novidades)</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Faturamento e gestao de planos pagos</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Melhoria continua da Plataforma</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>4. Base Legal</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              O tratamento de dados pessoais e realizado com base nas seguintes hipoteses legais da LGPD:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Consentimento do titular</strong> (Art. 7, I) — para cadastro e comunicacoes</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Execucao de contrato</strong> (Art. 7, V) — para prestacao dos servicos contratados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Legitimo interesse do controlador</strong> (Art. 7, IX) — para tratamento de dados de socios e representantes legais de pessoas juridicas disponiveis em fontes publicas (Receita Federal, Juntas Comerciais), utilizado exclusivamente nos servicos de due diligence contratados (secao 7)</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Cumprimento de obrigacao legal</strong> (Art. 7, II) — para retencao de dados fiscais e regulatorios</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>5. Armazenamento e Seguranca</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Os dados sao armazenados em servidores localizados no Brasil, com criptografia em transito (TLS 1.3) e em repouso. Credenciais de acesso sao armazenadas com hash bcrypt. Dados importados por clientes dos planos Profissional e Empresa sao segregados logicamente e criptografados com chaves exclusivas por cliente.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>6. Compartilhamento</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Nao vendemos, alugamos ou compartilhamos dados pessoais com terceiros para fins de marketing. Dados podem ser compartilhados com processadores de pagamento (para faturamento) e provedores de infraestrutura (para operacao da Plataforma), sempre sob acordos de confidencialidade e em conformidade com a LGPD.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>7. Dados Publicos na Plataforma e Tratamento de Dados de Terceiros</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Os dados de telecomunicacoes, demografia e infraestrutura exibidos na Plataforma sao provenientes de fontes publicas (Anatel, IBGE, INMET, NASA/SRTM, PGFN, Receita Federal, entre outras) e sao agregados por municipio. Esses dados nao contem informacoes pessoais de assinantes individuais.
            </p>
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>7.1. Dados de socios e representantes legais</h3>
              <p className="text-sm leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>
                Nos servicos de Due Diligence (disponveis somente via contratacao especifica com termo assinado), a Plataforma pode exibir nomes de socios e representantes legais de pessoas juridicas, obtidos de fontes publicas (Receita Federal, Juntas Comerciais). Para estes dados:
              </p>
              <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> CPFs sao parcialmente mascarados (exibicao apenas dos 3 primeiros e 2 ultimos digitos)</li>
                <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Dados de MEIs e empresarios individuais (pessoa natural) sao reduzidos ao minimo necessario, em conformidade com a LGPD</li>
                <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> O acesso e restrito ao contratante, mediante NDA, e registrado em log de auditoria com IP, data/hora e finalidade declarada</li>
                <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> A base legal aplicavel e o legitimo interesse (Art. 7, IX da LGPD), com balanceamento de interesses documentado</li>
              </ul>
            </div>
            <div className="rounded-lg p-4 mt-3" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>7.2. Dados fiscais e regulatorios de pessoas juridicas</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                Dados de divida ativa (PGFN), sancoes regulatorias (Anatel), reclamacoes (consumidor.gov.br) e financiamentos (BNDES) sao relativos a pessoas juridicas e provenientes de registros publicos. Estes dados nao se enquadram como dados pessoais nos termos da LGPD, exceto quando vinculados a empresarios individuais, caso em que se aplica a secao 7.1.
              </p>
            </div>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>8. Direitos do Titular</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Conforme a LGPD, voce tem direito a:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Confirmacao da existencia de tratamento dos seus dados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Acesso aos dados pessoais coletados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Correcao de dados incompletos ou desatualizados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Anonimizacao, bloqueio ou eliminacao de dados desnecessarios</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Portabilidade dos dados a outro fornecedor</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Eliminacao dos dados tratados com base em consentimento</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Revogacao do consentimento</li>
            </ul>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Para exercer seus direitos, entre em contato com nosso Encarregado de Protecao de Dados (DPO) pelo e-mail dpo@pulso.network. Responderemos em ate 15 dias uteis.
            </p>
            <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Socios ou representantes legais de empresas cujos dados aparecem na Plataforma (via fontes publicas) tambem podem exercer os direitos acima, incluindo solicitar a revisao ou exclusao de seus dados dos relatorios de due diligence.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>9. Retencao de Dados</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              A retencao varia conforme o tipo de dado e nivel de servico:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Dados de conta (cadastro):</strong> mantidos enquanto a conta estiver ativa. Apos encerramento, retidos por 6 meses para backup e conformidade.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Dados de faturamento:</strong> mantidos conforme exigencias fiscais (5 anos).</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Logs de auditoria (Due Diligence):</strong> mantidos por 5 anos para fins de conformidade e rastreabilidade.</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> <strong>Relatorios contratados:</strong> mantidos pelo prazo do contrato, mais 12 meses apos o termino.</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>10. Cookies</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              A Plataforma utiliza cookies essenciais para autenticacao e manutencao de sessao. Nao utilizamos cookies de rastreamento de terceiros ou cookies publicitarios.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>11. Alteracoes</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Esta Politica pode ser atualizada periodicamente. Alteracoes serao comunicadas por e-mail e publicadas nesta pagina com a data de atualizacao.
            </p>
          </div>

          <div className="pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Encarregado de Protecao de Dados (DPO): dpo@pulso.network
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
