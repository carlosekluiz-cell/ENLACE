"use client";

import Link from "next/link";
import Section from "@/components/ui/Section";
import { Check, ArrowRight } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export default function FeaturesContent() {
  const { t } = useI18n();

  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--accent)" }}
          >
            {t("features.eyebrow")}
          </p>
          <h1 className="font-serif text-4xl md:text-5xl font-bold leading-tight">
            {t("features.hero.title1")}
            <span
              className="block mt-2"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              {t("features.hero.title2")}
            </span>
          </h1>
          <p
            className="mt-6 text-lg leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            {t("features.hero.lead")}
          </p>
        </div>
      </Section>

      {/* ── FAULT DETECTION ──────────────────────────────────────── */}
      <Section background="primary" id="fault-detection">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent)" }}
            >
              {t("features.fault.eyebrow")}
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              {t("features.fault.title")}
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("features.fault.desc")}
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[1, 2, 3, 4, 5].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`features.fault.${n}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <div className="terminal-frame-dot" style={{ backgroundColor: "#ef4444" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#f59e0b" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#22c55e" }} />
              <span className="ml-2 font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                enlace-agent — fault event
              </span>
            </div>
            <div className="terminal-frame-body">
              <pre className="whitespace-pre-wrap">
                <span style={{ color: "#ef4444" }}>[FAULT]</span>
                {" PON 0/1/0 — 7 ONTs offline in 12s\n"}
                {"  Type: "}<span style={{ color: "#f59e0b" }}>FIBRE_CUT</span>{" (multi-ONT, same port)\n"}
                {"  Severity: "}<span style={{ color: "#ef4444" }}>CRITICAL</span>{"\n"}
                {"  Affected: ONT-0042, ONT-0043, ONT-0044, ONT-0045,\n"}
                {"            ONT-0046, ONT-0047, ONT-0048\n"}
                {"  Last known Rx: -24.3 to -26.1 dBm (normal range)\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"→ Slack alert sent"}</span>{"\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"→ Elasticsearch event indexed"}</span>
              </pre>
            </div>
          </div>
        </div>
      </Section>

      {/* ── SIGNAL PREDICTION ────────────────────────────────────── */}
      <Section background="subtle" id="signal-prediction">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent)" }}
            >
              {t("features.signal.eyebrow")}
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              {t("features.signal.title")}
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("features.signal.desc")}
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[1, 2, 3, 4].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`features.signal.${n}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <div className="terminal-frame-dot" style={{ backgroundColor: "#ef4444" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#f59e0b" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#22c55e" }} />
              <span className="ml-2 font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                enlace-agent — signal prediction
              </span>
            </div>
            <div className="terminal-frame-body">
              <pre className="whitespace-pre-wrap">
                <span style={{ color: "var(--accent)" }}>[PREDICTION]</span>
                {" ONT SN:HWTC-A1B2C3D4\n"}
                {"  Current Rx: -24.8 dBm\n"}
                {"  Trend: "}<span style={{ color: "#f59e0b" }}>-0.12 dBm/day</span>{" (WARNING tier)\n"}
                {"  Fit: R² 0.87 (trend confirmed)\n"}
                {"  Forecast: crosses -27 dBm in "}<span style={{ color: "#f59e0b" }}>~18 days</span>{"\n"}
                {"  Cause estimate: connector degradation or fibre bend\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"→ Schedule proactive maintenance"}</span>
              </pre>
            </div>
          </div>
        </div>
      </Section>

      {/* ── CAPACITY PLANNING ────────────────────────────────────── */}
      <Section background="surface" id="capacity-planning">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent)" }}
            >
              {t("features.capacity.eyebrow")}
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              {t("features.capacity.title")}
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("features.capacity.desc")}
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[1, 2, 3, 4].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`features.capacity.${n}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <div className="terminal-frame-dot" style={{ backgroundColor: "#ef4444" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#f59e0b" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#22c55e" }} />
              <span className="ml-2 font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                enlace-agent — capacity monitor
              </span>
            </div>
            <div className="terminal-frame-body">
              <pre className="whitespace-pre-wrap">
                <span style={{ color: "#f59e0b" }}>[CAPACITY]</span>
                {" OLT: HW-MA5800 Slot 0, PON 0/0/3\n"}
                {"  ONTs: "}<span style={{ color: "#f59e0b" }}>112/128</span>{" (87.5%) "}<span style={{ color: "#f59e0b" }}>WARNING</span>{" (>75%)\n"}
                {"  Splitter: 1:128 (configured)\n"}
                {"  ───────────────────────────────────────\n"}
                {"  Trend: +4 ONTs/month (last 90 days)\n"}
                {"  Projection: "}<span style={{ color: "#ef4444" }}>Full in ~4 months</span>{"\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"→ Recommend: provision new splitter on PON 0/0/7"}</span>
              </pre>
            </div>
          </div>
        </div>
      </Section>

      {/* ── MULTI-VENDOR ─────────────────────────────────────────── */}
      <Section background="primary" id="multi-vendor">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent)" }}
            >
              {t("features.vendor.eyebrow")}
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              {t("features.vendor.title")}
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("features.vendor.desc")}
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[1, 2, 3, 4].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`features.vendor.${n}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <div className="terminal-frame-dot" style={{ backgroundColor: "#ef4444" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#f59e0b" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#22c55e" }} />
              <span className="ml-2 font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                enlace-agent — startup
              </span>
            </div>
            <div className="terminal-frame-body">
              <pre className="whitespace-pre-wrap">
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Connecting to OLT at 10.0.1.1:161\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" sysObjectID: 1.3.6.1.4.1.2011.2.6.6.1\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Vendor detected: "}<span style={{ color: "var(--accent)" }}>Huawei</span>{" (MA5800-X17)\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Loading parser: huawei::ma5800\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Discovered 16 PON ports, 847 ONTs\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" First poll complete in 4.2s\n\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Connecting to OLT at 10.0.2.1:161\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Vendor detected: "}<span style={{ color: "var(--accent)" }}>ZTE</span>{" (C320)\n"}
                <span style={{ color: "#22c55e" }}>[INFO]</span>
                {" Discovered 8 PON ports, 312 ONTs"}
              </pre>
            </div>
          </div>
        </div>
      </Section>

      {/* ── DIAGNOSTICS ──────────────────────────────────────────── */}
      <Section background="subtle" id="diagnostics">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "var(--accent)" }}
            >
              {t("features.diag.eyebrow")}
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              {t("features.diag.title")}
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("features.diag.desc")}
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[1, 2, 3, 4].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`features.diag.${n}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <div className="terminal-frame-dot" style={{ backgroundColor: "#ef4444" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#f59e0b" }} />
              <div className="terminal-frame-dot" style={{ backgroundColor: "#22c55e" }} />
              <span className="ml-2 font-mono text-xs" style={{ color: "var(--text-on-dark-muted)" }}>
                enlace-agent — ONT diagnostics
              </span>
            </div>
            <div className="terminal-frame-body">
              <pre className="whitespace-pre-wrap">
                <span style={{ color: "#22c55e" }}>[DIAG]</span>
                {" ONT SN:HWTC-A1B2C3D4 on PON 0/1/0\n"}
                {"  Model:       HG8546M\n"}
                {"  Firmware:    V3R017C10S115\n"}
                {"  Status:      "}<span style={{ color: "#22c55e" }}>ONLINE</span>{"\n"}
                {"  Rx Power:    "}<span style={{ color: "#22c55e" }}>-22.4 dBm</span>{" (normal)\n"}
                {"  Tx Power:    2.1 dBm\n"}
                {"  Distance:    1,247 m\n"}
                {"  Temperature: 41 C\n"}
                {"  Uptime:      34d 12:07:22\n"}
                {"  Traffic In:  847.2 MB/hr\n"}
                {"  Traffic Out: 94.1 MB/hr\n"}
                {"  Trend:       "}<span style={{ color: "#22c55e" }}>STABLE</span>{" (0.0 dBm/week)\n"}
                {"  CRC Errors:  0/hr\n"}
                {"  FEC Errors:  12/hr (normal)"}
              </pre>
            </div>
          </div>
        </div>
      </Section>

      {/* ── CTA ──────────────────────────────────────────────────── */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-3xl font-bold md:text-4xl"
            style={{ color: "var(--text-on-dark)" }}
          >
            {t("features.cta.title")}
          </h2>
          <p
            className="mt-4 text-base leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            {t("features.cta.lead")}
          </p>
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/examples" className="enlace-btn-dark gap-2">
              {t("common.seeExample")}
              <ArrowRight size={16} />
            </Link>
            <Link href="/contact" className="enlace-btn-ghost">
              {t("common.requestPilot")}
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
