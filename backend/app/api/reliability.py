"""GET /reliability/weekly — last 7 days of per-route on-time stats."""

from __future__ import annotations

from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..db import SessionLocal
from ..models import ReliabilityDaily, Route

router = APIRouter(tags=["reliability"])


@router.get("/reliability/weekly")
def weekly(days: int = Query(7, ge=1, le=90)) -> dict:
    end = datetime.now().date()
    start = end - timedelta(days=days - 1)

    with SessionLocal() as session:
        rows = session.execute(
            select(ReliabilityDaily)
            .where(ReliabilityDaily.service_date >= start)
            .order_by(ReliabilityDaily.service_date)
        ).scalars().all()

        routes = {
            r.id: {
                "route_id": r.id,
                "agency_id": r.agency_id,
                "short_name": r.short_name,
                "long_name": r.long_name,
                "color": r.color,
                "kind": r.kind,
            }
            for r in session.scalars(select(Route))
        }

    series_by_route: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        series_by_route[r.route_id].append({
            "service_date": r.service_date.isoformat(),
            "on_time_pct": r.on_time_pct,
            "mean_delay_s": r.mean_delay_s,
            "trips_observed": r.trips_observed,
            "trips_scheduled": r.trips_scheduled,
        })

    summary = []
    for route_id, series in series_by_route.items():
        if not series:
            continue
        total_obs = sum(s["trips_observed"] for s in series)
        total_sched = sum(s["trips_scheduled"] for s in series)
        weighted_on_time = (
            sum(s["on_time_pct"] * s["trips_observed"] for s in series) / total_obs
            if total_obs else 0
        )
        weighted_delay = (
            sum(s["mean_delay_s"] * s["trips_observed"] for s in series) / total_obs
            if total_obs else 0
        )
        summary.append({
            **routes.get(route_id, {"route_id": route_id}),
            "on_time_pct": round(weighted_on_time, 1),
            "mean_delay_s": round(weighted_delay, 1),
            "trips_observed": total_obs,
            "trips_scheduled": total_sched,
            "series": series,
        })

    summary.sort(key=lambda r: r["on_time_pct"], reverse=True)
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "routes": summary,
    }
