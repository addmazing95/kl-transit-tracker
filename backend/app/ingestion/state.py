"""
In-memory snapshot of latest vehicle positions, broadcast to WebSocket clients.

Producers (ingestion jobs) call `update_latest()`. Consumers (the WebSocket
endpoint) call `snapshot()` and subscribe via `register_listener()`.

In addition to storing the latest position, this module derives two enrichments
from the history of recent positions:

  - `bearing`: degrees clockwise from true north, computed from the previous
    position to the current one. Falls back to the upstream feed's bearing when
    the vehicle hasn't moved enough to compute it reliably.
  - `stuck`: True iff the vehicle's last 3 positions are all within
    STUCK_RADIUS_M of each other. Used by the frontend to highlight the dot.
"""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

# A vehicle is "stuck" if all recent positions fall inside this radius.
STUCK_RADIUS_M = 30.0
STUCK_HISTORY_POINTS = 3
# Don't recompute bearing for tiny movements (GPS jitter, simulator rounding).
MIN_MOVE_M_FOR_BEARING = 8.0


@dataclass
class LiveVehicle:
    vehicle_id: str
    agency_id: str
    route_id: Optional[str]
    trip_id: Optional[str]
    lat: float
    lon: float
    bearing: Optional[float]
    speed: Optional[float]
    ts: str          # ISO-8601 UTC, ending in 'Z'
    source: str      # "live" | "scheduled"
    stuck: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


_latest: dict[str, LiveVehicle] = {}
_history: dict[str, deque[tuple[float, float]]] = defaultdict(
    lambda: deque(maxlen=STUCK_HISTORY_POINTS)
)
_lock = asyncio.Lock()
_listeners: set[asyncio.Queue[list[dict]]] = set()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from (lat1,lon1) to (lat2,lon2) in degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _enrich(v: LiveVehicle) -> LiveVehicle:
    """Compute bearing + stuck for this vehicle based on history; mutates v."""
    history = _history[v.vehicle_id]
    if history:
        last_lat, last_lon = history[-1]
        moved = _haversine_m(last_lat, last_lon, v.lat, v.lon)
        if moved >= MIN_MOVE_M_FOR_BEARING:
            v.bearing = _initial_bearing(last_lat, last_lon, v.lat, v.lon)
        # else: keep the feed-provided bearing (or None)
    history.append((v.lat, v.lon))

    # Stuck = last STUCK_HISTORY_POINTS positions all within STUCK_RADIUS_M.
    if len(history) >= STUCK_HISTORY_POINTS:
        pts = list(history)
        stuck = True
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if _haversine_m(pts[i][0], pts[i][1], pts[j][0], pts[j][1]) > STUCK_RADIUS_M:
                    stuck = False
                    break
            if not stuck:
                break
        v.stuck = stuck
    else:
        v.stuck = False
    return v


async def update_latest(updates: list[LiveVehicle]) -> None:
    async with _lock:
        for v in updates:
            _enrich(v)
            _latest[v.vehicle_id] = v
    if updates:
        payload = [v.to_dict() for v in _latest.values()]
        for q in list(_listeners):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


def snapshot() -> list[dict]:
    return [v.to_dict() for v in _latest.values()]


def register_listener() -> asyncio.Queue[list[dict]]:
    q: asyncio.Queue[list[dict]] = asyncio.Queue(maxsize=4)
    _listeners.add(q)
    return q


def unregister_listener(q: asyncio.Queue[list[dict]]) -> None:
    _listeners.discard(q)


def prune_stale(now: datetime, max_age_seconds: int = 300) -> int:
    """Remove vehicles that haven't reported recently. Returns count removed."""
    cutoff = now.timestamp() - max_age_seconds
    removed = 0
    for vid in list(_latest.keys()):
        try:
            ts = datetime.fromisoformat(_latest[vid].ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ts < cutoff:
            del _latest[vid]
            _history.pop(vid, None)
            removed += 1
    return removed
