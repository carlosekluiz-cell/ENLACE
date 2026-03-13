import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Lista de Espera',
  description: 'Entre na lista de espera do Pulso Network. Inteligência telecom com 38+ fontes de dados para provedores de internet brasileiros. Seja avisado no lançamento.',
  alternates: { canonical: 'https://pulso.network/precos' },
};

export default function PrecosLayout({ children }: { children: React.ReactNode }) {
  return children;
}
