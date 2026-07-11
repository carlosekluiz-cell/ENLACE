import type { Metadata } from "next";
import Section from "@/components/ui/Section";

export const metadata: Metadata = {
  title: "Pricing — Enlace",
  description:
    "Plans for WISPs, regional ISPs, consultancies and enterprises. RF planning calibrated against 3.55M Anatel measurements.",
};

const PLANS = [
  {
    name: "Teste",
    price: "R$ 0",
    period: "",
    tagline: "Para conhecer a plataforma",
    features: [
      "5 estudos de propagação / mês",
      "Enlaces ponto-a-ponto e cobertura",
      "Terreno + edifícios 0,5 m em todo o Brasil",
      "Sem exportação",
    ],
    cta: "Criar conta",
    href: "https://app.enlace.network/login",
    highlight: false,
  },
  {
    name: "WISP",
    price: "R$ 149",
    period: "/mês",
    tagline: "Para provedores regionais",
    features: [
      "Estudos ilimitados",
      "Exportação PDF · KMZ · GeoJSON",
      "Presets de equipamentos (Ubiquiti, Cambium, Mimosa, Intelbras)",
      "Projetos salvos ilimitados",
      "Busca por endereço / CEP",
      "1 usuário",
    ],
    cta: "Começar",
    href: "https://app.enlace.network/login",
    highlight: true,
  },
  {
    name: "Provedor",
    price: "R$ 499",
    period: "/mês",
    tagline: "Para ISPs em expansão",
    features: [
      "Tudo do plano WISP",
      "Antenas setoriais (azimute / downtilt)",
      "Cobertura P50 / P90 com incerteza calibrada",
      "5 usuários · relatórios com sua marca",
      "API — 1.000 chamadas / mês",
      "Suporte prioritário",
    ],
    cta: "Falar com a gente",
    href: "mailto:contato@enlace.network?subject=Plano%20Provedor",
    highlight: false,
  },
  {
    name: "Enterprise",
    price: "Sob consulta",
    period: "",
    tagline: "Consultorias, torres, M&A, bancos",
    features: [
      "API ilimitada + processamento em lote",
      "Verificação de cobertura para due diligence",
      "Avaliação de portfólio de torres",
      "Relatórios auditáveis (metodologia versionada)",
      "White-label completo · SLA",
      "Dados de calibração licenciáveis",
    ],
    cta: "Falar com a gente",
    href: "mailto:contato@enlace.network?subject=Plano%20Enterprise",
    highlight: false,
  },
];

export default function PricingPage() {
  return (
    <>
      <Section hero background="dark" grain>
        <div className="max-w-3xl">
          <p className="font-mono text-xs tracking-widest uppercase mb-4" style={{ color: "var(--accent)" }}>
            Planos · Propagação RF
          </p>
          <h1 className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6">
            Planejamento de rede calibrado com 3,55 milhões de medições reais
          </h1>
          <p className="text-lg md:text-xl leading-relaxed max-w-2xl opacity-90">
            Do provedor de bairro à operadora nacional — o mesmo motor, o mesmo
            benchmark publicado, planos para cada tamanho.
          </p>
        </div>
      </Section>

      <Section background="surface">
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className="rounded-xl p-6 flex flex-col"
              style={{
                border: p.highlight
                  ? "2px solid var(--accent)"
                  : "1px solid var(--border, #e5e5e5)",
                background: "var(--bg-primary)",
              }}
            >
              <p className="font-mono text-xs uppercase tracking-widest mb-1 opacity-60">
                {p.tagline}
              </p>
              <h2 className="font-serif text-2xl font-bold">{p.name}</h2>
              <p className="mt-2 mb-5">
                <span className="font-mono text-3xl font-bold">{p.price}</span>
                <span className="opacity-60">{p.period}</span>
              </p>
              <ul className="space-y-2 text-sm leading-relaxed flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span style={{ color: "var(--accent)" }}>✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <a
                href={p.href}
                className="mt-6 inline-block rounded-md px-4 py-2 text-center text-sm font-medium"
                style={
                  p.highlight
                    ? { background: "var(--accent)", color: "#fff" }
                    : { border: "1px solid var(--border, #d5d5d5)" }
                }
              >
                {p.cta}
              </a>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm opacity-60">
          Pagamento online em breve — por enquanto, todos os planos são ativados
          por contato direto. Preços de lançamento, sem fidelidade.
        </p>
      </Section>

      <Section background="subtle">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="font-serif text-2xl md:text-3xl font-bold leading-snug mb-4">
            Por que confiar nas previsões?
          </h2>
          <p className="text-base leading-relaxed opacity-80 mb-6">
            Nosso modelo é validado contra 3,55 milhões de medições de campo da
            Anatel, com erro medido de 7,0 dB (urbano) em avaliação
            out-of-sample — e a metodologia inteira é pública e reproduzível.
          </p>
          <a
            href="/validation"
            className="inline-block rounded-md px-5 py-2.5 text-sm font-medium"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            Ver o relatório de validação
          </a>
        </div>
      </Section>
    </>
  );
}
