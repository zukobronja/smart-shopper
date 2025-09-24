#!/usr/bin/env python3
"""Seed initial RSS feeds for SmartShopper."""
import asyncio
from pathlib import Path
import sys
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"

backend_path_str = str(BACKEND_PATH)
if backend_path_str not in sys.path:
    sys.path.insert(0, backend_path_str)

from app.config import settings
from app.db.client import connect_to_mongo, close_mongo_connection
from app.db.models import RSSFeedCreate
from app.rss import feed_service

FEEDS: List[RSSFeedCreate] = [
    RSSFeedCreate(
        name="TechCrunch Deals",
        url="https://techcrunch.com/tag/deals/feed/",
        categories=["technology", "electronics"],
        tags=["tech", "startups", "gadgets"],
        poll_interval_minutes=30,
    ),
    RSSFeedCreate(
        name="The Verge Deals",
        url="https://www.theverge.com/deals/rss/index.xml",
        categories=["technology", "electronics"],
        tags=["tech", "deals", "consumer"],
        poll_interval_minutes=20,
    ),
    RSSFeedCreate(
        name="Engadget Deals",
        url="https://www.engadget.com/tag/deals/rss.xml",
        categories=["technology", "electronics"],
        tags=["gadgets", "deals"],
        poll_interval_minutes=20,
    ),
    RSSFeedCreate(
        name="Slickdeals Frontpage",
        url="https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&rss=1",
        categories=["deals", "consumer"],
        tags=["deals", "discount", "flash"],
        poll_interval_minutes=15,
    ),
    RSSFeedCreate(
        name="HotUKDeals",
        url="https://www.hotukdeals.com/rss",
        categories=["deals", "consumer"],
        tags=["uk", "deals"],
        poll_interval_minutes=20,
    ),
    RSSFeedCreate(
        name="PCPartPicker News",
        url="https://pcpartpicker.com/feed/",
        categories=["pc", "components"],
        tags=["pc", "hardware", "builds"],
        poll_interval_minutes=60,
    ),
    RSSFeedCreate(
        name="Wirecutter Deals",
        url="https://www.nytimes.com/wirecutter/rss/deals.xml",
        categories=["consumer", "reviews"],
        tags=["wirecutter", "deals"],
        poll_interval_minutes=30,
    ),
    RSSFeedCreate(
        name="Amazon Gold Box",
        url="https://rss.anandtech.com/tag/amazon-gold-box",
        categories=["ecommerce", "consumer"],
        tags=["amazon", "deals"],
        poll_interval_minutes=30,
    ),
]


async def seed_feeds() -> None:
    await connect_to_mongo()
    existing = await feed_service.list_feeds(limit=500)
    existing_urls = {feed.url for feed in existing}

    created, skipped = 0, 0
    for feed in FEEDS:
        if feed.url in existing_urls:
            skipped += 1
            continue
        try:
            await feed_service.create_feed(feed)
            created += 1
            print(f"Created feed: {feed.name} ({feed.url})")
        except ValueError as exc:
            print(f"Skipped {feed.url}: {exc}")
            skipped += 1

    await close_mongo_connection()

    print()
    print(f"RSS feed seeding complete. Created: {created}, skipped: {skipped}.")
    print("You can verify with GET /v1/rss/feeds or checking the rss_feeds collection.")


def main() -> None:
    print("Starting RSS feed seeding...")
    print(f"Environment: {settings.ENVIRONMENT}")
    asyncio.run(seed_feeds())


if __name__ == "__main__":
    main()
