"""Async RSS ingestion worker."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import feedparser
import logging

from bson import ObjectId
from pymongo import UpdateOne

from app.config import settings
from app.db.client import mongo_client
from app.db.models import RSSFeed, RSSFeedStatus
from app.rss.embedding_provider import RSSEmbeddingProvider
from app.rss.feed_service import list_feeds

logger = logging.getLogger(__name__)


class RSSIngestionWorker:
    """Background worker that polls RSS feeds and stores normalized items."""

    def __init__(
        self,
        poll_interval_seconds: int = 60,
        embedding_provider: Optional[RSSEmbeddingProvider] = None,
    ):
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._embedding_provider = embedding_provider or RSSEmbeddingProvider()
        self._feeds_processed_total = 0
        self._items_ingested_total = 0
        self._embeddings_generated_total = 0

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "rss_worker_started",
            extra={
                "poll_interval_seconds": self.poll_interval_seconds,
                "max_concurrent_fetches": settings.RSS_MAX_CONCURRENT_FETCHES,
            },
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info(
            "rss_worker_stopped",
            extra={
                "feeds_processed_total": self._feeds_processed_total,
                "items_ingested_total": self._items_ingested_total,
                "embeddings_generated_total": self._embeddings_generated_total,
            },
        )

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._poll_once()
            await asyncio.wait(
                [asyncio.create_task(self._stop_event.wait())],
                timeout=self.poll_interval_seconds,
            )

    async def _poll_once(self) -> None:
        now = datetime.now(timezone.utc)
        feeds = await list_feeds(limit=100)
        due_feeds = [feed for feed in feeds if self._is_feed_due(feed, now)]
        if not due_feeds:
            logger.debug("rss_poll_skipped", extra={"reason": "no_due_feeds"})
            return

        semaphore = asyncio.Semaphore(settings.RSS_MAX_CONCURRENT_FETCHES)
        logger.info(
            "rss_poll_started",
            extra={
                "feeds_due": len(due_feeds),
                "timestamp": now.isoformat(),
            },
        )
        tasks = [self._process_feed(feed, semaphore) for feed in due_feeds]
        await asyncio.gather(*tasks, return_exceptions=True)

    def _is_feed_due(self, feed: RSSFeed, now: datetime) -> bool:
        if feed.status != RSSFeedStatus.ACTIVE:
            return False
        if feed.next_poll_at is None:
            return True
        # Ensure both datetimes have timezone info for comparison
        next_poll = feed.next_poll_at
        if next_poll.tzinfo is None:
            next_poll = next_poll.replace(tzinfo=timezone.utc)
        return next_poll <= now

    async def _process_feed(self, feed: RSSFeed, semaphore: asyncio.Semaphore) -> None:
        if self._session is None:
            return
        async with semaphore:
            try:
                response = await self._fetch_feed(feed)
                if response is None:
                    await self._schedule_next_poll(feed, success=False)
                    logger.debug(
                        "rss_feed_not_modified",
                        extra={"feed_url": feed.url},
                    )
                    return
                items = await self._parse_feed(feed, response)
                if items:
                    await self._persist_items(feed, items)
                await self._schedule_next_poll(feed, success=True)
                self._feeds_processed_total += 1
                logger.info(
                    "rss_feed_processed",
                    extra={
                        "feed_url": feed.url,
                        "items_parsed": len(items),
                        "feeds_processed_total": self._feeds_processed_total,
                    },
                )
            except Exception as exc:  # pylint: disable=broad-except
                await self._schedule_next_poll(feed, success=False, error=str(exc))
                logger.error(
                    "rss_feed_error",
                    extra={"feed_url": feed.url, "error": str(exc)},
                )

    async def _fetch_feed(self, feed: RSSFeed) -> Optional[Dict[str, Any]]:
        headers = {}
        if feed.etag:
            headers["If-None-Match"] = feed.etag
        if feed.last_modified:
            headers["If-Modified-Since"] = feed.last_modified
        assert self._session is not None
        async with self._session.get(feed.url, headers=headers) as resp:
            if resp.status == 304:
                return None
            resp.raise_for_status()
            text = await resp.text()
            parsed = feedparser.parse(text)
            return {
                "entries": parsed.entries,
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }

    async def _parse_feed(self, feed: RSSFeed, resource: Dict[str, Any]) -> List[Dict[str, Any]]:
        entries = resource.get("entries", [])
        normalized = []
        now = datetime.now(timezone.utc)
        for entry in entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue
            published = self._parse_published(entry)
            summary = entry.get("summary") or entry.get("description")
            dedupe_hash = self._create_dedupe_hash(feed.url, title, link)
            normalized.append(
                {
                    "feed_id": feed.id,
                    "feed_url": feed.url,
                    "source_domain": self._extract_domain(link),
                    "title": title.strip(),
                    "summary": summary.strip() if summary else None,
                    "link": link,
                    "guid": entry.get("id") or entry.get("guid"),
                    "published_at": published,
                    "retrieved_at": now,
                    "dedupe_hash": dedupe_hash,
                    "price_amount": self._extract_price(entry),
                    "price_currency": self._extract_currency(entry),
                    "tags": feed.tags,
                    "categories": feed.categories,
                }
            )
        return normalized

    async def _persist_items(self, feed: RSSFeed, items: List[Dict[str, Any]]) -> None:
        if not items:
            logger.debug("rss_persist_skipped", extra={"reason": "empty_items", "feed_url": feed.url})
            return

        collection = mongo_client.database.rss_items
        dedupe_hashes = [item["dedupe_hash"] for item in items]

        existing_hashes: set[str] = set()
        cursor = collection.find({"dedupe_hash": {"$in": dedupe_hashes}}, {"dedupe_hash": 1})
        async for doc in cursor:
            existing_hashes.add(doc["dedupe_hash"])

        new_items = [item for item in items if item["dedupe_hash"] not in existing_hashes]
        if not new_items:
            logger.info(
                "rss_persist_skipped",
                extra={"reason": "duplicates", "feed_url": feed.url},
            )
            return

        texts = [item.get("summary") or item["title"] for item in new_items]
        embeddings = await self._embedding_provider.embed_texts(texts)
        minilm_vectors = embeddings.get("minilm", [])
        openai_vectors = embeddings.get("openai", [])

        self._embeddings_generated_total += len(minilm_vectors) + len(openai_vectors)

        for idx, item in enumerate(new_items):
            if idx < len(minilm_vectors):
                item["summary_vec_minilm_384"] = minilm_vectors[idx]
            if idx < len(openai_vectors):
                item["summary_vec_openai_1536"] = openai_vectors[idx]

        operations = [
            UpdateOne(
                {"dedupe_hash": item["dedupe_hash"]},
                {"$setOnInsert": item},
                upsert=True,
            )
            for item in new_items
        ]

        if operations:
            await collection.bulk_write(operations, ordered=False)
            self._items_ingested_total += len(operations)
            logger.info(
                "rss_items_persisted",
                extra={
                    "feed_url": feed.url,
                    "items_inserted": len(operations),
                    "items_ingested_total": self._items_ingested_total,
                    "embeddings_generated_total": self._embeddings_generated_total,
                },
            )

    async def _schedule_next_poll(self, feed: RSSFeed, *, success: bool, error: Optional[str] = None) -> None:
        interval = feed.poll_interval_minutes or settings.RSS_DEFAULT_POLL_MINUTES
        next_poll = datetime.now(timezone.utc) + timedelta(minutes=interval)
        update = {}
        if success:
            update["error_streak"] = 0
            update["health_score"] = min(1.0, (feed.health_score or 1.0) + 0.1)
            update["last_error"] = None
        else:
            update["error_streak"] = (feed.error_streak or 0) + 1
            update["health_score"] = max(0.0, (feed.health_score or 1.0) - 0.2)
            update["last_error"] = error
        update["next_poll_at"] = next_poll
        update["last_polled_at"] = datetime.now(timezone.utc)
        if success:
            update["status"] = RSSFeedStatus.ACTIVE.value
        elif update["error_streak"] >= 5:
            update["status"] = RSSFeedStatus.ERROR.value

        await mongo_client.database.rss_feeds.update_one(
            {"_id": ObjectId(feed.id)},
            {"$set": update},
        )

    @staticmethod
    def _parse_published(entry: Dict[str, Any]) -> Optional[datetime]:
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published_parsed:
            return None
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    @staticmethod
    def _create_dedupe_hash(feed_url: str, title: str, link: str) -> str:
        key = f"{feed_url}|{title.strip().lower()}|{link.strip().lower()}"
        import hashlib

        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_domain(link: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(link)
        return parsed.netloc.lower()

    @staticmethod
    def _extract_price(entry: Dict[str, Any]) -> Optional[float]:
        price = entry.get("price")
        try:
            return float(price) if price is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_currency(entry: Dict[str, Any]) -> Optional[str]:
        currency = entry.get("pricecurrency") or entry.get("currency")
        if currency and isinstance(currency, str):
            return currency.upper()
        return None


_worker: Optional[RSSIngestionWorker] = None


async def start_worker() -> None:
    global _worker  # noqa: PLW0603
    print(f"start_worker called: ENABLE_RSS_INGESTION={settings.ENABLE_RSS_INGESTION}")
    if not settings.ENABLE_RSS_INGESTION:
        print("RSS ingestion disabled, not starting worker")
        return
    print("Creating RSS worker...")
    if _worker is None:
        _worker = RSSIngestionWorker()
    print("Starting RSS worker...")
    await _worker.start()
    print("RSS worker started successfully")


async def stop_worker() -> None:
    global _worker  # noqa: PLW0603
    if _worker is None:
        return
    await _worker.stop()
    _worker = None
