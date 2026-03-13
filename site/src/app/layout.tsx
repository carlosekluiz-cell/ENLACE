import type { Metadata } from 'next';
import { DM_Sans, Fraunces, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Nav from '@/components/layout/Nav';
import Footer from '@/components/layout/Footer';

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-dm-sans',
  display: 'swap',
});

const fraunces = Fraunces({
  subsets: ['latin'],
  weight: ['400', '600', '700', '800', '900'],
  style: ['normal', 'italic'],
  variable: '--font-fraunces',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  metadataBase: new URL('https://pulso.network'),
  title: {
    default: 'Pulso Network — Inteligência Telecom para o Brasil',
    template: '%s — Pulso Network',
  },
  description: 'Plataforma de inteligência de mercado para provedores de internet brasileiros. 38+ fontes de dados, 69 tabelas, motor RF em Rust. Expansão, M&A, conformidade e projeto RF.',
  keywords: ['provedor de internet', 'ISP', 'inteligência telecom', 'Anatel', 'banda larga', 'Brasil', 'telecomunicações', 'M&A telecom', 'expansão ISP', 'Pulso Network'],
  authors: [{ name: 'Pulso Network' }],
  alternates: { canonical: 'https://pulso.network' },
  openGraph: {
    title: 'Pulso Network — Inteligência Telecom para o Brasil',
    description: 'Plataforma de inteligência de mercado para 13.534 provedores de internet brasileiros. 38+ fontes de dados integradas.',
    url: 'https://pulso.network',
    siteName: 'Pulso Network',
    type: 'website',
    locale: 'pt_BR',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Pulso Network — Inteligência Telecom para o Brasil',
    description: 'Plataforma de inteligência de mercado para provedores de internet brasileiros.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-snippet': -1, 'max-image-preview': 'large' },
  },
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: '32x32' },
    ],
    apple: '/apple-touch-icon.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const orgJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Pulso Network',
    url: 'https://pulso.network',
    description: 'Plataforma de inteligência de mercado para provedores de internet brasileiros.',
    foundingDate: '2025',
    sameAs: [],
    contactPoint: {
      '@type': 'ContactPoint',
      email: 'contato@pulso.network',
      contactType: 'sales',
      availableLanguage: 'Portuguese',
    },
  };

  const softwareJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Pulso Network',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'BRL',
      lowPrice: '0',
      highPrice: '5000',
      offerCount: '5',
    },
    description: 'Inteligência de mercado para provedores de internet brasileiros. 38+ fontes de dados, 69 tabelas, 25 módulos.',
  };

  return (
    <html lang="pt-BR" className={`${dmSans.variable} ${fraunces.variable} ${jetbrainsMono.variable}`}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
        />
        <Nav />
        <main className="pt-14">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
