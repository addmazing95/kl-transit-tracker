import type { LiveVehicle } from "../../hooks/usePositionsWS";
import type { Line } from "../../api/hooks";

type Props = {
  vehicle: LiveVehicle | null;
  line?: Line;
  onClose: () => void;
};

function ago(iso: string): string {
  const sec = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  return `${Math.round(sec / 60)}m ago`;
}

export default function VehicleDrawer({ vehicle, line, onClose }: Props) {
  if (!vehicle) return null;
  const color = line?.color ? `#${line.color}` : "#9A93A7";

  return (
    <div className="absolute bottom-2 left-2 right-2 md:right-auto md:w-80 z-10 bg-white/95 backdrop-blur border border-sand rounded-xl shadow-lg p-3 text-sm text-ink">
      <div className="flex items-start gap-2 mb-2">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full mt-1.5"
          style={{ backgroundColor: color }}
        />
        <div className="flex-1">
          <div className="font-semibold">
            {line?.short_name ?? vehicle.route_id ?? "Unknown route"}
            <span
              className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] uppercase tracking-wide ${
                vehicle.source === "live"
                  ? "bg-sage text-ink"
                  : "bg-sand text-ink2"
              }`}
            >
              {vehicle.source}
            </span>
          </div>
          {line?.long_name && (
            <div className="text-xs text-ink2">{line.long_name}</div>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-ink2 hover:text-ink text-lg leading-none px-1"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      {vehicle.stuck && (
        <div className="mb-2 -mt-1 px-2 py-1 rounded-lg bg-rosey border border-crit/30 text-[11px] text-ink">
          Not moving — flagged stuck (no movement in last 3 polls)
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-ink2">Vehicle</dt>
        <dd className="font-mono">{vehicle.vehicle_id}</dd>
        <dt className="text-ink2">Trip</dt>
        <dd className="font-mono truncate">{vehicle.trip_id ?? "—"}</dd>
        <dt className="text-ink2">Position</dt>
        <dd className="font-mono">
          {vehicle.lat.toFixed(4)}, {vehicle.lon.toFixed(4)}
        </dd>
        <dt className="text-ink2">Bearing</dt>
        <dd>{vehicle.bearing != null ? `${vehicle.bearing.toFixed(0)}°` : "—"}</dd>
        <dt className="text-ink2">Speed</dt>
        <dd>{vehicle.speed != null ? `${vehicle.speed.toFixed(1)} km/h` : "—"}</dd>
        <dt className="text-ink2">Reported</dt>
        <dd>{ago(vehicle.ts)}</dd>
      </dl>
    </div>
  );
}
