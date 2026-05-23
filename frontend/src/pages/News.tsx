import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../api/client";

type NewsItem = {
  id: number;
  source: string;
  title: string;
  url: string;
  published_at: string | null;
  summary: string | null;
  tags: string[];
};

type Response = { items: NewsItem[]; count: number };

const TAG_COLORS: Record<string, string> = {
  disruption: "bg-rosey border-crit/30",
  maintenance: "bg-peach border-warn/30",
  safety: "bg-rosey border-crit/30",
  operations: "bg-mist border-sky2",
};

function tagClass(tag: string): string {
  return (
    TAG_COLORS[tag] ?? "bg-mist border-sky2"
  );
}

function timeOf(item: NewsItem): string {
  if (!item.published_at) return "—";
  const d = new Date(item.published_at);
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return d.toLocaleDateString();
}

export default function News() {
  const { data, isLoading, error } = useQuery<Response>({
    queryKey: ["news"],
    queryFn: () => api<Response>("/news?days=60&limit=200"),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
  });

  const [filterTag, setFilterTag] = useState<string | null>(null);
  const [filterSource, setFilterSource] = useState<string | null>(null);

  const sources = useMemo(() => {
    return Array.from(new Set((data?.items ?? []).map((i) => i.source))).sort();
  }, [data]);

  const filtered = useMemo(() => {
    let items = data?.items ?? [];
    if (filterTag) items = items.filter((i) => i.tags.includes(filterTag));
    if (filterSource) items = items.filter((i) => i.source === filterSource);
    return items;
  }, [data, filterTag, filterSource]);

  if (isLoading) {
    return <div className="p-6 text-ink2 text-sm">Loading news…</div>;
  }
  if (error) {
    return (
      <div className="p-6 text-red-300 text-sm">
        Failed to load: {String((error as Error).message)}
      </div>
    );
  }
  if (!data || data.items.length === 0) {
    return (
      <div className="p-6 text-slate-300 text-sm">
        <h2 className="text-lg font-semibold mb-2">Disruption news</h2>
        <p className="text-ink2">
          No items yet. The scraper polls every 15 minutes — give it one cycle.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 text-ink space-y-4 overflow-auto h-full bg-cream">
      <header className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-lg font-semibold">Disruption news</h2>
        <span className="text-xs text-ink2">{filtered.length} items</span>
        <div className="ml-auto flex gap-1 flex-wrap text-xs">
          <button
            onClick={() => {
              setFilterTag(null);
              setFilterSource(null);
            }}
            className={`px-2 py-0.5 rounded ${
              !filterTag && !filterSource ? "bg-peach" : "bg-white border border-sand"
            }`}
          >
            All
          </button>
          {["disruption", "maintenance", "safety", "operations"].map((t) => (
            <button
              key={t}
              onClick={() => setFilterTag(t === filterTag ? null : t)}
              className={`px-2 py-0.5 rounded ${
                filterTag === t ? "bg-peach" : "bg-white border border-sand"
              }`}
            >
              {t}
            </button>
          ))}
          <span className="text-slate-600 mx-1">·</span>
          {sources.map((s) => (
            <button
              key={s}
              onClick={() => setFilterSource(s === filterSource ? null : s)}
              className={`px-2 py-0.5 rounded ${
                filterSource === s ? "bg-peach" : "bg-white border border-sand"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </header>

      <ul className="space-y-2">
        {filtered.map((item) => (
          <li
            key={item.id}
            className="bg-white border border-sand rounded p-3 hover:border-peach"
          >
            <div className="flex items-start gap-2 mb-1">
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-ink hover:underline flex-1"
              >
                {item.title}
              </a>
              <span className="text-xs text-ink2 whitespace-nowrap">{timeOf(item)}</span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
              <span className="text-ink2">{item.source}</span>
              {item.tags
                .filter((t) => !t.startsWith("_"))
                .map((t) => (
                  <span
                    key={t}
                    className={`px-1.5 py-0.5 rounded border ${tagClass(t)} text-ink`}
                  >
                    {t}
                  </span>
                ))}
            </div>
            {item.summary && (
              <p className="text-xs text-ink2 mt-1.5 line-clamp-3">{item.summary}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
