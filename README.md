# KL Transit Tracker

A live dashboard for Kuala Lumpur's rail network — MRT, LRT, Monorail, KTM
Komuter. Trains render as direction-aware dots over a pastel vector map,
stations as ringed markers. The backend polls every 20 seconds, detects
disruptions from movement, rolls up weekly reliability stats, and aggregates
news from public RSS sources.

Runs entirely on your own machine via Docker. **No API keys, no cloud
accounts, no recurring cost.**

## Features

- **Live map** with direction arrows derived from poll-to-poll movement
- **Stuck detection** — pulsing red halo on any vehicle motionless for three consecutive polls
- **Per-line trains-in-service panel** — collapsible, with terminus-by-terminus direction split
- **Disruption banner** — surfaces critical events (STUCK / MISSING / LINE_DOWN) in real time
- **Weekly reliability page** — per-route on-time %, mean delay, daily trend chart
- **Disruption news feed** — Google News + MyRapid + KTMB scrapers, auto-tagged by line + category
- **Pastel light theme** — easy on the eyes, station vs train clearly distinguishable

## Data sources

| Source | Use |
|---|---|
| [data.gov.my GTFS-realtime](https://developer.data.gov.my/realtime-api/gtfs-realtime) | Live KTMB vehicle positions (30s refresh upstream) |
| [data.gov.my GTFS-static](https://developer.data.gov.my/realtime-api/gtfs-static) | KTMB + Prasarana rail line geometry, stops, schedule |
| [OpenFreeMap](https://openfreemap.org/) | Free vector tiles, no API key |
| Google News RSS, myrapid.com.my, ktmb.com.my | Disruption news scraping |

**Note**: Prasarana's `rapid-rail-kl` (MRT/LRT/Monorail) doesn't yet have a stable
realtime feed on data.gov.my. Those trains are simulated from the static
schedule and tagged `scheduled` in the UI. A `RAPID_RAIL_LIVE` env flag flips
to live data the day Prasarana ships the feed.

## Quick start

### 1. Install Docker Desktop

Download from <https://www.docker.com/products/docker-desktop/>, install, and
launch it. Wait until the whale icon stops animating.

Verify in your terminal:

```bash
docker --version
docker compose version
```

### 2. Clone and run

```bash
git clone https://github.com/addmazing95/kl-transit-tracker.git
cd kl-transit-tracker
docker compose up --build
```

First build takes ~2–3 minutes (pulls base images, installs Python deps,
builds the React bundle, bootstraps GTFS static data). When you see both
of these in the logs you're ready:

```
klt-backend   | [entrypoint] bootstrap complete.
klt-backend   | INFO:     Uvicorn running on http://0.0.0.0:8000
klt-frontend  | nginx: worker process started
```

### 3. Open the dashboard

<http://localhost:5173>

### 4. (Optional) Seed demo data

The Reliability page needs ~7 days of trip data to look interesting; the
disruption banner needs at least one event. From a second terminal:

```bash
docker compose exec backend python /app/scripts/seed_demo.py --days 7
docker compose exec backend python /app/scripts/seed_demo.py --demo-disruption
```

Refresh the Reliability and Map tabs.

## Day-to-day commands

| Command | What it does |
|---|---|
| `docker compose up -d` | Start in the background (no terminal window kept open) |
| `docker compose down` | Stop containers, keep your data |
| `docker compose down -v && rm -rf ./data` | Stop and wipe everything for a fresh start |
| `docker compose ps` | Show container status + health |
| `docker compose logs -f backend` | Tail backend logs |
| `docker compose restart backend` | Bounce just the backend |
| `docker compose exec backend sh` | Shell into the backend container |
| `git pull && docker compose up -d --build` | Pull updates from GitHub and rebuild |

## Persistence

Everything writable lives in `./data/`:

- `transit.db` — SQLite with routes, stops, observations, news items
- `gtfs_cache/` — downloaded GTFS zip files

That folder is bind-mounted into the container, so `docker compose down`
preserves your history. To start completely clean, delete it.

## API

The backend exposes a small REST + WebSocket surface at `http://localhost:8000`:

| Endpoint | Returns |
|---|---|
| `GET /health` | liveness check |
| `GET /lines` | catalog: routes + shapes + stops (cached) |
| `GET /lines/stats` | live count of trains per route, split by direction |
| `GET /vehicles` | latest in-memory snapshot (filter via `?route_id=` / `?agency_id=`) |
| `WS /ws/positions` | push of full vehicle snapshot every poll cycle |
| `GET /disruptions` | active + recent (24h) disruption events |
| `GET /reliability/weekly` | per-route on-time stats (`?days=N`) |
| `GET /news` | tagged news items (`?days=N&tag=...&limit=N`) |

## Configuration

All knobs are environment variables, set in `docker-compose.yml` under
`services.backend.environment`:

| Var | Default | Meaning |
|---|---|---|
| `POLL_INTERVAL_SECONDS` | `20` | Cadence for KTMB poll + simulator tick |
| `NEWS_SCRAPE_INTERVAL_MINUTES` | `15` | News scraper cadence |
| `RAPID_RAIL_LIVE` | `false` | Flip to `true` when Prasarana ships realtime rail |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING |
| `TIMEZONE` | `Asia/Kuala_Lumpur` | Used by the simulator + daily rollup |

Edit the file, then `docker compose up -d` to apply.

## Project structure

```
kl-transit-tracker/
├─ backend/                FastAPI app
│  └─ app/
│     ├─ main.py, config.py, db.py, models.py, scheduler.py
│     ├─ gtfs/             static loader + GTFS-rt protobuf client
│     ├─ ingestion/        live polling, simulator, disruption detector
│     ├─ reliability/      arrival observer + daily rollup
│     ├─ news/             RSS + HTML scrapers + classifier
│     └─ api/              FastAPI routers
├─ frontend/               Vite + React + TypeScript + MapLibre
│  └─ src/
│     ├─ pages/            MapView, Reliability, News
│     ├─ components/Map/   LineLayer, VehicleDots, VehicleDrawer, Legend, TrainsPanel
│     └─ hooks/, api/
├─ scripts/                bootstrap_static.py, seed_demo.py
├─ docker/                 entrypoint.sh, nginx.conf, docker-specific README
├─ Dockerfile.backend
├─ Dockerfile.frontend
└─ docker-compose.yml
```

## Tech stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, SQLite (WAL), APScheduler,
  httpx, `gtfs-realtime-bindings`, `feedparser`, `selectolax`
- **Frontend**: Vite + React 18 + TypeScript, MapLibre GL JS + react-map-gl,
  TanStack Query, Tailwind CSS, Recharts
- **Tiles**: [OpenFreeMap](https://openfreemap.org/) (positron style)
- **Runtime**: Docker + nginx (frontend) + uvicorn (backend)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `port already allocated` | something else on 8000 or 5173 | kill the other process, or edit the port mapping in `docker-compose.yml` |
| `entrypoint.sh: no such file` | Git converted line endings on Windows | `git checkout -- docker/entrypoint.sh` then `docker compose up --build` |
| Map empty, "0 veh" | KL is in the 00:00–06:00 service dead zone | wait until ~06:00 local, or inject a fake train: `docker compose exec backend python /app/scripts/seed_demo.py --stuck TEST_001` |
| Backend can't reach data.gov.my | corporate firewall / VPN | test `curl https://api.data.gov.my/gtfs-realtime/vehicle-position/ktmb` from your host |
| Reliability page empty | no observations yet | run the seed-demo command above |

## Limitations

- KTMB's GTFS-RT feed doesn't include `route_id`, only `trip_id` — live trains
  currently render in neutral color until a trip→route mapping is added.
- Prasarana's static GTFS ships only canonical trips per direction; the
  simulator cycles them at typical headways (MRT 6 min, LRT 4 min, Monorail
  10 min) to approximate reality.
- Real-world reliability rollups will be sparse until KTMB exposes `route_id`;
  seeded demo data fills the gap meanwhile.

## License

MIT — see [LICENSE](LICENSE). All data and software used is free / open source.
