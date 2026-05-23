"""
One-shot script: download GTFS static feeds for KTMB and Prasarana rail,
parse them, and populate the local SQLite database.

Usage (from repo root, with venv active):
    python scripts/bootstrap_static.py
    python scripts/bootstrap_static.py --force   # ignore on-disk cache
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running this file directly without installing the backend package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Base, engine  # noqa: E402
from app.gtfs.static_loader import load_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap KL Transit Tracker static data.")
    parser.add_argument("--force", action="store_true", help="Re-download even if cache exists.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Ensure tables exist.
    Base.metadata.create_all(bind=engine)

    counts = load_all(force_download=args.force)
    print("\n=== Bootstrap summary ===")
    for agency, c in counts.items():
        print(f"  {agency}: {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
