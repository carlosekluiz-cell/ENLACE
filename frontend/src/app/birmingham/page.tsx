'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import Map, { NavigationControl, Source, Layer } from 'react-map-gl/maplibre';
import { ScatterplotLayer, PathLayer, TextLayer, IconLayer } from '@deck.gl/layers';
import { DeckGL } from '@deck.gl/react';
import 'maplibre-gl/dist/maplibre-gl.css';

// ═══════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════

interface EstateNode {
  building: string;
  lat: number;
  lon: number;
  dwelling_count: number;
  splitter: string;
  distance_from_aux_m: number;
  cable_type: string;
  distance_from_previous_m: number;
  optical_budget: {
    total_loss_db: number;
    rx_power_dbm: number;
    margin_db: number;
    pass: boolean;
  };
}

interface EstateBranch {
  name: string;
  total_distance_m: number;
  building_count: number;
  nodes: EstateNode[];
}

interface EstateBom {
  cable_12f_m: number;
  cable_24f_m: number;
  cable_48f_m: number;
  cable_144f_m: number;
  total_cable_m: number;
  splitter_32way: number;
  splitter_64way: number;
  pbo_count: number;
  splice_closures: number;
  total_splices: number;
}

interface EstateCost {
  cable_cost: number;
  blowing_cost: number;
  sub_duct_cost: number;
  splitter_cost: number;
  pbo_cost: number;
  splice_closure_cost: number;
  splicing_cost: number;
  ont_cost: number;
  olt_cost: number;
  olt_ports: number;
  core_drill_cost: number;
  blockwire_cost: number;
  total_capex: number;
  capex_per_premises: number;
  pia_annual: number;
}

interface EstateRevenue {
  subscribers_y1: number;
  subscribers_y3: number;
  subscribers_y5: number;
  revenue_y1: number;
  revenue_y3: number;
  revenue_y5: number;
  annual_opex: number;
  five_year_revenue: number;
  payback_years: number;
}

interface EstateData {
  name: string;
  district: string;
  buildings: number;
  premises: number;
  branches: number;
  total_cable_m: number;
  cable_12f_m: number;
  cable_24f_m: number;
  cable_48f_m: number;
  cable_144f_m: number;
  splitter_32way: number;
  splitter_64way: number;
  pbo_count: number;
  centre_lat: number;
  centre_lon: number;
  costs: EstateCost;
  revenue: EstateRevenue;
  optical_budget: EstateNode[];
  all_pass_optical: boolean;
}

interface SummaryData {
  study: string;
  date: string;
  birmingham_totals: {
    total_premises_epc: number;
    total_no_fttp: number;
    fttp_coverage_pct: number;
    estimated_total_capex: number;
    avg_capex_per_premises: number;
  };
  estates: EstateData[];
  top_districts: Array<{
    district: string;
    total_premises: number;
    no_fttp: number;
    slow_broadband: number;
    mdu_premises: number;
    opportunity_score: number;
  }>;
}

interface GeoJsonFeature {
  type: 'Feature';
  geometry: {
    type: 'Point' | 'LineString';
    coordinates: number[] | number[][];
  };
  properties: Record<string, unknown>;
}

interface GeoJsonData {
  type: 'FeatureCollection';
  features: GeoJsonFeature[];
  properties?: Record<string, unknown>;
}

// ═══════════════════════════════════════════════════════════════════
// COST RATES (CF UK)
// ═══════════════════════════════════════════════════════════════════

const COST_RATES = {
  cable_12f_per_m: 1.20,
  cable_24f_per_m: 1.80,
  cable_48f_per_m: 3.00,
  cable_144f_per_m: 6.50,
  cable_blowing_per_m: 3.00,
  sub_duct_per_m: 8.00,
  splitter_32way: 120,
  splitter_64way: 180,
  pbo_unit: 85,
  splice_closure: 350,
  splice_each: 12,
  ont_per_premises: 100,
  olt_port: 750,
  core_drill_each: 150,
  blockwire_per_premises: 35,
};

// ═══════════════════════════════════════════════════════════════════
// CABLE COLOURS
// ═══════════════════════════════════════════════════════════════════

