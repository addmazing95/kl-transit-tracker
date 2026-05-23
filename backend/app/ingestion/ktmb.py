"""
Poll the KTMB GTFS-realtime vehicle position feed and persist samples.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import settings
from ..db import session_scope
from ..gtfs.rt_client import fetch_feed
from ..models import Route, VehiclePosition
from .state import LiveVehicle, update_latest

log = logging.getLogger(__name__)

AGENCY_ID = "ktmb"


async def poll_once() -> int:
    """Fetch latest KTMB positions, write to DB and broadcast. Returns vehicle count."""
    try:
        samples = await fetch_feed(settings.ktmb_gtfs_rt_url)
    except Exception as e:  # network / parse errors shouldn't kill the scheduler
        log.warning("KTMB poll failed: %s", e)
        return 0

    if not samples:
        log.debug("KTMB feed empty")
        return 0

    # Validate route_ids against our static catalog so we don't insert FK orphans.
    with session_scope() as session:
        known_routes = {r for (r,) in session.execute(
            select(Route.id).where(Route.agency_id == AGENCY_ID)
        )}

        rows: list[VehiclePosition] = []
        live: list[LiveVehicle] = []
        now_utc = datetime.now(tz=timezone.utc)
        for s in samples:
            route_id = s.route_id if s.route_id in known_routes else None
            rows.append(VehiclePosition(
                ts=s.ts.replace(tzinfo=None),  # store naive UTC for SQLite compat
                agency_id=AGENCY_ID,
                route_id=route_id,
                trip_id=s.trip_id,
                vehicle_id=s.vehicle_id,
                lat=s.lat,
                lon=s.lon,
                bearing=s.bearing,
                speed=s.speed,
                source="live",
            ))
            live.append(LiveVehicle(
                vehicle_id=s.vehicle_id,
                agency_id=AGENCY_ID,
                route_id=route_id,
                trip_id=s.trip_id,
                lat=s.lat,
                lon=s.lon,
                bearing=s.bearing,
                speed=s.speed,
                ts=s.ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                source="live",
            ))
        session.add_all(rows)

    await update_latest(live)
    log.info("KTMB poll ok: %d vehicles (ts=%s)", len(samples), now_utc.isoformat())
    return len(samples)
