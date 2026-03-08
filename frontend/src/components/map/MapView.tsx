'use client';

import { useState, useCallback, useEffect } from 'react';
import { MapPin, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

// Brazil center coordinates and initial view
const BRAZIL_VIEW = {
  latitude: -14.235,
  longitude: -51.9253,
  zoom: 4,
  pitch: 0,
  bearing: 0,
};

// Dynamically check if map libraries are available
let MapComponent: any = null;
let DeckGLComponent: any = null;
let mapLibrariesAvailable = false;

interface MapViewProps {
  layers?: any[];
  onMapClick?: (info: any) => void;
  className?: string;
}

function MapPlaceholder({ className }: { className?: string }) {
  return (
    <div
      className={`relative flex items-center justify-center rounded-lg bg-slate-800 border border-slate-700 overflow-hidden ${className || 'h-[600px]'}`}
    >
      {/* Stylized Brazil map background */}
      <div className="absolute inset-0 opacity-10">
        <svg viewBox="0 0 800 800" className="h-full w-full">
          {/* Simplified Brazil outline */}
          <path
            d="M350,100 L450,80 L550,120 L600,200 L620,300 L600,400 L580,500 L500,600 L400,650 L300,600 L250,500 L200,400 L220,300 L250,200 L300,150 Z"
            fill="currentColor"
            className="text-blue-500"
          />
          {/* Grid lines */}
          {Array.from({ length: 10 }, (_, i) => (
            <line
              key={`h${i}`}
              x1="0"
              y1={i * 80}
              x2="800"
              y2={i * 80}
              stroke="currentColor"
              className="text-slate-600"
              strokeWidth="0.5"
            />
          ))}
          {Array.from({ length: 10 }, (_, i) => (
            <line
              key={`v${i}`}
              x1={i * 80}
              y1="0"
              x2={i * 80}
              y2="800"
              stroke="currentColor"
              className="text-slate-600"
              strokeWidth="0.5"
            />
          ))}
          {/* Sample data points */}
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
              cx={point.x}
              cy={point.y}
              r={point.r}
              fill="currentColor"
              className="text-blue-500"
              opacity="0.6"
            />
          ))}
        </svg>
      </div>

      {/* Content overlay */}
      <div className="relative z-10 text-center">
        <MapPin className="mx-auto mb-4 text-blue-500" size={48} />
        <h3 className="text-lg font-semibold text-slate-200">
          Mapa de Cobertura Interativo
        </h3>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          Visualize cobertura telecom, rotas de fibra e dados municipais em todo
          o Brasil. Conecte-se a API ENLACE para carregar dados geograficos em tempo real.
        </p>
        <div className="mt-4 flex items-center justify-center gap-4 text-xs text-slate-500">
          <span>Lat: {BRAZIL_VIEW.latitude.toFixed(3)}</span>
          <span>Lng: {BRAZIL_VIEW.longitude.toFixed(3)}</span>
          <span>Zoom: {BRAZIL_VIEW.zoom}</span>
        </div>
      </div>
    </div>
  );
}

function InteractiveMap({ layers, onMapClick, className }: MapViewProps) {
  const [viewState, setViewState] = useState(BRAZIL_VIEW);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(false);

  useEffect(() => {
    // Dynamically import map libraries on client side
    Promise.all([
      import('react-map-gl/maplibre'),
      import('deck.gl'),
    ])
      .then(([mapMod, deckMod]) => {
        MapComponent = mapMod.default || mapMod.Map;
        DeckGLComponent = deckMod.DeckGL || deckMod.default;
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

  if (mapError || !mapReady) {
    return <MapPlaceholder className={className} />;
  }

  if (!DeckGLComponent || !MapComponent) {
    return <MapPlaceholder className={className} />;
  }

  const DeckGL = DeckGLComponent;
  const MapGL = MapComponent;

  return (
    <div
      className={`relative rounded-lg overflow-hidden border border-slate-700 ${className || 'h-[600px]'}`}
    >
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={layers || []}
        onClick={onMapClick}
      >
        <MapGL
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          attributionControl={false}
        />
      </DeckGL>

      {/* Map controls overlay */}
      <div className="absolute right-4 top-4 flex flex-col gap-2">
        <button
          onClick={() =>
            setViewState((prev) => ({ ...prev, zoom: prev.zoom + 1 }))
          }
          className="rounded-lg bg-slate-800/90 p-2 text-slate-300 hover:bg-slate-700 transition-colors"
          aria-label="Zoom in"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={() =>
            setViewState((prev) => ({
              ...prev,
              zoom: Math.max(prev.zoom - 1, 1),
            }))
          }
          className="rounded-lg bg-slate-800/90 p-2 text-slate-300 hover:bg-slate-700 transition-colors"
          aria-label="Zoom out"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={() => setViewState(BRAZIL_VIEW)}
          className="rounded-lg bg-slate-800/90 p-2 text-slate-300 hover:bg-slate-700 transition-colors"
          aria-label="Reset view"
        >
          <Maximize2 size={16} />
        </button>
      </div>

      {/* Coordinates display */}
      <div className="absolute bottom-4 left-4 rounded-lg bg-slate-800/90 px-3 py-1.5 text-xs text-slate-400">
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
