"""
Detect transit disruptions from recent vehicle positions.

Rules (per plan):
  STUCK      Vehicle hasn't moved >50m across last 3 polls (≥4min)
             AND isn't currently within 80m of any known stop.
             Severity warn; escalates to crit after 8min stuck.
  MISSING    Vehicle reported recently but hasn't in last 5min (during service window).
  LINE_DOWN  More than 50% of a route's expected vehicles are stuck or missing.

Simulated vehicles (source='scheduled') are excluded — they never get stuck.
Disruption news scraped in M7 will create equivalent NEWS-tagged events for
MRT/LRT so the UI looks consistent across operators.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, select

from ..db import session_scope
from ..models import DisruptionEvent, Stop, VehiclePosition

log = logging.getLogger(__name__)

STUCK_RADIUS_M = 50.0
STUCK_WINDOW_S = 4 * 60
CRIT_AFTER_S = 8 * 60
NEAR_STOP_M = 80.0
MISSING_AFTER_S = 5 * 60
LINE_DOWN_FRACTION = 0.5


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _is_in_service_window(now: datetime) -> bool:
    # KTMB Komuter runs roughly 05:00 – 24:00 local. Treat 04:30–24:30 as in-service.
    # The caller is already in UTC; converting via offset would be cleaner but for
    # disruption-detection slack this approximation is fine for KL (UTC+8).
    local_hour = (now.hour + 8) % 24
    return 4 <= local_hour <= 23 or local_hour == 0


def _find_or_create_event(
    session, vehicle_id: str, route_id: Optional[str], reason: str
) -> DisruptionEvent | None:
    return session.execute(
        select(DisruptionEvent)
        .where(
            DisruptionEvent.vehicle_id == vehicle_id,
            DisruptionEvent.reason == reason,
            DisruptionEvent.ended_at.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()


def _resolve_event(session, event: DisruptionEvent, now: datetime, why: str) -> None:
    event.ended_at = now
    evidence = json.loads(event.evidence_json or "{}")
    evidence["resolved"] = why
    event.evidence_json = json.dumps(evidence)


async def run_once() -> dict:
    """Single pass: returns counts of new/active/resolved events."""
    now = _now()
    counts = {"new": 0, "still_active": 0, "resolved": 0}

    with session_scope() as session:
        # Pull the last 3 positions per LIVE vehicle (KTMB only).
        # SQLite has no LATERAL — do it in two queries.
        recent_window = now - timedelta(seconds=STUCK_WINDOW_S + 60)
        rows = session.execute(
            select(
                VehiclePosition.vehicle_id,
                VehiclePosition.route_id,
                VehiclePosition.ts,
                VehiclePosition.lat,
                VehiclePosition.lon,
            )
            .where(
                VehiclePosition.source == "live",
                VehiclePosition.ts >= recent_window,
            )
            .order_by(VehiclePosition.vehicle_id, desc(VehiclePosition.ts))
        ).all()

        per_vehicle: dict[str, list] = {}
        for vid, rid, ts, lat, lon in rows:
            per_vehicle.setdefault(vid, []).append((rid, ts, lat, lon))

        # Stop coordinates for the near-stop check.
        stops = session.execute(select(Stop.lat, Stop.lon)).all()
        stops_xy = [(s.lat, s.lon) for s in stops]

        # ---- STUCK detection ----
        for vid, points in per_vehicle.items():
            if len(points) < 2:
                continue
            newest = points[0]
            oldest = points[-1]
            elapsed = (newest[1] - oldest[1]).total_seconds()
            if elapsed < STUCK_WINDOW_S:
                continue
            dist = _haversine(newest[2], newest[3], oldest[2], oldest[3])
            near_stop = any(
                _haversine(newest[2], newest[3], slat, slon) < NEAR_STOP_M
                for slat, slon in stops_xy
            )
            existing = _find_or_create_event(session, vid, newest[0], "STUCK")
            if dist < STUCK_RADIUS_M and not near_stop:
                severity = "crit" if elapsed > CRIT_AFTER_S else "warn"
                if existing:
                    existing.severity = severity
                    counts["still_active"] += 1
                else:
                    session.add(DisruptionEvent(
                        started_at=newest[1],
                        route_id=newest[0],
                        vehicle_id=vid,
                        severity=severity,
                        reason="STUCK",
                        evidence_json=json.dumps({
                            "distance_m": round(dist, 1),
                            "elapsed_s": int(elapsed),
                            "lat": newest[2], "lon": newest[3],
                        }),
                    ))
                    counts["new"] += 1
            elif existing:
                _resolve_event(session, existing, now, "moving again")
                counts["resolved"] += 1

        # ---- MISSING detection: vehicles seen recently but not in last 5 min ----
        if _is_in_service_window(now):
            last_seen_rows = session.execute(
                select(VehiclePosition.vehicle_id, func.max(VehiclePosition.ts))
                .where(VehiclePosition.source == "live")
                .where(VehiclePosition.ts > now - timedelta(hours=2))
                .group_by(VehiclePosition.vehicle_id)
            ).all()
            cutoff = now - timedelta(seconds=MISSING_AFTER_S)
            for vid, last_ts in last_seen_rows:
                existing = _find_or_create_event(session, vid, None, "MISSING")
                if last_ts < cutoff:
                    if not existing:
                        session.add(DisruptionEvent(
                            started_at=last_ts,
                            vehicle_id=vid,
                            severity="warn",
                            reason="MISSING",
                            evidence_json=json.dumps({"last_seen": last_ts.isoformat()}),
                        ))
                        counts["new"] += 1
                    else:
                        counts["still_active"] += 1
                elif existing:
                    _resolve_event(session, existing, now, "reporting again")
                    counts["resolved"] += 1

    if counts["new"] or counts["resolved"]:
        log.info("disruption: %s", counts)
    return counts
