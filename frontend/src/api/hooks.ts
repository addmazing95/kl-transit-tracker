import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type LineStop = { id: string; name: string; lat: number; lon: number };

export type Line = {
  route_id: string;
  agency_id: string;
  short_name: string | null;
  long_name: string | null;
  color: string | null;
  kind: string;
  polylines: number[][][]; // [polyline][point][lat,lon]
  stops: LineStop[];
};

export type LinesResponse = { lines: Line[] };

export function useLines() {
  return useQuery<LinesResponse>({
    queryKey: ["lines"],
    queryFn: () => api<LinesResponse>("/lines"),
    staleTime: 60 * 60 * 1000, // 1h — static data
  });
}
