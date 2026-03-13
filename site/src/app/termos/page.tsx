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
            Última atualização: 10 de março de 2026
          </p>
        </div>
      </Section>

      <Section background="primary">
        <div className="max-w-3xl space-y-8">
          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>1. Aceitação dos Termos</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Ao acessar ou utilizar a plataforma Pulso Network (&quot;Plataforma&quot;), operada por Pulso Network Tecnologia Ltda. (&quot;Pulso&quot;, &quot;nós&quot;), você concorda com estes Termos de Uso. Se você não concordar, não utilize a Plataforma.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>2. Descrição do Serviço</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso é uma plataforma de inteligência de mercado para o setor de telecomunicações brasileiro. Agregamos e processamos dados de fontes públicas — incluindo Anatel, IBGE, INMET, NASA/SRTM, DataSUS, INEP, SNIS, ANP, BNDES, PNCP e OpenStreetMap — para gerar análises, scores e visualizações. Os dados apresentados são públicos e agregados por município; não coletamos nem exibimos dados individuais de assinantes.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>3. Cadastro e Conta</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Para acessar funcionalidades além do plano gratuito, é necessário criar uma conta com informações verdadeiras. Você é responsável por manter a confidencialidade das suas credenciais de acesso. Cada conta é de uso pessoal e intransferível, salvo contas multi-usuário nos planos Profissional e Empresa. Reservamo-nos o direito de suspender contas que violem estes termos ou que apresentem atividade anômala.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>4. Planos e Pagamento</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso oferece planos gratuito e pagos, conforme descrito na página de Preços. Planos pagos são cobrados mensalmente, sem fidelidade. O cancelamento pode ser feito a qualquer momento e terá efeito ao final do ciclo de faturamento vigente. Aceitamos pagamento via PIX, boleto bancário e cartão de crédito.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>5. Uso dos Dados</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Os dados disponibilizados na Plataforma são derivados de fontes públicas e apresentados no estado em que se encontram (&quot;as is&quot;). O Pulso não garante a exatidão, completude ou atualidade dos dados de terceiros. Os dados podem ser utilizados para análise interna e tomada de decisão, mas não devem ser redistribuídos comercialmente sem autorização prévia. Dados importados pelo cliente permanecem de propriedade do cliente e são tratados conforme nossa Política de Privacidade.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>6. Propriedade Intelectual</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              A Plataforma, incluindo seu código-fonte, algoritmos de scoring, modelos de propagação RF, interface e marca, são propriedade do Pulso. Relatórios e análises gerados para o cliente podem ser utilizados livremente pelo cliente, mas a metodologia subjacente permanece propriedade do Pulso.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>7. Limitação de Responsabilidade</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              O Pulso não se responsabiliza por decisões de negócio tomadas com base nos dados da Plataforma. Os scores de oportunidade, análises de mercado e projeções são indicadores baseados em dados públicos e não constituem recomendação de investimento ou garantia de resultado. Em nenhuma hipótese a responsabilidade do Pulso excederá o valor pago pelo cliente nos 12 meses anteriores ao evento.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>8. Disponibilidade</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Nos esforçamos para manter a Plataforma disponível 24/7, com SLA de 99,9% para clientes do plano Empresa. Manutenções programadas serão comunicadas com 48 horas de antecedência. Não nos responsabilizamos por indisponibilidades causadas por fatores externos (provedores de infraestrutura, APIs de terceiros, eventos de força maior).
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>9. Alterações</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Podemos atualizar estes Termos periodicamente. Alterações materiais serão notificadas por e-mail com 30 dias de antecedência. O uso continuado da Plataforma após a notificação constitui aceitação dos novos termos.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>10. Foro e Legislação</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Estes Termos são regidos pela legislação brasileira. Fica eleito o foro da comarca de São Paulo/SP para dirimir quaisquer controvérsias.
            </p>
          </div>

          <div className="pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Dúvidas sobre os Termos de Uso? Entre em contato pelo e-mail legal@pulso.network.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
