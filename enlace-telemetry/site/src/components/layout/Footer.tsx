import Link from "next/link";

const footerColumns = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/features" },
      { label: "Examples", href: "/examples" },
      { label: "Request a pilot", href: "/contact" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Examples", href: "/examples" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      {
        label: "Pulso Technologies",
        href: "https://find-and-update.company-information.service.gov.uk/company/17151141",
        external: true,
      },
    ],
  },
] as const;

export default function Footer() {
  return (
    <footer
      className="grain relative"
      style={{
        backgroundColor: "var(--bg-dark)",
        color: "var(--text-on-dark-secondary)",
      }}
    >
      <style>{`
        .footer-link { color: var(--text-on-dark-secondary); text-decoration: none; transition: color 0.15s; }
        .footer-link:hover { color: var(--accent); }
      `}</style>
      <div className="relative z-10 mx-auto max-w-6xl px-4 py-16 md:py-20">
        {/* Columns */}
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {footerColumns.map((col) => (
            <div key={col.title}>
              <h3
                className="text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                {col.title}
              </h3>
              <ul className="space-y-2.5 list-none p-0 m-0">
                {col.links.map((link) => {
                  const isExternal = "external" in link && link.external;
                  return (
                    <li key={link.label}>
                      {isExternal ? (
                        <a
                          href={link.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="footer-link text-sm"
                        >
                          {link.label}
                        </a>
                      ) : (
                        <Link
                          href={link.href}
                          className="footer-link text-sm"
                        >
                          {link.label}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div
          className="mt-14 pt-6 flex flex-col gap-2 md:flex-row md:items-center md:justify-between text-xs"
          style={{
            borderTop: "1px solid var(--border-dark-strong)",
            color: "var(--text-on-dark-muted)",
          }}
        >
          <span>&copy; 2026 Pulso Technologies. All rights reserved.</span>
          <span>
            Read-only telemetry · multi-vendor · your data stays yours
          </span>
        </div>

        {/* Legal */}
        <p
          className="mt-4 text-xs"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          Pulso Technologies Limited &middot; Registered in England &amp; Wales
          &middot; company no. 17151141
        </p>
      </div>
    </footer>
  );
}
