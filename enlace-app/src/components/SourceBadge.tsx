"use client";

// Data provenance badge — always on screen (honesty rule 4). Says exactly
// where the numbers came from, and why the live feed is absent when it is.

import type { AuditFeed } from "@/lib/api";
import { DEMO_PROVENANCE } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function SourceBadge({ feed }: { feed: AuditFeed }) {
  const { t } = useI18n();

  const color =
    feed.source === "live"
      ? "var(--status-online)"
      : feed.source === "audit"
        ? "var(--accent)"
        : "var(--status-warn)";

  const title =
    feed.source === "demo"
      ? `Real agent output, bundled sample. Generated ${DEMO_PROVENANCE.generatedAt} by: ${DEMO_PROVENANCE.command}`
      : feed.source === "audit"
        ? `Audit ${feed.auditId ?? ""} from the pulso-agent audit server`
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
        {t(`source.${feed.source}`)}
      </span>
      {!feed.live.available && (
        <span
          className="font-mono text-[10px]"
          style={{ color: "var(--text-on-dark-muted)" }}
        >
          {t("source.liveDown")} ({feed.live.reason})
        </span>
      )}
    </div>
  );
}
