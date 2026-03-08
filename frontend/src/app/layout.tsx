import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Sidebar from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'ENLACE - Telecom Intelligence Platform',
  description:
    'Comprehensive telecom intelligence platform for the Brazilian market. Coverage mapping, opportunity scoring, compliance monitoring, and rural connectivity planning.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-100`}>
        <div className="flex min-h-screen">
          {/* Sidebar navigation */}
          <Sidebar />

          {/* Main content area */}
          <div className="flex flex-1 flex-col lg:pl-64">
            <Header />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
