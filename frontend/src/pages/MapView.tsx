import { useCallback, useEffect, useMemo, useState } from "react";
import { Map as MapGL, NavigationControl, Popup, type MapLayerMouseEvent } from "react-map-gl/maplibre";
import { useLines } from "../api/hooks";
import { usePositionsWS, type LiveVehicle } from "../hooks/usePositionsWS";
import LineLayer from "../components/Map/LineLayer";
import VehicleDots, { VEHICLE_LAYER_ID } from "../components/Map/VehicleDots";
import VehicleDrawer from "../components/Map/VehicleDrawer";
import Legend from "../components/Map/Legend";
import TrainsPanel from "../components/Map/TrainsPanel";
import DisruptionBanner from "../components/DisruptionBanner";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const KL_ROUTE_KINDS = new Set(["mrt", "lrt", "monorail", "ktm", "brt"]);

const INITIAL_VIEW = {
  longitude: 101.6869,
  latitude: 3.139,
  zoom: 10.5,
};

const MAX_BOUNDS: [number, number, number, number] = [
  101.4, 2.85, // SW
  101.95, 3.40, // NE
];

function formatAgo(ms: number | null): string {
  if (!ms) return "—";
  const sec = Math.round((Date.now() - ms) / 1000);
  if (sec < 60) return `${sec}s ago`;
  return `${Math.round(sec / 60)}m ago`;
}

export default function MapView() {
  const { data, isLoading, error } = useLines();
  const { vehicles, status, lastUpdate } = usePositionsWS();
  const [hiddenKinds, setHiddenKinds] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<LiveVehicle | null>(null);
  const [hoverInfo, setHoverInfo] = useState<{
    lng: number;
    lat: number;
    text: string;
  } | null>(null);
  const [, forceTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => forceTick((n) => n + 1), 5000);
    return () => clearInterval(id);
  }, []);

  const klLines = useMemo(() => {
    if (!data) return [];
    return data.lines
      .filter((l) => l.polylines.length > 0)
      .filter((l) => KL_ROUTE_KINDS.has(l.kind) || l.kind === "ets");
  }, [data]);

  const vehicleById = useMemo(
    () => new Map(vehicles.map((v) => [v.vehicle_id, v])),
    [vehicles]
  );

  const selectedFresh = useMemo(() => {
    if (!selected) return null;
    return vehicleById.get(selected.vehicle_id) ?? selected;
  }, [selected, vehicleById]);

  const selectedLine = useMemo(
    () =>
      selectedFresh
        ? klLines.find((l) => l.route_id === selectedFresh.route_id)
        : undefined,
    [selectedFresh, klLines]
  );

  const toggleKind = useCallback((kind: string) => {
    setHiddenKinds((prev) => {
      const next = new Set(prev);
      next.has(kind) ? next.delete(kind) : next.add(kind);
      return next;
    });
  }, []);

  const handleClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const feature = e.features?.find((f) => f.layer.id === VEHICLE_LAYER_ID);
      if (!feature) {
        setSelected(null);
        return;
      }
      const vid = feature.properties?.vehicle_id as string | undefined;
      if (vid && vehicleById.has(vid)) {
        setSelected(vehicleById.get(vid)!);
      }
    },
    [vehicleById]
  );

  const handleHover = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.find(
      (f) => f.layer.id === VEHICLE_LAYER_ID || f.layer.id === "stops-circle"
    );
    if (!feature) {
      setHoverInfo(null);
      return;
    }
    const props = feature.properties as Record<string, string> | undefined;
    if (!props) return setHoverInfo(null);
    if (feature.layer.id === VEHICLE_LAYER_ID) {
      setHoverInfo({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        text: `${props.route_short || props.vehicle_id} · ${props.source}`,
      });
    } else {
      setHoverInfo({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        text: props.stop_name ?? "stop",
      });
    }
  }, []);

  return (
    <div className="absolute inset-0">
      <MapGL
        initialViewState={INITIAL_VIEW}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
        maxBounds={MAX_BOUNDS}
        minZoom={9}
        maxZoom={17}
        interactiveLayerIds={[VEHICLE_LAYER_ID, "stops-circle"]}
        onClick={handleClick}
        onMouseMove={handleHover}
        onMouseLeave={() => setHoverInfo(null)}
        cursor={hoverInfo ? "pointer" : "grab"}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <LineLayer lines={klLines} hiddenKinds={hiddenKinds} />
        <VehicleDots
          vehicles={vehicles}
          lines={klLines}
          hiddenKinds={hiddenKinds}
        />
        {hoverInfo && (
          <Popup
            longitude={hoverInfo.lng}
            latitude={hoverInfo.lat}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={12}
            className="pointer-events-none"
          >
            {hoverInfo.text}
          </Popup>
        )}
      </MapGL>

      {data && (
        <Legend lines={klLines} hidden={hiddenKinds} onToggle={toggleKind} />
      )}

      <DisruptionBanner />
      <TrainsPanel />

      <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 items-end">
        <div className="bg-white/95 border border-sand rounded-full px-3 py-1 text-xs flex items-center gap-2 shadow-sm text-ink">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              status === "open"
                ? "bg-live"
                : status === "connecting"
                ? "bg-warn"
                : "bg-crit"
            }`}
          />
          <span>{status === "open" ? "live" : status}</span>
          <span className="text-ink2">·</span>
          <span>{vehicles.length} veh</span>
          <span className="text-ink2">·</span>
          <span>updated {formatAgo(lastUpdate)}</span>
        </div>
        {isLoading && (
          <div className="bg-mist border border-sky2 px-2 py-1 rounded-full text-xs text-ink2">
            Loading lines…
          </div>
        )}
        {error && (
          <div className="bg-rosey border border-crit/40 px-2 py-1 rounded-full text-xs text-ink">
            Failed to load lines: {String((error as Error).message)}
          </div>
        )}
      </div>

      <VehicleDrawer
        vehicle={selectedFresh}
        line={selectedLine}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
