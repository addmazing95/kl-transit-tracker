// Resolve backend base URL at runtime when not pinned at build time. This
// makes the same bundle work on localhost, a cloud VM, Play with Docker,
// Codespaces, etc. — the browser uses whatever hostname it's already talking
// to, port 8000. Pin VITE_API_BASE / VITE_WS_BASE at build time to override
// (e.g. when backend and frontend are on different hosts).
function _defaultHttp(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}
function _defaultWs(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8000";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.hostname}:8000`;
}

const _envBase = import.meta.env.VITE_API_BASE;
const _envWs = import.meta.env.VITE_WS_BASE;
const BASE = _envBase && _envBase.length > 0 ? _envBase : _defaultHttp();
export const WS_BASE = _envWs && _envWs.length > 0 ? _envWs : _defaultWs();

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json() as Promise<T>;
}
