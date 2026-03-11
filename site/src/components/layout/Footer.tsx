import Link from 'next/link';
import { FOOTER_LINKS } from '@/lib/constants';

export default function Footer() {
  return (
    <footer style={{ background: 'var(--bg-dark)', borderTop: '1px solid var(--border-dark)' }}>
      <div className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-5">
          {/* Logo + description */}
          <div className="md:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2.5 mb-4">
              <div
                className="flex h-8 w-8 items-center justify-center text-sm font-bold"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                P
              </div>
              <span className="font-serif text-lg font-semibold" style={{ color: 'var(--text-on-dark)' }}>
                Pulso
              </span>
            </div>
            <p className="text-sm leading-relaxed max-w-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
              Inteligência telecom para provedores de internet brasileiros.
              19+ fontes de dados públicos integradas em uma plataforma.
            </p>
          </div>

          {/* Product links */}
          <div>
            <h3
              className="text-xs font-medium uppercase tracking-wider mb-4"
              style={{ color: 'var(--text-on-dark-muted)' }}
            >
              Plataforma
            </h3>
            <ul className="space-y-2.5">
              {FOOTER_LINKS.product.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm transition-colors hover:text-white"
                    style={{ color: 'var(--text-on-dark-secondary)' }}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources links */}
          <div>
            <h3
              className="text-xs font-medium uppercase tracking-wider mb-4"
              style={{ color: 'var(--text-on-dark-muted)' }}
            >
              Recursos
            </h3>
            <ul className="space-y-2.5">
              {FOOTER_LINKS.recursos.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm transition-colors hover:text-white"
                    style={{ color: 'var(--text-on-dark-secondary)' }}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company links */}
          <div>
            <h3
              className="text-xs font-medium uppercase tracking-wider mb-4"
              style={{ color: 'var(--text-on-dark-muted)' }}
            >
              Empresa
            </h3>
            <ul className="space-y-2.5">
              {FOOTER_LINKS.company.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm transition-colors hover:text-white"
                    style={{ color: 'var(--text-on-dark-secondary)' }}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal links */}
          <div>
            <h3
              className="text-xs font-medium uppercase tracking-wider mb-4"
              style={{ color: 'var(--text-on-dark-muted)' }}
            >
              Legal
            </h3>
            <ul className="space-y-2.5">
              {FOOTER_LINKS.legal.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm transition-colors hover:text-white"
                    style={{ color: 'var(--text-on-dark-secondary)' }}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="mt-10 pt-6" style={{ borderTop: '1px solid var(--border-dark)' }}>
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <p className="text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
              &copy; 2026 Pulso Network. Todos os direitos reservados.
            </p>
            <p className="text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
              Dados: Anatel, IBGE, NASA/SRTM, INMET, SNIS, ANP, DataSUS, INEP, PNCP, BNDES, ESA Sentinel-2, OpenStreetMap
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
