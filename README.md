# KL Transit Tracker

Locally-run live dashboard for Kuala Lumpur public transport — rail-first.
Vehicles render as dots over a Greater KL map, with line overlays from GTFS
static shapes. Refreshes every 60 seconds. Detects disruptions by analysing
poll-over-poll movement. Reports weekly reliability stats. Aggregates news
from RSS + lightweight HTML scrapers.

## Data sources

- **[data.gov.my GTFS-RT](https://developer.data.gov.my/realtime-api/gtfs-realtime)**
  - **KTMB**: live vehicle positions every 30 s (we poll at 60 s)
  - **Prasarana rapid-rail-kl** (MRT/LRT/Monorail): static GTFS only — no
    realtime feed yet. We simulate dots from the static schedule and tag them
    `scheduled`. The `RAPID_RAIL_LIVE` flag in `.env` flips to real feed
    when Prasarana ships it.
- News: Google News RSS + MyRapid + KTMB HTML scrapers (15 min cadence).

All free. No paid APIs.

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2 + SQLite (WAL),
  APScheduler, httpx, `gtfs-realtime-bindings`, `feedparser`, `selectolax`
- **Frontend**: Vite + React 18 + TypeScript, Leaflet + react-leaflet,
  TanStack Query, Tailwind, Recharts

## Setup (one-time)

From `C:\Users\User\KL Transit Tracker` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .\backend
npm install --prefix .\frontend
Copy-Item .env.example .env   # optional, defaults work

# Download static GTFS for KTMB + Prasarana rail
.\.venv\Scripts\python.exe scripts\bootstrap_static.py

# Seed 7 days of demo reliability data so the Reliability page is populated
.\.venv\Scripts\python.exe scripts\seed_demo.py --days 7
```

## Run

Two terminals — or use the launcher:

```powershell
.\scripts\dev.ps1
```

This opens two PowerShell windows: backend on **127.0.0.1:8000**, frontend on
**127.0.0.1:5173**. Closing either window stops that side. Nothing runs in the
background.

Manual equivalent:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

# Terminal 2
npm run dev --prefix .\frontend
```

Then open <http://127.0.0.1:5173>.

## Features

### Map (`/`)
- All KL rail lines drawn from GTFS shapes (MRT/LRT) and stop sequences (KTMB)
- **Live KTMB dots** — green badge, updated via WebSocket every 60 s
- **Simulated MRT/LRT/Monorail dots** — grey "scheduled" badge, animated along
  the static schedule with realistic per-kind headways (MRT 6 min, LRT 4 min,
  Monorail 10 min). ~160 simulated trains visible at midday.
- Click a dot → side drawer with vehicle/trip details, speed, bearing
- Legend toggles route kinds (MRT, LRT, Monorail, KTM, BRT)
- Live status pill (top-right) — connection state + vehicle count + last update
- Disruption banner (top-center) when any `crit` event is active

### Reliability (`/reliability`)
- Last 7 days of per-route on-time %
- Daily trend line chart
- Per-route table: on-time %, mean delay, observed vs scheduled trips
- Filterable by route kind

### News (`/news`)
- Aggregated from Google News, MyRapid, KTMB
- Auto-tagged: `disruption`, `maintenance`, `safety`, `operations` +
  per-line tags (`lrt-kelana-jaya`, `mrt-kajang`, etc.)
- Filter by tag or source
- Polls every 15 min

## Testing the disruption banner

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --demo-disruption
# Banner should appear within 30 seconds of opening the Map page.
```

To test STUCK detection against the live KTMB feed:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --stuck KTM_TEST_001
# After the next disruption sweep (~60s), the banner shows STUCK for KTM_TEST_001.
```

## API

| Endpoint                    | Purpose |
|-----------------------------|---------|
| `GET /health`               | Liveness check |
| `GET /lines`                | Catalog: routes + shapes + stops (cached in-process) |
| `GET /vehicles`             | Latest in-memory snapshot (filter by `route_id`, `agency_id`) |
| `WS /ws/positions`          | Push of full vehicle snapshot on every poll |
| `GET /disruptions`          | Active events + recent (24h) |
| `GET /reliability/weekly`   | Per-route on-time stats (`?days=N`) |
| `GET /news`                 | Tagged news items (`?days=N&tag=...&limit=N`) |

## Project layout

```
KL Transit Tracker/
├─ backend/
│  └─ app/
│     ├─ main.py, config.py, db.py, models.py, scheduler.py
│     ├─ gtfs/static_loader.py, gtfs/rt_client.py
│     ├─ ingestion/{ktmb.py, rapid_rail_sim.py, disruption.py, state.py}
│     ├─ reliability/{observer.py, rollup.py}
│     ├─ news/{scrapers.py, classifier.py}
│     └─ api/{lines.py, vehicles.py, ws_positions.py,
│             disruptions.py, reliability.py, news.py}
├─ frontend/
│  └─ src/
│     ├─ pages/{MapView, Reliability, News}.tsx
│     ├─ components/Map/{LineLayer, VehicleDots, VehicleDrawer, Legend}.tsx
│     ├─ components/DisruptionBanner.tsx
│     ├─ hooks/usePositionsWS.ts
│     └─ api/{client.ts, hooks.ts}
├─ data/         SQLite DB + GTFS zip cache (gitignored)
├─ scripts/      bootstrap_static.py, seed_demo.py, dev.ps1
└─ README.md
```

## Costs

**Zero.** All data and software is free. Runs entirely on your laptop, only
when you launch it. Nothing in the background, no daemons, no cloud bills.

## Limitations

- KTMB GTFS-RT doesn't include `route_id`, only `trip_id` — live trains
  currently render in neutral color until a trip→route mapping is added.
- Prasarana static GTFS ships only canonical trips, not full timetables — the
  simulator cycles canonical trips at typical headways to approximate reality.
- The reliability observer needs `route_id` on live polls to work; with seeded
  demo data the page is fully functional, real-world rollups will sparse until
  data.gov.my fixes route_id on KTMB feeds.
