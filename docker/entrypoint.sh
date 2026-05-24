#!/bin/sh
# Backend entrypoint:
#   1. Make sure /data exists and is writable.
#   2. If the routes table is empty (first boot), download GTFS static.
#   3. Hand off to whatever CMD was passed (uvicorn by default).
set -e

mkdir -p /data /data/gtfs_cache

python - <<'PY'
import sys
sys.path.insert(0, "/app/backend")
from sqlalchemy import select
from app.db import Base, engine, SessionLocal
from app.models import Route

Base.metadata.create_all(bind=engine)

with SessionLocal() as s:
    has_routes = s.scalar(select(Route).limit(1)) is not None

if not has_routes:
    print("[entrypoint] routes table empty — bootstrapping GTFS static…", flush=True)
    from app.gtfs.static_loader import load_all
    load_all()
    print("[entrypoint] bootstrap complete.", flush=True)
else:
    print("[entrypoint] routes already loaded; skipping bootstrap.", flush=True)
PY

exec "$@"
