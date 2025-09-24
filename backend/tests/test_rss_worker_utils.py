from datetime import UTC, datetime, timezone

import pytest

from app.rss.ingestion_worker import RSSIngestionWorker
from app.db.models import RSSFeed, RSSFeedStatus
from app.db.client import mongo_client


class DummyProvider:
    async def embed_texts(self, texts):
        return {"minilm": [[float(i)] for i, _ in enumerate(texts, start=1)]}


class FakeCursor:
    def __init__(self, docs):
        self._iter = iter(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:  # pragma: no cover - normal termination
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.writes = []

    def find(self, query, projection):
        return FakeCursor(self.existing)

    async def bulk_write(self, operations, ordered=False):
        self.writes.append((operations, ordered))


def test_create_dedupe_hash_stable():
    worker = RSSIngestionWorker()
    hash1 = worker._create_dedupe_hash("https://example.com/feed", "Title", "https://example.com/item")
    hash2 = worker._create_dedupe_hash("https://example.com/feed", "Title", "https://example.com/item")
    assert hash1 == hash2


def test_create_dedupe_hash_sensitive_to_changes():
    worker = RSSIngestionWorker()
    hash1 = worker._create_dedupe_hash("https://example.com/feed", "Title", "https://example.com/item")
    hash2 = worker._create_dedupe_hash("https://example.com/feed", "Title2", "https://example.com/item")
    assert hash1 != hash2


def test_parse_published_handles_missing():
    worker = RSSIngestionWorker()
    assert worker._parse_published({}) is None


def test_parse_published_with_struct_time():
    worker = RSSIngestionWorker()
    entry = {"published_parsed": (2024, 12, 25, 10, 30, 0, 0, 0, 0)}
    result = worker._parse_published(entry)
    assert result is not None
    assert result.year == 2024
    assert result.tzinfo == timezone.utc


def test_extract_domain_lowercases():
    worker = RSSIngestionWorker()
    domain = worker._extract_domain("https://Sub.Example.com/path")
    assert domain == "sub.example.com"


@pytest.mark.asyncio
async def test_persist_items_embeds_and_bulk_inserts(monkeypatch):
    provider = DummyProvider()
    worker = RSSIngestionWorker(embedding_provider=provider)

    fake_collection = FakeCollection()

    class FakeDatabase:
        rss_items = fake_collection

    monkeypatch.setattr(mongo_client, "database", FakeDatabase())

    now = datetime.now(UTC)
    feed = RSSFeed(
        name="Feed",
        url="https://example.com/rss",
        categories=[],
        tags=[],
        poll_interval_minutes=10,
        next_poll_at=None,
        last_polled_at=None,
        status=RSSFeedStatus.ACTIVE,
        error_streak=0,
        health_score=1.0,
        last_error=None,
        created_at=now,
        updated_at=now,
    )

    items = [
        {
            "feed_id": feed.id,
            "feed_url": feed.url,
            "source_domain": "example.com",
            "title": "Item 1",
            "summary": "First",
            "link": "https://example.com/item1",
            "guid": "1",
            "published_at": now,
            "retrieved_at": now,
            "dedupe_hash": "hash1",
            "price_amount": None,
            "price_currency": None,
            "tags": [],
            "categories": [],
        },
        {
            "feed_id": feed.id,
            "feed_url": feed.url,
            "source_domain": "example.com",
            "title": "Item 2",
            "summary": None,
            "link": "https://example.com/item2",
            "guid": "2",
            "published_at": now,
            "retrieved_at": now,
            "dedupe_hash": "hash2",
            "price_amount": None,
            "price_currency": None,
            "tags": [],
            "categories": [],
        },
    ]

    await worker._persist_items(feed, items)

    assert fake_collection.writes, "Expected bulk_write to be called"
    operations, ordered = fake_collection.writes[0]
    assert ordered is False
    assert len(operations) == 2

    first_doc = operations[0]._doc["$setOnInsert"]
    assert "summary_vec_minilm_384" in first_doc
    second_doc = operations[1]._doc["$setOnInsert"]
    assert "summary_vec_minilm_384" in second_doc
