const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
export const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json() as Promise<T>;
}
