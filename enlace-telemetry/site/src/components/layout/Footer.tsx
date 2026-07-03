"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

interface FooterLink {
  labelKey: string;
  href: string;
  external?: boolean;
  literal?: string;
}

const footerColumns: { titleKey: string; links: FooterLink[] }[] = [
  {
    titleKey: "footer.product",
    links: [
      { labelKey: "footer.features", href: "/features" },
      { labelKey: "footer.examples", href: "/examples" },
      { labelKey: "footer.requestPilot", href: "/contact" },
    ],
  },
  {
    titleKey: "footer.resources",
    links: [
      { labelKey: "footer.examples", href: "/examples" },
      { labelKey: "footer.contact", href: "/contact" },
    ],
  },
  {
    titleKey: "footer.company",
    links: [
      { labelKey: "footer.about", href: "/about" },
      {
        labelKey: "",
        literal: "Pulso Technologies",
        href: "https://find-and-update.company-information.service.gov.uk/company/17151141",
        external: true,
      },
    ],
  },
];

export default function Footer() {
  const { t } = useI18n();
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
            <div key={col.titleKey}>
              <h3
                className="text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                {t(col.titleKey)}
              </h3>
              <ul className="space-y-2.5 list-none p-0 m-0">
                {col.links.map((link) => {
                  const label = link.literal ?? t(link.labelKey);
                  return (
                    <li key={label}>
                      {link.external ? (
                        <a
                          href={link.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="footer-link text-sm"
                        >
                          {label}
                        </a>
                      ) : (
                        <Link
                          href={link.href}
                          className="footer-link text-sm"
                        >
                          {label}
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
          <span>{t("footer.copyright")}</span>
          <span>{t("footer.tagline")}</span>
        </div>

        {/* Legal */}
        <p
          className="mt-4 text-xs"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          {t("footer.legal")}
        </p>
      </div>
    </footer>
  );
}
