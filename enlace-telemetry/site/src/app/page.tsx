import Link from "next/link";
import Section from "@/components/ui/Section";
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
              Your network is talking.
              <span
                className="block mt-2"
                style={{ color: "var(--text-on-dark-muted)" }}
              >
                Now you can listen.
              </span>
            </h1>

            <p
              className="mt-6 max-w-xl text-lg leading-relaxed"
              style={{ color: "var(--text-on-dark-secondary)" }}
            >
              Enlace reads the telemetry your OLTs already produce — read-only —
              and turns it into early warnings: fibre faults, degrading signal,
              ghost connections, churn risk. 12+ OLT vendors. 60-second
              intervals. One 8.7&nbsp;MB static binary.
            </p>

            <p
              className="mt-4 max-w-xl text-sm leading-relaxed"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              Enlace is the first product from Pulso Technologies, a UK
              telecom-technology startup. We&apos;re pre-launch — onboarding a
              small number of fibre operators as validation partners.
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link href="/contact" className="enlace-btn-dark gap-2">
                Request a pilot
                <ArrowRight size={16} />
              </Link>
              <Link href="/examples" className="enlace-btn-ghost gap-2">
                See an example
                <ArrowRight size={16} />
              </Link>
            </div>

            {/* Metric bar */}
            <div
              className="mt-12 grid grid-cols-3 gap-px md:grid-cols-6"
              style={{ borderTop: "1px solid var(--border-dark-strong)" }}
            >
              {[
                ["8.7 MB", "Binary size"],
                ["12+", "OLT vendors"],
                ["60s", "Poll interval"],
                ["<1%", "CPU usage"],
                ["6", "Protocols"],
                ["0", "Credentials sent"],
              ].map(([value, label]) => (
                <div key={label} className="pt-5">
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
                    {label}
                  </p>
                </div>
              ))}
            </div>
            <p
              className="mt-4 font-mono text-[11px]"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              Figures from internal validation.
            </p>
          </div>

          {/* Right column — terminal mockup */}
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
              <span style={{ color: "#eab308" }}>{"  \u26A0"}</span>
              {" 3 ONTs with degrading signal (est. failure: 8-21 days)\n"}
              <span style={{ color: "#22c55e" }}>{"  \u2713"}</span>
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
          THE PROBLEM
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          Your NOC is reactive.
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            Your customers know before you do.
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
              Before
            </p>
            <ul className="space-y-4 list-none p-0 m-0">
              {[
                "Customer calls with complaint",
                "Technician dispatched blind",
                "Signal degrading undetected for weeks",
                "No per-ONT visibility",
                "Truck roll: £80–150 each",
                "15–25% are 'no fault found'",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  <X
                    size={16}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--danger)" }}
                  />
                  {item}
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
              After
            </p>
            <ul className="space-y-4 list-none p-0 m-0">
              {[
                "Per-ONT monitoring every 60 seconds",
                "Tech gets diagnosis before customer calls",
                "Continuous failure prediction",
                "Dashboard with signal, distance, trend",
                "70% of calls resolved by help desk",
                "Churn scoring (coming soon)",
              ].map((item) => (
                <li
                  key={item}
                  className="flex gap-3 items-start text-sm"
                  style={{ color: "var(--text-primary)" }}
                >
                  <Check
                    size={16}
                    className="mt-0.5 shrink-0"
                    style={{ color: "var(--success)" }}
                  />
                  {item}
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
          HOW IT WORKS
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          One binary. Five minutes.
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            From blind to predictive.
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
            <h3 className="font-serif text-xl font-bold mt-2">Install</h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              One command. Under 10 seconds.
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
            <h3 className="font-serif text-xl font-bold mt-2">Configure</h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              One TOML file. Add your OLTs, set the interval, done.
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
            <h3 className="font-serif text-xl font-bold mt-2">Collect</h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              The agent connects to each OLT using the right protocol and pulls per-ONT data.
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
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" edge-olt-2: gRPC stream opened\n"}
              <span style={{ color: "#22c55e" }}>[INFO]</span>{" edge-olt-2: 312 ONTs collected in 1.8s\n"}
              <span style={{ color: "var(--text-on-dark-muted)" }}>{"───────────────────────────────────"}</span>{"\n"}
              {"  Rx power, Tx power, distance, status,\n"}
              {"  temperature, traffic, uptime per ONT"}
            </div>
          </div>

          {/* Step 4: Act */}
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
            <h3 className="font-serif text-xl font-bold mt-2">Connect</h3>
            <p
              className="mt-2 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Data flows to Elasticsearch, Slack, and webhooks. Plug into what you already use.
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
          CAPABILITIES
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          Six intelligence modules.
          <span
            className="block mt-2"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            Each one replaces a manual process.
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: AlertTriangle,
              title: "Fault Detection",
              anchor: "/features#fault-detection",
              desc: "Fibre cut vs power outage. Multi-ONT correlation on the same PON port. Instant classification.",
              metric: "Per-cycle detection",
            },
            {
              icon: TrendingDown,
              title: "Signal Prediction",
              anchor: "/features#signal-prediction",
              desc: "Linear regression on dBm history. Continuous failure forecast per ONT.",
              metric: "Continuous forecast",
            },
            {
              icon: UserMinus,
              title: "Churn Scoring",
              anchor: "",
              desc: "Degrading signal + repeated disconnects + low usage = cancellation risk score. Currently in development.",
              metric: "Coming Q3 2026",
            },
            {
              icon: BarChart3,
              title: "Capacity Planning",
              anchor: "/features#capacity-planning",
              desc: "PON port utilisation tracking. Alerts at 80%. Splitter saturation forecasting.",
              metric: "80% threshold alert",
            },
            {
              icon: Layers,
              title: "Multi-Vendor",
              anchor: "/features#multi-vendor",
              desc: "Huawei, ZTE, FiberHome, Adtran, Nokia, Datacom + more. One dashboard.",
              metric: "12+ vendors",
            },
            {
              icon: Activity,
              title: "Real-time Diagnostics",
              anchor: "/features#diagnostics",
              desc: "Per-ONT signal level, distance, status, temperature. Customer health card for the help desk.",
              metric: "60s intervals",
            },
          ].map((feature) => {
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
                  {feature.title}
                </h3>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--text-on-dark-secondary)" }}
                >
                  {feature.desc}
                </p>
                <p
                  className="mt-4 font-mono text-xs font-semibold"
                  style={{ color: "var(--accent)" }}
                >
                  {feature.metric}
                </p>
                {feature.anchor && (
                  <p
                    className="mt-3 text-sm font-medium"
                    style={{ color: "var(--text-on-dark-muted)" }}
                  >
                    {"Learn more \u2193"}
                  </p>
                )}
              </>
            );

            return feature.anchor ? (
              <a
                key={feature.title}
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
                key={feature.title}
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
          VENDOR SUPPORT
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          12+ OLT vendors.
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            Every protocol. One agent.
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
                  Vendor
                </th>
                <th
                  className="text-left py-3 pr-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  Models
                </th>
                <th
                  className="text-left py-3 font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}
                >
                  Protocols
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
                ["Adtran", "SDX 6320", "gRPC (OpenOLT)"],
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
                  Partial support
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
                  Also collected
                </td>
              </tr>
              {[
                ["MikroTik", "—", "RouterOS API (PPPoE, BGP, traffic)"],
                ["RADIUS", "—", "UDP 1813 (sessions, bytes, duration)"],
                ["TR-069 CPE", "—", "GenieACS API (WiFi, SNR, devices)"],
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
      </Section>

      {/* ── SECTION 6: TRUST ────────────────────────────────────── */}
      <Section background="primary" id="trust">
        <p
          className="font-mono text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--accent)" }}
        >
          TRUST
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          Read-only &amp; verifiable.
          <span className="block mt-2" style={{ color: "var(--text-muted)" }}>
            No lock-in by design.
          </span>
        </h2>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: Shield,
              title: "Read-only — the agent never writes to your kit",
            },
            {
              icon: Lock,
              title: "Your credentials stay on your network",
            },
            {
              icon: Scale,
              title:
                "Vendor-agnostic via open standards (SNMP/NETCONF) — no single-vendor lock-in",
            },
            {
              icon: Database,
              title: "Your data stays yours",
            },
            {
              icon: BookOpen,
              title:
                "We'll walk your engineers through exactly what the agent does — read-only — so they can verify it without us handing over source",
            },
          ].map((item) => (
            <div
              key={item.title}
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
                {item.title}
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
          COMPARISON
        </p>

        <h2 className="font-serif text-3xl font-bold md:text-5xl">
          Calix Cloud charges per subscriber.
          <span
            className="block mt-2"
            style={{ color: "var(--text-on-dark-muted)" }}
          >
            And only works with Calix hardware.
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
                  Feature
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
                ["OLT vendors", "Calix only", "12+ vendors"],
                ["Per-ONT telemetry", "Yes", "Yes"],
                ["Predictive maintenance", "Yes", "Yes"],
                ["Read-only / no lock-in", "Closed", "Yes — open standards"],
                ["Vendor lock-in", "Total", "None"],
                ["Pricing model", "Per subscriber", "Free pilot at launch"],
                ["Install time", "Weeks", "5 minutes"],
                ["Credentials leave network", "Yes", "Never"],
              ].map(([feature, calix, enlace]) => (
                <tr
                  key={feature}
                  style={{
                    borderBottom: "1px solid var(--border-dark-strong)",
                  }}
                >
                  <td
                    className="py-3 pr-4 font-medium"
                    style={{ color: "var(--text-on-dark)" }}
                  >
                    {feature}
                  </td>
                  <td
                    className="py-3 pr-4"
                    style={{ color: "var(--text-on-dark-muted)" }}
                  >
                    {calix}
                  </td>
                  <td
                    className="py-3 font-medium"
                    style={{ color: "var(--text-on-dark)" }}
                  >
                    {enlace}
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
            LAUNCH PARTNERS
          </p>

          <h2 className="font-serif text-3xl font-bold md:text-5xl">
            Free pilot for launch partners
          </h2>

          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            We&apos;re onboarding a small number of fibre operators to validate
            Enlace on real networks — free during the pilot, with preferential
            pricing at launch.
          </p>

          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-primary gap-2">
              Request a pilot
              <ArrowRight size={16} />
            </Link>
            <Link href="/examples" className="enlace-btn-outline">
              See an example
            </Link>
          </div>
        </div>
      </Section>

      {/* ── SECTION 9: CTA ──────────────────────────────────────── */}
      <Section background="dark" grain>
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-3xl font-bold md:text-5xl">
            Your network has the data.
            <span
              className="block mt-2"
              style={{ color: "var(--text-on-dark-muted)" }}
            >
              Stop flying blind.
            </span>
          </h2>

          <p
            className="mt-6 text-lg leading-relaxed"
            style={{ color: "var(--text-on-dark-secondary)" }}
          >
            See an example of what Enlace finds, then request a pilot to run it
            against your own network.
          </p>

          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link href="/contact" className="enlace-btn-dark gap-2">
              Request a pilot
              <ArrowRight size={16} />
            </Link>
            <Link href="/examples" className="enlace-btn-ghost gap-2">
              See an example
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
