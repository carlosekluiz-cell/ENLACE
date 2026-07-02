import type { Metadata } from "next";
import Link from "next/link";
import Section from "@/components/ui/Section";
import ReportExplorer from "@/components/report/ReportExplorer";
import { exampleAudit } from "@/lib/example-audit";
import { ArrowRight, FlaskConical, AlertTriangle } from "lucide-react";

export const metadata: Metadata = {
  title: "Example report — Enlace Telemetry",
  description:
    "See what an Enlace audit produces: fleet health score, fault classification with dying-gasp evidence, churn risk with stated assumptions, proactive tickets, and per-ONT diagnostics. Example output from internal validation on representative data — not customer data.",
};

// These findings are read straight from the bundled audit JSON — the
// verbatim output of `pulso-agent --audit-csv` on the validation sample.
const findings = [
  {
    title: "Two branch outages, classified by evidence",
    detail:
      "Five ONTs on CTP-0/4 and four on CTP-0/2 dropped inside the detection window. On CTP-0/4, two sent a dying gasp and three went silent — mixed evidence, so the engine says “Mixed” instead of guessing power vs fibre. Per-ONT gasp evidence is attached to each fault.",
  },
  {
    title: "Churn risk: 3 customers, assumptions stated",
    detail:
      "Three subscribers at −25 to −29 dBm with degrading signal — an estimated 35% 90-day churn probability and ~£378/yr revenue at risk each. Every figure carries its assumptions inline (ARPU £89.90, probability model), so the ROI is auditable, not asserted.",
  },
  {
    title: "One proactive ticket, ready to dispatch",
    detail:
      "The three churn risks were rolled into a single P2 ticket with a 5-day SLA: evidence lines per ONT, a recommended action, £1,133/yr at risk vs a £450 estimated fix — a 2.5× ROI with the cost assumptions printed on the ticket.",
  },
  {
    title: "Shared-plant downtrend on CTP-0/1",
    detail:
      "The whole PON branch is trending down at −0.74 dB/week — roughly 13 weeks to threshold at the current rate. A fleet-wide trend points at shared plant (splitter, feeder, OLT SFP), not any single customer's kit.",
  },
  {
    title: "Three links running on marginal optical budget",
    detail:
      "Loss-model analysis of all 52 links found three with ~8 dB more loss than their distance and splitter ratio explain — probable excess connector loss, flagged with the expected-vs-measured maths.",
  },
  {
    title: "What it refused to claim",
    detail:
      "This sample has no FEC or laser-bias columns, so the report states “0 of 52 ONTs covered” for those analyses instead of implying health. No ghosts, no flapping, no rogue ONTs were flagged — absence of a finding is reported as absence of evidence, never as a pass.",
  },
];

export default function ExamplesPage() {
  return (
    <>
      {/* Hero + example banner */}
      <Section background="dark" grain hero>
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-6"
          style={{ color: "var(--accent)" }}
        >
          Example output
        </p>

        <h1 className="font-serif text-4xl font-bold leading-tight md:text-5xl md:leading-[1.1]">
          What an Enlace audit produces
        </h1>

        <p
          className="mt-6 max-w-2xl text-lg leading-relaxed"
          style={{ color: "var(--text-on-dark-secondary)" }}
        >
          Enlace reads the telemetry your OLTs already produce and turns it into
          a plain-language report: a fleet health score, the faults worth acting
          on, and a per-ONT table you can sort and filter. Below is a
          representative example.
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
              Example output
            </span>{" "}
            — generated from Enlace&apos;s internal validation on representative
            data. Not customer data.
          </p>
        </div>
      </Section>

      {/* Interactive report showcase */}
      <Section background="dark-surface" grain>
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          The report
        </p>
        <h2
          className="font-serif text-2xl font-bold md:text-3xl"
          style={{ color: "var(--text-on-dark)" }}
        >
          Fleet health, findings, and every ONT
        </h2>
        <p
          className="mt-3 mb-8 max-w-2xl text-sm leading-relaxed"
          style={{ color: "var(--text-on-dark-secondary)" }}
        >
          Click a finding to filter the ONT table. 52 ONTs across four PON
          branches, analysed over a 7-day window — this is the verbatim JSON
          the current engine produced from our validation sample, including
          its own coverage notes.
        </p>

        <ReportExplorer result={exampleAudit} />

        <p
          className="mt-4 font-mono text-xs"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          Figures from internal validation on representative data.
        </p>
      </Section>

      {/* What it found */}
      <Section background="primary">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          What it found
        </p>
        <h2 className="font-serif text-3xl font-bold md:text-4xl">
          Six findings — including what it refused to claim
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {findings.map((f) => (
            <div
              key={f.title}
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
                <h3 className="font-serif text-lg font-bold">{f.title}</h3>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {f.detail}
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
            Want this for your network?
          </h2>
          <p
            className="mt-4 text-base leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            We&apos;re onboarding a small number of fibre operators as
            validation partners. Enlace runs read-only against the OLTs you
            already have.
          </p>
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-dark gap-2">
              Request a pilot
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
