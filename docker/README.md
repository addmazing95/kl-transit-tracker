# Docker version

A containerised version of KL Transit Tracker that runs the **same code** as
the local build, but in two long-running containers — one for FastAPI, one for
the React bundle served via nginx.

The original local-venv workflow described in the root `README.md` still works
unchanged. Pick whichever fits your moment.

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

The `./data` folder is shared with the local-venv build, so switching between
"local" and "Docker" preserves your database.

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

## Differences vs the local-venv build

| | Local (venv) | Docker |
|---|---|---|
| Backend host | 127.0.0.1 | 0.0.0.0 (inside container) |
| Frontend serving | Vite dev (HMR) | Static bundle via nginx |
| DB path | `./data/transit.db` (cwd-relative) | `/data/transit.db` (absolute, via volume) |
| Bootstrap | `python scripts/bootstrap_static.py` once | Auto on first boot |
| Restart policy | manual | `unless-stopped` |

No source code differs between the two modes — Docker only adds 4 files:
`Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, plus
`docker/{nginx.conf, entrypoint.sh}`.

## CORS

The backend already allows `http://localhost:5173`, which is why the Docker
frontend port is mapped to `5173:80`. If you change the host port, also extend
the CORS list in `backend/app/main.py` (or wire it to an env var).
