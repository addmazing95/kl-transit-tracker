"""
Seed synthetic trip_observations + reliability_daily rows for the last N days
so the Reliability page has something to render before real data accumulates.

Also supports injecting a stuck-vehicle disruption to test the banner.

Usage:
    python scripts/seed_demo.py --days 7
    python scripts/seed_demo.py --stuck KTM_001
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timedelta, timezone, time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import Base, engine, session_scope  # noqa: E402
from app.models import (  # noqa: E402
    DisruptionEvent,
    ReliabilityDaily,
    Route,
    TripObservation,
    VehiclePosition,
)


def seed_reliability(days: int) -> None:
    """Generate plausible weekly reliability per route."""
    today = datetime.now().date()
    with session_scope() as session:
        routes = session.scalars(select(Route)).all()
        if not routes:
            print("No routes in DB. Run bootstrap_static.py first.")
            return

        # Per-kind baseline on-time % and noise.
        baselines = {
            "mrt": (95, 3),
            "lrt": (92, 4),
            "monorail": (90, 4),
            "brt": (88, 5),
            "ktm": (85, 6),
            "ets": (87, 5),
        }
        # Wipe existing demo rows in the window.
        start = today - timedelta(days=days - 1)
        session.query(ReliabilityDaily).filter(
            ReliabilityDaily.service_date >= start
        ).delete(synchronize_session=False)

        for r in routes:
            base, sigma = baselines.get(r.kind, (85, 6))
            for i in range(days):
                d = today - timedelta(days=days - 1 - i)
                on_time = max(50.0, min(100.0, random.gauss(base, sigma)))
                # Mean delay increases as on-time drops.
                mean_delay = (100 - on_time) * 6 + random.uniform(-15, 30)
                trips_scheduled = random.randint(180, 320)
                trips_observed = int(trips_scheduled * random.uniform(0.92, 0.99))
                session.add(ReliabilityDaily(
                    service_date=d,
                    route_id=r.id,
                    on_time_pct=round(on_time, 1),
                    mean_delay_s=round(mean_delay, 1),
                    trips_observed=trips_observed,
                    trips_scheduled=trips_scheduled,
                    cancellations=random.randint(0, 3),
                ))
        print(f"Seeded reliability for {len(routes)} routes × {days} days.")


def seed_stuck(vehicle_id: str) -> None:
    """Insert frozen positions for a vehicle so disruption detector triggers STUCK."""
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    lat, lon = 3.1700, 101.7100  # arbitrary KL spot away from any station
    with session_scope() as session:
        for k in range(5):
            session.add(VehiclePosition(
                ts=now - timedelta(seconds=60 * k),
                agency_id="ktmb",
                route_id=None,
                trip_id=None,
                vehicle_id=vehicle_id,
                lat=lat + random.uniform(-1e-6, 1e-6),
                lon=lon + random.uniform(-1e-6, 1e-6),
                bearing=0.0,
                speed=0.0,
                source="live",
            ))
    print(f"Seeded 5 stationary positions for {vehicle_id}. "
          f"Next disruption sweep should emit STUCK.")


def seed_demo_disruption() -> None:
    """Add a fake critical disruption so the banner shows up."""
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    with session_scope() as session:
        session.add(DisruptionEvent(
            started_at=now - timedelta(minutes=12),
            route_id=None,
            vehicle_id="DEMO_001",
            severity="crit",
            reason="STUCK",
            evidence_json='{"distance_m": 8.2, "elapsed_s": 720, "demo": true}',
        ))
    print("Seeded one DEMO critical disruption.")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=0, help="Generate N days of reliability data")
    p.add_argument("--stuck", help="Vehicle ID to mark stuck (creates frozen positions)")
    p.add_argument("--demo-disruption", action="store_true",
                   help="Insert a fake crit disruption to test the banner")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)

    if args.days:
        seed_reliability(args.days)
    if args.stuck:
        seed_stuck(args.stuck)
    if args.demo_disruption:
        seed_demo_disruption()
    if not (args.days or args.stuck or args.demo_disruption):
        p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
