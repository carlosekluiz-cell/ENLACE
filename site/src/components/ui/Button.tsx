import Link from 'next/link';
import { clsx } from 'clsx';

interface ButtonProps {
  href?: string;
  variant?: 'primary' | 'secondary';
  children: React.ReactNode;
  className?: string;
  type?: 'button' | 'submit';
  disabled?: boolean;
}

export default function Button({ href, variant = 'primary', children, className, type, disabled }: ButtonProps) {
  const cls = clsx(
    variant === 'primary' ? 'pulso-btn-primary' : 'pulso-btn-secondary',
    className
  );

  if (href) {
    return <Link href={href} className={cls}>{children}</Link>;
  }

  return <button type={type || 'button'} disabled={disabled} className={cls}>{children}</button>;
}
