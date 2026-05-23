import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "../api/client";

export type LiveVehicle = {
  vehicle_id: string;
  agency_id: string;
  route_id: string | null;
  trip_id: string | null;
  lat: number;
  lon: number;
  bearing: number | null;
  speed: number | null;
  ts: string;
  source: "live" | "scheduled";
  stuck: boolean;
};

type Msg =
  | { type: "snapshot"; vehicles: LiveVehicle[] }
  | { type: "update"; vehicles: LiveVehicle[] };

export function usePositionsWS(): {
  vehicles: LiveVehicle[];
  status: "connecting" | "open" | "closed";
  lastUpdate: number | null;
} {
  const [vehicles, setVehicles] = useState<LiveVehicle[]>([]);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const reconnectAttempt = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let timer: number | null = null;

    const connect = () => {
      if (cancelled) return;
      setStatus("connecting");
      ws = new WebSocket(`${WS_BASE}/ws/positions`);
      ws.onopen = () => {
        reconnectAttempt.current = 0;
        setStatus("open");
      };
      ws.onmessage = (ev) => {
        try {
          const msg: Msg = JSON.parse(ev.data);
          setVehicles(msg.vehicles ?? []);
          setLastUpdate(Date.now());
        } catch {
          // ignore malformed frames
        }
      };
      ws.onclose = () => {
        setStatus("closed");
        if (cancelled) return;
        const delay = Math.min(30_000, 1_000 * 2 ** reconnectAttempt.current);
        reconnectAttempt.current++;
        timer = window.setTimeout(connect, delay);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { vehicles, status, lastUpdate };
}
