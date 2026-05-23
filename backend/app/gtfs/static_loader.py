"""
Download GTFS static zips from data.gov.my and load them into the local database.

Supports KTMB and Prasarana rapid-rail-kl. Idempotent — re-running replaces rows
per agency so the static catalog stays in sync with upstream weekly updates.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx
from sqlalchemy import delete

from ..config import settings
from ..db import session_scope
from ..models import Agency, Route, ScheduledStopTime, Shape, Stop

log = logging.getLogger(__name__)


# Color hints for known KL rail routes — applied only when GTFS omits route_color.
# Keys are matched case-insensitively against route_short_name OR route_long_name.
ROUTE_COLOR_HINTS: dict[str, str] = {
    "kelana jaya": "E51937",     # LRT Kelana Jaya (red)
    "ampang": "F36F21",          # LRT Ampang
    "sri petaling": "8E1B7A",    # LRT Sri Petaling (purple)
    "kajang": "16A75C",          # MRT Kajang line
    "putrajaya": "FFD200",       # MRT Putrajaya line
    "monorail": "8FCD3C",        # KL Monorail
    "kl monorail": "8FCD3C",
    "ktm komuter": "5D2A82",
    "ets": "1D4E89",
}

ROUTE_KIND_HINTS: list[tuple[str, str]] = [
    ("brt", "brt"),
    ("monorail", "monorail"),
    ("mrl", "monorail"),
    ("mrt", "mrt"),
    ("kajang", "mrt"),
    ("putrajaya", "mrt"),
    ("lrt", "lrt"),
    ("kelana jaya", "lrt"),
    ("ampang", "lrt"),
    ("sri petaling", "lrt"),
    ("ets", "ets"),
    ("komuter", "ktm"),
    ("ktm", "ktm"),
]


@dataclass
class GtfsSource:
    agency_id: str
    agency_name: str
    agency_kind: str           # rail | bus
    url: str
    default_route_kind: str    # fallback when route name has no hint


KTMB_SOURCE = GtfsSource(
    agency_id="ktmb",
    agency_name="KTMB",
    agency_kind="rail",
    url=settings.ktmb_gtfs_static_url,
    default_route_kind="ktm",
)

PRASARANA_RAIL_SOURCE = GtfsSource(
    agency_id="prasarana_rail",
    agency_name="Rapid KL Rail",
    agency_kind="rail",
    url=settings.prasarana_rail_static_url,
    default_route_kind="mrt",
)


def _infer_route_kind(short: str | None, long: str | None, default: str) -> str:
    text = f"{short or ''} {long or ''}".lower()
    for needle, kind in ROUTE_KIND_HINTS:
        if needle in text:
            return kind
    return default


def _infer_color(short: str | None, long: str | None, gtfs_color: str | None) -> str | None:
    if gtfs_color:
        return gtfs_color.strip().lstrip("#") or None
    text = f"{short or ''} {long or ''}".lower()
    for needle, color in ROUTE_COLOR_HINTS.items():
        if needle in text:
            return color
    return None


def _download(url: str, cache_path: Path) -> bytes:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Fetching GTFS static: %s", url)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        cache_path.write_bytes(r.content)
        log.info("Cached %d bytes to %s", len(r.content), cache_path)
        return r.content


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    if name not in zf.namelist():
        return []
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def _parse_time_to_seconds(t: str) -> int:
    # GTFS allows hours > 23 for trips spanning midnight.
    parts = t.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"bad time: {t!r}")
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s


def _wipe_agency(session, agency_id: str) -> None:
    """Delete existing static rows for this agency before re-inserting."""
    # Child tables first.
    session.execute(delete(ScheduledStopTime).where(
        ScheduledStopTime.route_id.in_(
            session.query(Route.id).filter(Route.agency_id == agency_id)
        )
    ))
    session.execute(delete(Shape).where(
        Shape.route_id.in_(
            session.query(Route.id).filter(Route.agency_id == agency_id)
        )
    ))
    session.execute(delete(Stop).where(Stop.agency_id == agency_id))
    session.execute(delete(Route).where(Route.agency_id == agency_id))
    session.execute(delete(Agency).where(Agency.id == agency_id))
    session.flush()


def load_source(source: GtfsSource, force_download: bool = False) -> dict[str, int]:
    """Download (or reuse cache), parse, and upsert into DB. Returns counts."""
    cache_path = settings.gtfs_cache_dir / f"{source.agency_id}.zip"
    if force_download or not cache_path.exists():
        raw = _download(source.url, cache_path)
    else:
        log.info("Using cached %s", cache_path)
        raw = cache_path.read_bytes()

    counts = {"routes": 0, "stops": 0, "shapes": 0, "stop_times": 0}

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        routes_rows = _read_csv(zf, "routes.txt")
        stops_rows = _read_csv(zf, "stops.txt")
        shapes_rows = _read_csv(zf, "shapes.txt")
        trips_rows = _read_csv(zf, "trips.txt")
        stop_times_rows = _read_csv(zf, "stop_times.txt")

    trip_to_route: dict[str, str] = {t["trip_id"]: t["route_id"] for t in trips_rows}
    trip_to_shape: dict[str, str | None] = {
        t["trip_id"]: t.get("shape_id") or None for t in trips_rows
    }

    # Build shape -> route mapping (best-effort: pick first trip's route for each shape).
    shape_to_route: dict[str, str] = {}
    for t in trips_rows:
        sid = t.get("shape_id")
        if sid and sid not in shape_to_route:
            shape_to_route[sid] = t["route_id"]

    loaded_stop_ids: set[str] = set()
    loaded_route_ids: set[str] = set()

    with session_scope() as session:
        _wipe_agency(session, source.agency_id)

        session.add(Agency(
            id=source.agency_id,
            name=source.agency_name,
            kind=source.agency_kind,
        ))

        for r in routes_rows:
            short = r.get("route_short_name") or None
            long_ = r.get("route_long_name") or None
            session.add(Route(
                id=r["route_id"],
                agency_id=source.agency_id,
                short_name=short,
                long_name=long_,
                color=_infer_color(short, long_, r.get("route_color")),
                kind=_infer_route_kind(short, long_, source.default_route_kind),
            ))
            loaded_route_ids.add(r["route_id"])
            counts["routes"] += 1

        for s in stops_rows:
            try:
                lat = float(s["stop_lat"])
                lon = float(s["stop_lon"])
            except (KeyError, ValueError):
                continue
            session.add(Stop(
                id=s["stop_id"],
                agency_id=source.agency_id,
                name=s.get("stop_name") or s["stop_id"],
                code=s.get("stop_code") or None,
                lat=lat,
                lon=lon,
            ))
            loaded_stop_ids.add(s["stop_id"])
            counts["stops"] += 1

        session.flush()

        # Shapes — attribute to a route via shape_to_route mapping. Skip orphans.
        for sh in shapes_rows:
            shape_id = sh["shape_id"]
            route_id = shape_to_route.get(shape_id)
            if not route_id or route_id not in loaded_route_ids:
                continue
            try:
                seq = int(sh["shape_pt_sequence"])
                lat = float(sh["shape_pt_lat"])
                lon = float(sh["shape_pt_lon"])
            except (KeyError, ValueError):
                continue
            session.add(Shape(
                route_id=route_id, shape_id=shape_id, seq=seq, lat=lat, lon=lon,
            ))
            counts["shapes"] += 1

        # Stop times — skip orphans whose route or stop wasn't loaded.
        skipped_orphans = 0
        for st in stop_times_rows:
            trip_id = st["trip_id"]
            route_id = trip_to_route.get(trip_id)
            stop_id = st.get("stop_id")
            if not route_id or route_id not in loaded_route_ids:
                skipped_orphans += 1
                continue
            if not stop_id or stop_id not in loaded_stop_ids:
                skipped_orphans += 1
                continue
            try:
                arr_s = _parse_time_to_seconds(st["arrival_time"])
                dep_s = _parse_time_to_seconds(st["departure_time"])
                seq = int(st["stop_sequence"])
            except (KeyError, ValueError):
                continue
            session.add(ScheduledStopTime(
                route_id=route_id,
                trip_id=trip_id,
                stop_id=stop_id,
                arrival_s=arr_s,
                departure_s=dep_s,
                seq=seq,
                shape_id=trip_to_shape.get(trip_id),
            ))
            counts["stop_times"] += 1
        if skipped_orphans:
            log.warning("%s: skipped %d orphan stop_times rows", source.agency_id, skipped_orphans)

    log.info("Loaded %s: %s", source.agency_id, counts)
    return counts


def load_all(force_download: bool = False) -> dict[str, dict[str, int]]:
    return {
        "ktmb": load_source(KTMB_SOURCE, force_download=force_download),
        "prasarana_rail": load_source(PRASARANA_RAIL_SOURCE, force_download=force_download),
    }
