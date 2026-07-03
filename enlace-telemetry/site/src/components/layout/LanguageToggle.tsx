"use client";

import { useI18n, type Locale } from "@/lib/i18n";

interface LanguageToggleProps {
  // When true, use light text (for the transparent dark nav); otherwise dark.
  onDark: boolean;
}

const OPTIONS: { code: Locale; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "pt-BR", label: "PT" },
];

// Small EN | PT switch. Persists via the i18n provider (localStorage).
export default function LanguageToggle({ onDark }: LanguageToggleProps) {
  const { locale, setLocale, t } = useI18n();

  const idle = onDark ? "var(--text-on-dark-muted)" : "var(--text-muted)";
  const active = onDark ? "var(--text-on-dark)" : "var(--text-primary)";

  return (
    <div
      className="flex items-center gap-1 font-mono text-xs"
      role="group"
      aria-label={t("nav.language")}
    >
      {OPTIONS.map((opt, i) => {
        const isActive = locale === opt.code;
        return (
          <span key={opt.code} className="flex items-center gap-1">
            {i > 0 && <span style={{ color: idle }}>|</span>}
            <button
              type="button"
              onClick={() => setLocale(opt.code)}
              aria-pressed={isActive}
              className="font-semibold tracking-wide"
              style={{
                color: isActive ? active : idle,
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "2px 2px",
              }}
            >
              {opt.label}
            </button>
          </span>
        );
      })}
    </div>
  );
}
