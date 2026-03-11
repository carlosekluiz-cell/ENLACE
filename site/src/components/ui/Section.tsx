import { clsx } from 'clsx';

interface SectionProps {
  children: React.ReactNode;
  className?: string;
  id?: string;
  background?: 'primary' | 'surface' | 'subtle' | 'dark' | 'dark-surface' | 'dark-subtle';
  grain?: boolean;
  hero?: boolean;
}

export default function Section({
  children,
  className,
  id,
  background = 'primary',
  grain = false,
  hero = false,
}: SectionProps) {
  const bgMap = {
    primary: 'var(--bg-primary)',
    surface: 'var(--bg-surface)',
    subtle: 'var(--bg-subtle)',
    dark: 'var(--bg-dark)',
    'dark-surface': 'var(--bg-dark-surface)',
    'dark-subtle': 'var(--bg-dark-subtle)',
  };

  return (
    <section
      id={id}
      className={clsx(
        'relative',
        hero ? '-mt-14 pt-28 pb-20 md:pt-36 md:pb-28' : 'py-20 md:py-28',
        grain && 'grain',
        className,
      )}
      style={{ background: bgMap[background] }}
    >
      <div className="relative z-10 mx-auto max-w-6xl px-4">
        {children}
      </div>
    </section>
  );
}
