import type { Metadata } from "next";
import Link from "next/link";
import Section from "@/components/ui/Section";
import { Check, ArrowRight } from "lucide-react";

export const metadata: Metadata = {
  title: "Features — Enlace Telemetry",
  description:
    "Fault detection, signal prediction, capacity planning, multi-vendor support, and real-time diagnostics. Everything Enlace does for your fibre network.",
};

export default function FeaturesPage() {
  return (
    <>
      {/* Hero */}
      <Section background="dark" grain hero>
        <div className="max-w-3xl">
          <p
            className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--accent)" }}
          >
            Platform Capabilities
          </p>
          <h1 className="font-serif text-4xl md:text-5xl font-bold leading-tight">
            Everything Enlace does for your network.
            <span
              className="block mt-2"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              Five modules. One agent. Zero guesswork.
            </span>
          </h1>
          <p
            className="mt-6 text-lg leading-relaxed max-w-2xl"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            Each module below is built into the Enlace agent. No add-ons, no
            upsells — every feature ships with every install.
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
              FAULT DETECTION
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              Fibre cut vs power outage — classified every poll cycle.
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              The agent monitors every ONT on every PON port each poll cycle.
              When ONTs go offline, it correlates the pattern to classify the
              fault type — no human analysis needed.
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[
                "Multiple ONTs offline on same PON port = fibre cut (CRITICAL)",
                "Single ONT offline, neighbours up = CPE failure (MINOR)",
                "ONTs across different ports, same area = power outage (MAJOR)",
                "Rx power dropping below -25 dBm = signal degradation (WARNING)",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
                {"  "}<span style={{ color: "#22c55e" }}>{"\u2192 Slack alert sent"}</span>{"\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"\u2192 Elasticsearch event indexed"}</span>
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
              SIGNAL PREDICTION
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              Know which ONTs will fail before they do.
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              The agent stores Rx power history per ONT and runs linear
              regression on the signal trend. It extrapolates the current
              degradation rate to a failure threshold, producing a continuous
              days-to-failure forecast.
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[
                "Polls Rx power (dBm) every cycle, stores per-ONT time series",
                "Linear regression calculates slope (dBm/week)",
                "Warning at -25 dBm, critical at -28 dBm threshold crossing",
                "Cause estimate based on degradation pattern (connector, bend, splice)",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
                {"  Current Rx: -24.8 dBm (normal)\n"}
                {"  Trend: "}<span style={{ color: "#f59e0b" }}>-0.3 dBm/week</span>{" (degrading)\n"}
                {"  Forecast: failure in "}<span style={{ color: "#f59e0b" }}>~23 days</span>{" at current rate\n"}
                {"  Warning threshold (-25 dBm): ~1 day\n"}
                {"  Critical threshold (-28 dBm): ~73 days\n"}
                {"  Cause estimate: connector degradation or fibre bend\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"\u2192 Schedule proactive maintenance"}</span>
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
              CAPACITY PLANNING
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              Know when your PON ports will saturate.
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              The agent tracks ONT count, bandwidth utilisation, and splitter
              occupancy across every PON port. You get alerts before you run
              out of capacity — not after a failed installation.
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[
                "ONTs per PON port — alert at 80% (103/128 for GPON)",
                "Bandwidth utilisation — alert at 70% sustained for 15 min",
                "Splitter occupancy — alert at last 2 available ports",
                "Growth trend projection — months until full capacity",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
                {"  ONTs: "}<span style={{ color: "#f59e0b" }}>112/128</span>{" (87.5%) "}<span style={{ color: "#f59e0b" }}>WARNING</span>{"\n"}
                {"  Bandwidth: 1.82/2.49 Gbps downstream (73.1%)\n"}
                {"  Splitter: 1:32 — 30/32 ports occupied\n"}
                {"  ───────────────────────────────────────\n"}
                {"  Trend: +4 ONTs/month (last 90 days)\n"}
                {"  Projection: "}<span style={{ color: "#ef4444" }}>Full in ~4 months</span>{"\n"}
                {"  "}<span style={{ color: "#22c55e" }}>{"\u2192 Recommend: provision new splitter on PON 0/0/7"}</span>
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
              MULTI-VENDOR
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              12+ OLT vendors. One unified view.
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Most ISPs run equipment from multiple vendors. Enlace normalises
              the data from all of them into a single schema — same metrics,
              same alerts, regardless of whether the OLT is Huawei, ZTE, or
              BDCOM.
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[
                "Auto-detects vendor from SNMP sysObjectID",
                "Loads correct parser per vendor automatically",
                "No vendor lock-in — mix Huawei and ZTE in the same network",
                "Acquisition-ready: unify both networks on day one",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
              REAL-TIME DIAGNOSTICS
            </p>
            <h2 className="font-serif text-3xl font-bold md:text-4xl">
              Per-ONT health cards for the help desk.
            </h2>
            <p
              className="mt-4 text-base leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              When a subscriber calls, your support agent needs answers in
              seconds. Enlace provides a complete health card for every ONT —
              no SSH into the OLT, no CLI commands, no guessing.
            </p>
            <ul className="mt-6 space-y-3 list-none p-0 m-0">
              {[
                "Serial number, model, firmware, Rx/Tx power, distance",
                "Temperature, traffic in/out, uptime, signal trend",
                "12 data points per ONT per poll cycle",
                "Normalised schema regardless of OLT vendor",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
            See it in action.
          </h2>
          <p
            className="mt-4 text-base leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            See an example report — signal scores, fault detection, ghost
            connections, and churn risk — then request a pilot to run Enlace
            against your own network.
          </p>
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/examples" className="enlace-btn-dark gap-2">
              See an example
              <ArrowRight size={16} />
            </Link>
            <Link href="/contact" className="enlace-btn-ghost">
              Request a pilot
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
