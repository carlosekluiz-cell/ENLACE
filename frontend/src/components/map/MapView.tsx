'use client';

import { useState, useCallback, useEffect, useRef, Component, type ReactNode } from 'react';
import { MapPin, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

// Error boundary to catch WebGL initialization failures (luma.gl resize race)
class MapErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

// Brazil center coordinates and initial view
const BRAZIL_VIEW = {
  latitude: -14.235,
  longitude: -51.9253,
  zoom: 4,
  pitch: 45,
  bearing: -15,
};

const MAP_STYLES = {
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
};

// Dynamically check if map libraries are available
let MapComponent: any = null;
let DeckGLComponent: any = null;
let TileLayerClass: any = null;
let BitmapLayerClass: any = null;

interface FlyToTarget {
  latitude: number;
  longitude: number;
  zoom?: number;
}

interface MapViewProps {
  layers?: any[];
  onMapClick?: (info: any) => void;
  className?: string;
  initialViewState?: Partial<typeof BRAZIL_VIEW>;
  flyTo?: FlyToTarget | null;
  satelliteTileUrl?: string;
  showSatelliteLayer?: boolean;
  satelliteOpacity?: number;
}

function MapPlaceholder({ className }: { className?: string }) {
  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden ${className || 'h-full'}`}
      style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}
    >
      <div className="absolute inset-0 opacity-10">
        <svg viewBox="0 0 800 800" className="h-full w-full">
          <path
            d="M350,100 L450,80 L550,120 L600,200 L620,300 L600,400 L580,500 L500,600 L400,650 L300,600 L250,500 L200,400 L220,300 L250,200 L300,150 Z"
            fill="currentColor"
            style={{ color: 'var(--accent)' }}
          />
          {Array.from({ length: 10 }, (_, i) => (
            <line
              key={`h${i}`}
              x1="0" y1={i * 80} x2="800" y2={i * 80}
              stroke="currentColor"
              style={{ color: 'var(--border)' }}
              strokeWidth="0.5"
            />
          ))}
          {Array.from({ length: 10 }, (_, i) => (
            <line
              key={`v${i}`}
              x1={i * 80} y1="0" x2={i * 80} y2="800"
              stroke="currentColor"
              style={{ color: 'var(--border)' }}
              strokeWidth="0.5"
            />
          ))}
          {[
            { x: 400, y: 300, r: 8 },
            { x: 500, y: 250, r: 12 },
            { x: 350, y: 400, r: 6 },
            { x: 480, y: 350, r: 10 },
            { x: 300, y: 350, r: 5 },
            { x: 420, y: 500, r: 7 },
            { x: 550, y: 300, r: 9 },
          ].map((point, i) => (
            <circle
              key={`p${i}`}
              cx={point.x} cy={point.y} r={point.r}
              fill="currentColor"
              style={{ color: 'var(--accent)' }}
              opacity="0.6"
            />
          ))}
        </svg>
      </div>

      <div className="relative z-10 text-center">
        <MapPin className="mx-auto mb-4" size={48} style={{ color: 'var(--accent)' }} />
        <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          Mapa de Cobertura Interativo
        </h3>
        <p className="mt-2 max-w-md text-sm" style={{ color: 'var(--text-muted)' }}>
          Visualize cobertura telecom, rotas de fibra e dados municipais em todo
          o Brasil.
        </p>
        <div className="mt-4 flex items-center justify-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
          <span>Lat: {BRAZIL_VIEW.latitude.toFixed(3)}</span>
          <span>Lng: {BRAZIL_VIEW.longitude.toFixed(3)}</span>
          <span>Zoom: {BRAZIL_VIEW.zoom}</span>
        </div>
      </div>
    </div>
  );
}

function InteractiveMap({ layers, onMapClick, className, initialViewState, flyTo, satelliteTileUrl, showSatelliteLayer, satelliteOpacity }: MapViewProps) {
  const [viewState, setViewState] = useState({ ...BRAZIL_VIEW, ...initialViewState });
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [containerReady, setContainerReady] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  // Fly to a location when the flyTo prop changes
  useEffect(() => {
    if (flyTo) {
      setViewState((prev) => ({
        ...prev,
        latitude: flyTo.latitude,
        longitude: flyTo.longitude,
        zoom: flyTo.zoom ?? 10,
        pitch: 45,
        bearing: -15,
      }));
    }
  }, [flyTo]);

  // Always render container div so ref is attached from first render.
  // Check dimensions once mapReady flips (dynamic imports done).
  useEffect(() => {
    const el = containerRef.current;
    if (!el || containerReady) return;
    const check = () => {
      if (el.offsetWidth > 0 && el.offsetHeight > 0) {
        setContainerReady(true);
      }
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [mapReady, containerReady]);

  useEffect(() => {
    Promise.all([
      import('react-map-gl/maplibre'),
      import('deck.gl'),
      import('@deck.gl/geo-layers'),
      import('@deck.gl/layers'),
    ])
      .then(([mapMod, deckMod, geoLayersMod, layersMod]) => {
        MapComponent = mapMod.default || mapMod.Map;
        DeckGLComponent = deckMod.DeckGL || deckMod.default;
        TileLayerClass = geoLayersMod.TileLayer;
        BitmapLayerClass = layersMod.BitmapLayer;
        setMapReady(true);
      })
      .catch(() => {
        setMapError(true);
      });
  }, []);

  const handleViewStateChange = useCallback(
    ({ viewState: newViewState }: any) => {
      setViewState(newViewState);
    },
    []
  );

  // Build satellite tile overlay when URL is provided and layer is toggled on
  const satelliteLayer =
    satelliteTileUrl && showSatelliteLayer && TileLayerClass && BitmapLayerClass
      ? new TileLayerClass({
          id: 'satellite-tiles',
          data: satelliteTileUrl,
          minZoom: 10,
          maxZoom: 16,
          tileSize: 256,
          renderSubLayers: (props: any) => {
            const { boundingBox } = props.tile;
            return new BitmapLayerClass(props, {
              data: undefined,
              image: props.data,
              bounds: [
                boundingBox[0][0],
                boundingBox[0][1],
                boundingBox[1][0],
                boundingBox[1][1],
              ],
              opacity: satelliteOpacity ?? 0.7,
            });
          },
        })
      : null;

  // Satellite tiles render below other layers so boundaries/points stay on top
  const allLayers = [
    ...(satelliteLayer ? [satelliteLayer] : []),
    ...(layers || []),
  ];

  const canRenderMap = mapReady && containerReady && DeckGLComponent && MapComponent && !mapError;
  const DeckGL = DeckGLComponent;
  const MapGL = MapComponent;
  const mapStyle = MAP_STYLES[resolvedTheme as keyof typeof MAP_STYLES] || MAP_STYLES.light;

  return (
    <div ref={containerRef} className={`relative overflow-hidden ${className || 'h-full'}`}>
      {!canRenderMap && <MapPlaceholder className="h-full w-full" />}

      {canRenderMap && (
        <MapErrorBoundary fallback={<MapPlaceholder className="h-full w-full" />}>
          <DeckGL
            viewState={viewState}
            onViewStateChange={handleViewStateChange}
            controller={true}
            layers={allLayers}
            onClick={onMapClick}
          >
            <MapGL
              mapStyle={mapStyle}
              attributionControl={false}
            />
          </DeckGL>
        </MapErrorBoundary>
      )}

      {/* Map controls top-right */}
      <div className="absolute right-4 top-4 z-10 flex flex-col gap-2">
        <button
          onClick={() => setViewState((prev) => ({ ...prev, zoom: prev.zoom + 1 }))}
          className="rounded-md p-2 transition-colors"
          style={{
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
          }}
          aria-label="Aumentar zoom"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={() => setViewState((prev) => ({ ...prev, zoom: Math.max(prev.zoom - 1, 1) }))}
          className="rounded-md p-2 transition-colors"
          style={{
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
          }}
          aria-label="Diminuir zoom"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={() => setViewState({ ...BRAZIL_VIEW, ...initialViewState })}
          className="rounded-md p-2 transition-colors"
          style={{
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
          }}
          aria-label="Redefinir visualização"
        >
          <Maximize2 size={16} />
        </button>
      </div>

      {/* Attribution bottom-left */}
      <div
        className="absolute bottom-2 left-2 z-10 rounded px-2 py-1 text-xs"
        style={{ color: 'var(--text-muted)', background: 'var(--bg-surface)', opacity: 0.8 }}
      >
        {viewState.latitude.toFixed(4)}, {viewState.longitude.toFixed(4)} | Zoom:{' '}
        {viewState.zoom.toFixed(1)}
      </div>
    </div>
  );
}

export default function MapView(props: MapViewProps) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return <MapPlaceholder className={props.className} />;
  }

  return <InteractiveMap {...props} />;
}
