from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    DateTime,
    Date,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # ktmb | prasarana_rail | prasarana_bus
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # rail | bus

    routes: Mapped[list["Route"]] = relationship(back_populates="agency")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    short_name: Mapped[Optional[str]] = mapped_column(String)
    long_name: Mapped[Optional[str]] = mapped_column(String)
    color: Mapped[Optional[str]] = mapped_column(String)  # hex without '#'
    kind: Mapped[str] = mapped_column(String, nullable=False)  # mrt|lrt|monorail|ktm|ets|bus

    agency: Mapped[Agency] = relationship(back_populates="routes")


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)


class Shape(Base):
    __tablename__ = "shapes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    shape_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_shapes_route_seq", "route_id", "shape_id", "seq"),
    )


class ScheduledStopTime(Base):
    __tablename__ = "scheduled_stop_times"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    trip_id: Mapped[str] = mapped_column(String, index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    arrival_s: Mapped[int] = mapped_column(Integer, nullable=False)  # seconds since midnight
    departure_s: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    shape_id: Mapped[Optional[str]] = mapped_column(String, index=True)

    __table_args__ = (
        Index("ix_sst_trip_seq", "trip_id", "seq"),
    )


class VehiclePosition(Base):
    __tablename__ = "vehicle_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    route_id: Mapped[Optional[str]] = mapped_column(ForeignKey("routes.id"), index=True)
    trip_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    vehicle_id: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    bearing: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String, nullable=False, default="live")  # live | scheduled

    __table_args__ = (
        Index("ix_vp_route_ts", "route_id", "ts"),
        Index("ix_vp_vehicle_ts", "vehicle_id", "ts"),
    )


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    route_id: Mapped[Optional[str]] = mapped_column(ForeignKey("routes.id"), index=True)
    stop_id: Mapped[Optional[str]] = mapped_column(ForeignKey("stops.id"))
    vehicle_id: Mapped[Optional[str]] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, nullable=False)  # info|warn|crit
    reason: Mapped[str] = mapped_column(String, nullable=False)  # STUCK|MISSING|LINE_DOWN|NEWS
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)


class TripObservation(Base):
    __tablename__ = "trip_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    trip_id: Mapped[str] = mapped_column(String, index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"))
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observed_arrival: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("trip_id", "stop_id", "service_date", name="uq_trip_stop_date"),
    )


class ReliabilityDaily(Base):
    __tablename__ = "reliability_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    on_time_pct: Mapped[float] = mapped_column(Float, nullable=False)
    mean_delay_s: Mapped[float] = mapped_column(Float, nullable=False)
    trips_observed: Mapped[int] = mapped_column(Integer, nullable=False)
    trips_scheduled: Mapped[int] = mapped_column(Integer, nullable=False)
    cancellations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("service_date", "route_id", name="uq_rel_date_route"),
    )


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    tags_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of tags
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
