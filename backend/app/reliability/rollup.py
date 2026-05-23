"""
Daily aggregation: yesterday's trip observations -> reliability_daily rows.

On-time = observed arrival in [-60s, +300s] of scheduled.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import session_scope  # noqa: E402
from app.models import ReliabilityDaily, ScheduledStopTime, TripObservation  # noqa: E402

log = logging.getLogger(__name__)

ON_TIME_EARLY_S = -60
ON_TIME_LATE_S = 300


def rollup_date(target: date) -> int:
    """Rebuild reliability_daily rows for a single date. Returns rows written."""
    with session_scope() as session:
        session.execute(delete(ReliabilityDaily).where(ReliabilityDaily.service_date == target))

        # Aggregate per route.
        obs = session.execute(
            select(
                TripObservation.route_id,
                TripObservation.delay_seconds,
            ).where(TripObservation.service_date == target)
        ).all()

        if not obs:
            return 0

        by_route: dict[str, list[int]] = {}
        for route_id, delay in obs:
            by_route.setdefault(route_id, []).append(delay)

        # Scheduled-trips denominator: count distinct trip_ids per route from
        # scheduled_stop_times. Daily approximation — for routes with one
        # canonical trip in the static feed we treat it as 1 scheduled "trip".
        scheduled_counts = dict(session.execute(
            select(
                ScheduledStopTime.route_id,
                func.count(func.distinct(ScheduledStopTime.trip_id)),
            ).group_by(ScheduledStopTime.route_id)
        ).all())

        written = 0
        for route_id, delays in by_route.items():
            on_time = sum(1 for d in delays if ON_TIME_EARLY_S <= d <= ON_TIME_LATE_S)
            mean = sum(delays) / len(delays)
            session.add(ReliabilityDaily(
                service_date=target,
                route_id=route_id,
                on_time_pct=on_time / len(delays) * 100,
                mean_delay_s=mean,
                trips_observed=len(delays),
                trips_scheduled=scheduled_counts.get(route_id, len(delays)),
                cancellations=0,
            ))
            written += 1
        return written


async def run_daily() -> int:
    """Scheduler entrypoint — rolls up yesterday."""
    yesterday = (datetime.now() - timedelta(days=1)).date()
    written = rollup_date(yesterday)
    log.info("rollup: wrote %d rows for %s", written, yesterday)
    return written


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD (default: yesterday)")
    p.add_argument("--backfill", type=int, default=0,
                   help="Roll up the last N days including today")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.backfill:
        today = datetime.now().date()
        total = 0
        for i in range(args.backfill):
            d = today - timedelta(days=i)
            total += rollup_date(d)
        print(f"Backfilled {args.backfill} days, total rows: {total}")
    else:
        target = (
            date.fromisoformat(args.date)
            if args.date
            else (datetime.now() - timedelta(days=1)).date()
        )
        n = rollup_date(target)
        print(f"Rolled up {target}: {n} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
