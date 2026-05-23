"""GET /news — aggregated news items, newest first."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from ..db import SessionLocal
from ..models import NewsItem

router = APIRouter(tags=["news"])


@router.get("/news")
def list_news(
    days: int = Query(60, ge=1, le=365),
    tag: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    cutoff = datetime.now() - timedelta(days=days)
    with SessionLocal() as session:
        # Order: items with a published date first (newest), then undated items.
        q = select(NewsItem).order_by(
            desc(NewsItem.published_at),
            desc(NewsItem.id),
        )
        rows = session.scalars(q.limit(limit * 3)).all()
        items = []
        for n in rows:
            if n.published_at and n.published_at < cutoff:
                continue
            tags = json.loads(n.tags_json) if n.tags_json else []
            if tag and tag not in tags:
                continue
            items.append({
                "id": n.id,
                "source": n.source,
                "title": n.title,
                "url": n.url,
                "published_at": n.published_at.isoformat() + "Z" if n.published_at else None,
                "summary": n.summary,
                "tags": tags,
            })
            if len(items) >= limit:
                break

    return {"items": items, "count": len(items)}
