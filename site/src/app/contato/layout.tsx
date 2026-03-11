import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Contato — Pulso Network',
  description: 'Entre em contato com a equipe Pulso Network. Dúvidas, demonstrações ou parcerias comerciais.',
};

export default function ContatoLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
