import type { Metadata } from "next";
import Section from "@/components/ui/Section";
import { Mail, Code2, Shield, Terminal } from "lucide-react";

export const metadata: Metadata = {
  title: "About — Enlace Telemetry",
  description:
    "Pulso Technologies builds telemetry intelligence for fibre operators. Enlace is our telemetry agent for per-ONT visibility.",
};

export default function AboutPage() {
  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-4"
            style={{ color: "var(--accent)" }}
          >
            About
          </p>
          <h1
            className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6"
            style={{ color: "var(--text-on-dark)" }}
          >
            Engineered for ISPs.{" "}
            <span style={{ color: "var(--text-on-dark-muted)" }}>
              Built in Rust.
            </span>
          </h1>
          <p
            className="text-lg md:text-xl leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            Pulso Technologies builds telemetry intelligence for fibre
            operators. Enlace is our first product — a telemetry agent that
            gives ISPs the per-ONT visibility they've never had.
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
            We believe every ISP deserves the same network intelligence that
            Tier 1 carriers have.
          </p>
          <p
            className="text-lg leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            The data is already in your OLTs. We just help you use it.
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
            Under the hood
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
                Built with Rust
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                For performance and reliability.
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
                15,482
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                Lines of code.
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
                Read-only &amp; verifiable
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                Never writes to your kit. We&apos;ll walk your engineers through
                exactly what it does.
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
            Get in touch
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
                  Email
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
            Pulso Technologies Limited. Registered in England &amp; Wales,
            company no. 17151141.
          </p>
        </div>
      </Section>
    </>
  );
}
