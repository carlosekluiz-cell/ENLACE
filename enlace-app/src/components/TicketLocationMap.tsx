"use client";

// Map pin for a ticket with GENUINE coordinates (Wave C2). Rendered only
// when the audit data really carries lat/lon — the app never invents a pin.
//
// Style is an inline raster-OSM definition (no external style JSON to
// fetch); if the tile server is unreachable (offline pilot box) the card
// degrades gracefully: a notice appears and the "Open in Google Maps" link
// in the parent card keeps working.

import { useState } from "react";
import Map, { Marker } from "react-map-gl/maplibre";
import { MapPin } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";

/** Inline raster style — attempts OSM tiles, needs no external style JSON. */
const OSM_RASTER_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

export default function TicketLocationMap({
  lat,
  lon,
  label,
}: {
  lat: number;
  lon: number;
  label?: string;
}) {
  const [tileError, setTileError] = useState(false);

  return (
    <div>
      <div style={{ height: 220, border: "1px solid var(--border-dark-strong)" }}>
        <Map
          initialViewState={{ latitude: lat, longitude: lon, zoom: 14 }}
          mapStyle={OSM_RASTER_STYLE}
          style={{ width: "100%", height: "100%" }}
          attributionControl={false}
          onError={() => setTileError(true)}
        >
          <Marker latitude={lat} longitude={lon} anchor="bottom">
            <MapPin size={26} style={{ color: "var(--danger)" }} aria-label={label ?? "fault location"} />
          </Marker>
        </Map>
      </div>
      {tileError && (
        <p className="mt-1 font-mono text-[10px]" style={{ color: "var(--text-on-dark-muted)" }}>
          map tiles unavailable (offline?) — coordinates are still correct;
          use the Google Maps link below
        </p>
      )}
    </div>
  );
}
