"""Tag a news item with high-level categories via keyword matching."""

from __future__ import annotations

import re

KEYWORD_TAGS: list[tuple[str, list[str]]] = [
    ("disruption", [
        "disruption", "disrupted", "delay", "delayed", "service halt", "suspended",
        "breakdown", "incident", "stranded", "evacuated", "fault", "interrupted",
        "tergendala", "gangguan",
    ]),
    ("maintenance", [
        "maintenance", "upgrade", "track work", "scheduled work", "closure",
        "shut down", "shutdown", "naik taraf", "penyelenggaraan",
    ]),
    ("safety", [
        "fire", "smoke", "evacuation", "injury", "accident", "collision",
        "security", "police",
    ]),
    ("operations", [
        "new service", "extended hours", "frequency", "free ride", "free travel",
        "tambang", "service update", "schedule change",
    ]),
]

LINE_TAGS: list[tuple[str, list[str]]] = [
    ("mrt-kajang", ["kajang line", "kgl", "sungai buloh-kajang"]),
    ("mrt-putrajaya", ["putrajaya line", "pyl", "sungai buloh-putrajaya"]),
    ("lrt-kelana-jaya", ["kelana jaya", "kjl"]),
    ("lrt-ampang", ["ampang line", "agl"]),
    ("lrt-sri-petaling", ["sri petaling", "spl"]),
    ("monorail", ["monorail", "monorel", "mrl"]),
    ("ktm", ["ktm", "komuter", "ets", "intercity"]),
    ("brt", ["brt", "bus rapid transit"]),
]


def _matches(text: str, needles: list[str]) -> bool:
    t = text.lower()
    return any(n in t for n in needles)


def classify(title: str, summary: str | None = None) -> list[str]:
    text = f"{title} {summary or ''}"
    tags: list[str] = []
    for tag, needles in KEYWORD_TAGS:
        if _matches(text, needles):
            tags.append(tag)
    for tag, needles in LINE_TAGS:
        if _matches(text, needles):
            tags.append(tag)
    # Filter to only KL-relevant items: must mention a line OR be a rail keyword.
    rail_keywords = ["mrt", "lrt", "rail", "train", "komuter", "ets", "monorail",
                     "rapid kl", "myrapid", "prasarana", "ktmb"]
    if not any(t.startswith(("mrt-", "lrt-", "ktm", "monorail", "brt")) for t in tags):
        if not _matches(text, rail_keywords):
            tags.append("_not_relevant")
    return tags
