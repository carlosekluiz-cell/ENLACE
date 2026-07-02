import type { Metadata } from "next";
import Section from "@/components/ui/Section";
import ContactForm from "@/components/ContactForm";
import { Mail, ArrowRight } from "lucide-react";

export const metadata: Metadata = {
  title: "Request a pilot — Enlace Telemetry",
  description:
    "We're onboarding a small number of fibre operators to validate Enlace on real networks — free during the pilot, with preferential pricing at launch.",
};

const MAILTO =
  "mailto:hello@enlace.network?subject=Enlace%20pilot%20enquiry";

export default function ContactPage() {
  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs tracking-widest uppercase mb-4"
            style={{ color: "var(--accent)" }}
          >
            Launch partners
          </p>
          <h1
            className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6"
            style={{ color: "var(--text-on-dark)" }}
          >
            Request a pilot.
          </h1>
          <p
            className="text-lg md:text-xl leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            We&apos;re onboarding a small number of fibre operators to validate
            Enlace on real networks — free during the pilot, with preferential
            pricing at launch.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <a href={MAILTO} className="enlace-btn-dark gap-2">
              Email us
              <ArrowRight size={16} />
            </a>
          </div>
        </div>
      </Section>

      {/* Contact + form */}
      <Section background="primary">
        <div className="grid gap-12 lg:grid-cols-2">
          {/* Left: context + email */}
          <div className="max-w-md">
            <p
              className="font-serif text-2xl md:text-3xl font-bold leading-snug mb-6"
              style={{ color: "var(--text-primary)" }}
            >
              Tell us about your network.
            </p>
            <p
              className="text-base leading-relaxed mb-8"
              style={{ color: "var(--text-secondary)" }}
            >
              Send us a note about your OLT fleet and what you&apos;d like
              visibility into. We&apos;ll get back to you to set up a pilot on
              your network.
            </p>

            <a
              href={MAILTO}
              className="flex items-center gap-3 no-underline group"
            >
              <div
                className="w-10 h-10 flex items-center justify-center"
                style={{ backgroundColor: "var(--accent-subtle)" }}
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

            <p
              className="mt-6 text-sm"
              style={{ color: "var(--text-secondary)" }}
            >
              Prefer email?{" "}
              <a
                href={MAILTO}
                className="font-medium"
                style={{ color: "var(--accent)" }}
              >
                hello@enlace.network
              </a>
            </p>
          </div>

          {/* Right: form */}
          <ContactForm />
        </div>
      </Section>

      {/* Company note */}
      <Section background="subtle">
        <div className="max-w-2xl mx-auto text-center">
          <p
            className="text-sm leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            Enlace is built by{" "}
            <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
              Pulso Technologies Limited
            </span>
            , a UK-registered company. Registered in England &amp; Wales,
            company no. 17151141.
          </p>
        </div>
      </Section>
    </>
  );
}
