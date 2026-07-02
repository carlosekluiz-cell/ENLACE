"use client";

import { useEffect, useState } from "react";
import { loadAuditFeed, type AuditFeed } from "@/lib/api";

export interface AuditFeedState {
  feed: AuditFeed | null;
  loading: boolean;
  error: string | null;
}

/** Loads the audit feed (live → audit → demo fallback) once per mount. */
export function useAuditFeed(): AuditFeedState {
  const [state, setState] = useState<AuditFeedState>({
    feed: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    loadAuditFeed()
      .then((feed) => {
        if (!cancelled) setState({ feed, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            feed: null,
            loading: false,
            error: err instanceof Error ? err.message : "failed to load audit feed",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
