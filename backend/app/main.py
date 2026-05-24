from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("kl-transit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("Database ready at %s", settings.database_url)
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="KL Transit Tracker", version="0.1.0", lifespan=lifespan)

# CORS: configurable via env so remote hosts (Codespaces, PWD, a cloud VM)
# can serve the bundle from one domain while calling the backend on another.
#   CORS_ORIGINS=*                            → allow any origin (self-hosted, no auth)
#   CORS_ORIGINS=https://foo.com,https://bar  → comma-separated allowlist
#   (unset)                                   → localhost dev defaults
_cors_env = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_env == "*":
    _cors_origins: list[str] = ["*"]
elif _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _cors_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


from .api import lines as lines_router  # noqa: E402
from .api import lines_stats as lines_stats_router  # noqa: E402
from .api import vehicles as vehicles_router  # noqa: E402
from .api import ws_positions as ws_positions_router  # noqa: E402
from .api import disruptions as disruptions_router  # noqa: E402
from .api import reliability as reliability_router  # noqa: E402
from .api import news as news_router  # noqa: E402

app.include_router(lines_router.router)
app.include_router(lines_stats_router.router)
app.include_router(vehicles_router.router)
app.include_router(ws_positions_router.router)
app.include_router(disruptions_router.router)
app.include_router(reliability_router.router)
app.include_router(news_router.router)

# Future routers (later milestones):
# from .api import reliability, news
# app.include_router(reliability.router)
# app.include_router(news.router)
