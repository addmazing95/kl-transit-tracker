"""
GET /lines — catalog of all rail routes with their geometry and stops.

Response is cached in-process; static GTFS data only changes when the user reruns
`bootstrap_static.py`. Frontend hits this once on load.
"""

from __future__ import annotations

import threading
from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Route, ScheduledStopTime, Shape, Stop

router = APIRouter(tags=["lines"])


_cache: dict | None = None
_cache_lock = threading.Lock()


def _build_payload() -> dict:
    """Assemble the line catalog from the DB."""
    with SessionLocal() as session:
        routes = session.scalars(select(Route).order_by(Route.agency_id, Route.id)).all()

        # Shape points grouped by (route_id, shape_id) -> ordered polyline.
        shape_rows = session.execute(
            select(Shape.route_id, Shape.shape_id, Shape.seq, Shape.lat, Shape.lon)
            .order_by(Shape.route_id, Shape.shape_id, Shape.seq)
        ).all()
        polylines_by_route: dict[str, list[list[list[float]]]] = defaultdict(list)
        current_key: tuple[str, str] | None = None
        current: list[list[float]] = []
        for route_id, shape_id, _seq, lat, lon in shape_rows:
            key = (route_id, shape_id)
            if key != current_key:
                if current_key and current:
                    polylines_by_route[current_key[0]].append(current)
                current_key = key
                current = []
            current.append([lat, lon])
        if current_key and current:
            polylines_by_route[current_key[0]].append(current)

        # Stop ids per route (via stop_times).
        stop_id_rows = session.execute(
            select(ScheduledStopTime.route_id, ScheduledStopTime.stop_id, ScheduledStopTime.seq)
            .order_by(ScheduledStopTime.route_id, ScheduledStopTime.trip_id, ScheduledStopTime.seq)
        ).all()
        # Use the first trip we encounter per route as representative ordering.
        rep_stops_by_route: dict[str, list[str]] = {}
        seen_keys: set[tuple[str, str]] = set()  # (route_id, trip_id) tracker not needed; use ordering
        stops_by_route: dict[str, list[str]] = defaultdict(list)
        seen_per_route: dict[str, set[str]] = defaultdict(set)
        for route_id, stop_id, _seq in stop_id_rows:
            if stop_id in seen_per_route[route_id]:
                continue
            seen_per_route[route_id].add(stop_id)
            stops_by_route[route_id].append(stop_id)

        # Pull all needed stops in one query.
        all_stop_ids = {sid for ids in stops_by_route.values() for sid in ids}
        stop_records = {
            s.id: s
            for s in session.scalars(select(Stop).where(Stop.id.in_(all_stop_ids))).all()
        } if all_stop_ids else {}

        lines = []
        for r in routes:
            stop_ids = stops_by_route.get(r.id, [])
            stops_payload = [
                {
                    "id": stop_records[sid].id,
                    "name": stop_records[sid].name,
                    "lat": stop_records[sid].lat,
                    "lon": stop_records[sid].lon,
                }
                for sid in stop_ids
                if sid in stop_records
            ]

            polylines = polylines_by_route.get(r.id, [])
            # Fallback: synthesize a polyline from stop order for routes without shapes (KTMB).
            if not polylines and stops_payload:
                polylines = [[[s["lat"], s["lon"]] for s in stops_payload]]

            lines.append({
                "route_id": r.id,
                "agency_id": r.agency_id,
                "short_name": r.short_name,
                "long_name": r.long_name,
                "color": r.color,
                "kind": r.kind,
                "polylines": polylines,
                "stops": stops_payload,
            })

        return {"lines": lines}


def get_lines_cached() -> dict:
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = _build_payload()
        return _cache


def invalidate_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


@router.get("/lines")
def list_lines() -> dict:
    return get_lines_cached()
