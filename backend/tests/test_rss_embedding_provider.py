import asyncio

from app.rss.embedding_provider import RSSEmbeddingProvider


async def _fake_minilm(self, texts):  # type: ignore[override]
    return [[float(len(text))] for text in texts]


def test_embed_texts_with_minilm_only(monkeypatch):
    provider = RSSEmbeddingProvider()

    monkeypatch.setattr(RSSEmbeddingProvider, "_embed_minilm", _fake_minilm, raising=False)

    async def _fake_openai(self, texts):  # type: ignore[override]
        return []

    monkeypatch.setattr(RSSEmbeddingProvider, "_embed_openai", _fake_openai, raising=False)

    vectors = asyncio.run(provider.embed_texts(["a", "bb"]))

    assert "minilm" in vectors
    assert vectors["minilm"] == [[1.0], [2.0]]
    assert "openai" not in vectors or not vectors["openai"]
