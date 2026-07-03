"use client";

import Link from "next/link";
import Section from "@/components/ui/Section";
import ReportExplorer from "@/components/report/ReportExplorer";
import { exampleAudit } from "@/lib/example-audit";
import { ArrowRight, FlaskConical, AlertTriangle } from "lucide-react";
import { useI18n } from "@/lib/i18n";

// The findings themselves are read straight from the bundled audit JSON — the
// verbatim output of `pulso-agent --audit-csv` on the validation sample. The
// summaries below are the human-facing narration of that output; the numbers
// (dBm, £, %, counts) are unchanged across languages.

export default function ExamplesContent() {
  const { t } = useI18n();

  return (
    <>
      {/* Hero + example banner */}
      <Section background="dark" grain hero>
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-6"
          style={{ color: "var(--accent)" }}
        >
          {t("examples.eyebrow")}
        </p>

        <h1 className="font-serif text-4xl font-bold leading-tight md:text-5xl md:leading-[1.1]">
          {t("examples.hero.title")}
        </h1>

        <p
          className="mt-6 max-w-2xl text-lg leading-relaxed"
          style={{ color: "var(--text-on-dark-secondary)" }}
        >
          {t("examples.hero.lead")}
        </p>

        {/* Prominent labelled banner */}
        <div
          className="mt-8 flex items-start gap-3 p-4 max-w-2xl"
          style={{
            backgroundColor: "var(--bg-dark-subtle)",
            border: "1px solid var(--accent)",
            borderLeft: "3px solid var(--accent)",
          }}
        >
          <FlaskConical
            size={18}
            className="mt-0.5 shrink-0"
            style={{ color: "var(--accent)" }}
          />
          <p
            className="text-sm leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            <span style={{ color: "var(--text-on-dark)", fontWeight: 600 }}>
              {t("examples.banner.label")}
            </span>{" "}
            {t("examples.banner.text")}
          </p>
        </div>
      </Section>

      {/* Interactive report showcase */}
      <Section background="dark-surface" grain>
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("examples.report.eyebrow")}
        </p>
        <h2
          className="font-serif text-2xl font-bold md:text-3xl"
          style={{ color: "var(--text-on-dark)" }}
        >
          {t("examples.report.title")}
        </h2>
        <p
          className="mt-3 mb-8 max-w-2xl text-sm leading-relaxed"
          style={{ color: "var(--text-on-dark-secondary)" }}
        >
          {t("examples.report.lead")}
        </p>

        <ReportExplorer result={exampleAudit} />

        <p
          className="mt-4 font-mono text-xs"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          {t("examples.report.figuresNote")}
        </p>
      </Section>

      {/* What it found */}
      <Section background="primary">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("examples.found.eyebrow")}
        </p>
        <h2 className="font-serif text-3xl font-bold md:text-4xl">
          {t("examples.found.title")}
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div
              key={n}
              className="flex gap-4 items-start p-6"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderLeft: "3px solid var(--accent)",
              }}
            >
              <AlertTriangle
                size={18}
                className="mt-0.5 shrink-0"
                style={{ color: "var(--accent)" }}
              />
              <div>
                <h3 className="font-serif text-lg font-bold">
                  {t(`examples.find.${n}.title`)}
                </h3>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {t(`examples.find.${n}.detail`)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* CTA */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-3xl font-bold md:text-4xl"
            style={{ color: "var(--text-on-dark)" }}
          >
            {t("examples.cta.title")}
          </h2>
          <p
            className="mt-4 text-base leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            {t("examples.cta.lead")}
          </p>
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-dark gap-2">
              {t("common.requestPilot")}
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
