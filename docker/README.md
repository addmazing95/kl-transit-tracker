# Docker reference

Detailed reference for the Docker deployment. For the quick-start, see the
[root README](../README.md).

The stack is two long-running containers:

- `backend` — FastAPI + APScheduler + scrapers, on port 8000
- `frontend` — nginx serving the built React bundle, on port 5173 (mapped to nginx :80 internally)

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2). That's it.

## Run

From the repo root:

```bash
docker compose up --build
```

First run takes ~2 min (downloading base images, installing deps, building the
frontend bundle). Subsequent runs use the cached layers.

Open <http://localhost:5173>.

To stop:

```bash
docker compose down            # stop containers, keep data
docker compose down -v         # stop and discard local data volume
```

## What lives where

| Concern | In the container | On your host |
|---|---|---|
| SQLite DB | `/data/transit.db` | `./data/transit.db` (bind-mounted) |
| GTFS zip cache | `/data/gtfs_cache/` | `./data/gtfs_cache/` |
| Logs | container stdout | `docker compose logs -f backend` |
| Config | env vars in `docker-compose.yml` | edit compose file & `up` again |

Persisting via bind-mount means `docker compose down` keeps your data;
`docker compose down -v && rm -rf ./data` wipes everything for a fresh start.

## First boot

The backend entrypoint (`docker/entrypoint.sh`) detects an empty `routes`
table and runs the GTFS static bootstrap automatically. You don't need to run
`scripts/bootstrap_static.py` separately.

To seed demo reliability/disruption data (otherwise those pages are empty
until enough live data accumulates):

```bash
docker compose exec backend python /app/scripts/seed_demo.py --days 7
docker compose exec backend python /app/scripts/seed_demo.py --demo-disruption
```

## Operations

```bash
docker compose logs -f backend       # tail backend log
docker compose logs -f frontend      # tail nginx access log
docker compose ps                    # health + status
docker compose restart backend       # bounce just the backend
docker compose exec backend sh       # shell into the backend
```

## Configuration

All knobs are env vars. Edit `docker-compose.yml` under `services.backend.environment`:

- `POLL_INTERVAL_SECONDS` — how often to poll KTMB GTFS-rt and tick the simulator
- `NEWS_SCRAPE_INTERVAL_MINUTES` — news scraper cadence
- `RAPID_RAIL_LIVE` — flip to `true` the day Prasarana ships realtime rail
- `LOG_LEVEL` — DEBUG / INFO / WARNING

To point the frontend at a backend on a different host (e.g. deploying
backend and frontend separately):

```bash
docker build -f Dockerfile.frontend \
  --build-arg VITE_API_BASE=https://api.example.com \
  --build-arg VITE_WS_BASE=wss://api.example.com \
  -t kl-transit-tracker-frontend:custom .
```

These values are baked into the bundle at build time.

## CORS

The backend allows `http://localhost:5173`, which is why the frontend port is
mapped to `5173:80`. If you change the host port, also extend the CORS
allowlist in `backend/app/main.py` (or wire it to an env var).

## Rebuilding after code changes

After `git pull` or local edits:

```bash
docker compose up -d --build
```

Backend code changes trigger a re-install of the Python package layer.
Frontend code changes trigger a fresh `npm install + build`. Both layers are
cached when only `docker-compose.yml` or `docker/*` files change.
