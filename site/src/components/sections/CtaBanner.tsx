import Link from 'next/link';

export default function CtaBanner() {
  return (
    <section className="py-16" style={{ background: 'var(--accent-subtle)' }}>
      <div className="mx-auto max-w-6xl px-4 text-center">
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Pronto para expandir com inteligência?
        </h2>
        <p className="mt-3 text-base" style={{ color: 'var(--text-secondary)' }}>
          Comece gratuitamente. Sem cartão de crédito, sem compromisso.
        </p>
        <div className="mt-6">
          <Link href="/cadastro" className="pulso-btn-primary">
            Criar conta gratuita
          </Link>
        </div>
      </div>
    </section>
  );
}
