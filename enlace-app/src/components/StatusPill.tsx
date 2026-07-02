"use client";

// Status pill — Unknown gets its own violet, never Offline's red (rule 2).

import { statusColor } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

export default function StatusPill({ status }: { status: string }) {
  const { t } = useI18n();
  const color = statusColor(status);
  const key = `status.${status}`;
  const label = t(key) === key ? status : t(key);

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 font-mono text-[11px]"
      style={{ color, border: `1px solid ${color}` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
