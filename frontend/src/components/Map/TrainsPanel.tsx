import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";

type Direction = { label: string; count: number; stuck: number };

type LineStat = {
  route_id: string;
  short_name: string | null;
  long_name: string | null;
  color: string | null;
  kind: string;
  agency_id: string;
  total: number;
  stuck: number;
  directions: Direction[];
  uncategorized: number;
};

type Response = {
  stats: LineStat[];
  total_vehicles: number;
  total_stuck: number;
};

const KIND_LABELS: Record<string, string> = {
  mrt: "MRT",
  lrt: "LRT",
  monorail: "Monorail",
  ktm: "KTM",
  ets: "ETS",
  brt: "BRT",
};

function titleCase(s: string): string {
  return s
    .toLowerCase()
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export default function TrainsPanel() {
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [expandedLines, setExpandedLines] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery<Response>({
    queryKey: ["lines-stats"],
    queryFn: () => api<Response>("/lines/stats"),
    refetchInterval: 5_000,
    staleTime: 4_000,
  });

  const toggleLine = (id: string) =>
    setExpandedLines((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const expandAll = () =>
    setExpandedLines(new Set(data?.stats.map((s) => s.route_id) ?? []));
  const collapseAll = () => setExpandedLines(new Set());

  return (
    <div className="absolute top-12 right-2 z-10 w-[280px] max-h-[calc(100vh-7rem)] flex flex-col bg-white/95 backdrop-blur border border-sand rounded-xl text-xs shadow-sm text-ink">
      <button
        onClick={() => setPanelCollapsed((c) => !c)}
        className="flex items-baseline gap-2 px-3 py-2 border-b border-sand w-full text-left hover:bg-mist rounded-t-xl"
      >
        <span className="font-semibold">Trains in service</span>
        {data && (
          <span className="ml-auto flex items-baseline gap-2">
            <span className="text-ink font-mono text-sm">{data.total_vehicles}</span>
            {data.total_stuck > 0 && (
              <span className="text-crit font-mono text-[11px]">
                {data.total_stuck} stuck
              </span>
            )}
            <span className="text-ink2 text-[10px]">
              {panelCollapsed ? "▸" : "▾"}
            </span>
          </span>
        )}
      </button>

      {!panelCollapsed && (
        <>
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-sand text-[10px] text-ink2 bg-cream/60">
            <button
              onClick={expandAll}
              className="hover:text-ink hover:underline"
            >
              Expand all
            </button>
            <span>·</span>
            <button
              onClick={collapseAll}
              className="hover:text-ink hover:underline"
            >
              Collapse all
            </button>
            <span className="ml-auto">click a line to expand</span>
          </div>

          <div className="overflow-auto min-h-0">
            {isLoading && <div className="px-3 py-3 text-ink2">Loading…</div>}
            {error && (
              <div className="px-3 py-3 text-crit">
                Failed: {String((error as Error).message)}
              </div>
            )}
            {data && data.stats.length === 0 && (
              <div className="px-3 py-3 text-ink2">No trains active right now.</div>
            )}

            {data?.stats.map((line) => {
              const color = line.color ? `#${line.color}` : "#9A93A7";
              const isOpen = expandedLines.has(line.route_id);
              const hasDetails = line.directions.length > 0 || line.uncategorized > 0;
              return (
                <div
                  key={line.route_id}
                  className="border-b border-sand last:border-b-0"
                >
                  <button
                    onClick={() => hasDetails && toggleLine(line.route_id)}
                    className={`flex items-center gap-2 w-full px-3 py-2 text-left rounded-none transition ${
                      hasDetails ? "hover:bg-mist cursor-pointer" : "cursor-default"
                    }`}
                  >
                    <span
                      className="inline-block w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="font-medium">
                      {line.short_name ?? line.route_id}
                    </span>
                    <span className="text-ink2 text-[10px] uppercase">
                      {KIND_LABELS[line.kind] ?? line.kind}
                    </span>
                    <span className="ml-auto flex items-baseline gap-2">
                      {line.stuck > 0 && (
                        <span className="font-mono text-[10px] text-crit">
                          {line.stuck} stuck
                        </span>
                      )}
                      <span className="font-mono text-ink">{line.total}</span>
                      {hasDetails && (
                        <span className="text-ink2 text-[10px] w-3 text-center">
                          {isOpen ? "▾" : "▸"}
                        </span>
                      )}
                    </span>
                  </button>

                  {isOpen && hasDetails && (
                    <div className="px-3 pb-2 pt-0.5 bg-cream/50 space-y-0.5">
                      {line.directions.map((d) => (
                        <div
                          key={d.label}
                          className="flex items-baseline gap-2 text-[11px] text-ink2 pl-5"
                        >
                          <span className="text-ink2">→</span>
                          <span className="truncate">
                            {titleCase(d.label.replace(/^to\s+/i, ""))}
                          </span>
                          <span className="ml-auto font-mono text-ink">
                            {d.count}
                          </span>
                          {d.stuck > 0 && (
                            <span className="font-mono text-crit text-[10px]">
                              ({d.stuck})
                            </span>
                          )}
                        </div>
                      ))}
                      {line.uncategorized > 0 && (
                        <div className="flex items-baseline gap-2 text-[11px] text-ink2 pl-5">
                          <span>?</span>
                          <span>unknown direction</span>
                          <span className="ml-auto font-mono">
                            {line.uncategorized}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
