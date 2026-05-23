"""
RSS + lightweight HTML scrapers for KL transit news.

Each scraper is fail-soft: network errors or layout changes log a warning and
return an empty list, never throwing into the scheduler. The aggregator
deduplicates by URL/hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

import feedparser
import httpx
from selectolax.parser import HTMLParser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import session_scope
from ..models import NewsItem
from .classifier import classify

log = logging.getLogger(__name__)

USER_AGENT = "KL-Transit-Tracker/0.1 (+local research)"

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=%22Rapid+KL%22+OR+%22MRT%22+OR+%22LRT%22+OR+%22KTM+Komuter%22+disruption"
    "&hl=en-MY&gl=MY&ceid=MY:en"
)
MYRAPID_URL = "https://myrapid.com.my/announcements/"
KTMB_URL = "https://www.ktmb.com.my/"
PRASARANA_URL = "https://www.prasarana.com.my/media-room/"


@dataclass
class NewsCandidate:
    source: str
    title: str
    url: str
    published_at: Optional[datetime]
    summary: Optional[str]


def _hash_item(c: NewsCandidate) -> str:
    h = hashlib.sha1()
    h.update(c.source.encode())
    h.update(b"|")
    h.update(c.url.encode())
    return h.hexdigest()


async def _fetch_html(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
    except Exception as e:
        log.warning("HTML fetch failed for %s: %s", url, e)
        return None


# -------------------- individual scrapers --------------------

async def scrape_google_news() -> list[NewsCandidate]:
    out: list[NewsCandidate] = []
    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = await client.get(GOOGLE_NEWS_RSS)
            r.raise_for_status()
            text = r.text
    except Exception as e:
        log.warning("Google News fetch failed: %s", e)
        return out

    parsed = feedparser.parse(text)
    for entry in parsed.entries[:50]:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        out.append(NewsCandidate(
            source="Google News",
            title=getattr(entry, "title", ""),
            url=getattr(entry, "link", ""),
            published_at=published,
            summary=getattr(entry, "summary", None),
        ))
    return out


async def _scrape_generic(url: str, source: str) -> list[NewsCandidate]:
    """Best-effort: find <a> tags with title-like text on a news page."""
    html = await _fetch_html(url)
    if not html:
        return []
    tree = HTMLParser(html)
    out: list[NewsCandidate] = []
    seen: set[str] = set()
    for a in tree.css("a"):
        href = a.attributes.get("href")
        text = (a.text(strip=True) or "").strip()
        if not href or not text or len(text) < 20:
            continue
        # Crude filter: must look like article content
        if any(skip in text.lower() for skip in ("login", "home", "about us", "contact")):
            continue
        # Resolve relative URLs
        if href.startswith("/"):
            href = url.split("/")[0] + "//" + url.split("/")[2] + href
        if not href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(NewsCandidate(
            source=source,
            title=text[:300],
            url=href,
            published_at=None,
            summary=None,
        ))
    return out[:30]


async def scrape_myrapid() -> list[NewsCandidate]:
    return await _scrape_generic(MYRAPID_URL, "MyRapid")


async def scrape_ktmb() -> list[NewsCandidate]:
    return await _scrape_generic(KTMB_URL, "KTMB")


async def scrape_prasarana() -> list[NewsCandidate]:
    return await _scrape_generic(PRASARANA_URL, "Prasarana")


SCRAPERS = [
    ("google_news", scrape_google_news),
    ("myrapid", scrape_myrapid),
    ("ktmb", scrape_ktmb),
    # Prasarana corporate site disabled: media-room URL 404s. Google News covers
    # Prasarana stories anyway. Re-enable once a valid landing page is known.
    # ("prasarana", scrape_prasarana),
]


# -------------------- orchestrator --------------------

async def scrape_all() -> dict:
    """Run all scrapers, classify, dedupe, insert new items."""
    counts = {"fetched": 0, "kept": 0, "inserted": 0, "skipped_irrelevant": 0}
    all_candidates: list[NewsCandidate] = []
    for name, fn in SCRAPERS:
        try:
            cands = await fn()
            log.debug("scraper %s: %d candidates", name, len(cands))
            all_candidates.extend(cands)
        except Exception as e:
            log.warning("scraper %s crashed: %s", name, e)

    counts["fetched"] = len(all_candidates)
    if not all_candidates:
        return counts

    # Tag + filter.
    kept: list[tuple[NewsCandidate, list[str]]] = []
    for c in all_candidates:
        tags = classify(c.title, c.summary)
        if "_not_relevant" in tags:
            counts["skipped_irrelevant"] += 1
            continue
        kept.append((c, tags))
    counts["kept"] = len(kept)

    with session_scope() as session:
        for c, tags in kept:
            h = _hash_item(c)
            existing = session.scalar(select(NewsItem).where(NewsItem.hash == h))
            if existing:
                continue
            try:
                session.add(NewsItem(
                    source=c.source,
                    title=c.title,
                    url=c.url,
                    published_at=c.published_at.replace(tzinfo=None) if c.published_at else None,
                    summary=c.summary,
                    tags_json=json.dumps(tags),
                    hash=h,
                ))
                session.flush()
                counts["inserted"] += 1
            except IntegrityError:
                session.rollback()

    if counts["inserted"]:
        log.info("news scrape: %s", counts)
    return counts


async def run_once() -> dict:
    """Scheduler entrypoint."""
    return await scrape_all()
