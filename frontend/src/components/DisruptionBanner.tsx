import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

type Disruption = {
  id: number;
  started_at: string;
  ended_at: string | null;
  route_id: string | null;
  route_name: string | null;
  vehicle_id: string | null;
  severity: "info" | "warn" | "crit";
  reason: string;
  evidence: Record<string, unknown>;
};

type Response = {
  active: Disruption[];
  recent: Disruption[];
  counts: { active: number; crit: number; warn: number };
};

export default function DisruptionBanner() {
  const { data } = useQuery<Response>({
    queryKey: ["disruptions"],
    queryFn: () => api<Response>("/disruptions"),
    refetchInterval: 30_000,
  });

  if (!data || data.active.length === 0) return null;

  const crit = data.active.filter((d) => d.severity === "crit");
  const banners = crit.length > 0 ? crit : data.active;
  const bgClass =
    crit.length > 0
      ? "bg-rosey/95 border-crit/40"
      : "bg-peach/95 border-warn/40";

  return (
    <div
      className={`absolute top-2 left-1/2 -translate-x-1/2 z-10 ${bgClass} border rounded-xl px-3 py-2 text-xs max-w-[600px] shadow-sm text-ink`}
    >
      <div className="font-semibold mb-0.5">
        {crit.length > 0 ? "Critical disruption" : "Active disruptions"} · {data.counts.active}
      </div>
      <ul className="space-y-0.5">
        {banners.slice(0, 3).map((d) => (
          <li key={d.id}>
            <span className="font-mono uppercase mr-2 text-ink/80">{d.reason}</span>
            {d.route_name ?? d.vehicle_id ?? "unknown"}
            <span className="text-ink2 ml-2">
              since {new Date(d.started_at).toLocaleTimeString()}
            </span>
          </li>
        ))}
        {banners.length > 3 && (
          <li className="text-ink2">…and {banners.length - 3} more</li>
        )}
      </ul>
    </div>
  );
}
