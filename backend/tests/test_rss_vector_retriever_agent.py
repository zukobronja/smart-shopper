import pytest
from datetime import UTC, datetime

from app.agents.state import create_initial_state, SearchQuery
from app.agents.rss_vector_retriever_agent import RSSVectorRetrieverAgent
from app.db.client import mongo_client


class DummyEmbeddingProvider:
    async def embed_texts(self, texts):
        return {"minilm": [[0.1, 0.2, 0.3]]}


class EmptyEmbeddingProvider:
    async def embed_texts(self, texts):
        return {}


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_pipeline = None

    async def aggregate(self, pipeline):
        self.last_pipeline = pipeline
        return FakeCursor(self.docs)


class FakeDatabase:
    def __init__(self, docs):
        self.rss_items = FakeCollection(docs)


@pytest.mark.asyncio
async def test_rss_vector_retriever_returns_results(monkeypatch):
    provider = DummyEmbeddingProvider()
    now = datetime.now(UTC)
    docs = [
        {
            "title": "Deal 1",
            "summary": "Great price",
            "link": "https://example.com/deal1",
            "source_domain": "example.com",
            "feed_url": "https://example.com/rss",
            "feed_id": "abc123",
            "published_at": now,
            "price_amount": 999.0,
            "price_currency": "USD",
            "tags": ["laptop"],
            "categories": ["electronics"],
            "_score": 0.87,
        }
    ]
    fake_db = FakeDatabase(docs)
    monkeypatch.setattr(mongo_client, "database", fake_db)

    agent = RSSVectorRetrieverAgent(max_results=5, freshness_days=30, embedding_provider=provider)

    state = create_initial_state("gaming laptop")
    state["search_query"] = SearchQuery(raw_query="gaming laptop", normalized_query="gaming laptop")

    new_state = await agent.process(state)

    assert new_state["rss_results"], "Expected RSS results"
    result = new_state["rss_results"][0]
    assert result["title"] == "Deal 1"
    assert result["price"]["amount"] == 999.0
    assert fake_db.rss_items.last_pipeline is not None
    vector_stage = fake_db.rss_items.last_pipeline[0]["$vectorSearch"]
    assert vector_stage["limit"] == 5
    assert isinstance(vector_stage["queryVector"], list)
    assert new_state["agent_steps"][-1].status == "success"


@pytest.mark.asyncio
async def test_rss_vector_retriever_skips_without_embeddings(monkeypatch):
    provider = EmptyEmbeddingProvider()
    fake_db = FakeDatabase([])
    monkeypatch.setattr(mongo_client, "database", fake_db)

    agent = RSSVectorRetrieverAgent(max_results=5, embedding_provider=provider)

    state = create_initial_state("gaming laptop")
    new_state = await agent.process(state)

    assert new_state["rss_results"] == []
    assert new_state["agent_steps"][-1].status == "skipped"
