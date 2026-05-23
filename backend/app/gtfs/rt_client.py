"""
Thin GTFS-realtime client. Fetches a feed URL via httpx and parses the protobuf
into plain Python dataclasses so callers never touch protobuf directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from google.transit import gtfs_realtime_pb2

log = logging.getLogger(__name__)


@dataclass
class VehiclePositionSample:
    vehicle_id: str
    route_id: Optional[str]
    trip_id: Optional[str]
    lat: float
    lon: float
    bearing: Optional[float]
    speed: Optional[float]
    ts: datetime
    current_stop_sequence: Optional[int]
    current_status: Optional[str]


def parse_feed(buf: bytes) -> list[VehiclePositionSample]:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(buf)

    samples: list[VehiclePositionSample] = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        if not v.HasField("position"):
            continue
        pos = v.position
        ts = (
            datetime.fromtimestamp(v.timestamp, tz=timezone.utc)
            if v.timestamp
            else datetime.now(tz=timezone.utc)
        )
        samples.append(VehiclePositionSample(
            vehicle_id=v.vehicle.id or entity.id,
            route_id=v.trip.route_id or None,
            trip_id=v.trip.trip_id or None,
            lat=pos.latitude,
            lon=pos.longitude,
            bearing=pos.bearing if pos.HasField("bearing") else None,
            speed=pos.speed if pos.HasField("speed") else None,
            ts=ts,
            current_stop_sequence=v.current_stop_sequence if v.HasField("current_stop_sequence") else None,
            current_status=gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name(v.current_status)
            if v.HasField("current_status") else None,
        ))
    return samples


async def fetch_feed(url: str, timeout: float = 30.0) -> list[VehiclePositionSample]:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return parse_feed(r.content)
