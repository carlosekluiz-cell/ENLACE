"use client";

import Link from "next/link";
import Section from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import {
  AlertTriangle,
  TrendingDown,
  UserMinus,
  BarChart3,
  Layers,
  Activity,
  Check,
  X,
  ArrowRight,
  Shield,
  BookOpen,
  Database,
  Lock,
  Scale,
} from "lucide-react";

/* ───────────────────────────── helpers ───────────────────────────── */

const vendors = [
  "Huawei",
  "ZTE",
  "FiberHome",
  "Adtran",
  "Nokia",
  "Datacom",
  "Parks",
  "BDCOM",
  "CDATA",
  "VSOL",
  "Ubiquiti",
  "Intelbras",
  "MikroTik",
  "RADIUS",
];

/* ───────────────────────────── page ─────────────────────────────── */

export default function Home() {
  const { t } = useI18n();

  const featureCards = [
    {
      icon: AlertTriangle,
      titleKey: "home.feat.fault.title",
      anchor: "/features#fault-detection",
      descKey: "home.feat.fault.desc",
      metricKey: "home.feat.fault.metric",
    },
    {
      icon: TrendingDown,
      titleKey: "home.feat.signal.title",
      anchor: "/features#signal-prediction",
      descKey: "home.feat.signal.desc",
      metricKey: "home.feat.signal.metric",
    },
    {
      icon: UserMinus,
      titleKey: "home.feat.churn.title",
      anchor: "",
      descKey: "home.feat.churn.desc",
      metricKey: "home.feat.churn.metric",
    },
    {
      icon: BarChart3,
      titleKey: "home.feat.capacity.title",
      anchor: "/features#capacity-planning",
      descKey: "home.feat.capacity.desc",
      metricKey: "home.feat.capacity.metric",
    },
    {
      icon: Layers,
      titleKey: "home.feat.vendor.title",
      anchor: "/features#multi-vendor",
      descKey: "home.feat.vendor.desc",
      metricKey: "home.feat.vendor.metric",
    },
    {
      icon: Activity,
      titleKey: "home.feat.diag.title",
      anchor: "/features#diagnostics",
      descKey: "home.feat.diag.desc",
      metricKey: "home.feat.diag.metric",
    },
  ];

  const trustItems = [
    { icon: Shield, key: "home.trust.1" },
    { icon: Lock, key: "home.trust.2" },
    { icon: Scale, key: "home.trust.3" },
    { icon: Database, key: "home.trust.4" },
    { icon: BookOpen, key: "home.trust.5" },
  ];

  return (
    <>
      {/* ── SECTION 1: HERO ─────────────────────────────────────── */}
      <Section background="dark" grain hero>
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center">
          {/* Left column */}
          <div>
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-6"
              style={{ color: "var(--accent)" }}
            >
              Enlace Telemetry
            </p>

            <h1 className="font-serif text-4xl font-bold leading-tight md:text-6xl md:leading-[1.1]">
              {t("home.hero.title1")}
              <span
                className="block mt-2"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                {t("home.hero.title2")}
              </span>
            </h1>

            <p
              className="mt-6 max-w-xl text-lg leading-relaxed"
              style={{ color: "var(--text-on-dark-secondary)" }}
            >
              {t("home.hero.lead")}
            </p>

            <p
              className="mt-4 max-w-xl text-sm leading-relaxed"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              {t("home.hero.sub")}
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link href="/contact" className="enlace-btn-dark gap-2">
                {t("common.requestPilot")}
                <ArrowRight size={16} />
              </Link>
              <Link href="/examples" className="enlace-btn-ghost gap-2">
                {t("common.seeExample")}
                <ArrowRight size={16} />
              </Link>
            </div>

            {/* Metric bar */}
            <div
              className="mt-12 grid grid-cols-3 gap-px md:grid-cols-6"
              style={{ borderTop: "1px solid var(--border-dark-strong)" }}
            >
              {[
                ["8.7 MB", "home.metric.binarySize"],
                ["12+", "home.metric.oltVendors"],
                ["60s", "home.metric.pollInterval"],
                ["0.12s", "home.metric.audit"],
                ["5", "home.metric.protocols"],
                ["0", "home.metric.credentials"],
              ].map(([value, labelKey]) => (
                <div key={labelKey} className="pt-5">
                  <p
                    className="font-mono text-xl font-bold"
                    style={{ color: "var(--accent)" }}
                  >
                    {value}
                  </p>
                  <p
                    className="font-mono text-[11px] uppercase tracking-wide mt-1"
                    style={{ color: "var(--text-on-dark-muted)" }}
                  >
                    {t(labelKey)}
                  </p>
                </div>
              ))}
            </div>
            <p
              className="mt-4 font-mono text-[11px]"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              {t("home.hero.figuresNote")}
            </p>
          </div>

          {/* Right column — terminal mockup (literal agent console output) */}
          <div className="terminal-frame">
            <div className="terminal-frame-header">
              <span
                className="terminal-frame-dot"
                style={{ backgroundColor: "#ef4444" }}
              />
              <span
                className="terminal-frame-dot"
                style={{ backgroundColor: "#eab308" }}
              />
              <span
                className="terminal-frame-dot"
                style={{ backgroundColor: "#22c55e" }}
              />
              <span
                className="ml-3 font-mono text-[11px]"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                enlace-agent
              </span>
            </div>
            <div className="terminal-frame-body whitespace-pre-wrap">
              <span style={{ color: "#22c55e" }}>●</span>
              {" enlace-agent.service — Enlace Telemetry Agent\n"}
              {"   Active: "}
              <span style={{ color: "#22c55e" }}>active (running)</span>
              {" since 47 days\n"}
              {"   Memory: 12.4 MB  CPU: 0.3%\n\n"}
              <span style={{ color: "var(--accent)" }}>$</span>
              {" enlace status\n"}
              {"  OLTs: "}
              <span style={{ color: "var(--text-on-dark)" }}>4 connected</span>
              {" | ONTs: "}
              <span style={{ color: "var(--text-on-dark)" }}>
                2,847 monitored
              </span>
              {"\n"}
              {"  MikroTik: "}
              <span style={{ color: "var(--text-on-dark)" }}>2 peers</span>
              {" | RADIUS: "}
              <span style={{ color: "var(--text-on-dark)" }}>
                1,923 active sessions
              </span>
              {"\n\n"}
              <span style={{ color: "#eab308" }}>{"  ⚠"}</span>
              {" 3 ONTs with degrading signal (est. failure: 8-21 days)\n"}
              <span style={{ color: "#22c55e" }}>{"  ✓"}</span>
              {" Last sync: 4s ago | Buffer: 0 pending"}
            </div>
          </div>
        </div>

        {/* Vendor ticker */}
        <div
          className="mt-16 overflow-hidden"
          style={{ borderTop: "1px solid var(--border-dark-strong)" }}
        >
          <div className="pt-8 flex vendor-ticker">
            {[...vendors, ...vendors].map((name, i) => (
              <span
                key={`${name}-${i}`}
                className="shrink-0 px-6 font-mono text-sm uppercase tracking-wider"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </Section>

      {/* ── SECTION 2: PROBLEM ──────────────────────────────────── */}
      <Section background="primary" id="problem">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.problem.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.problem.title1")}
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            {t("home.problem.title2")}
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {/* BEFORE */}
          <div
            className="p-8"
            style={{
              backgroundColor: "var(--bg-dark)",
              border: "1px solid var(--border-dark-strong)",
            }}
          >
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-6"
              style={{ color: "var(--danger)" }}
            >
              {t("home.problem.before")}
            </p>
            <ul className="space-y-4 list-none p-0 m-0">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  <X
                    size={16}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--danger)" }}
                  />
                  {t(`home.problem.before.${n}`)}
                </li>
              ))}
            </ul>
          </div>

          {/* AFTER */}
          <div
            className="p-8"
            style={{
              backgroundColor: "var(--bg-surface)",
              borderLeft: "3px solid var(--accent)",
              border: "1px solid var(--border)",
              borderLeftWidth: "3px",
              borderLeftColor: "var(--accent)",
            }}
          >
            <p
              className="font-mono text-xs font-semibold uppercase tracking-widest mb-6"
              style={{ color: "var(--accent)" }}
            >
              {t("home.problem.after")}
            </p>
            <ul className="space-y-4 list-none p-0 m-0">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <li
                  key={n}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-primary)" }}
                >
                  <Check
                    size={16}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {t(`home.problem.after.${n}`)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* ── SECTION 3: HOW IT WORKS ─────────────────────────────── */}
      <Section background="subtle" id="how-it-works">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.how.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.how.title1")}
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            {t("home.how.title2")}
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {/* Step 1: Install */}
          <div
            className="p-6"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <span
              className="font-mono text-xs font-semibold"
              style={{ color: "var(--accent)" }}
            >
              01
            </span>
            <h3 className="font-serif text-xl font-bold mt-2">
              {t("home.how.install.title")}
            </h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("home.how.install.desc")}
            </p>
            <div
              className="mt-4 p-3 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap"
              style={{
                backgroundColor: "var(--bg-dark)",
                color: "var(--text-on-dark-secondary)",
                border: "1px solid var(--border-dark-strong)",
              }}
            >
              <span style={{ color: "var(--text-on-dark-muted)" }}>$</span>{" curl -sSL enlace.network/install.sh | bash\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" Downloaded pulso-agent v0.1.0 (8.7 MB, static binary)\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" SHA-256 checksum verified\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" Installed to /usr/local/bin/pulso-agent\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" Ready. Edit /etc/pulso-agent/agent.toml to configure."}
            </div>
          </div>

          {/* Step 2: Configure */}
          <div
            className="p-6"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <span
              className="font-mono text-xs font-semibold"
              style={{ color: "var(--accent)" }}
            >
              02
            </span>
            <h3 className="font-serif text-xl font-bold mt-2">
              {t("home.how.configure.title")}
            </h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("home.how.configure.desc")}
            </p>
            <div
              className="mt-4 p-3 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap"
              style={{
                backgroundColor: "var(--bg-dark)",
                color: "var(--text-on-dark-secondary)",
                border: "1px solid var(--border-dark-strong)",
              }}
            >
              <span style={{ color: "var(--text-on-dark-muted)" }}>{"# /etc/enlace/agent.toml"}</span>{"\n\n"}
              <span style={{ color: "var(--accent)" }}>[[olts]]</span>{"\n"}
              {"name = \"core-olt-1\"\n"}
              {"host = \"10.0.1.1\"\n"}
              {"vendor = \"huawei\"\n\n"}
              <span style={{ color: "var(--accent)" }}>[[olts]]</span>{"\n"}
              {"name = \"edge-olt-2\"\n"}
              {"host = \"10.0.2.1\"\n"}
              {"vendor = \"adtran\""}
            </div>
          </div>

          {/* Step 3: Collect */}
          <div
            className="p-6"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <span
              className="font-mono text-xs font-semibold"
              style={{ color: "var(--accent)" }}
            >
              03
            </span>
            <h3 className="font-serif text-xl font-bold mt-2">
              {t("home.how.collect.title")}
            </h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("home.how.collect.desc")}
            </p>
            <div
              className="mt-4 p-3 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap"
              style={{
                backgroundColor: "var(--bg-dark)",
                color: "var(--text-on-dark-secondary)",
                border: "1px solid var(--border-dark-strong)",
              }}
            >
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" core-olt-1: SNMP poll started\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" core-olt-1: 847 ONTs collected in 4.2s\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" edge-olt-2: NETCONF session opened\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" edge-olt-2: 312 ONTs collected in 1.8s\n"}
              <span style={{ color: "var(--text-on-dark-muted)" }}>{"───────────────────────────────────"}</span>{"\n"}
              {"  Rx power, Tx power, distance, status,\n"}
              {"  temperature, traffic, uptime per ONT"}
            </div>
          </div>

          {/* Step 4: Connect */}
          <div
            className="p-6"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <span
              className="font-mono text-xs font-semibold"
              style={{ color: "var(--accent)" }}
            >
              04
            </span>
            <h3 className="font-serif text-xl font-bold mt-2">
              {t("home.how.connect.title")}
            </h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {t("home.how.connect.desc")}
            </p>
            <div
              className="mt-4 p-3 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap"
              style={{
                backgroundColor: "var(--bg-dark)",
                color: "var(--text-on-dark-secondary)",
                border: "1px solid var(--border-dark-strong)",
              }}
            >
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" Output: Elasticsearch at elastic:9200\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" Output: Slack webhook #noc-alerts\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" Output: Enlace Cloud (api.enlace.network)\n"}
              <span style={{ color: "var(--text-on-dark-muted)" }}>{"───────────────────────────────────"}</span>{"\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" 1,159 ONT metrics → Elasticsearch\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" 2 fault events → Slack\n"}
              <span style={{ color: "#22c55e" }}>{"✓"}</span>{" 3 predictions → Cloud dashboard"}
            </div>
          </div>
        </div>
      </Section>

      {/* ── SECTION 4: FEATURES ─────────────────────────────────── */}
      <Section background="dark" grain id="features">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.features.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.features.title1")}
          <span
            className="block mt-2"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            {t("home.features.title2")}
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {featureCards.map((feature) => {
            const content = (
              <>
                <feature.icon
                  size={24}
                  style={{ color: "var(--accent)" }}
                />
                <h3
                  className="font-serif text-lg font-bold mt-4"
                  style={{ color: "var(--text-on-dark)" }}
                >
                  {t(feature.titleKey)}
                </h3>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  {t(feature.descKey)}
                </p>
                <p
                  className="mt-4 font-mono text-xs font-semibold"
                  style={{ color: "var(--accent)" }}
                >
                  {t(feature.metricKey)}
                </p>
                {feature.anchor && (
                  <p
                    className="mt-3 text-sm font-medium"
                    style={{ color: "var(--text-on-dark-muted)" }}
                  >
                    {t("common.learnMore")}
                  </p>
                )}
              </>
            );

            return feature.anchor ? (
              <a
                key={feature.titleKey}
                href={feature.anchor}
                className="block p-6 transition-colors no-underline"
                style={{
                  backgroundColor: "var(--bg-dark-surface)",
                  border: "1px solid var(--border-dark-strong)",
                }}
              >
                {content}
              </a>
            ) : (
              <div
                key={feature.titleKey}
                className="block p-6"
                style={{
                  backgroundColor: "var(--bg-dark-surface)",
                  border: "1px solid var(--border-dark-strong)",
                }}
              >
                {content}
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── SECTION 5: VENDOR COMPATIBILITY ─────────────────────── */}
      <Section background="surface" id="vendors">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.vendors.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.vendors.title1")}
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            {t("home.vendors.title2")}
          </span>
        </h2>

        <div className="mt-12 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  borderBottom: "2px solid var(--border-strong)",
                }}
              >
                <th
                  className="text-left py-3 pr-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("home.vendors.col.vendor")}
                </th>
                <th
                  className="text-left py-3 pr-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("home.vendors.col.models")}
                </th>
                <th
                  className="text-left py-3 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("home.vendors.col.protocols")}
                </th>
              </tr>
            </thead>
            <tbody>
              {/* Full support */}
              {[
                [
                  "Huawei",
                  "MA5800-X2/X7, MA5600T",
                  "SNMP + SSH + NETCONF",
                ],
                ["ZTE", "C320, C300, C600, C650", "SNMP + SSH"],
                ["FiberHome", "AN5516, AN6001", "SNMP + SSH"],
                ["Adtran", "SDX 6320", t("home.vendors.proto.adtran")],
                ["Datacom", "DM4610, DM4615", "SNMP + NETCONF"],
                ["Nokia", "ISAM/Lightspan", "SNMP + NETCONF"],
                ["Parks", "FiberLink 200/300/400", "SNMP + SSH"],
                ["Intelbras", "G08, G16", "SNMP + SSH"],
              ].map(([vendor, models, protocols]) => (
                <tr
                  key={vendor}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td className="py-3 pr-4 font-medium">{vendor}</td>
                  <td
                    className="py-3 pr-4 font-mono text-xs"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {models}
                  </td>
                  <td
                    className="py-3 font-mono text-xs"
                    style={{ color: "var(--accent)" }}
                  >
                    {protocols}
                  </td>
                </tr>
              ))}

              {/* Partial separator */}
              <tr>
                <td
                  colSpan={3}
                  className="pt-6 pb-2 font-mono text-[11px] uppercase tracking-widest"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("home.vendors.partial")}
                </td>
              </tr>
              {[
                ["BDCOM", "GP3600", "SNMP + SSH"],
                ["VSOL", "V1600D", "SNMP + SSH"],
                ["CDATA", "FD1604S", "SNMP"],
                ["Ubiquiti", "UFiber", "REST API"],
              ].map(([vendor, models, protocols]) => (
                <tr
                  key={vendor}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td className="py-3 pr-4 font-medium">{vendor}</td>
                  <td
                    className="py-3 pr-4 font-mono text-xs"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {models}
                  </td>
                  <td
                    className="py-3 font-mono text-xs"
                    style={{ color: "var(--accent)" }}
                  >
                    {protocols}
                  </td>
                </tr>
              ))}

              {/* Also collected */}
              <tr>
                <td
                  colSpan={3}
                  className="pt-6 pb-2 font-mono text-[11px] uppercase tracking-widest"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("home.vendors.alsoCollected")}
                </td>
              </tr>
              {[
                ["MikroTik", "—", t("home.vendors.proto.mikrotik")],
                ["RADIUS", "—", t("home.vendors.proto.radius")],
                ["TR-069 CPE", "—", t("home.vendors.proto.tr069")],
              ].map(([vendor, models, protocols]) => (
                <tr
                  key={vendor}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td className="py-3 pr-4 font-medium">{vendor}</td>
                  <td
                    className="py-3 pr-4 font-mono text-xs"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {models}
                  </td>
                  <td
                    className="py-3 font-mono text-xs"
                    style={{ color: "var(--accent)" }}
                  >
                    {protocols}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p
          className="mt-4 font-mono text-xs leading-relaxed"
          style={{ color: "var(--text-muted)" }}
        >
          {t("home.vendors.footnote")}
        </p>
      </Section>

      {/* ── SECTION 6: TRUST ────────────────────────────────────── */}
      <Section background="primary" id="trust">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.trust.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.trust.title1")}
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            {t("home.trust.title2")}
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {trustItems.map((item) => (
            <div
              key={item.key}
              className="flex gap-4 items-start p-6"
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <item.icon
                size={20}
                className="mt-0.5 shrink-0"
                style={{ color: "var(--accent)" }}
              />
              <p className="text-sm font-medium leading-relaxed">
                {t(item.key)}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── SECTION 7: VS CALIX ─────────────────────────────────── */}
      <Section background="dark" grain id="vs-calix">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          {t("home.calix.eyebrow")}
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          {t("home.calix.title1")}
          <span
            className="block mt-2"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            {t("home.calix.title2")}
          </span>
        </h2>

        <div className="mt-12 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  borderBottom: "2px solid var(--border-dark-strong)",
                }}
              >
                <th
                  className="text-left py-3 pr-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  {t("home.calix.col.feature")}
                </th>
                <th
                  className="text-left py-3 pr-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-on-dark-muted)" }}
                >
                  Calix Cloud
                </th>
                <th
                  className="text-left py-3 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--accent)" }}
                >
                  Enlace
                </th>
              </tr>
            </thead>
            <tbody>
              {[
                "vendors",
                "telemetry",
                "predictive",
                "readonly",
                "lockin",
                "pricing",
                "install",
                "creds",
              ].map((row) => (
                <tr
                  key={row}
                  style={{
                    borderBottom: "1px solid var(--border-dark-strong)",
                  }}
                >
                  <td
                    className="py-3 pr-4 font-medium"
                    style={{ color: "var(--text-on-dark)" }}
                  >
                    {t(`home.calix.row.${row}.f`)}
                  </td>
                  <td
                    className="py-3 pr-4"
                    style={{ color: "var(--text-on-dark-muted)" }}
                  >
                    {t(`home.calix.row.${row}.c`)}
                  </td>
                  <td
                    className="py-3 font-medium"
                    style={{ color: "var(--text-on-dark)" }}
                  >
                    {t(`home.calix.row.${row}.e`)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── SECTION 8: PILOT ────────────────────────────────────── */}
      <Section background="surface" id="pilot">
        <div className="text-center max-w-2xl mx-auto">
          <p
            className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--accent)" }}
          >
            {t("home.pilot.eyebrow")}
          </p>

          <h2 className="font-serif text-3xl font-bold md:text-5xl">
            {t("home.pilot.title")}
          </h2>

          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            {t("home.pilot.lead")}
          </p>

          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-primary gap-2">
              {t("common.requestPilot")}
              <ArrowRight size={16} />
            </Link>
            <Link href="/examples" className="enlace-btn-outline">
              {t("common.seeExample")}
            </Link>
          </div>
        </div>
      </Section>

      {/* ── SECTION 9: CTA ──────────────────────────────────────── */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-3xl font-bold md:text-5xl">
            {t("home.cta.title1")}
            <span
              className="block mt-2"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              {t("home.cta.title2")}
            </span>
          </h2>

          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            {t("home.cta.lead")}
          </p>

          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-dark gap-2">
              {t("common.requestPilot")}
              <ArrowRight size={16} />
            </Link>
            <Link href="/examples" className="enlace-btn-ghost gap-2">
              {t("common.seeExample")}
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
