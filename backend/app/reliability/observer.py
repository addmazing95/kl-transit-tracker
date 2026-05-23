"""
Detect "arrival at stop" events from live vehicle position polls and record
delay vs the static schedule. Runs alongside ingestion.

A trip is considered to have arrived at stop S when the live vehicle is within
ARRIVAL_RADIUS_M of S AND the previous poll for that vehicle was outside that
radius (rising-edge detection). The scheduled arrival is the nearest
scheduled_stop_time row for the same route+stop with a timestamp within
SCHEDULE_WINDOW_S of "now".
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..db import session_scope
from ..models import ScheduledStopTime, Stop, TripObservation, VehiclePosition

log = logging.getLogger(__name__)

ARRIVAL_RADIUS_M = 80.0
SCHEDULE_WINDOW_S = 30 * 60


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _seconds_since_midnight(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


async def run_once() -> int:
    """Scan for new arrivals. Returns observations recorded."""
    now_utc = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    now_local = datetime.now(tz=ZoneInfo(settings.timezone))
    local_t = _seconds_since_midnight(now_local)
    today_local = now_local.date()
    recorded = 0

    with session_scope() as session:
        # Latest 2 positions per live vehicle (so we can detect arrival edges).
        recent = session.execute(
            select(VehiclePosition)
            .where(
                VehiclePosition.source == "live",
                VehiclePosition.ts >= now_utc - timedelta(minutes=10),
            )
            .order_by(VehiclePosition.vehicle_id, desc(VehiclePosition.ts))
        ).scalars().all()

        by_vehicle: dict[str, list[VehiclePosition]] = {}
        for vp in recent:
            by_vehicle.setdefault(vp.vehicle_id, []).append(vp)

        for vid, points in by_vehicle.items():
            if not points or not points[0].route_id:
                continue
            newest, prev = points[0], (points[1] if len(points) > 1 else None)

            # Candidate stops: those on the vehicle's route within 200m.
            candidates = session.execute(
                select(Stop, ScheduledStopTime)
                .join(ScheduledStopTime, ScheduledStopTime.stop_id == Stop.id)
                .where(ScheduledStopTime.route_id == newest.route_id)
                .where(ScheduledStopTime.arrival_s.between(
                    local_t - SCHEDULE_WINDOW_S, local_t + SCHEDULE_WINDOW_S
                ))
            ).all()

            for stop, sched in candidates:
                d_now = _haversine(newest.lat, newest.lon, stop.lat, stop.lon)
                if d_now > ARRIVAL_RADIUS_M:
                    continue
                # Rising edge: previously outside, now inside.
                if prev:
                    d_prev = _haversine(prev.lat, prev.lon, stop.lat, stop.lon)
                    if d_prev <= ARRIVAL_RADIUS_M:
                        continue

                scheduled = datetime.combine(today_local, datetime.min.time()) + timedelta(
                    seconds=sched.arrival_s
                )
                # Strip tz for SQLite storage.
                scheduled = scheduled.replace(tzinfo=None)
                observed = newest.ts
                delay = int((observed - scheduled).total_seconds())

                try:
                    session.add(TripObservation(
                        service_date=today_local,
                        trip_id=sched.trip_id,
                        route_id=newest.route_id,
                        stop_id=stop.id,
                        scheduled_arrival=scheduled,
                        observed_arrival=observed,
                        delay_seconds=delay,
                    ))
                    session.flush()
                    recorded += 1
                except IntegrityError:
                    session.rollback()
                    # Already recorded this trip+stop+date.

    if recorded:
        log.info("observer: recorded %d new arrivals", recorded)
    return recorded
