import type { Metadata } from 'next';
import Section from '@/components/ui/Section';

export const metadata: Metadata = {
  title: 'Política de Privacidade — Pulso Network',
  description: 'Política de privacidade e conformidade LGPD da plataforma Pulso Network.',
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
            Política de Privacidade
          </h1>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-on-dark-muted)' }}>
            Última atualização: 10 de março de 2026
          </p>
        </div>
      </Section>

      <Section background="primary">
        <div className="max-w-3xl space-y-8">
          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>1. Introdução</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Esta Política de Privacidade descreve como a Pulso Network Tecnologia Ltda. (&quot;Pulso&quot;) coleta, utiliza, armazena e protege dados pessoais em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018).
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>2. Dados Coletados</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Coletamos os seguintes dados pessoais no momento do cadastro:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Nome completo</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Endereço de e-mail</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Nome da empresa / ISP</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Estado de atuação</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Faixa de assinantes (dado opcional)</li>
            </ul>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Durante o uso da Plataforma, coletamos dados de navegação (páginas acessadas, funcionalidades utilizadas) para fins de melhoria do serviço. Não coletamos dados sensíveis conforme definidos pela LGPD.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>3. Finalidade do Tratamento</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Os dados pessoais são tratados para as seguintes finalidades:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Criação e gerenciamento da conta de acesso</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Personalização da experiência (dados filtrados por região de atuação)</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Comunicações operacionais (atualizações de dados, manutenções, novidades)</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Faturamento e gestão de planos pagos</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Melhoria contínua da Plataforma</li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>4. Base Legal</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O tratamento de dados pessoais é realizado com base no consentimento do titular (Art. 7º, I da LGPD) e na execução de contrato (Art. 7º, V), conforme o plano contratado.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>5. Armazenamento e Segurança</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Os dados são armazenados em servidores localizados no Brasil, com criptografia em trânsito (TLS 1.3) e em repouso. Credenciais de acesso são armazenadas com hash bcrypt. Dados importados por clientes dos planos Profissional e Empresa são segregados logicamente e criptografados com chaves exclusivas por cliente.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>6. Compartilhamento</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Não vendemos, alugamos ou compartilhamos dados pessoais com terceiros para fins de marketing. Dados podem ser compartilhados com processadores de pagamento (para faturamento) e provedores de infraestrutura (para operação da Plataforma), sempre sob acordos de confidencialidade e em conformidade com a LGPD.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>7. Dados Públicos na Plataforma</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Os dados de telecomunicações, demografia e infraestrutura exibidos na Plataforma são provenientes de fontes públicas (Anatel, IBGE, INMET, NASA/SRTM, entre outras) e são agregados por município. Esses dados não contêm informações pessoais de assinantes individuais.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>8. Direitos do Titular</h2>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              Conforme a LGPD, você tem direito a:
            </p>
            <ul className="space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Confirmação da existência de tratamento dos seus dados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Acesso aos dados pessoais coletados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Correção de dados incompletos ou desatualizados</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Anonimização, bloqueio ou eliminação de dados desnecessários</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Portabilidade dos dados a outro fornecedor</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Eliminação dos dados tratados com base em consentimento</li>
              <li className="flex gap-2"><span style={{ color: 'var(--accent)' }}>—</span> Revogação do consentimento</li>
            </ul>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Para exercer seus direitos, entre em contato com nosso Encarregado de Proteção de Dados (DPO) pelo e-mail dpo@pulso.network. Responderemos em até 15 dias úteis.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>9. Retenção de Dados</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Dados pessoais são mantidos enquanto a conta estiver ativa. Após encerramento da conta, os dados são retidos por 6 meses para fins de backup e conformidade, sendo eliminados após esse período. Dados de faturamento são mantidos conforme exigências fiscais (5 anos).
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>10. Cookies</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              A Plataforma utiliza cookies essenciais para autenticação e manutenção de sessão. Não utilizamos cookies de rastreamento de terceiros ou cookies publicitários.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>11. Alterações</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Esta Política pode ser atualizada periodicamente. Alterações serão comunicadas por e-mail e publicadas nesta página com a data de atualização.
            </p>
          </div>

          <div className="pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Encarregado de Proteção de Dados (DPO): dpo@pulso.network
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
