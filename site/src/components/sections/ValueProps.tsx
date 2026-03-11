export default function ValueProps() {
  const props = [
    {
      title: 'Dados reais, não estimativas',
      description: 'Integramos dados da Anatel, IBGE, SNIS e fontes proprietárias para entregar inteligência baseada em fatos, não em achismo.',
    },
    {
      title: 'Mapa-primeiro',
      description: 'Cada decisão começa no mapa. Veja oportunidades, concorrência e cobertura em um único visual — sem planilhas infinitas.',
    },
    {
      title: 'Feito para provedores brasileiros',
      description: 'Conformidade com Norma n.4, programas de funding rurais, análise HHI por município. Não é uma plataforma genérica adaptada — foi construída para o mercado brasileiro.',
    },
  ];

  return (
    <section className="py-16" style={{ background: 'var(--bg-subtle)' }}>
      <div className="mx-auto max-w-6xl px-4">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-3">
          {props.map((prop) => (
            <div key={prop.title}>
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                {prop.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {prop.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
