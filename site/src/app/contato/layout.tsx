import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Contato',
  description: 'Entre em contato com a equipe Pulso Network. Dúvidas, demonstrações ou parcerias comerciais.',
  alternates: { canonical: 'https://pulso.network/contato' },
};

export default function ContatoLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