const CABLE_COLOURS: Record<string, [number, number, number, number]> = {
  '12F': [0, 255, 0, 200],      // green
  '24F': [255, 215, 0, 200],    // gold
  '48F': [255, 140, 0, 200],    // orange
  '144F': [255, 0, 0, 200],     // red
};

const SPLITTER_COLOURS: Record<string, [number, number, number, number]> = {
  'PBO': [0, 200, 0, 255],
  '32-way': [255, 165, 0, 255],
  '64-way': [255, 69, 0, 255],
};

// ═══════════════════════════════════════════════════════════════════
// GAP AREAS (postcode districts with low FTTP coverage)
// ═══════════════════════════════════════════════════════════════════

const GAP_AREAS = [
  { district: 'B5', lat: 52.475, lon: -1.885, coverage: 0.68 },
  { district: 'B7', lat: 52.499, lon: -1.875, coverage: 0.72 },
  { district: 'B9', lat: 52.477, lon: -1.862, coverage: 0.70 },
  { district: 'B10', lat: 52.468, lon: -1.860, coverage: 0.73 },
  { district: 'B16', lat: 52.480, lon: -1.922, coverage: 0.71 },
  { district: 'B19', lat: 52.505, lon: -1.907, coverage: 0.73 },
  { district: 'B12', lat: 52.465, lon: -1.880, coverage: 0.76 },
  { district: 'B6', lat: 52.507, lon: -1.892, coverage: 0.75 },
  { district: 'B8', lat: 52.488, lon: -1.845, coverage: 0.74 },
  { district: 'B15', lat: 52.465, lon: -1.922, coverage: 0.77 },
];

// ═══════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════

function formatGBP(value: number): string {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    maximumFractionDigits: 0,
  }).format(value);
}

