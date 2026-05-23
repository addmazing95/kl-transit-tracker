import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { Line } from "../../api/hooks";

const FALLBACK_COLOR = "#94a3b8";

function colorOf(line: Line): string {
  return line.color ? `#${line.color}` : FALLBACK_COLOR;
}

type Props = {
  lines: Line[];
  hiddenKinds?: Set<string>;
};

export default function LineLayer({ lines, hiddenKinds }: Props) {
  const visibleLines = useMemo(
    () => lines.filter((l) => !hiddenKinds?.has(l.kind)),
    [lines, hiddenKinds]
  );

  const linesGeojson = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    for (const line of visibleLines) {
      const color = colorOf(line);
      for (const poly of line.polylines) {
        features.push({
          type: "Feature",
          properties: {
            route_id: line.route_id,
            kind: line.kind,
            color,
          },
          // poly is [[lat,lon], ...]; GeoJSON is [lon,lat]
          geometry: {
            type: "LineString",
            coordinates: poly.map(([lat, lon]) => [lon, lat]),
          },
        });
      }
    }
    return { type: "FeatureCollection" as const, features };
  }, [visibleLines]);

  const stopsGeojson = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    for (const line of visibleLines) {
      const color = colorOf(line);
      for (const stop of line.stops) {
        features.push({
          type: "Feature",
          properties: {
            stop_id: stop.id,
            stop_name: stop.name,
            route_id: line.route_id,
            route_short: line.short_name ?? line.route_id,
            kind: line.kind,
            color,
          },
          geometry: { type: "Point", coordinates: [stop.lon, stop.lat] },
        });
      }
    }
    return { type: "FeatureCollection" as const, features };
  }, [visibleLines]);

  return (
    <>
      <Source id="lines" type="geojson" data={linesGeojson}>
        <Layer
          id="lines-casing"
          type="line"
          paint={{
            "line-color": "#0f172a",
            "line-width": [
              "match",
              ["get", "kind"],
              "mrt", 6,
              "lrt", 6,
              "monorail", 6,
              "ets", 5,
              "ktm", 5,
              4,
            ],
            "line-opacity": 0.55,
          }}
          layout={{ "line-cap": "round", "line-join": "round" }}
        />
        <Layer
          id="lines-stroke"
          type="line"
          paint={{
            "line-color": ["get", "color"],
            "line-width": [
              "match",
              ["get", "kind"],
              "mrt", 4,
              "lrt", 4,
              "monorail", 4,
              "ets", 3,
              "ktm", 3,
              2,
            ],
            "line-opacity": 0.95,
          }}
          layout={{ "line-cap": "round", "line-join": "round" }}
        />
      </Source>

      <Source id="stops" type="geojson" data={stopsGeojson}>
        {/* Station style: white-filled "tick" with thick route-colored border —
            the classic transit-map look. Distinct from filled train arrows. */}
        <Layer
          id="stops-circle"
          type="circle"
          paint={{
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              9, 2.5,
              12, 5,
              15, 8,
            ],
            "circle-color": "#ffffff",
            "circle-stroke-color": ["get", "color"],
            "circle-stroke-width": [
              "interpolate", ["linear"], ["zoom"],
              9, 1.5,
              12, 2.5,
              15, 3.5,
            ],
            "circle-opacity": 0.95,
          }}
        />
      </Source>
    </>
  );
}
