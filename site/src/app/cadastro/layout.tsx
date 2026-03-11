import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Criar conta — Pulso Network',
  description: 'Crie sua conta gratuita no Pulso Network. Acesso imediato a dados de telecomunicações de 5.570 municípios brasileiros.',
};

export default function CadastroLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
