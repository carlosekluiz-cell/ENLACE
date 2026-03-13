import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Raio-X do Provedor — Inteligência Gratuita para ISPs — Pulso Network',
  description: 'Relatório gratuito de inteligência para provedores de internet brasileiros. Posição competitiva, market share, selos de qualidade Anatel, crescimento e mais.',
  alternates: { canonical: 'https://pulso.network/raio-x' },
  openGraph: {
    title: 'Raio-X do Provedor — Inteligência Gratuita para ISPs',
    description: 'Descubra sua posição competitiva, market share e selos de qualidade Anatel. Gratuito para qualquer provedor de internet brasileiro.',
    url: 'https://pulso.network/raio-x',
    type: 'website',
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
