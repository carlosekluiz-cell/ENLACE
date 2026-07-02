// GET /api/noc/summary — live NOC feed from Elasticsearch, proxied
// server-side (ELASTIC_URL / ELASTIC_API_KEY never reach the browser).
//
// Honesty contract: when ES is not configured or not answering, this route
// returns { available: false, reason } and the UI states "live feed not
// connected — showing audit data". It NEVER fabricates liveness.

import { NextRequest, NextResponse } from "next/server";
import type { NocSummaryResponse } from "@/lib/types";
import { authzResponse, requireSession } from "@/lib/serverAuth";

const INDEX_PATTERN = "enlace-ont-*";

interface EsAggResponse {
  hits?: { total?: { value?: number } };
  aggregations?: {
    by_status?: { buckets?: Array<{ key: string; doc_count: number }> };
    latest?: { value_as_string?: string | null };
  };
}

export async function GET(req: NextRequest) {
  // Any authenticated session: the SourceBadge on every persona view shows
  // honest live-feed availability, so viewer+ may read this aggregate.
  try {
    await requireSession(req);
  } catch (err) {
    return authzResponse(err);
  }

  const url = process.env.ELASTIC_URL;
  if (!url) {
    const body: NocSummaryResponse = {
      available: false,
      reason: "ELASTIC_URL not configured",
    };
    return NextResponse.json(body);
  }

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (process.env.ELASTIC_API_KEY) {
    headers.Authorization = `ApiKey ${process.env.ELASTIC_API_KEY}`;
  }

  try {
    const res = await fetch(
      `${url.replace(/\/$/, "")}/${INDEX_PATTERN}/_search`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          size: 0,
          aggs: {
            by_status: { terms: { field: "status.keyword", size: 10 } },
            latest: { max: { field: "@timestamp" } },
          },
        }),
        // Live board: never serve a cached liveness answer.
        cache: "no-store",
      },
    );

    if (!res.ok) {
      const body: NocSummaryResponse = {
        available: false,
        reason: `Elasticsearch returned ${res.status}`,
      };
      return NextResponse.json(body);
    }

    const data = (await res.json()) as EsAggResponse;
    const buckets = data.aggregations?.by_status?.buckets ?? [];
    const body: NocSummaryResponse = {
      available: true,
      index_pattern: INDEX_PATTERN,
      doc_count: data.hits?.total?.value ?? 0,
      latest_timestamp: data.aggregations?.latest?.value_as_string ?? null,
      status_counts: Object.fromEntries(
        buckets.map((b) => [b.key, b.doc_count]),
      ),
    };
    return NextResponse.json(body);
  } catch {
    const body: NocSummaryResponse = {
      available: false,
      reason: "Elasticsearch unreachable",
    };
    return NextResponse.json(body);
  }
}
