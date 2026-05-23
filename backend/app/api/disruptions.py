"""GET /disruptions — currently-active disruption events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import select

from ..db import SessionLocal
from ..models import DisruptionEvent, Route

router = APIRouter(tags=["disruptions"])


@router.get("/disruptions")
def list_disruptions(history_hours: int = 24) -> dict:
    cutoff = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(hours=history_hours)
    with SessionLocal() as session:
        events = session.scalars(
            select(DisruptionEvent)
            .where((DisruptionEvent.ended_at.is_(None)) | (DisruptionEvent.started_at >= cutoff))
            .order_by(DisruptionEvent.started_at.desc())
        ).all()

        route_names = {
            r.id: r.short_name or r.long_name or r.id
            for r in session.scalars(select(Route)).all()
        }

    def serialize(e: DisruptionEvent) -> dict:
        return {
            "id": e.id,
            "started_at": e.started_at.isoformat() + "Z",
            "ended_at": (e.ended_at.isoformat() + "Z") if e.ended_at else None,
            "route_id": e.route_id,
            "route_name": route_names.get(e.route_id) if e.route_id else None,
            "vehicle_id": e.vehicle_id,
            "severity": e.severity,
            "reason": e.reason,
            "evidence": json.loads(e.evidence_json) if e.evidence_json else {},
        }

    serialized = [serialize(e) for e in events]
    active = [e for e in serialized if e["ended_at"] is None]
    return {
        "active": active,
        "recent": serialized,
        "counts": {
            "active": len(active),
            "crit": sum(1 for e in active if e["severity"] == "crit"),
            "warn": sum(1 for e in active if e["severity"] == "warn"),
        },
    }
