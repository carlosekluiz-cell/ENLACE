import type { Metadata } from 'next';
import { IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';
import Script from 'next/script';
import 'maplibre-gl/dist/maplibre-gl.css';
import './globals.css';
import Sidebar from '@/components/layout/Sidebar';
import { Providers } from './providers';
import { ThemeScript } from './theme-script';

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-ibm-plex-sans',
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-ibm-plex-mono',
});

export const metadata: Metadata = {
  title: 'Pulso - Inteligência Telecom',
  description:
    'Plataforma de inteligência telecom para o mercado brasileiro. Mapeamento de cobertura, scoring de oportunidades, conformidade regulatória e planejamento de conectividade rural.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body
        className={`${ibmPlexSans.variable} ${ibmPlexMono.variable} font-sans`}
        style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
      >
        <Script
          defer
          src={`${process.env.NEXT_PUBLIC_API_URL || 'https://api.enlace.network'}/umami/script.js`}
          data-website-id="ecfe3a7c-1795-44a5-af9d-a15851765c05"
          strategy="afterInteractive"
        />
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
