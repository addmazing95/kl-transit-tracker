import type { Line } from "../../api/hooks";

const KIND_LABELS: Record<string, string> = {
  mrt: "MRT",
  lrt: "LRT",
  monorail: "Monorail",
  ktm: "KTM Komuter",
  ets: "ETS",
  brt: "BRT",
};

type Props = {
  lines: Line[];
  hidden: Set<string>;
  onToggle: (kind: string) => void;
};

export default function Legend({ lines, hidden, onToggle }: Props) {
  const kinds = Array.from(new Set(lines.map((l) => l.kind)));
  kinds.sort((a, b) => (KIND_LABELS[a] ?? a).localeCompare(KIND_LABELS[b] ?? b));

  return (
    <div className="absolute top-2 left-2 z-10 bg-white/95 border border-sand rounded-xl p-2 text-xs space-y-1 max-w-[220px] shadow-sm">
      <div className="font-semibold mb-1 text-ink">Lines</div>
      {kinds.map((kind) => {
        const sample = lines.find((l) => l.kind === kind);
        const color = sample?.color ? `#${sample.color}` : "#9A93A7";
        const isHidden = hidden.has(kind);
        return (
          <button
            key={kind}
            onClick={() => onToggle(kind)}
            className={`flex items-center gap-2 w-full text-left rounded px-1 py-0.5 transition ${
              isHidden ? "opacity-40 hover:bg-sand" : "hover:bg-mist"
            }`}
          >
            <span className="inline-block w-4 h-1.5 rounded" style={{ backgroundColor: color }} />
            <span className="text-ink">{KIND_LABELS[kind] ?? kind}</span>
            <span className="ml-auto text-ink2 font-mono">
              {lines.filter((l) => l.kind === kind).length}
            </span>
          </button>
        );
      })}
      <div className="pt-1 mt-1 border-t border-sand text-[10px] text-ink2">
        Click to toggle visibility
      </div>
    </div>
  );
}
