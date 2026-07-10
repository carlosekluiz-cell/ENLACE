'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { api, fetchBlob } from '@/lib/api';
import { GRAHAME_PARK_REFERENCE } from '@/lib/grahame-park-reference';
import type {
  UkTopologyResult,
  UkTopologyComparison,
  UkTopologyNode,
} from '@/lib/types';
import {
  Cable,
  Search,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
  ChevronRight,
  Zap,
  Package,
  PoundSterling,
  ToggleLeft,
  ToggleRight,
  Pencil,
  Undo2,
  Download,
  FileJson,
  Globe,
  FileSpreadsheet,
  FileText,
  ChevronDown,
  RotateCcw,
  MousePointer,
  Phone,
  Users,
  ExternalLink,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const UK_VIEW = {
  latitude: 51.5955,
  longitude: -0.2535,
  zoom: 15.5,
  pitch: 50,
  bearing: -20,
};

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/bright';

// Cable colours by fibre count
const CABLE_COLORS: Record<string, [number, number, number]> = {
  '12F': [34, 197, 94],    // green
  '24F': [245, 158, 11],   // amber
  '48F': [249, 115, 22],   // orange
  '144F': [239, 68, 68],   // red
};
const CABLE_WIDTHS: Record<string, number> = {
  '12F': 2, '24F': 3, '48F': 4, '144F': 5,
};

// UK pilot-outreach shortlist — altnets with no telemetry evidence that own
// their network & buying decision. Contacts verified June 2026 (public sources).
type PilotCandidate = {
  name: string;
  website: string;
  contact: string;
  linkedin?: string;
  phone: string;
  note?: string;
};
const PILOT_CANDIDATES: PilotCandidate[] = [
  { name: 'Truespeed', website: 'https://www.truespeed.com/', contact: 'https://www.truespeed.com/contact/', phone: '01225 300370', note: 'Verify exec — team page lists COO Bill Keddie / CTO Josef Karthauser' },
  { name: 'Quickline', website: 'https://quickline.co.uk/', contact: 'https://quickline.co.uk/contact-us/', phone: '01482 247365', note: 'Adtran SDX exact parser match; CTO Darryl Petch (no LinkedIn verified)' },
  { name: 'Wessex Internet', website: 'https://www.wessexinternet.com/', contact: 'https://www.wessexinternet.com/wholesale-and-partners/', linkedin: 'https://uk.linkedin.com/in/gerainte', phone: '0333 240 7997', note: 'CTO Geraint Evans — explicitly manual NOC' },
  { name: 'Voneus', website: 'https://www.voneus.com/', contact: 'https://www.voneus.com/contact-voneus', linkedin: 'https://uk.linkedin.com/in/justinfielder', phone: '0333 880 4141', note: 'CTO Justin Fielder (ex-Zen)' },
  { name: 'ITS Technology', website: 'https://itstechnologygroup.com/', contact: 'https://itstechnologygroup.com/partner-with-us/', linkedin: 'https://www.linkedin.com/in/michael-g-17963ba/', phone: '0333 996 2100', note: 'CTO Mike Goodwin' },
  { name: 'Giganet / M12', website: 'https://www.giganet.uk/', contact: 'https://www.giganet.uk/contact-us/', linkedin: 'https://uk.linkedin.com/in/matthewskipsey', phone: '0330 311 6555', note: 'CTO Matthew Skipsey — may have moved to Netomnia; confirm' },
  { name: 'Toob', website: 'https://www.toob.co.uk/', contact: 'https://www.toob.co.uk/business-broadband/', phone: '023 9206 5558' },
  { name: 'Trooli', website: 'https://www.trooli.com/', contact: 'https://www.trooli.com/contact-us', phone: '0333 344 6601' },
  { name: 'Grain Connect', website: 'https://www.grainconnect.com/', contact: 'https://www.grainconnect.com/about-grain/partners-developers/', phone: '0330 223 2266' },
  { name: 'Hyperoptic', website: 'https://www.hyperoptic.com/', contact: 'https://www.hyperoptic.com/contact-us/', linkedin: 'https://www.linkedin.com/in/duncan-macdonald-5bb434/', phone: 'HQ 174 Hammersmith Rd, W6 7JP', note: 'CTIO Duncan Macdonald' },
  { name: 'Zen Internet', website: 'https://www.zen.co.uk/', contact: 'https://www.zen.co.uk/advantage-partners/', linkedin: 'https://uk.linkedin.com/in/john-lyons-6010554', phone: '01706 902000', note: 'CTO John Lyons' },
  { name: 'G.Network', website: 'https://www.g.network/', contact: 'https://www.g.network/contact-us', linkedin: 'https://uk.linkedin.com/in/mike-ghent-3229811', phone: '0203 909 4555', note: 'COO Mike Ghent' },
  { name: 'Wildanet', website: 'https://www.wildanet.com/', contact: 'https://www.wildanet.com/contact-us/', linkedin: 'https://uk.linkedin.com/in/justin-clark-9863b924', phone: '0800 0699906', note: 'Justin Clark' },
  { name: 'Airband', website: 'https://www.airband.co.uk/', contact: 'https://www.airband.co.uk/contact/', linkedin: 'https://uk.linkedin.com/in/ctintinger', phone: '01905 676 121', note: 'CTO Charl Tintinger — FTTP estate is the white space' },
  { name: 'Glide', website: 'https://glide.co.uk/', contact: 'https://glide.co.uk/partners/', phone: '02476 998 998' },
  { name: 'F&W / Hey! Broadband', website: 'https://fwnetworks.co.uk/', contact: 'https://fwnetworks.co.uk/about/contact-us/', phone: '0330 822 2878' },
];

// Splitter colours
function splitterColor(splitter: string): [number, number, number] {
  if (splitter.includes('32')) return [34, 197, 94];    // green
  if (splitter.includes('64')) return [59, 130, 246];   // blue
  if (splitter.toUpperCase() === 'PBO') return [249, 115, 22]; // orange
  return [156, 163, 175];
}
function splitterHex(splitter: string): string {
  const [r, g, b] = splitterColor(splitter);
  return `rgb(${r},${g},${b})`;
}
function splitterRadius(splitter: string): number {
  if (splitter.includes('64')) return 22;
  if (splitter.includes('32')) return 18;
  if (splitter.toUpperCase() === 'PBO') return 14;
  return 12;
}

// Undo stack entry
interface UndoEntry {
  label: string;
  topology: UkTopologyResult;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function UkTopologyPage() {
  // State
  const [postcode, setPostcode] = useState('NW9');
  const [topology, setTopology] = useState<UkTopologyResult | null>(null);
  const [comparison, setComparison] = useState<UkTopologyComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<UkTopologyNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  // Phase 5 — Edit mode
  const [editMode, setEditMode] = useState(false);
  const [undoStack, setUndoStack] = useState<UndoEntry[]>([]);
  const [dragTarget, setDragTarget] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number; y: number; nodeId: string;
  } | null>(null);

  // Phase 6 — Export dropdown
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  // deck.gl + map modules (lazy)
  const deckRef = useRef<any>(null);
  const [deckReady, setDeckReady] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const MapRef = useRef<any>(null);
  const DeckRef = useRef<any>(null);

  // ViewState
  const [viewState, setViewState] = useState(UK_VIEW);

  // Load deck.gl + react-map-gl/maplibre
  useEffect(() => {
    Promise.all([
      import('@deck.gl/layers'),
      import('deck.gl'),
      import('react-map-gl/maplibre'),
    ]).then(([layersMod, deckMod, mapMod]) => {
      deckRef.current = {
        ScatterplotLayer: layersMod.ScatterplotLayer,
        PathLayer: layersMod.PathLayer,
        TextLayer: layersMod.TextLayer,
      };
      DeckRef.current = deckMod.DeckGL || deckMod.default;
      MapRef.current = mapMod.default || mapMod.Map;
      setDeckReady(true);
      setMapReady(true);
    });
  }, []);

  // Close export dropdown on outside click
  useEffect(() => {
    if (!exportOpen) return;
    const handler = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportOpen]);

  // Close context menu on click elsewhere
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [contextMenu]);

  // ── Generate topology ──────────────────────────────────────────────────

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setTopology(null);
    setComparison(null);
    setSelectedBranch(null);
    setUndoStack([]);
    setEditMode(false);

    try {
      const result = await api.ukTopology.generate(postcode.trim());
      setTopology(result);
      try {
        const cmp = await api.ukTopology.compare(postcode.trim());
        setComparison(cmp);
      } catch { /* comparison optional */ }
    } catch (err: any) {
      setError(err?.message || 'Failed to generate topology');
    } finally {
      setLoading(false);
    }
  }, [postcode]);

  // ── Edit mode helpers ──────────────────────────────────────────────────

  const pushUndo = useCallback((label: string, topo: UkTopologyResult) => {
    setUndoStack((prev) => [...prev.slice(-19), { label, topology: topo }]);
  }, []);

  const handleUndo = useCallback(() => {
    setUndoStack((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      setTopology(last.topology);
      return prev.slice(0, -1);
    });
  }, []);

  const handleReset = useCallback(() => {
    if (undoStack.length > 0) {
      setTopology(undoStack[0].topology);
      setUndoStack([]);
    }
  }, [undoStack]);

  // Splitter override via context menu
  const handleSplitterOverride = useCallback(
    (nodeId: string, newSplitter: string) => {
      if (!topology) return;
      pushUndo(`Override ${nodeId} → ${newSplitter}`, topology);
      const updated = structuredClone(topology);
      for (const branch of updated.branches) {
        for (const node of branch.nodes) {
          if (node.building === nodeId) {
            node.splitter = newSplitter;
          }
        }
      }
      setTopology(updated);
      setContextMenu(null);
    },
    [topology, pushUndo],
  );

  // Drag node — update position and recalculate
  const handleDragEnd = useCallback(
    async (nodeId: string, newLon: number, newLat: number) => {
      if (!topology) return;
      pushUndo(`Move ${nodeId}`, topology);
      try {
        const result = await api.ukTopology.recalculate({
          postcode: topology.postcode,
          node_id: nodeId,
          new_lat: newLat,
          new_lon: newLon,
        });
        setTopology(result);
      } catch {
        // If recalculate fails, do local update
        const updated = structuredClone(topology);
        for (const branch of updated.branches) {
          for (const node of branch.nodes) {
            if (node.building === nodeId) {
              node.lat = newLat;
              node.lon = newLon;
            }
          }
        }
        setTopology(updated);
      }
      setDragTarget(null);
    },
    [topology, pushUndo],
  );

  // ── Export helpers ─────────────────────────────────────────────────────

  const downloadUrl = useCallback(async (url: string, filename: string) => {
    try {
      // Extract API path from the full URL
      const apiPath = url.includes('/api/') ? '/api/' + url.split('/api/').slice(1).join('/api/') : url;
      const blob = await fetchBlob(apiPath);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      // Fallback: open in new tab
      window.open(url, '_blank');
    }
    setExportOpen(false);
  }, []);

  const exportActions = useMemo(() => {
    if (!topology) return [];
    const pc = topology.postcode.replace(/\s/g, '');
    return [
      { label: 'GeoJSON', icon: FileJson, url: api.ukTopology.exportGeojsonUrl(topology.postcode), filename: `topology_${pc}.geojson` },
      { label: 'KML (Google Earth)', icon: Globe, url: api.ukTopology.exportKmlUrl(topology.postcode), filename: `topology_${pc}.kml` },
      { label: 'BOM Excel', icon: FileSpreadsheet, url: api.ukTopology.exportBomXlsxUrl(topology.postcode), filename: `bom_${pc}.xlsx` },
      { label: 'PDF Report', icon: FileText, url: api.ukTopology.exportPdfUrl(topology.postcode), filename: `topology_${pc}.pdf` },
    ];
  }, [topology]);

  // ── Build deck.gl layers ──────────────────────────────────────────────

  const layers = useMemo(() => {
    if (!deckRef.current || !topology) return [];
    const { ScatterplotLayer, PathLayer, TextLayer } = deckRef.current;

    const allNodes: (UkTopologyNode & { branch: string })[] = [];
    const paths: { path: [number, number][]; cable: string; branch: string }[] = [];

    for (const branch of topology.branches) {
      let prevCoord: [number, number] | null = topology.aux_joint
        ? [topology.aux_joint.lon, topology.aux_joint.lat]
        : null;

      for (const node of branch.nodes) {
        allNodes.push({ ...node, branch: branch.name });
        const coord: [number, number] = [node.lon, node.lat];
        if (prevCoord) {
          paths.push({ path: [prevCoord, coord], cable: node.cable_type, branch: branch.name });
        }
        prevCoord = coord;
      }
    }

    const filteredNodes = selectedBranch
      ? allNodes.filter((n) => n.branch === selectedBranch)
      : allNodes;
    const filteredPaths = selectedBranch
      ? paths.filter((p) => p.branch === selectedBranch)
      : paths;

    const layerList: any[] = [];

    // Cable paths — colour-coded by fibre type
    layerList.push(
      new PathLayer({
        id: 'cable-paths',
        data: filteredPaths,
        getPath: (d: any) => d.path,
        getColor: (d: any) => [...(CABLE_COLORS[d.cable] || [107, 114, 128]), 200],
        getWidth: (d: any) => CABLE_WIDTHS[d.cable] || 2,
        widthMinPixels: 2,
        widthMaxPixels: 8,
        widthUnits: 'pixels',
        pickable: false,
        jointRounded: true,
        capRounded: true,
      }),
    );

    // 3D building extrusions (simulated via large opaque scatterplots with stroke)
    layerList.push(
      new ScatterplotLayer({
        id: 'building-bases',
        data: filteredNodes,
        getPosition: (d: any) => [d.lon, d.lat],
        getFillColor: (d: any) => {
          const [r, g, b] = splitterColor(d.splitter);
          return [r, g, b, 40];
        },
        getRadius: 30,
        radiusMinPixels: 14,
        radiusMaxPixels: 36,
        stroked: true,
        getLineColor: (d: any) => [...splitterColor(d.splitter), 60],
        lineWidthMinPixels: 1,
        pickable: false,
      }),
    );

    // Splitter nodes — interactive
    layerList.push(
      new ScatterplotLayer({
        id: 'splitter-nodes',
        data: filteredNodes,
        getPosition: (d: any) => [d.lon, d.lat],
        getFillColor: (d: any) => [...splitterColor(d.splitter), 230],
        getRadius: (d: any) => splitterRadius(d.splitter),
        radiusMinPixels: 7,
        radiusMaxPixels: 26,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 100],
        stroked: true,
        getLineColor: [255, 255, 255, 160],
        lineWidthMinPixels: 1.5,
      }),
    );

    // AUX node — red diamond
    if (topology.aux_joint) {
      layerList.push(
        new ScatterplotLayer({
          id: 'aux-node',
          data: [topology.aux_joint],
          getPosition: (d: any) => [d.lon, d.lat],
          getFillColor: [239, 68, 68, 255],
          getRadius: 24,
          radiusMinPixels: 11,
          radiusMaxPixels: 30,
          pickable: false,
          stroked: true,
          getLineColor: [255, 255, 255, 220],
          lineWidthMinPixels: 2.5,
        }),
      );
    }

    // Building name labels
    layerList.push(
      new TextLayer({
        id: 'building-labels',
        data: filteredNodes,
        getPosition: (d: any) => [d.lon, d.lat],
        getText: (d: any) => d.building,
        getSize: 11,
        getColor: [226, 232, 240, 255],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'top',
        getPixelOffset: [0, 16],
        pickable: false,
        fontFamily: 'Inter, system-ui, sans-serif',
        fontWeight: 600,
        outlineWidth: 2,
        outlineColor: [15, 23, 42, 220],
      }),
    );

    // AUX label
    if (topology.aux_joint) {
      layerList.push(
        new TextLayer({
          id: 'aux-label',
          data: [topology.aux_joint],
          getPosition: (d: any) => [d.lon, d.lat],
          getText: () => 'AUX-1',
          getSize: 12,
          getColor: [255, 255, 255, 255],
          getTextAnchor: 'middle',
          getAlignmentBaseline: 'center',
          pickable: false,
          fontFamily: 'Inter, system-ui, sans-serif',
          fontWeight: 700,
        }),
      );
    }

    // Cable type labels (at midpoint of each cable)
    const cableMidpoints = filteredPaths.map((p) => ({
      position: [(p.path[0][0] + p.path[1][0]) / 2, (p.path[0][1] + p.path[1][1]) / 2] as [number, number],
      label: p.cable,
    }));
    layerList.push(
      new TextLayer({
        id: 'cable-labels',
        data: cableMidpoints,
        getPosition: (d: any) => d.position,
        getText: (d: any) => d.label,
        getSize: 9,
        getColor: [148, 163, 184, 200],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        pickable: false,
        fontFamily: 'Inter, system-ui, sans-serif',
        fontWeight: 500,
        outlineWidth: 1,
        outlineColor: [15, 23, 42, 180],
      }),
    );

    return layerList;
  }, [topology, selectedBranch, deckReady]);

  // ── Map event handlers ────────────────────────────────────────────────

  const handleMapClick = useCallback((info: any, event: any) => {
    if (info?.object && info.object.building) {
      setHoveredNode(info.object);
      setTooltipPos({ x: info.x, y: info.y });
    } else {
      setHoveredNode(null);
      setTooltipPos(null);
    }
  }, []);

  const handleMapRightClick = useCallback(
    (info: any, event: any) => {
      if (!editMode) return;
      if (info?.object && info.object.building) {
        event?.srcEvent?.preventDefault?.();
        setContextMenu({
          x: info.x,
          y: info.y,
          nodeId: info.object.building,
        });
      }
    },
    [editMode],
  );

  const handleDrag = useCallback(
    (info: any) => {
      if (!editMode || !dragTarget || !topology) return;
      const updated = structuredClone(topology);
      for (const branch of updated.branches) {
        for (const node of branch.nodes) {
          if (node.building === dragTarget) {
            node.lon = info.coordinate[0];
            node.lat = info.coordinate[1];
          }
        }
      }
      setTopology(updated);
    },
    [editMode, dragTarget, topology],
  );

  const handleDragStart = useCallback(
    (info: any) => {
      if (!editMode) return;
      if (info?.object && info.object.building) {
        setDragTarget(info.object.building);
      }
    },
    [editMode],
  );

  const handleDragEndEvent = useCallback(
    (info: any) => {
      if (!editMode || !dragTarget) return;
      if (info.coordinate) {
        handleDragEnd(dragTarget, info.coordinate[0], info.coordinate[1]);
      }
    },
    [editMode, dragTarget, handleDragEnd],
  );

  const handleBranchClick = useCallback((branchName: string) => {
    setSelectedBranch((prev) => (prev === branchName ? null : branchName));
  }, []);

  const handleFlyToBranch = useCallback(
    (branchName: string) => {
      if (!topology) return;
      const branch = topology.branches.find((b) => b.name === branchName);
      if (!branch || branch.nodes.length === 0) return;
      const mid = branch.nodes[Math.floor(branch.nodes.length / 2)];
      setViewState((prev) => ({ ...prev, latitude: mid.lat, longitude: mid.lon, zoom: 16.5 }));
    },
    [topology],
  );

  const bom = topology?.bom;
  const cost = topology?.cost;

  const DeckGL = DeckRef.current;
  const MapGL = MapRef.current;
  const canRender = deckReady && mapReady && DeckGL && MapGL;

  return (
    <div className="relative flex h-full w-full overflow-hidden">
      {/* ═══ Left sidebar ═══ */}
      <div
        className="flex w-80 shrink-0 flex-col overflow-y-auto border-r"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        {/* Header */}
        <div className="border-b p-4" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 mb-3">
            <Cable size={18} style={{ color: 'var(--accent)' }} />
            <h1 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
              UK FTTH Topology
            </h1>
            <span className="ml-auto rounded bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-bold text-blue-400">
              3D
            </span>
          </div>

          {/* Postcode input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={postcode}
              onChange={(e) => setPostcode(e.target.value)}
              placeholder="Postcode (e.g. NW9)"
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              style={{ background: 'var(--bg-subtle)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
              onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            />
            <button
              onClick={handleGenerate}
              disabled={loading || !postcode.trim()}
              className="flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium"
              style={{ background: 'var(--accent)', color: 'white', opacity: loading ? 0.6 : 1 }}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Generate
            </button>
          </div>

          {/* Action buttons row */}
          {topology && (
            <div className="mt-2 flex gap-1.5">
              {/* Edit mode toggle */}
              <button
                onClick={() => setEditMode((v) => !v)}
                className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors"
                style={{
                  background: editMode ? 'var(--accent)' : 'var(--bg-subtle)',
                  color: editMode ? 'white' : 'var(--text-muted)',
                  border: `1px solid ${editMode ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >
                {editMode ? <MousePointer size={12} /> : <Pencil size={12} />}
                {editMode ? 'Editing' : 'Edit'}
              </button>

              {/* Undo */}
              <button
                onClick={handleUndo}
                disabled={undoStack.length === 0}
                className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs"
                style={{
                  background: 'var(--bg-subtle)',
                  color: undoStack.length > 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  opacity: undoStack.length > 0 ? 1 : 0.5,
                }}
              >
                <Undo2 size={12} />
                {undoStack.length > 0 && <span>{undoStack.length}</span>}
              </button>

              {/* Reset */}
              {undoStack.length > 0 && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs"
                  style={{ background: 'var(--bg-subtle)', color: 'var(--danger)', border: '1px solid var(--border)' }}
                >
                  <RotateCcw size={12} />
                </button>
              )}

              {/* Compare toggle */}
              <button
                onClick={() => setShowCompare((v) => !v)}
                className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs"
                style={{
                  background: showCompare ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
                  color: showCompare ? 'var(--accent)' : 'var(--text-muted)',
                  border: `1px solid ${showCompare ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >
                {showCompare ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
                CF
              </button>

              {/* Export dropdown */}
              <div ref={exportRef} className="relative ml-auto">
                <button
                  onClick={() => setExportOpen((v) => !v)}
                  className="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium"
                  style={{ background: 'var(--bg-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                >
                  <Download size={12} />
                  Export
                  <ChevronDown size={10} />
                </button>
                {exportOpen && (
                  <div
                    className="absolute right-0 top-full z-50 mt-1 w-48 rounded-md border py-1 shadow-lg"
                    style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                  >
                    {exportActions.map((action) => (
                      <button
                        key={action.label}
                        onClick={() => downloadUrl(action.url, action.filename)}
                        className="flex w-full items-center gap-2 px-3 py-2 text-xs hover:bg-white/5 transition-colors"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        <action.icon size={14} style={{ color: 'var(--text-muted)' }} />
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div
            className="mx-4 mt-3 flex items-center gap-2 rounded-md border px-3 py-2"
            style={{
              borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
              background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
            }}
          >
            <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />
            <span className="text-xs" style={{ color: 'var(--danger)' }}>{error}</span>
          </div>
        )}

        {/* Edit mode hint */}
        {editMode && (
          <div
            className="mx-4 mt-2 rounded-md border px-3 py-2 text-xs"
            style={{
              borderColor: 'color-mix(in srgb, var(--accent) 40%, transparent)',
              background: 'color-mix(in srgb, var(--accent) 8%, transparent)',
              color: 'var(--accent)',
            }}
          >
            <strong>Edit Mode:</strong> Drag splitter nodes to reposition. Right-click to override splitter type. Changes recalculate optical budget automatically.
          </div>
        )}

        {/* Topology data */}
        {topology && (
          <div className="flex-1 space-y-0 divide-y" style={{ borderColor: 'var(--border)' }}>
            {/* Summary */}
            <div className="p-4 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                Summary
              </p>
              <div className="grid grid-cols-2 gap-2">
                <StatCard label="Premises" value={String(topology.premises)} />
                <StatCard label="Buildings" value={String(topology.buildings)} />
                <StatCard label="Branches" value={String(topology.branches.length)} />
                <StatCard label="Cable" value={`${bom?.total_cable_m?.toFixed(0) ?? '—'}m`} />
              </div>
            </div>

            {/* Branches */}
            <div className="p-4 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                Branches
              </p>
              {topology.branches.map((branch) => (
                <button
                  key={branch.name}
                  onClick={() => {
                    handleBranchClick(branch.name);
                    handleFlyToBranch(branch.name);
                  }}
                  className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors"
                  style={{
                    background: selectedBranch === branch.name ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
                    color: selectedBranch === branch.name ? 'var(--accent)' : 'var(--text-primary)',
                    border: `1px solid ${selectedBranch === branch.name ? 'var(--accent)' : 'transparent'}`,
                  }}
                >
                  <div>
                    <span className="font-medium">{branch.name}</span>
                    <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                      {branch.building_count} bldgs · {branch.total_distance_m.toFixed(0)}m
                    </span>
                  </div>
                  <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
                </button>
              ))}
              {selectedBranch && (
                <button
                  onClick={() => setSelectedBranch(null)}
                  className="text-xs underline"
                  style={{ color: 'var(--text-muted)' }}
                >
                  Show all branches
                </button>
              )}
            </div>

            {/* BOM */}
            {bom && (
              <div className="p-4 space-y-2">
                <div className="flex items-center gap-1.5">
                  <Package size={12} style={{ color: 'var(--text-muted)' }} />
                  <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                    Bill of Materials
                  </p>
                </div>
                <div className="space-y-1">
                  <DetailRow label="32-way splitters" value={String(bom.splitter_32way)} />
                  <DetailRow label="64-way splitters" value={String(bom.splitter_64way)} />
                  <DetailRow label="PBO boxes" value={String(bom.pbo_count)} />
                  <DetailRow label="Splice closures" value={String(bom.splice_closures)} />
                  <DetailRow label="Cable segments" value={String(bom.cable_segments)} />
                  <DetailRow label="Total cable" value={`${bom.total_cable_m.toFixed(0)}m`} />
                  {bom.cable_12f_m > 0 && <DetailRow label="  12F cable" value={`${bom.cable_12f_m.toFixed(0)}m`} />}
                  {bom.cable_24f_m > 0 && <DetailRow label="  24F cable" value={`${bom.cable_24f_m.toFixed(0)}m`} />}
                  {bom.cable_48f_m > 0 && <DetailRow label="  48F cable" value={`${bom.cable_48f_m.toFixed(0)}m`} />}
                  {bom.cable_144f_m > 0 && <DetailRow label="  144F cable" value={`${bom.cable_144f_m.toFixed(0)}m`} />}
                </div>
              </div>
            )}

            {/* Cost */}
            {cost && (
              <div className="p-4 space-y-2">
                <div className="flex items-center gap-1.5">
                  <PoundSterling size={12} style={{ color: 'var(--text-muted)' }} />
                  <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                    Cost Estimate
                  </p>
                </div>
                <div className="space-y-1">
                  <DetailRow label="Total CAPEX" value={`£${cost.total_capex_gbp.toLocaleString('en-GB', { maximumFractionDigits: 0 })}`} />
                  <DetailRow label="CAPEX / premises" value={`£${cost.capex_per_premises_gbp.toFixed(0)}`} />
                  <DetailRow label="Annual PIA rental" value={`£${cost.annual_pia_rental_gbp.toLocaleString('en-GB', { maximumFractionDigits: 0 })}`} />
                </div>
              </div>
            )}

            {/* Optical budget */}
            <div className="p-4 space-y-2">
              <div className="flex items-center gap-1.5">
                <Zap size={12} style={{ color: 'var(--text-muted)' }} />
                <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                  Optical Budget
                </p>
              </div>
              <div className="space-y-1">
                {topology.branches.flatMap((b) => b.nodes).map((node) => {
                  const ob = node.optical_budget;
                  return (
                    <div
                      key={node.building}
                      className="flex items-center justify-between rounded px-2 py-1 text-xs"
                      style={{ background: 'var(--bg-subtle)' }}
                    >
                      <span style={{ color: 'var(--text-primary)' }}>{node.building}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: 'var(--text-muted)' }}>
                          {ob.margin_db.toFixed(1)}dB
                        </span>
                        {ob.pass ? (
                          <CheckCircle2 size={12} style={{ color: '#22c55e' }} />
                        ) : (
                          <XCircle size={12} style={{ color: '#ef4444' }} />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!topology && !loading && !error && (
          <div className="flex flex-1 items-center justify-center p-8">
            <div className="text-center">
              <Cable size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Enter a postcode and click Generate to build FTTH topology
              </p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Demo: NW9 (Grahame Park)
              </p>
            </div>
          </div>
        )}
        {/* ═══ UK pilot outreach shortlist ═══ */}
        <details className="border-t" style={{ borderColor: 'var(--border)' }}>
          <summary
            className="flex cursor-pointer list-none items-center gap-2 p-4 text-[10px] font-semibold uppercase tracking-wide"
            style={{ color: 'var(--text-muted)' }}
          >
            <Users size={12} style={{ color: 'var(--accent)' }} />
            UK Pilot Outreach
            <span className="ml-auto rounded bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-bold text-blue-400">
              {PILOT_CANDIDATES.length}
            </span>
          </summary>
          <div className="space-y-2 px-4 pb-4">
            <p className="text-[10px] leading-snug" style={{ color: 'var(--text-muted)' }}>
              Altnets with no telemetry evidence — priority pilot candidates. Verify named exec before contact.
            </p>
            {PILOT_CANDIDATES.map((c) => (
              <div
                key={c.name}
                className="rounded-md border p-2.5"
                style={{ background: 'var(--bg-subtle)', borderColor: 'var(--border)' }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {c.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <a href={c.website} target="_blank" rel="noopener noreferrer" title="Website" style={{ color: 'var(--text-muted)' }}>
                      <Globe size={13} />
                    </a>
                    <a href={c.contact} target="_blank" rel="noopener noreferrer" title="Contact / partnerships" style={{ color: 'var(--text-muted)' }}>
                      <ExternalLink size={13} />
                    </a>
                    {c.linkedin && (
                      <a href={c.linkedin} target="_blank" rel="noopener noreferrer" title="Exec LinkedIn" style={{ color: 'var(--accent)' }}>
                        <Users size={13} />
                      </a>
                    )}
                  </div>
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  <Phone size={11} />
                  {c.phone}
                </div>
                {c.note && (
                  <p className="mt-1 text-[10px] leading-snug" style={{ color: 'var(--text-muted)' }}>
                    {c.note}
                  </p>
                )}
              </div>
            ))}
          </div>
        </details>
      </div>

      {/* ═══ Center — 3D Map ═══ */}
      <div ref={mapContainerRef} className="relative flex-1">
        {loading && (
          <div className="absolute top-0 left-0 right-0 z-20 overflow-hidden" style={{ height: '2px' }}>
            <div className="pulso-progress-bar w-full" />
          </div>
        )}

        {!canRender && (
          <div className="flex h-full items-center justify-center" style={{ background: 'var(--bg-subtle)' }}>
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        )}

        {canRender && (
          <DeckGL
            viewState={viewState}
            onViewStateChange={({ viewState: vs }: any) => setViewState(vs)}
            controller={{ dragPan: !dragTarget, dragRotate: !dragTarget }}
            layers={layers}
            onClick={handleMapClick}
            onDragStart={editMode ? handleDragStart : undefined}
            onDrag={editMode ? handleDrag : undefined}
            onDragEnd={editMode ? handleDragEndEvent : undefined}
            getCursor={({ isDragging, isHovering }: any) =>
              editMode && isDragging ? 'grabbing' : editMode && isHovering ? 'grab' : isHovering ? 'pointer' : 'default'
            }
            style={{ width: '100%', height: '100%' }}
          >
            <MapGL
              mapStyle={MAP_STYLE}
              attributionControl={false}
            />
          </DeckGL>
        )}

        {/* Legend overlay — enhanced with cable colours */}
        <div
          className="absolute bottom-4 left-4 z-10 rounded-lg px-3 py-2.5"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          <p className="mb-1.5 text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
            Splitter Type
          </p>
          <div className="flex items-center gap-3 mb-2">
            {[
              { color: '#22c55e', label: '32-way' },
              { color: '#3b82f6', label: '64-way' },
              { color: '#f97316', label: 'PBO' },
              { color: '#ef4444', label: 'AUX' },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-1">
                <div className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{item.label}</span>
              </div>
            ))}
          </div>
          <p className="mb-1 text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
            Cable Type
          </p>
          <div className="flex items-center gap-3">
            {[
              { color: '#22c55e', label: '12F', width: 1 },
              { color: '#f59e0b', label: '24F', width: 1.5 },
              { color: '#f97316', label: '48F', width: 2 },
              { color: '#ef4444', label: '144F', width: 2.5 },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-1">
                <div
                  className="rounded-sm"
                  style={{
                    background: item.color,
                    width: `${12 + item.width * 4}px`,
                    height: `${item.width + 1}px`,
                  }}
                />
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Edit mode badge */}
        {editMode && (
          <div
            className="absolute top-4 left-4 z-10 flex items-center gap-1.5 rounded-md px-2.5 py-1.5"
            style={{ background: 'var(--accent)', color: 'white', boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}
          >
            <Pencil size={12} />
            <span className="text-xs font-bold">EDIT MODE</span>
          </div>
        )}

        {/* Hover tooltip */}
        {hoveredNode && tooltipPos && (
          <div
            className="pointer-events-none absolute z-30 rounded-lg p-3"
            style={{
              left: tooltipPos.x + 12,
              top: tooltipPos.y - 10,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
              maxWidth: 260,
            }}
          >
            <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
              {hoveredNode.building}
            </p>
            <div className="mt-1 space-y-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              <p>
                <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ background: splitterHex(hoveredNode.splitter) }} />
                {hoveredNode.splitter} · {hoveredNode.dwelling_count} dwellings
              </p>
              <p>Cable: {hoveredNode.cable_type} · {hoveredNode.distance_from_aux_m.toFixed(0)}m from AUX</p>
              <p>
                Rx: {hoveredNode.optical_budget.rx_power_dbm.toFixed(1)} dBm ·
                Margin: {hoveredNode.optical_budget.margin_db.toFixed(1)} dB
                {hoveredNode.optical_budget.pass ? ' ✓' : ' ✗'}
              </p>
            </div>
          </div>
        )}

        {/* Right-click context menu (edit mode) */}
        {contextMenu && (
          <div
            className="absolute z-40 rounded-md border py-1 shadow-lg"
            style={{
              left: contextMenu.x,
              top: contextMenu.y,
              background: 'var(--bg-surface)',
              borderColor: 'var(--border)',
              minWidth: 160,
            }}
          >
            <p className="px-3 py-1 text-[10px] font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>
              Override Splitter: {contextMenu.nodeId}
            </p>
            {['32-way', '64-way', 'PBO', 'none'].map((spl) => (
              <button
                key={spl}
                onClick={() => handleSplitterOverride(contextMenu.nodeId, spl)}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-white/5 transition-colors"
                style={{ color: 'var(--text-primary)' }}
              >
                <div className="h-2 w-2 rounded-full" style={{ background: splitterHex(spl) }} />
                {spl}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ═══ Right panel — CF Comparison ═══ */}
      {showCompare && comparison && (
        <div
          className="w-80 shrink-0 overflow-y-auto border-l"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="border-b p-4" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <Eye size={14} style={{ color: 'var(--accent)' }} />
              <h2 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                CF Comparison
              </h2>
            </div>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
              {comparison.reference_source}
            </p>
          </div>

          {/* Overall match */}
          <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Overall Match</span>
              <span
                className="rounded-full px-2.5 py-0.5 text-sm font-bold"
                style={{
                  background: comparison.overall_match_pct >= 90 ? '#22c55e20' : '#f9731620',
                  color: comparison.overall_match_pct >= 90 ? '#22c55e' : '#f97316',
                }}
              >
                {comparison.overall_match_pct}%
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>PBO Detection</span>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {comparison.pbo_detection.found}/{comparison.pbo_detection.expected}
              </span>
            </div>
          </div>

          {/* Per-building comparison */}
          <div className="p-4 space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
              Per-Building Match
            </p>
            <div className="space-y-1">
              {comparison.buildings.map((b) => (
                <div
                  key={b.name}
                  className="flex items-center justify-between rounded px-2 py-1.5 text-xs"
                  style={{ background: 'var(--bg-subtle)' }}
                >
                  <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{b.name}</span>
                  <div className="flex items-center gap-2">
                    <span style={{ color: splitterHex(b.generated_splitter) }}>
                      {b.generated_splitter}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>vs</span>
                    <span style={{ color: splitterHex(b.reference_splitter) }}>
                      {b.reference_splitter}
                    </span>
                    {b.match ? (
                      <CheckCircle2 size={12} style={{ color: '#22c55e' }} />
                    ) : (
                      <XCircle size={12} style={{ color: '#ef4444' }} />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reference data */}
          <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <p className="text-[10px] font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
              CF Reference Totals
            </p>
            <div className="space-y-1">
              <DetailRow label="Buildings" value={String(GRAHAME_PARK_REFERENCE.totals.buildings)} />
              <DetailRow label="Premises" value={String(GRAHAME_PARK_REFERENCE.totals.premises)} />
              <DetailRow label="32-way splitters" value={String(GRAHAME_PARK_REFERENCE.totals.splitters_32way)} />
              <DetailRow label="64-way splitters" value={String(GRAHAME_PARK_REFERENCE.totals.splitters_64way)} />
              <DetailRow label="PBO boxes" value={String(GRAHAME_PARK_REFERENCE.totals.pbo_count)} />
              <DetailRow label="Cable runs" value={String(GRAHAME_PARK_REFERENCE.cables.length)} />
              <DetailRow label="Branches" value={String(GRAHAME_PARK_REFERENCE.branches.length)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md p-2" style={{ background: 'var(--bg-subtle)' }}>
      <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{label}</p>
      <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-center justify-between rounded px-2 py-1.5"
      style={{ background: 'var(--bg-subtle)' }}
    >
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}
