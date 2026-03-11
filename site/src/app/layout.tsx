import type { Metadata } from 'next';
import './globals.css';
import Nav from '@/components/layout/Nav';
import Footer from '@/components/layout/Footer';

export const metadata: Metadata = {
  title: 'Pulso Network — Inteligência Telecom para o Brasil',
  description: 'Plataforma de inteligência telecom para provedores de internet brasileiros. Expansão, conformidade, projeto RF e muito mais.',
  openGraph: {
    title: 'Pulso Network — Inteligência Telecom para o Brasil',
    description: 'Plataforma de inteligência telecom para provedores de internet brasileiros. Expansão, conformidade, projeto RF e muito mais.',
    url: 'https://pulso.network',
    siteName: 'Pulso Network',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Pulso Network — Inteligência Telecom para o Brasil',
    description: 'Plataforma de inteligência telecom para provedores de internet brasileiros.',
  },
  icons: {
    icon: '/favicon.svg',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>
        <Nav />
        <main className="pt-14">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
