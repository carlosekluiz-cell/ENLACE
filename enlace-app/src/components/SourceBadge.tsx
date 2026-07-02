"use client";

// Data provenance badge — always on screen (honesty rule 4). Says exactly
// where the numbers came from (stored DB provenance, not a UI guess), and
// why the live feed is absent when it is.

import { DEMO_PROVENANCE } from "@/lib/api";
import type { FeedMeta } from "@/lib/useOps";
import { useI18n } from "@/lib/i18n";

export default function SourceBadge({ meta }: { meta: FeedMeta }) {
  const { t } = useI18n();

  const color =
    meta.source === "live"
      ? "var(--status-online)"
      : meta.source === "audit"
        ? "var(--accent)"
        : "var(--status-warn)";

  const title =
    meta.source === "demo"
      ? `Real agent output, bundled sample, persisted with source=demo. Generated ${DEMO_PROVENANCE.generatedAt} by: ${DEMO_PROVENANCE.command}`
      : meta.source === "audit"
        ? `Audit ${meta.auditId ?? ""} — uploaded CSV, persisted in the app DB`
        : "Live Elasticsearch feed connected";

  return (
    <div className="flex flex-col items-end gap-0.5" title={title}>
      <span
        className="inline-flex items-center gap-1.5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest"
        style={{ border: `1px solid ${color}`, color }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: color }}
        />
        {t(`source.${meta.source}`)}
      </span>
      {!meta.live.available && (
        <span
          className="font-mono text-[10px]"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          {t("source.liveDown")} ({meta.live.reason})
        </span>
      )}
    </div>
  );
}
