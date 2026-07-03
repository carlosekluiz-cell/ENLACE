"use client";

import Section from "@/components/ui/Section";
import { Mail, Code2, Shield, Terminal } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export default function AboutContent() {
  const { t } = useI18n();

  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-4"
            style={{ color: "var(--accent)" }}
          >
            {t("about.eyebrow")}
          </p>
          <h1
            className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6"
            style={{ color: "var(--text-on-dark)" }}
          >
            {t("about.hero.title1")}{" "}
            <span style={{ color: "var(--text-on-dark-muted)" }}>
              {t("about.hero.title2")}
            </span>
          </h1>
          <p
            className="text-lg md:text-xl leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            {t("about.hero.lead")}
          </p>
        </div>
      </Section>

      {/* Mission */}
      <Section background="primary">
        <div className="max-w-2xl mx-auto">
          <p
            className="font-serif text-2xl md:text-3xl font-bold leading-snug mb-6"
            style={{ color: "var(--text-primary)" }}
          >
            {t("about.mission.title")}
          </p>
          <p
            className="text-lg leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            {t("about.mission.body")}
          </p>
        </div>
      </Section>

      {/* Tech */}
      <Section background="subtle">
        <div className="max-w-2xl mx-auto">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-8"
            style={{ color: "var(--accent)" }}
          >
            {t("about.tech.eyebrow")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div
              className="p-5"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <Terminal
                size={20}
                className="mb-3"
                style={{ color: "var(--accent)" }}
              />
              <p
                className="font-serif text-base font-semibold mb-1"
                style={{ color: "var(--text-primary)" }}
              >
                {t("about.tech.rust.title")}
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                {t("about.tech.rust.body")}
              </p>
            </div>

            <div
              className="p-5"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <Code2
                size={20}
                className="mb-3"
                style={{ color: "var(--accent)" }}
              />
              <p
                className="font-mono text-2xl font-bold mb-1"
                style={{ color: "var(--text-primary)" }}
              >
                ~23,500
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                {t("about.tech.lines.body")}
              </p>
            </div>

            <div
              className="p-5"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <Shield
                size={20}
                className="mb-3"
                style={{ color: "var(--accent)" }}
              />
              <p
                className="font-serif text-base font-semibold mb-1"
                style={{ color: "var(--text-primary)" }}
              >
                {t("about.tech.readonly.title")}
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                {t("about.tech.readonly.body")}
              </p>
            </div>
          </div>
        </div>
      </Section>

      {/* Contact */}
      <Section background="surface">
        <div className="max-w-2xl mx-auto">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-8"
            style={{ color: "var(--accent)" }}
          >
            {t("about.contact.eyebrow")}
          </p>
          <div className="flex flex-col sm:flex-row gap-6">
            <a
              href="mailto:hello@enlace.network"
              className="flex items-center gap-3 no-underline group"
            >
              <div
                className="w-10 h-10 flex items-center justify-center"
                style={{
                  backgroundColor: "var(--accent-subtle)",
                }}
              >
                <Mail size={18} style={{ color: "var(--accent)" }} />
              </div>
              <div>
                <p
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {t("about.contact.emailLabel")}
                </p>
                <p
                  className="font-mono text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  hello@enlace.network
                </p>
              </div>
            </a>

          </div>

          <p
            className="mt-10 text-xs leading-relaxed"
            style={{ color: "var(--text-muted)" }}
          >
            {t("about.legal")}
          </p>
        </div>
      </Section>
    </>
  );
}
