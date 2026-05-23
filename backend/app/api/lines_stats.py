"""
GET /lines/stats — live count of trains in service per route, split by direction.

Direction is derived from the trip_id encoded by the simulator:
  sim-{CANONICAL_TRIP_ID}#{phantom_index}
The canonical trip's first/last stop name gives us a human-readable
"to <terminus>" label for each direction.

Live KTMB vehicles whose route_id is unknown or whose trip_id isn't a sim trip
are counted under `uncategorized` for that route (or skipped if route_id is
missing entirely, since they can't be attributed to a line).
"""

from __future__ import annotations

import threading
from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from ..db import SessionLocal
from ..ingestion.state import snapshot
from ..models import Route, ScheduledStopTime, Stop

router = APIRouter(tags=["lines"])

_canonical_cache: dict | None = None
_cache_lock = threading.Lock()

KIND_ORDER = ["mrt", "lrt", "monorail", "ktm", "ets", "brt"]


def _build_canonical_cache() -> dict:
    """trip_id -> {first_stop, last_stop, route_id} for every canonical trip."""
    with SessionLocal() as session:
        rows = session.execute(
            select(
                ScheduledStopTime.trip_id,
                ScheduledStopTime.route_id,
                ScheduledStopTime.seq,
                Stop.name,
            )
            .join(Stop, Stop.id == ScheduledStopTime.stop_id)
            .order_by(ScheduledStopTime.trip_id, ScheduledStopTime.seq)
        ).all()

    by_trip: dict[str, list] = defaultdict(list)
    for tid, rid, seq, sname in rows:
        by_trip[tid].append((seq, rid, sname))

    out: dict[str, dict] = {}
    for tid, stops in by_trip.items():
        if len(stops) < 2:
            continue
        stops.sort()
        out[tid] = {
            "route_id": stops[0][1],
            "first_stop": stops[0][2],
            "last_stop": stops[-1][2],
        }
    return out


def _canonical_lookup() -> dict:
    global _canonical_cache
    with _cache_lock:
        if _canonical_cache is None:
            _canonical_cache = _build_canonical_cache()
        return _canonical_cache


def invalidate_cache() -> None:
    global _canonical_cache
    with _cache_lock:
        _canonical_cache = None


def _canonical_trip_of(trip_id: str | None) -> str | None:
    """Phantom simulator trip_ids look like `{canonical}#{index}` — strip the
    `#index` suffix to recover the canonical trip_id. Real KTMB trip_ids never
    contain `#`, so they pass through unchanged and won't match the canonical
    cache (correctly bucketing them as uncategorized)."""
    if not trip_id:
        return None
    return trip_id.rsplit("#", 1)[0] if "#" in trip_id else trip_id


@router.get("/lines/stats")
def lines_stats() -> dict:
    canonicals = _canonical_lookup()

    with SessionLocal() as session:
        routes = {
            r.id: {
                "route_id": r.id,
                "short_name": r.short_name,
                "long_name": r.long_name,
                "color": r.color,
                "kind": r.kind,
                "agency_id": r.agency_id,
            }
            for r in session.scalars(select(Route)).all()
        }

    snap = snapshot()

    # route_id -> aggregate
    agg: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "directions": {}, "uncategorized": 0, "stuck": 0}
    )

    for v in snap:
        rid = v.get("route_id")
        if not rid or rid not in routes:
            continue
        st = agg[rid]
        st["total"] += 1
        if v.get("stuck"):
            st["stuck"] += 1

        canonical_tid = _canonical_trip_of(v.get("trip_id"))
        info = canonicals.get(canonical_tid) if canonical_tid else None
        if info:
            key = info["last_stop"]
            bucket = st["directions"].setdefault(
                key, {"label": f"to {key}", "count": 0, "stuck": 0}
            )
            bucket["count"] += 1
            if v.get("stuck"):
                bucket["stuck"] += 1
        else:
            st["uncategorized"] += 1

    out = []
    for rid, st in agg.items():
        r = routes.get(rid)
        if not r:
            continue
        out.append({
            **r,
            "total": st["total"],
            "stuck": st["stuck"],
            "directions": sorted(st["directions"].values(), key=lambda x: -x["count"]),
            "uncategorized": st["uncategorized"],
        })

    out.sort(
        key=lambda r: (
            KIND_ORDER.index(r["kind"]) if r["kind"] in KIND_ORDER else 99,
            -r["total"],
        )
    )
    return {
        "stats": out,
        "total_vehicles": sum(r["total"] for r in out),
        "total_stuck": sum(r["stuck"] for r in out),
    }
