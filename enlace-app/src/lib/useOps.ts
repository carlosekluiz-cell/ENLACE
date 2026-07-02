"use client";

// ── Client hooks for the persisted-audit data flow ──
//
// "Current audit" resolution: the module-level store below holds the
// user's explicit pick from the audit picker (per tab); null means "most
// recent for the tenant" (the server default). Views fetch their persona
// projection from the server — the client never computes projections from
// shipped JSON. Mutations (ack/assign/close/load-demo) bump an ops version
// so every mounted hook refetches — state survives refresh because it lives
// in the app DB, not here.
//
// Store convention: useSyncExternalStore over a module store (app rule —
// no setState-in-effect for shared state). Fetch results still use local
// useState inside effects, same pattern as the rest of the app.

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { fetchNocSummary, type DataSource } from "@/lib/api";
import type { NocSummaryResponse } from "@/lib/types";
import type {
  AuditListEntry,
  AuditListResponse,
  ProjectionBase,
  ProjectionUnavailable,
  TicketActionResponse,
} from "@/lib/opsTypes";

// ── Selected audit + ops version (module store) ──

interface OpsSnapshot {
  /** Audits row id explicitly picked in the UI; null = most recent. */
  selectedAuditId: string | null;
  /** Bumped after every mutation so hooks refetch. */
  version: number;
}

const SERVER_SNAPSHOT: OpsSnapshot = { selectedAuditId: null, version: 0 };
let snapshot: OpsSnapshot = SERVER_SNAPSHOT;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function setSelectedAudit(id: string | null): void {
  snapshot = { ...snapshot, selectedAuditId: id };
  emit();
}

/** Refetch trigger after any server-side state change. */
export function bumpOpsVersion(): void {
  snapshot = { ...snapshot, version: snapshot.version + 1 };
  emit();
}

export function useOpsSnapshot(): OpsSnapshot {
  return useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => SERVER_SNAPSHOT,
  );
}

// ── Feed metadata for the always-visible SourceBadge ──

export interface FeedMeta {
  source: DataSource;
  /** Agent-assigned audit id. */
  auditId: string | null;
  /** audits row id (what ticket actions and ?audit= use). */
  auditRowId: string | null;
  /** Honest live-feed availability from /api/noc/summary. */
  live: NocSummaryResponse;
  fetchedAt: string;
}

// ── Generic projection fetch ──

export interface ProjectionState<T extends ProjectionBase> {
  data: T | null;
  /** Honest empty state: no audit persisted yet / bad id / parse failure. */
  unavailable: ProjectionUnavailable | null;
  meta: FeedMeta | null;
  loading: boolean;
  error: string | null;
}

function useOpsFetch<T extends ProjectionBase>(
  path: string,
  auditOverride?: string | null,
): ProjectionState<T> {
  const { selectedAuditId, version } = useOpsSnapshot();
  // Deep links (?audit= on /field/ticket/[id]) pin the audit explicitly and
  // win over the per-tab picker selection.
  const effectiveAuditId = auditOverride ?? selectedAuditId;
  const [state, setState] = useState<ProjectionState<T>>({
    data: null,
    unavailable: null,
    meta: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    const url = effectiveAuditId
      ? `${path}?audit=${encodeURIComponent(effectiveAuditId)}`
      : path;

    Promise.all([
      fetch(url).then(async (res) => {
        const body = (await res.json().catch(() => null)) as
          | T
          | ProjectionUnavailable
          | { error?: string }
          | null;
        if (!res.ok && !(body && "available" in body)) {
          const msg =
            body && "error" in body && typeof body.error === "string"
              ? body.error
              : `request failed (${res.status})`;
          throw new Error(msg);
        }
        return body as T | ProjectionUnavailable;
      }),
      fetchNocSummary(),
    ])
      .then(([body, live]) => {
        if (cancelled) return;
        if (body.available === false) {
          setState({
            data: null,
            unavailable: body,
            meta: null,
            loading: false,
            error: null,
          });
          return;
        }
        setState({
          data: body,
          unavailable: null,
          meta: {
            source: body.provenance.source,
            auditId: body.provenance.audit_id,
            auditRowId: body.provenance.id,
            live,
            fetchedAt: new Date().toISOString(),
          },
          loading: false,
          error: null,
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            data: null,
            unavailable: null,
            meta: null,
            loading: false,
            error: err instanceof Error ? err.message : "failed to load data",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [path, effectiveAuditId, version]);

  return state;
}

export type ProjectionKind = "noc" | "field" | "supervisor" | "exec";

/** Persona projection for the current audit (picked or most recent). */
export function useProjection<T extends ProjectionBase>(
  kind: ProjectionKind,
): ProjectionState<T> {
  return useOpsFetch<T>(`/api/projections/${kind}`);
}

/**
 * Role-scoped ticket list (viewer: own; analyst+: all) for the current audit.
 * `auditOverride` pins an explicit audit (deep links); null/undefined falls
 * back to the picker selection, then the tenant's most recent audit.
 */
export function useTicketList<T extends ProjectionBase>(
  auditOverride?: string | null,
): ProjectionState<T> {
  return useOpsFetch<T>("/api/tickets", auditOverride);
}

// ── Audit listing (picker data) ──

export interface AuditListState {
  audits: AuditListEntry[];
  loading: boolean;
  error: string | null;
}

export function useAuditList(): AuditListState {
  const { version } = useOpsSnapshot();
  const [state, setState] = useState<AuditListState>({
    audits: [],
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/audits")
      .then(async (res) => {
        if (!res.ok) throw new Error(`audit list failed (${res.status})`);
        return (await res.json()) as AuditListResponse;
      })
      .then((body) => {
        if (!cancelled) setState({ audits: body.audits, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            audits: [],
            loading: false,
            error: err instanceof Error ? err.message : "failed to list audits",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [version]);

  return state;
}

// ── Mutations (all bump the ops version on success) ──

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const parsed = (await res.json().catch(() => null)) as
    | (T & { error?: string })
    | null;
  if (!res.ok) {
    throw new Error(parsed?.error ?? `request failed (${res.status})`);
  }
  return parsed as T;
}

export async function ackTicketAction(
  ref: string,
  auditRowId: string,
): Promise<TicketActionResponse> {
  const out = await postJson<TicketActionResponse>(
    `/api/tickets/${encodeURIComponent(ref)}/ack`,
    { audit: auditRowId },
  );
  bumpOpsVersion();
  return out;
}

export async function assignTicketAction(
  ref: string,
  auditRowId: string,
  assignee: string,
): Promise<TicketActionResponse> {
  const out = await postJson<TicketActionResponse>(
    `/api/tickets/${encodeURIComponent(ref)}/assign`,
    { audit: auditRowId, assignee },
  );
  bumpOpsVersion();
  return out;
}

export async function closeTicketAction(
  ref: string,
  auditRowId: string,
  note: string,
  ack: boolean,
): Promise<TicketActionResponse> {
  const out = await postJson<TicketActionResponse>(
    `/api/tickets/${encodeURIComponent(ref)}/close`,
    { audit: auditRowId, note, ack },
  );
  bumpOpsVersion();
  return out;
}

/** Persist the bundled demo fixture (source badge stays DEMO — honest). */
export async function loadDemoAuditAction(): Promise<void> {
  await postJson<{ created: boolean }>("/api/audits/demo", {});
  bumpOpsVersion();
}

/** Stable hook wrapper so components get a memoized refresh callback. */
export function useOpsRefresh(): () => void {
  return useCallback(() => bumpOpsVersion(), []);
}
