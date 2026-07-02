"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

const navLinks = [
  { label: "Features", href: "/features" },
  { label: "Examples", href: "/examples" },
  { label: "UK Intelligence", href: "/intelligence/" },
  { label: "Contact", href: "/contact" },
] as const;

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const linkColor = scrolled ? "var(--text-secondary)" : "var(--text-on-dark-secondary)";

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        backgroundColor: scrolled ? "rgba(250, 250, 249, 0.85)" : "transparent",
        backdropFilter: scrolled ? "blur(12px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(12px)" : "none",
        borderBottom: scrolled ? "1px solid var(--border)" : "1px solid transparent",
      }}
    >
      <div className="mx-auto max-w-6xl px-4 flex items-center justify-between h-14">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 no-underline">
          <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <defs>
              <linearGradient id="enlaceNavMark" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                <stop stopColor="#818cf8" />
                <stop offset="1" stopColor="#4f46e5" />
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="8" fill="url(#enlaceNavMark)" />
            <path
              d="M5 17.5 H11.2 L14.2 8.5 L18 24 L21 16 H27"
              stroke="#ffffff"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="14.2" cy="8.5" r="1.9" fill="#ffffff" />
          </svg>
          <span
            className="text-lg font-semibold tracking-tight"
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              color: scrolled ? "var(--text-primary)" : "var(--text-on-dark)",
            }}
          >
            Enlace
          </span>
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-6">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium no-underline"
              style={{ color: linkColor }}
            >
              {link.label}
            </a>
          ))}

          <Link
            href="/contact"
            className={scrolled ? "enlace-btn-primary" : "enlace-btn-dark"}
          >
            Request a pilot
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-1"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          style={{
            color: scrolled ? "var(--text-primary)" : "var(--text-on-dark)",
            background: "none",
            border: "none",
            cursor: "pointer",
          }}
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div
          className="md:hidden border-t px-4 pb-4 pt-3"
          style={{
            backgroundColor: scrolled
              ? "rgba(250, 250, 249, 0.95)"
              : "rgba(12, 10, 9, 0.95)",
            backdropFilter: "blur(12px)",
            borderColor: scrolled ? "var(--border)" : "var(--border-dark-strong)",
          }}
        >
          <div className="flex flex-col gap-3">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="text-sm font-medium py-1.5 no-underline"
                style={{ color: linkColor }}
              >
                {link.label}
              </a>
            ))}

            <Link
              href="/contact"
              className={scrolled ? "enlace-btn-primary" : "enlace-btn-dark"}
              onClick={() => setMobileOpen(false)}
            >
              Request a pilot
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
