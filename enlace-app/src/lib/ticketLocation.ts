// ── Fault location derivation (Wave C2) ──
//
// Derives a TicketLocation from what the audit JSON ACTUALLY contains for a
// ticket's affected ONTs. Sources, in order of preference:
//
//   1. Genuine coordinates — lat/lon on an ONT row (top-level or in the
//      vendor `extended` map). The agent's telemetry does not produce these
//      today; they appear only when a geo join / ONT geo data exists. We
//      never synthesize them.
//   2. Distance estimate — ONT ranging distance from the OLT
//      (onts[].distance_meters), cross-checked against fault events'
//      affected_onts[].distance_meters (fault/locator.rs works off the same
//      field: "Break estimated within N m of OLT").
//   3. Honest none — the audit simply has no location data for these ONTs.
//
// Pure over agent-shaped types (no DB, no next imports): usable from server
// routes AND from test scripts. Honesty invariant (ONTOLOGY.md §5): an
// estimate is always labeled as one; missing is missing, never zero.

import type { AuditResult, OntData, Ticket } from "@/lib/types";
import type { TicketLocation } from "@/lib/opsTypes";

/** Keys we accept as genuine latitude/longitude on an ONT record. */
const LAT_KEYS = ["lat", "latitude"] as const;
const LON_KEYS = ["lon", "lng", "longitude"] as const;

function numeric(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function pick(
  obj: Record<string, unknown>,
  keys: readonly string[],
): number | null {
  for (const k of keys) {
    if (k in obj) {
      const n = numeric(obj[k]);
      if (n !== null) return n;
    }
  }
  return null;
}

/** Real lat/lon on an ONT row, or null. Never invented. */
function coordinatesOf(ont: OntData): { lat: number; lon: number } | null {
  const own = ont as unknown as Record<string, unknown>;
  const sources = [own, ont.extended ?? {}];
  for (const src of sources) {
    const lat = pick(src, LAT_KEYS);
    const lon = pick(src, LON_KEYS);
    // Both must exist and be plausible — a bare 0,0 island is a data bug.
    if (
      lat !== null &&
      lon !== null &&
      Math.abs(lat) <= 90 &&
      Math.abs(lon) <= 180 &&
      !(lat === 0 && lon === 0)
    ) {
      return { lat, lon };
    }
  }
  return null;
}

interface OntDistance {
  serial: string;
  distance_m: number;
  pon_port: string | null;
}

/**
 * Distance-from-OLT readings for the given serials: prefer the ONT snapshot
 * row; fall back to the fault events' affected_onts entries (offline ONTs
 * may only appear there).
 */
function distancesFor(result: AuditResult, serials: string[]): OntDistance[] {
  const wanted = new Set(serials);
  const bySerial = new Map<string, OntDistance>();

  for (const ont of result.onts ?? []) {
    if (!wanted.has(ont.serial_number)) continue;
    const d = numeric(ont.distance_meters);
    if (d !== null && d > 0) {
      bySerial.set(ont.serial_number, {
        serial: ont.serial_number,
        distance_m: d,
        pon_port: ont.pon_port || null,
      });
    }
  }

  for (const fault of result.faults ?? []) {
    for (const a of fault.affected_onts ?? []) {
      if (!wanted.has(a.serial_number) || bySerial.has(a.serial_number)) {
        continue;
      }
      const d = numeric(a.distance_meters);
      if (d !== null && d > 0) {
        bySerial.set(a.serial_number, {
          serial: a.serial_number,
          distance_m: d,
          pon_port: fault.pon_port || null,
        });
      }
    }
  }

  return [...bySerial.values()].sort((a, b) => a.distance_m - b.distance_m);
}

const NO_LOCATION: TicketLocation = {
  kind: "none",
  summary:
    "No location data in this audit — provide ONT geo data or an OTDR/GIS join to enable fault location.",
  evidence: [],
};

/**
 * Derive the location object for one ticket from the audit it belongs to.
 * `kind: "coordinates"` only when genuine lat/lon exists in the data.
 */
export function deriveTicketLocation(
  result: AuditResult | null,
  ticket: Ticket,
): TicketLocation {
  if (!result) return NO_LOCATION;
  const serials = ticket.affected_ont_serials ?? [];
  if (serials.length === 0) return NO_LOCATION;

  // 1. Genuine coordinates, if any affected ONT carries them.
  const wanted = new Set(serials);
  const withCoords = (result.onts ?? [])
    .filter((o) => wanted.has(o.serial_number))
    .map((o) => ({ ont: o, coords: coordinatesOf(o) }))
    .filter((x) => x.coords !== null);
  if (withCoords.length > 0) {
    const first = withCoords[0];
    const c = first.coords as { lat: number; lon: number };
    return {
      kind: "coordinates",
      summary:
        withCoords.length === 1
          ? `ONT ${first.ont.serial_number} at ${c.lat.toFixed(5)}, ${c.lon.toFixed(5)} (from ONT geo data).`
          : `${withCoords.length} of ${serials.length} affected ONTs carry coordinates — pin shows ${first.ont.serial_number}.`,
      coordinates: { lat: c.lat, lon: c.lon, label: first.ont.serial_number },
      pon_port: first.ont.pon_port || undefined,
      evidence: withCoords.map(
        ({ ont, coords }) =>
          `${ont.serial_number} · ${(coords as { lat: number; lon: number }).lat.toFixed(5)}, ${(coords as { lat: number; lon: number }).lon.toFixed(5)} · ${ont.pon_port}`,
      ),
    };
  }

  // 2. Distance-from-OLT estimate from ONT ranging data.
  const distances = distancesFor(result, serials);
  if (distances.length > 0) {
    const min = distances[0].distance_m;
    const max = distances[distances.length - 1].distance_m;
    const ports = [
      ...new Set(distances.map((d) => d.pon_port).filter((p): p is string => !!p)),
    ];
    const range =
      min === max ? `~${min} m` : `~${min}–${max} m`;
    const portPart = ports.length > 0 ? ` on ${ports.join(", ")}` : "";
    return {
      kind: "distance-estimate",
      summary: `Estimated ${range} of fibre from the OLT${portPart} (ONT ranging distance for ${distances.length} of ${serials.length} affected ONTs — an estimate, not a street location).`,
      distance_m_range: { min, max },
      pon_port: ports.length > 0 ? ports.join(", ") : undefined,
      evidence: distances.map(
        (d) =>
          `${d.serial} · ${d.distance_m} m from OLT${d.pon_port ? ` · ${d.pon_port}` : ""}`,
      ),
    };
  }

  // 3. Honest none.
  return NO_LOCATION;
}
