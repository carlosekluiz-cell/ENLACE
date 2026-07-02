"use client";

// Honest empty state: no audit persisted for this tenant yet. Never renders
// placeholder numbers — points at the two real ways to get data in (CSV
// upload through the agent proxy, or persisting the bundled demo fixture,
// which keeps its DEMO source badge).

import { useState } from "react";
import { Database } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { roleAtLeast } from "@/lib/roles";
import { loadDemoAuditAction } from "@/lib/useOps";

export default function NoAuditState({ reason }: { reason: string }) {
  const { session } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canLoad = session ? roleAtLeast(session.role, "analyst") : false;

  return (
    <div className="op-card p-6 max-w-xl flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Database size={16} style={{ color: "var(--text-on-dark-muted)" }} />
        <span className="op-label">no audit loaded yet</span>
      </div>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text-on-dark-secondary)" }}>
        {reason}
      </p>
      <p className="text-xs leading-relaxed" style={{ color: "var(--text-on-dark-muted)" }}>
        Upload an OLT CSV export (analyst+) to run a real audit through the
        agent, or load the bundled demo audit — real agent output, persisted
        with an honest DEMO source badge.
      </p>
      {canLoad ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError(null);
            loadDemoAuditAction()
              .catch((err: unknown) =>
                setError(err instanceof Error ? err.message : "failed to load demo audit"),
              )
              .finally(() => setBusy(false));
          }}
          className="enlace-btn-primary self-start"
        >
          {busy ? "loading demo audit…" : "Load demo audit"}
        </button>
      ) : (
        <p className="font-mono text-[11px]" style={{ color: "var(--text-on-dark-muted)" }}>
          loading the demo audit requires role analyst or above — ask your NOC
          operator or supervisor
        </p>
      )}
      {error && (
        <p className="font-mono text-xs" style={{ color: "var(--danger)" }} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
