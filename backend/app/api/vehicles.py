"""GET /vehicles — returns the current in-memory snapshot of live vehicles."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..ingestion.state import snapshot

router = APIRouter(tags=["vehicles"])


@router.get("/vehicles")
def list_vehicles(
    route_id: str | None = Query(None),
    agency_id: str | None = Query(None),
) -> dict:
    items = snapshot()
    if route_id:
        items = [v for v in items if v.get("route_id") == route_id]
    if agency_id:
        items = [v for v in items if v.get("agency_id") == agency_id]
    return {"vehicles": items, "count": len(items)}
