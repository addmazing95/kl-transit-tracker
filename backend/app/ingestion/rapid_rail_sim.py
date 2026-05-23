"""
Simulate MRT/LRT/Monorail vehicle positions from the static GTFS schedule.

Used as a stand-in until Prasarana's rapid-rail-kl realtime feed is stable. Each
simulated vehicle is tagged source="scheduled" so the UI can badge it differently.

Algorithm (per 60s tick):
  1. For each Prasarana rail route, get all trips active at "now" (KL time).
  2. For each active trip, find the stop_times pair (i, i+1) bracketing now.
  3. Linearly interpolate position between stop[i].coords and stop[i+1].coords
     by the fractional time elapsed in that segment.

This is intentionally simple: dots move in straight lines between stations, not
along the curved shape. Good enough for visualization at city zoom.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Route, ScheduledStopTime, Stop
from .state import LiveVehicle, update_latest

log = logging.getLogger(__name__)

AGENCY_ID = "prasarana_rail"

# Typical observed peak-hours headway by route kind (seconds between trains).
# Used to synthesize phantom trips from the single canonical trip the static
# feed ships per route+direction.
HEADWAY_BY_KIND: dict[str, int] = {
    "mrt": 360,        # ~6 min
    "lrt": 240,        # ~4 min
    "monorail": 600,   # ~10 min
    "brt": 600,        # ~10 min
}
SERVICE_START_S = 6 * 3600     # 06:00
SERVICE_END_S = 24 * 3600 - 1  # 23:59:59


@dataclass
class StopTime:
    stop_id: str
    seq: int
    arrival_s: int
    departure_s: int
    lat: float
    lon: float


@dataclass
class Trip:
    trip_id: str
    route_id: str
    stops: list[StopTime]

    @property
    def earliest(self) -> int:
        return self.stops[0].arrival_s if self.stops else 0

    @property
    def latest(self) -> int:
        return self.stops[-1].departure_s if self.stops else 0


_trips_cache: list[Trip] | None = None


def _build_cache() -> list[Trip]:
    with SessionLocal() as session:
        prasarana_routes = session.scalars(
            select(Route).where(Route.agency_id == AGENCY_ID)
        ).all()
        if not prasarana_routes:
            return []
        route_kinds = {r.id: r.kind for r in prasarana_routes}
        route_ids = list(route_kinds.keys())

        rows = session.execute(
            select(
                ScheduledStopTime.trip_id,
                ScheduledStopTime.route_id,
                ScheduledStopTime.stop_id,
                ScheduledStopTime.seq,
                ScheduledStopTime.arrival_s,
                ScheduledStopTime.departure_s,
                Stop.lat,
                Stop.lon,
            )
            .join(Stop, Stop.id == ScheduledStopTime.stop_id)
            .where(ScheduledStopTime.route_id.in_(route_ids))
            .order_by(ScheduledStopTime.trip_id, ScheduledStopTime.seq)
        ).all()

    canonical: dict[str, Trip] = {}
    for trip_id, route_id, stop_id, seq, arr, dep, lat, lon in rows:
        t = canonical.setdefault(trip_id, Trip(trip_id=trip_id, route_id=route_id, stops=[]))
        t.stops.append(StopTime(stop_id, seq, arr, dep, lat, lon))

    # Drop degenerate trips with fewer than 2 stops.
    raw_trips = [t for t in canonical.values() if len(t.stops) >= 2]

    # Dedupe: the feed sometimes ships multiple canonical variants per direction
    # (weekday/weekend/etc). Keep one trip per (route_id, first_stop, last_stop).
    seen_dirs: dict[tuple[str, str, str], Trip] = {}
    for t in raw_trips:
        key = (t.route_id, t.stops[0].stop_id, t.stops[-1].stop_id)
        if key not in seen_dirs or len(t.stops) > len(seen_dirs[key].stops):
            seen_dirs[key] = t
    canonical_trips = list(seen_dirs.values())

    # The static feed ships ~1 canonical trip per route+direction. Synthesize
    # phantom trips by repeating each canonical trip at the route's typical
    # headway across the operating window.
    synthesized: list[Trip] = []
    for ct in canonical_trips:
        kind = route_kinds.get(ct.route_id, "mrt")
        headway = HEADWAY_BY_KIND.get(kind, 360)
        first_arr = ct.stops[0].arrival_s
        last_dep = ct.stops[-1].departure_s
        # Shift the canonical schedule so the first trip starts at SERVICE_START_S.
        base_shift = SERVICE_START_S - first_arr
        # Generate phantoms while their start fits before SERVICE_END_S.
        k = 0
        while True:
            shift = base_shift + k * headway
            new_first = first_arr + shift
            new_last = last_dep + shift
            if new_first > SERVICE_END_S:
                break
            shifted_stops = [
                StopTime(
                    stop_id=s.stop_id, seq=s.seq,
                    arrival_s=s.arrival_s + shift,
                    departure_s=s.departure_s + shift,
                    lat=s.lat, lon=s.lon,
                )
                for s in ct.stops
            ]
            synthesized.append(Trip(
                trip_id=f"{ct.trip_id}#{k}",
                route_id=ct.route_id,
                stops=shifted_stops,
            ))
            k += 1
            if new_last > SERVICE_END_S:
                break

    log.info(
        "rapid_rail_sim: cached %d canonical trips → %d phantom trips across %d routes",
        len(canonical_trips), len(synthesized), len({t.route_id for t in synthesized})
    )
    return synthesized


def _ensure_cache() -> list[Trip]:
    global _trips_cache
    if _trips_cache is None:
        _trips_cache = _build_cache()
    return _trips_cache


def invalidate_cache() -> None:
    global _trips_cache
    _trips_cache = None


def _seconds_since_midnight(now_local: datetime) -> int:
    return now_local.hour * 3600 + now_local.minute * 60 + now_local.second


def _interp_position(a: StopTime, b: StopTime, t_seconds: int) -> tuple[float, float]:
    span = max(1, b.arrival_s - a.departure_s)
    frac = max(0.0, min(1.0, (t_seconds - a.departure_s) / span))
    lat = a.lat + (b.lat - a.lat) * frac
    lon = a.lon + (b.lon - a.lon) * frac
    return lat, lon


def _simulate_trip(trip: Trip, t: int) -> Optional[LiveVehicle]:
    """Return a synthetic position for this trip at time t, or None if inactive."""
    if t < trip.earliest or t > trip.latest:
        return None
    # Find segment (i, i+1) where dep_i <= t <= arr_{i+1}, or hovering at a stop.
    stops = trip.stops
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a.arrival_s <= t <= b.departure_s:
            lat, lon = _interp_position(a, b, t)
            ts = datetime.now(tz=timezone.utc)
            return LiveVehicle(
                vehicle_id=f"sim-{trip.trip_id}",
                agency_id=AGENCY_ID,
                route_id=trip.route_id,
                trip_id=trip.trip_id,
                lat=lat,
                lon=lon,
                bearing=None,
                speed=None,
                ts=ts.isoformat().replace("+00:00", "Z"),
                source="scheduled",
            )
    return None


async def poll_once() -> int:
    """Simulate one tick. Returns count of synthetic vehicles emitted."""
    if settings.rapid_rail_live:
        log.debug("rapid_rail_live=true → skipping simulation")
        return 0

    trips = _ensure_cache()
    if not trips:
        return 0

    now_local = datetime.now(tz=ZoneInfo(settings.timezone))
    t = _seconds_since_midnight(now_local)

    samples: list[LiveVehicle] = []
    for trip in trips:
        v = _simulate_trip(trip, t)
        if v:
            samples.append(v)

    if samples:
        await update_latest(samples)
        log.info("rapid_rail_sim: emitted %d synthetic vehicles at t=%ds (local %s)",
                 len(samples), t, now_local.strftime("%H:%M:%S"))
    else:
        log.debug("rapid_rail_sim: no active trips at t=%ds", t)
    return len(samples)
