import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Mapa de Banda Larga do Brasil — Pulso Network',
  description: 'Mapa interativo com dados de assinantes de banda larga em todos os 5.570 municípios brasileiros. Animação temporal de 37 meses. Dados Anatel atualizados.',
  alternates: { canonical: 'https://pulso.network/mapa-brasil' },
  openGraph: {
    title: 'Mapa de Banda Larga do Brasil',
    description: 'Visualização interativa de assinantes de internet em todos os municípios brasileiros. Dados Anatel atualizados mensalmente.',
    url: 'https://pulso.network/mapa-brasil',
    type: 'website',
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
