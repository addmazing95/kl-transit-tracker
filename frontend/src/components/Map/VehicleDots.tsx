import { useEffect, useMemo, useState } from "react";
import { Layer, Source, useMap } from "react-map-gl/maplibre";
import type { LiveVehicle } from "../../hooks/usePositionsWS";
import type { Line } from "../../api/hooks";

type Props = {
  vehicles: LiveVehicle[];
  lines: Line[];
  hiddenKinds?: Set<string>;
};

export const VEHICLE_LAYER_ID = "vehicle-dots";
const ARROW_IMAGE_ID = "vehicle-arrow";

/** Build a 64x64 chevron pointing up — used by MapLibre as an icon
 *  that can be rotated per-feature. Crisp at the icon-size we render at. */
function makeArrowImage(): ImageData {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, size, size);

  // Solid white chevron body
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.moveTo(size / 2, 4);                 // tip
  ctx.lineTo(size - 6, size - 10);         // bottom right
  ctx.lineTo(size / 2, size - 22);         // inner notch
  ctx.lineTo(6, size - 10);                // bottom left
  ctx.closePath();
  ctx.fill();

  // Dark outline so it pops on light tiles
  ctx.lineWidth = 4;
  ctx.lineJoin = "round";
  ctx.strokeStyle = "#0f172a";
  ctx.stroke();

  return ctx.getImageData(0, 0, size, size);
}

/** Register the arrow image once with the underlying maplibre instance. */
function useArrowImage() {
  const { current: map } = useMap();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!map) return;
    const m = map.getMap();
    const register = () => {
      if (!m.hasImage(ARROW_IMAGE_ID)) {
        m.addImage(ARROW_IMAGE_ID, makeArrowImage() as unknown as ImageBitmap, {
          sdf: false,
        });
      }
      setReady(true);
    };
    if (m.isStyleLoaded()) register();
    else m.once("load", register);
    return () => {
      // intentionally leave the image registered between mounts
    };
  }, [map]);
  return ready;
}

export default function VehicleDots({ vehicles, lines, hiddenKinds }: Props) {
  useArrowImage();

  const lineByRoute = useMemo(
    () => new Map(lines.map((l) => [l.route_id, l])),
    [lines]
  );

  const geojson = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    for (const v of vehicles) {
      const line = v.route_id ? lineByRoute.get(v.route_id) : undefined;
      if (line && hiddenKinds?.has(line.kind)) continue;
      const color = line?.color
        ? `#${line.color}`
        : v.source === "live"
        ? "#22c55e"
        : "#94a3b8";
      features.push({
        type: "Feature",
        properties: {
          vehicle_id: v.vehicle_id,
          route_id: v.route_id ?? "",
          trip_id: v.trip_id ?? "",
          agency_id: v.agency_id,
          source: v.source,
          color,
          route_short: line?.short_name ?? v.route_id ?? v.vehicle_id,
          bearing: v.bearing ?? -1,         // -1 = unknown
          stuck: v.stuck ? 1 : 0,
        },
        geometry: { type: "Point", coordinates: [v.lon, v.lat] },
      });
    }
    return { type: "FeatureCollection" as const, features };
  }, [vehicles, lineByRoute, hiddenKinds]);

  // Pulse driver for the stuck halo (0..1 sinusoidal).
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const s = (Math.sin((t - start) / 400) + 1) / 2; // 0..1, ~1.3 Hz
      setPulse(s);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <Source id="vehicles" type="geojson" data={geojson}>
      {/* Stuck pulse: pulsing red halo behind any vehicle flagged stuck. */}
      <Layer
        id="vehicle-stuck-pulse"
        type="circle"
        filter={["==", ["get", "stuck"], 1]}
        paint={{
          "circle-radius": 22 + pulse * 10,
          "circle-color": "#ef4444",
          "circle-opacity": 0.18 + (1 - pulse) * 0.32,
          "circle-stroke-color": "#ef4444",
          "circle-stroke-width": 2,
          "circle-stroke-opacity": 0.55 + pulse * 0.25,
        }}
      />
      {/* Colored disc behind the arrow — gives each train a clear route-colored
          body distinct from white-filled stations. */}
      <Layer
        id="vehicle-disc"
        type="circle"
        paint={{
          "circle-radius": [
            "case",
            ["==", ["get", "source"], "live"], 13,
            10,
          ],
          "circle-color": ["get", "color"],
          "circle-stroke-color": [
            "case",
            ["==", ["get", "stuck"], 1], "#ef4444",
            "#0f172a",
          ],
          "circle-stroke-width": [
            "case",
            ["==", ["get", "stuck"], 1], 3,
            2,
          ],
          "circle-opacity": 0.95,
        }}
      />
      {/* Bigger direction arrow overlaid on the disc (only when bearing known
          and not stuck — stuck trains keep their full disc visible instead). */}
      <Layer
        id="vehicle-arrow"
        type="symbol"
        filter={[
          "all",
          ["!=", ["get", "bearing"], -1],
          ["==", ["get", "stuck"], 0],
        ]}
        layout={{
          "icon-image": ARROW_IMAGE_ID,
          // Bearing is degrees clockwise from north; "rotation-alignment: map"
          // keeps the arrow oriented to geography as the user rotates/pitches.
          "icon-rotate": ["get", "bearing"],
          "icon-rotation-alignment": "map",
          "icon-size": [
            "case",
            ["==", ["get", "source"], "live"], 0.42,
            0.34,
          ],
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
          "icon-anchor": "center",
        }}
        paint={{
          "icon-opacity": 1,
        }}
      />
      {/* Click target — invisible larger circle to make selection easy. */}
      <Layer
        id={VEHICLE_LAYER_ID}
        type="circle"
        paint={{
          "circle-radius": 16,
          "circle-color": "rgba(0,0,0,0)",
        }}
      />
    </Source>
  );
}