function StatusBadge({ pass }: { pass: boolean }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
      pass ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
    }`}>
      {pass ? 'PASS' : 'FAIL'}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════

export default function BirminghamPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [geojsons, setGeojsons] = useState<GeoJsonData[]>([]);
  const [selectedEstate, setSelectedEstate] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGaps, setShowGaps] = useState(true);
  const [showFwa, setShowFwa] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<'bom' | 'cost' | 'revenue' | 'optical'>('bom');
  const [hoveredBuilding, setHoveredBuilding] = useState<string | null>(null);

  // Load data
  useEffect(() => {
    async function loadData() {
      try {
        const summaryRes = await fetch('/api/birmingham/summary');
        if (!summaryRes.ok) throw new Error('Failed to load summary');
        const summaryData = await summaryRes.json();
        setSummary(summaryData);

        const geoPromises = [1, 2, 3].map(i =>
          fetch(`/api/birmingham/estate/${i}`).then(r => r.json())
        );
        const geoData = await Promise.all(geoPromises);
        setGeojsons(geoData);
      } catch {
        // Fallback: try loading from static files
        try {
          const summaryRes = await fetch('/data/birmingham_estates_summary.json');
          const summaryData = await summaryRes.json();
          setSummary(summaryData);

          const geoPromises = [1, 2, 3].map(i =>
            fetch(`/data/birmingham_estate_${i}.geojson`).then(r => r.json())
          );
          const geoData = await Promise.all(geoPromises);
          setGeojsons(geoData);
        } catch (e2) {
          setError('Failed to load Birmingham study data. Ensure output files are in frontend/public/data/');
        }
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const estate = summary?.estates?.[selectedEstate];
  const geojson = geojsons[selectedEstate];

  // Build deck.gl layers from GeoJSON
  const deckLayers = useMemo(() => {
    if (!geojson?.features) return [];

    const layers = [];

    // Cable lines
    const cables = geojson.features.filter(
      (f: GeoJsonFeature) => f.geometry.type === 'LineString'
    );
    if (cables.length > 0) {
      layers.push(
        new PathLayer({
          id: 'cables',
          data: cables,
          getPath: (d: GeoJsonFeature) => (d.geometry.coordinates as number[][]).map(c => [c[0], c[1]]) as any,
          getColor: (d: GeoJsonFeature) => {
            const ct = (d.properties.cable_type as string) || '24F';
            return CABLE_COLOURS[ct] || [128, 128, 128, 200];
          },
          getWidth: (d: GeoJsonFeature) => {
            const ct = (d.properties.cable_type as string) || '24F';
            return ct === '144F' ? 5 : ct === '48F' ? 4 : ct === '24F' ? 3 : 2;
          },
          widthUnits: 'pixels',
          pickable: true,
        })
      );
    }

    // Splitter/building points
    const splitters = geojson.features.filter(
      (f: GeoJsonFeature) =>
        f.geometry.type === 'Point' && f.properties.type === 'SPLITTER'
    );
    if (splitters.length > 0) {
      layers.push(
        new ScatterplotLayer({
          id: 'splitters',
          data: splitters,
          getPosition: (d: GeoJsonFeature) => {
            const coords = d.geometry.coordinates as number[];
            return [coords[0], coords[1]];
          },
          getRadius: (d: GeoJsonFeature) => {
            const dw = (d.properties.dwellings as number) || 10;
            return Math.max(8, Math.min(25, dw * 0.5));
          },
          getFillColor: (d: GeoJsonFeature) => {
            const st = (d.properties.splitter_type as string) || '';
            return SPLITTER_COLOURS[st] || [255, 165, 0, 255];
          },
          getLineColor: [255, 255, 255, 255],
          lineWidthMinPixels: 2,
          stroked: true,
          radiusUnits: 'pixels',
          pickable: true,
          onHover: (info: { object?: GeoJsonFeature }) => {
            setHoveredBuilding(
              info.object ? (info.object.properties.name as string) : null
            );
          },
        })
      );

      // Text labels for buildings
      layers.push(
        new TextLayer({
          id: 'building-labels',
          data: splitters,
          getPosition: (d: GeoJsonFeature) => {
            const coords = d.geometry.coordinates as number[];
            return [coords[0], coords[1]];
          },
          getText: (d: GeoJsonFeature) => {
            const name = (d.properties.name as string) || '';
            return name.length > 15 ? name.substring(0, 15) + '...' : name;
          },
          getSize: 11,
          getColor: [255, 255, 255, 230],
          getAngle: 0,
          getTextAnchor: 'middle',
          getAlignmentBaseline: 'top',
          getPixelOffset: [0, 12],
          fontFamily: 'monospace',
          fontWeight: 'bold',
          outlineWidth: 2,
          outlineColor: [0, 0, 0, 200],
          billboard: true,
        })
      );
    }

    // AUX joint
    const auxJoints = geojson.features.filter(
      (f: GeoJsonFeature) =>
        f.geometry.type === 'Point' && f.properties.type === 'AUX_JOINT'
    );
    if (auxJoints.length > 0) {
      layers.push(
        new ScatterplotLayer({
          id: 'aux-joints',
          data: auxJoints,
          getPosition: (d: GeoJsonFeature) => {
            const coords = d.geometry.coordinates as number[];
            return [coords[0], coords[1]];
          },
          getRadius: 12,
          getFillColor: [255, 0, 0, 255],
          getLineColor: [255, 255, 255, 255],
          lineWidthMinPixels: 3,
          stroked: true,
          radiusUnits: 'pixels',
          pickable: true,
        })
      );
    }

    // Gap areas overlay
    if (showGaps) {
      layers.push(
        new ScatterplotLayer({
          id: 'gap-areas',
          data: GAP_AREAS,
          getPosition: (d: (typeof GAP_AREAS)[0]) => [d.lon, d.lat],
          getRadius: 500,
          getFillColor: [255, 0, 0, 40],
          getLineColor: [255, 0, 0, 120],
          lineWidthMinPixels: 2,
          stroked: true,
          radiusUnits: 'meters',
          pickable: true,
        })
      );

      layers.push(
        new TextLayer({
          id: 'gap-labels',
          data: GAP_AREAS,
          getPosition: (d: (typeof GAP_AREAS)[0]) => [d.lon, d.lat],
          getText: (d: (typeof GAP_AREAS)[0]) =>
            `${d.district}\n${((1 - d.coverage) * 100).toFixed(0)}% gap`,
          getSize: 12,
          getColor: [255, 60, 60, 255],
          getTextAnchor: 'middle',
          getAlignmentBaseline: 'center',
          fontFamily: 'monospace',
          fontWeight: 'bold',
          outlineWidth: 2,
          outlineColor: [0, 0, 0, 200],
          billboard: true,
        })
      );
    }

    return layers;
  }, [geojson, showGaps, showFwa]);

  // Initial view
  const initialViewState = useMemo(() => {
    if (estate) {
      return {
        latitude: estate.centre_lat,
        longitude: estate.centre_lon,
        zoom: 14,
        pitch: 45,
        bearing: -20,
      };
    }
    return {
      latitude: 52.4862,
      longitude: -1.8904,
      zoom: 11,
      pitch: 45,
      bearing: 0,
    };
  }, [estate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-lg">Loading Birmingham Expansion Study...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-bold mb-4">Birmingham Expansion Study</h1>
          <p className="text-red-400 mb-4">{error || 'Failed to load data'}</p>
          <p className="text-gray-400 text-sm">
            Copy output files to frontend/public/data/ and reload.
          </p>
        </div>
      </div>
    );
  }

  const totals = summary.birmingham_totals;

  return (
    <div className="h-screen flex bg-gray-900 text-white">
      {/* Sidebar */}
      <div className="w-96 flex-shrink-0 overflow-y-auto bg-gray-800 border-r border-gray-700">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 bg-gradient-to-r from-blue-900 to-purple-900">
          <h1 className="text-lg font-bold">Community Fibre</h1>
          <h2 className="text-sm text-gray-300">Birmingham Expansion Study</h2>
          <p className="text-xs text-gray-400 mt-1">PULSO Network Intelligence — March 2026</p>
        </div>

        {/* Market Totals */}
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-2">Birmingham Market</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="bg-gray-700 rounded p-2">
              <div className="text-gray-400 text-xs">Total Premises</div>
              <div className="font-bold">{totals.total_premises_epc.toLocaleString()}</div>
            </div>
            <div className="bg-gray-700 rounded p-2">
              <div className="text-gray-400 text-xs">No FTTP</div>
              <div className="font-bold text-red-400">{totals.total_no_fttp.toLocaleString()}</div>
            </div>
            <div className="bg-gray-700 rounded p-2">
              <div className="text-gray-400 text-xs">Total CAPEX</div>
              <div className="font-bold">{formatGBP(totals.estimated_total_capex)}</div>
            </div>
            <div className="bg-gray-700 rounded p-2">
              <div className="text-gray-400 text-xs">CAPEX/Premises</div>
              <div className="font-bold">{formatGBP(totals.avg_capex_per_premises)}</div>
            </div>
          </div>
        </div>

        {/* Estate Selector */}
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-2">Estates</h3>
          <div className="flex gap-1">
            {summary.estates.map((e, i) => (
              <button
                key={i}
                onClick={() => setSelectedEstate(i)}
                className={`flex-1 px-2 py-2 rounded text-xs font-medium transition ${
                  selectedEstate === i
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <div className="font-bold">{e.district}</div>
                <div className="text-[10px] opacity-75">{e.premises} prem</div>
              </button>
            ))}
          </div>
        </div>

        {/* Estate Details */}
        {estate && (
          <>
            <div className="p-4 border-b border-gray-700">
              <h3 className="text-sm font-semibold text-blue-400 mb-2">{estate.name}</h3>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className="text-center">
                  <div className="text-gray-400 text-xs">Buildings</div>
                  <div className="font-bold">{estate.buildings}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 text-xs">Premises</div>
                  <div className="font-bold">{estate.premises}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 text-xs">Cable</div>
                  <div className="font-bold">{estate.total_cable_m.toLocaleString()}m</div>
                </div>
              </div>
              <div className="mt-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Optical budget:</span>
                  <StatusBadge pass={estate.all_pass_optical} />
                </div>
              </div>
            </div>

            {/* Tab selector */}
            <div className="flex border-b border-gray-700">
              {(['bom', 'cost', 'revenue', 'optical'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setSidebarTab(tab)}
                  className={`flex-1 px-2 py-2 text-xs font-medium uppercase ${
                    sidebarTab === tab
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="p-4">
              {sidebarTab === 'bom' && (
                <div className="space-y-1 text-sm">
                  <h4 className="font-semibold text-gray-300 mb-2">Bill of Materials</h4>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-400 border-b border-gray-600">
                        <th className="text-left py-1">Item</th>
                        <th className="text-right py-1">Qty</th>
                        <th className="text-right py-1">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      <tr><td className="py-1"><span className="inline-block w-3 h-3 bg-green-500 mr-1 rounded-sm" />12F cable</td><td className="text-right">{estate.cable_12f_m.toFixed(0)}m</td><td className="text-right">{formatGBP(estate.cable_12f_m * COST_RATES.cable_12f_per_m)}</td></tr>
                      <tr><td className="py-1"><span className="inline-block w-3 h-3 bg-yellow-500 mr-1 rounded-sm" />24F cable</td><td className="text-right">{estate.cable_24f_m.toFixed(0)}m</td><td className="text-right">{formatGBP(estate.cable_24f_m * COST_RATES.cable_24f_per_m)}</td></tr>
                      <tr><td className="py-1"><span className="inline-block w-3 h-3 bg-orange-500 mr-1 rounded-sm" />48F cable</td><td className="text-right">{estate.cable_48f_m.toFixed(0)}m</td><td className="text-right">{formatGBP(estate.cable_48f_m * COST_RATES.cable_48f_per_m)}</td></tr>
                      <tr><td className="py-1"><span className="inline-block w-3 h-3 bg-red-500 mr-1 rounded-sm" />144F cable</td><td className="text-right">{estate.cable_144f_m.toFixed(0)}m</td><td className="text-right">{formatGBP(estate.cable_144f_m * COST_RATES.cable_144f_per_m)}</td></tr>
                      <tr className="border-t border-gray-600"><td className="py-1 font-bold">Total cable</td><td className="text-right font-bold">{estate.total_cable_m.toFixed(0)}m</td><td></td></tr>
                      <tr><td className="py-1">32-way splitters</td><td className="text-right">{estate.splitter_32way}</td><td className="text-right">{formatGBP(estate.splitter_32way * COST_RATES.splitter_32way)}</td></tr>
                      <tr><td className="py-1">64-way splitters</td><td className="text-right">{estate.splitter_64way}</td><td className="text-right">{formatGBP(estate.splitter_64way * COST_RATES.splitter_64way)}</td></tr>
                      <tr><td className="py-1">PBOs</td><td className="text-right">{estate.pbo_count}</td><td className="text-right">{formatGBP(estate.pbo_count * COST_RATES.pbo_unit)}</td></tr>
                      <tr><td className="py-1">ONTs</td><td className="text-right">{estate.premises}</td><td className="text-right">{formatGBP(estate.premises * COST_RATES.ont_per_premises)}</td></tr>
                    </tbody>
                  </table>
                </div>
              )}

              {sidebarTab === 'cost' && estate.costs && (
                <div className="space-y-1 text-sm">
                  <h4 className="font-semibold text-gray-300 mb-2">Cost Breakdown</h4>
                  <table className="w-full text-xs">
                    <tbody className="divide-y divide-gray-700">
                      <tr><td className="py-1">Cable (supply)</td><td className="text-right">{formatGBP(estate.costs.cable_cost)}</td></tr>
                      <tr><td className="py-1">Cable (blowing)</td><td className="text-right">{formatGBP(estate.costs.blowing_cost)}</td></tr>
                      <tr><td className="py-1">Sub-duct (PIA)</td><td className="text-right">{formatGBP(estate.costs.sub_duct_cost)}</td></tr>
                      <tr><td className="py-1">Splitters + PBOs</td><td className="text-right">{formatGBP(estate.costs.splitter_cost + estate.costs.pbo_cost)}</td></tr>
                      <tr><td className="py-1">Splice closures</td><td className="text-right">{formatGBP(estate.costs.splice_closure_cost)}</td></tr>
                      <tr><td className="py-1">Splicing labour</td><td className="text-right">{formatGBP(estate.costs.splicing_cost)}</td></tr>
                      <tr><td className="py-1">ONT per premises</td><td className="text-right">{formatGBP(estate.costs.ont_cost)}</td></tr>
                      <tr><td className="py-1">OLT ports ({estate.costs.olt_ports})</td><td className="text-right">{formatGBP(estate.costs.olt_cost)}</td></tr>
                      <tr><td className="py-1">Core drills</td><td className="text-right">{formatGBP(estate.costs.core_drill_cost)}</td></tr>
                      <tr><td className="py-1">Blockwire drops</td><td className="text-right">{formatGBP(estate.costs.blockwire_cost)}</td></tr>
                      <tr className="border-t-2 border-blue-500 font-bold">
                        <td className="py-2 text-blue-400">TOTAL CAPEX</td>
                        <td className="text-right text-blue-400">{formatGBP(estate.costs.total_capex)}</td>
                      </tr>
                      <tr className="font-bold">
                        <td className="py-1">Per premises</td>
                        <td className="text-right">{formatGBP(estate.costs.capex_per_premises)}</td>
                      </tr>
                      <tr><td className="py-1 text-gray-400">Annual PIA rental</td><td className="text-right text-gray-400">{formatGBP(estate.costs.pia_annual)}/yr</td></tr>
                    </tbody>
                  </table>
                </div>
              )}

              {sidebarTab === 'revenue' && estate.revenue && (
                <div className="space-y-1 text-sm">
                  <h4 className="font-semibold text-gray-300 mb-2">Revenue Projection</h4>
                  <table className="w-full text-xs">
                    <tbody className="divide-y divide-gray-700">
                      <tr><td className="py-1">Subscribers Y1 (25%)</td><td className="text-right">{estate.revenue.subscribers_y1}</td></tr>
                      <tr><td className="py-1">Subscribers Y3 (40%)</td><td className="text-right">{estate.revenue.subscribers_y3}</td></tr>
                      <tr><td className="py-1">Subscribers Y5 (55%)</td><td className="text-right">{estate.revenue.subscribers_y5}</td></tr>
                      <tr className="border-t border-gray-600"><td className="py-1">Revenue Y1</td><td className="text-right">{formatGBP(estate.revenue.revenue_y1)}</td></tr>
                      <tr><td className="py-1">Revenue Y3</td><td className="text-right">{formatGBP(estate.revenue.revenue_y3)}</td></tr>
                      <tr><td className="py-1">Revenue Y5</td><td className="text-right">{formatGBP(estate.revenue.revenue_y5)}</td></tr>
                      <tr><td className="py-1">Annual OpEx</td><td className="text-right text-red-400">{formatGBP(estate.revenue.annual_opex)}</td></tr>
                      <tr><td className="py-1">5-year revenue</td><td className="text-right">{formatGBP(estate.revenue.five_year_revenue)}</td></tr>
                      <tr className="border-t-2 border-green-500 font-bold">
                        <td className="py-2 text-green-400">Payback period</td>
                        <td className="text-right text-green-400">{estate.revenue.payback_years.toFixed(1)} years</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {sidebarTab === 'optical' && (
                <div className="space-y-1 text-sm">
                  <h4 className="font-semibold text-gray-300 mb-2">Optical Budget</h4>
                  <div className="max-h-64 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-gray-800">
                        <tr className="text-gray-400 border-b border-gray-600">
                          <th className="text-left py-1">Building</th>
                          <th className="text-right py-1">Rx</th>
                          <th className="text-right py-1">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {estate.optical_budget?.map((ob, i) => (
                          <tr key={i}>
                            <td className="py-1 truncate max-w-[120px]">{ob.building || `Node ${i+1}`}</td>
                            <td className="text-right">{typeof (ob as any).rx_dbm === 'number' ? (ob as any).rx_dbm.toFixed(1) : ob.optical_budget?.rx_power_dbm?.toFixed(1) || '—'}dBm</td>
                            <td className="text-right"><StatusBadge pass={(ob as any).status === 'PASS' || ob.optical_budget?.pass !== false} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {/* Layer toggles */}
        <div className="p-4 border-t border-gray-700">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-2">Layers</h3>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={showGaps} onChange={e => setShowGaps(e.target.checked)}
                     className="rounded border-gray-600 bg-gray-700" />
              <span className="text-red-400">FTTP gap areas</span>
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={showFwa} onChange={e => setShowFwa(e.target.checked)}
                     className="rounded border-gray-600 bg-gray-700" />
              <span className="text-yellow-400">FWA viability overlay</span>
            </label>
          </div>
        </div>

        {/* Legend */}
        <div className="p-4 border-t border-gray-700">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-2">Legend</h3>
          <div className="space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="inline-block w-6 h-1 bg-green-500 rounded" /> 12F cable (drops)
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-6 h-1 bg-yellow-500 rounded" /> 24F cable (distribution)
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-6 h-1 bg-orange-500 rounded" /> 48F cable (feeder)
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-6 h-1 bg-red-500 rounded" /> 144F cable (trunk)
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="inline-block w-3 h-3 bg-red-600 rounded-full" /> AUX joint
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-orange-500 rounded-full" /> 32-way splitter
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-red-500 rounded-full" /> 64-way splitter
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-green-500 rounded-full" /> PBO
            </div>
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <DeckGL
          initialViewState={initialViewState}
          controller={true}
          layers={deckLayers}
          getTooltip={({ object }: { object?: GeoJsonFeature }) => {
            if (!object?.properties) return null;
            const p = object.properties;
            if (p.type === 'SPLITTER') {
              return {
                html: `<div style="padding:8px;background:#1a1a2e;color:white;border-radius:4px;font-size:12px">
                  <strong>${p.name}</strong><br/>
                  Splitter: ${p.splitter_type}<br/>
                  Dwellings: ${p.dwellings}
                </div>`,
              };
            }
            if (p.type === 'CABLE') {
              return {
                html: `<div style="padding:8px;background:#1a1a2e;color:white;border-radius:4px;font-size:12px">
                  <strong>${p.cable_type} Cable</strong><br/>
                  Length: ${typeof p.length_m === 'number' ? p.length_m.toFixed(0) : '—'}m
                </div>`,
              };
            }
            if (p.type === 'AUX_JOINT') {
              return {
                html: `<div style="padding:8px;background:#1a1a2e;color:white;border-radius:4px;font-size:12px">
                  <strong>AUX Joint</strong><br/>Network aggregation point
                </div>`,
              };
            }
            // Gap area
            if (p.district) {
              return {
                html: `<div style="padding:8px;background:#1a1a2e;color:white;border-radius:4px;font-size:12px">
                  <strong>${p.district}</strong><br/>
                  FTTP gap: ${((1 - (p.coverage as number)) * 100).toFixed(0)}%
                </div>`,
              };
            }
            return null;
          }}
        >
          <Map
            mapStyle="https://tiles.openfreemap.org/styles/liberty"
            attributionControl={false}
          >
            <NavigationControl position="top-right" />
          </Map>
        </DeckGL>

        {/* Hover info */}
        {hoveredBuilding && (
          <div className="absolute top-4 left-4 bg-gray-900/90 text-white px-3 py-2 rounded shadow text-sm">
            {hoveredBuilding}
          </div>
        )}

        {/* Title overlay */}
        <div className="absolute bottom-4 left-4 bg-gray-900/80 text-white px-4 py-2 rounded-lg">
          <div className="text-xs text-gray-400">Community Fibre Birmingham</div>
          <div className="font-bold">{estate?.name || 'Loading...'}</div>
          <div className="text-xs text-gray-400">
            {estate?.buildings} buildings / {estate?.premises} premises / {formatGBP(estate?.costs?.total_capex || 0)} CAPEX
          </div>
        </div>
      </div>
    </div>
  );
}
