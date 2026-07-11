import type { Metadata } from "next";
import Section from "@/components/ui/Section";

export const metadata: Metadata = {
  title: "Validation — Enlace RF Propagation",
  description:
    "Held-out validation of the Enlace RF propagation model against 3.55 million Anatel field measurements. Every number reproducible from public data.",
};

const SLICES: [string, string, string, string][] = [
  ["Urban (station-attributed)", "257,446", "25.8 dB", "7.0 dB"],
  ["Suburban", "13,625", "26.1 dB", "7.6 dB"],
  ["Rural", "35,621", "25.6 dB", "8.3 dB"],
  ["Urban (blind proximity tier)", "359,914", "28.6 dB", "8.3 dB"],
];

export default function ValidationPage() {
  return (
    <>
      <Section hero background="dark" grain>
        <div className="max-w-3xl">
          <p className="font-mono text-xs tracking-widest uppercase mb-4" style={{ color: "var(--accent)" }}>
            Validation Report · v1 · July 2026
          </p>
          <h1 className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-6">
            Measured against 3.55 million government field measurements
          </h1>
          <p className="text-lg md:text-xl leading-relaxed max-w-2xl opacity-90">
            Most propagation tools publish no accuracy numbers at all. Ours are
            computed against Anatel&apos;s national RF measurement database
            (2005–2025), evaluated strictly out-of-sample, and reproducible by
            anyone from public data.
          </p>
        </div>
      </Section>

      <Section background="surface">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-2xl md:text-3xl font-bold leading-snug mb-6">
            Held-out accuracy of the calibrated model
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr className="font-mono text-xs uppercase tracking-wider text-left opacity-60">
                  <th className="py-2 pr-4">Slice</th>
                  <th className="py-2 pr-4 text-right">Test points</th>
                  <th className="py-2 pr-4 text-right">RMSE uncalibrated</th>
                  <th className="py-2 text-right">RMSE calibrated</th>
                </tr>
              </thead>
              <tbody>
                {SLICES.map(([name, n, before, after]) => (
                  <tr key={name} style={{ borderTop: "1px solid var(--border, #e5e5e5)" }}>
                    <td className="py-3 pr-4">{name}</td>
                    <td className="py-3 pr-4 text-right font-mono">{n}</td>
                    <td className="py-3 pr-4 text-right font-mono opacity-60">{before}</td>
                    <td className="py-3 text-right font-mono font-bold" style={{ color: "var(--accent)" }}>
                      {after}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-6 text-sm leading-relaxed opacity-70">
            Method: near-station composite field prediction over five open data
            layers (SRTM, Copernicus GLO-30, ANADEM bare earth, MapBiomas land
            cover, Google Open Buildings), scored against Anatel RNI
            measurements joined to the daily-refreshed SMP licensing registry.
            Corrections fitted on an 80% split; every number above comes from
            the untouched 20%. Assumptions (typical per-band EIRP, sector
            heuristic) are documented in the methodology.
          </p>
        </div>
      </Section>

      <Section background="subtle">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-2xl md:text-3xl font-bold leading-snug mb-6">
            What the data revealed
          </h2>
          <ul className="space-y-4 text-base leading-relaxed">
            <li>
              <strong>The antenna pattern is visible in the national data.</strong>{" "}
              Prediction bias decays from −26 dB under towers to ≈0 dB at
              1.5–2 km — the signature of sector downtilt, learned from 1.7M
              points and folded back into the model.
            </li>
            <li>
              <strong>Frequency behavior isolated per band.</strong> 700 MHz
              out-propagates 2.5 GHz by ~10 dB after distance correction,
              measured from single-band stations.
            </li>
            <li>
              <strong>Physically coherent clutter structure.</strong> Water
              paths lose ~4 dB less than land; forest spreads widest — exactly
              as propagation physics predicts.
            </li>
          </ul>
          <p className="mt-8 text-sm opacity-70">
            Data sources: Anatel open data (RNI measurements; SMP licensing) ·
            MapBiomas C9 · SRTM GL1 · Copernicus GLO-30 · ANADEM v1 · Google
            Open Buildings 2.5D. Scoring and fit scripts ship in the Enlace
            repository.
          </p>
          <div className="mt-8">
            <a
              href="/whitepaper/enlace-rf-whitepaper.pdf"
              className="inline-block rounded-md px-5 py-2.5 text-sm font-medium"
              style={{ background: "var(--accent)", color: "#fff" }}
            >
              Baixar o whitepaper completo (PDF) — arquitetura, física,
              calibração e go-to-market
            </a>
          </div>
        </div>
      </Section>
    </>
  );
}
