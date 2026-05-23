import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";

type DayPoint = {
  service_date: string;
  on_time_pct: number;
  mean_delay_s: number;
  trips_observed: number;
  trips_scheduled: number;
};

type RouteRow = {
  route_id: string;
  agency_id: string;
  short_name: string | null;
  long_name: string | null;
  color: string | null;
  kind: string;
  on_time_pct: number;
  mean_delay_s: number;
  trips_observed: number;
  trips_scheduled: number;
  series: DayPoint[];
};

type Response = {
  window: { start: string; end: string; days: number };
  routes: RouteRow[];
};

function colorOf(r: { color: string | null; kind: string }): string {
  return r.color ? `#${r.color}` : "#94a3b8";
}

export default function Reliability() {
  const { data, isLoading, error } = useQuery<Response>({
    queryKey: ["reliability-weekly"],
    queryFn: () => api<Response>("/reliability/weekly?days=7"),
    staleTime: 60_000,
  });

  const [selectedKind, setSelectedKind] = useState<string>("all");

  const filteredRoutes = useMemo(() => {
    if (!data) return [];
    if (selectedKind === "all") return data.routes;
    return data.routes.filter((r) => r.kind === selectedKind);
  }, [data, selectedKind]);

  const summaryChart = useMemo(() => {
    return filteredRoutes.map((r) => ({
      name: r.short_name ?? r.route_id,
      onTime: r.on_time_pct,
      delay: r.mean_delay_s,
      color: colorOf(r),
    }));
  }, [filteredRoutes]);

  const trendChart = useMemo(() => {
    if (!filteredRoutes.length) return [];
    // Pivot to dates × routes.
    const dates = Array.from(
      new Set(filteredRoutes.flatMap((r) => r.series.map((s) => s.service_date)))
    ).sort();
    return dates.map((d) => {
      const row: Record<string, number | string> = { date: d.slice(5) };
      filteredRoutes.forEach((r) => {
        const day = r.series.find((s) => s.service_date === d);
        row[r.short_name ?? r.route_id] = day?.on_time_pct ?? 0;
      });
      return row;
    });
  }, [filteredRoutes]);

  if (isLoading) {
    return <div className="p-6 text-ink2 text-sm">Loading reliability…</div>;
  }
  if (error) {
    return (
      <div className="p-6 text-red-300 text-sm">
        Failed to load: {String((error as Error).message)}
      </div>
    );
  }
  if (!data || data.routes.length === 0) {
    return (
      <div className="p-6 text-ink2 text-sm space-y-2">
        <h2 className="text-lg font-semibold">Weekly reliability</h2>
        <p className="text-ink2">
          No observations recorded yet. Either let the app run for a few days, or
          seed demo data:
        </p>
        <pre className="bg-white border border-sand rounded p-2 text-xs">
{`python scripts/seed_demo.py --days 7`}
        </pre>
      </div>
    );
  }

  const kinds = Array.from(new Set(data.routes.map((r) => r.kind))).sort();

  return (
    <div className="p-6 text-ink space-y-6 overflow-auto h-full bg-cream">
      <header className="flex items-baseline gap-3">
        <h2 className="text-lg font-semibold">Weekly reliability</h2>
        <span className="text-xs text-ink2">
          {data.window.start} → {data.window.end}
        </span>
        <div className="ml-auto flex gap-1">
          <button
            onClick={() => setSelectedKind("all")}
            className={`text-xs px-2 py-0.5 rounded ${
              selectedKind === "all" ? "bg-peach" : "bg-white border border-sand"
            }`}
          >
            All
          </button>
          {kinds.map((k) => (
            <button
              key={k}
              onClick={() => setSelectedKind(k)}
              className={`text-xs px-2 py-0.5 rounded uppercase ${
                selectedKind === k ? "bg-peach" : "bg-white border border-sand"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
      </header>

      <section>
        <h3 className="text-sm font-medium mb-2 text-ink2">On-time % by route</h3>
        <div className="h-64 bg-white border border-sand rounded p-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={summaryChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5DCC8" />
              <XAxis dataKey="name" stroke="#6B6477" fontSize={11} />
              <YAxis domain={[60, 100]} stroke="#6B6477" fontSize={11} unit="%" />
              <Tooltip
                contentStyle={{ background: "#FBF7F0", border: "1px solid #E5DCC8", borderRadius: 6, color: "#3F3A4C" }}
              />
              <Bar dataKey="onTime" radius={[4, 4, 0, 0]}>
                {summaryChart.map((d, i) => (
                  <rect key={i} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium mb-2 text-ink2">Daily trend</h3>
        <div className="h-64 bg-white border border-sand rounded p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5DCC8" />
              <XAxis dataKey="date" stroke="#6B6477" fontSize={11} />
              <YAxis domain={[60, 100]} stroke="#6B6477" fontSize={11} unit="%" />
              <Tooltip
                contentStyle={{ background: "#FBF7F0", border: "1px solid #E5DCC8", borderRadius: 6, color: "#3F3A4C" }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {filteredRoutes.map((r) => (
                <Line
                  key={r.route_id}
                  type="monotone"
                  dataKey={r.short_name ?? r.route_id}
                  stroke={colorOf(r)}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium mb-2 text-ink2">Per-route table</h3>
        <table className="w-full text-xs border-collapse">
          <thead className="text-ink2 text-left">
            <tr className="border-b border-sand">
              <th className="py-1.5 px-2">Route</th>
              <th className="py-1.5 px-2">Kind</th>
              <th className="py-1.5 px-2 text-right">On-time %</th>
              <th className="py-1.5 px-2 text-right">Mean delay</th>
              <th className="py-1.5 px-2 text-right">Observed</th>
              <th className="py-1.5 px-2 text-right">Scheduled</th>
            </tr>
          </thead>
          <tbody>
            {filteredRoutes.map((r) => (
              <tr key={r.route_id} className="border-b border-sand/60">
                <td className="py-1.5 px-2 flex items-center gap-2">
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: colorOf(r) }}
                  />
                  <span className="font-medium">{r.short_name ?? r.route_id}</span>
                  <span className="text-ink2 truncate max-w-[200px]">
                    {r.long_name}
                  </span>
                </td>
                <td className="py-1.5 px-2 uppercase text-ink2">{r.kind}</td>
                <td className="py-1.5 px-2 text-right font-mono">
                  {r.on_time_pct.toFixed(1)}%
                </td>
                <td className="py-1.5 px-2 text-right font-mono">
                  {r.mean_delay_s >= 0 ? "+" : ""}
                  {r.mean_delay_s.toFixed(0)}s
                </td>
                <td className="py-1.5 px-2 text-right font-mono">{r.trips_observed}</td>
                <td className="py-1.5 px-2 text-right font-mono text-ink2">
                  {r.trips_scheduled}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
