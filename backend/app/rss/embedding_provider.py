"""Embedding utilities for RSS ingestion."""
from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any, Dict, List, Optional, Type

from app.config import settings

OpenAIEmbeddingsType = Optional[Type[Any]]
SentenceTransformerType = Optional[Type[Any]]


class RSSEmbeddingProvider:
    """Generates embeddings for RSS item summaries/titles."""

    def __init__(self) -> None:
        self._minilm_model = None
        self._openai_embeddings = None
        self._sentence_cls: SentenceTransformerType = None
        self._openai_cls: OpenAIEmbeddingsType = None

    async def embed_texts(self, texts: List[str]) -> Dict[str, List[List[float]]]:
        if not texts:
            return {"minilm": []}

        results: Dict[str, List[List[float]]] = {}
        minilm_vectors = await self._embed_minilm(texts)
        if minilm_vectors:
            results["minilm"] = minilm_vectors

        openai_vectors = await self._embed_openai(texts)
        if openai_vectors:
            results["openai"] = openai_vectors

        return results

    async def _embed_minilm(self, texts: List[str]) -> List[List[float]]:
        if settings.EMBEDDINGS_PROVIDER != "minilm":
            return []
        model = self._get_minilm_model()
        if model is None:
            return []
        # Run synchronously in thread to avoid blocking event loop
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            batch_size=settings.RSS_EMBED_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=False,
        )
        return [list(map(float, vector)) for vector in embeddings]

    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        if settings.OPENAI_API_KEY == "":
            return []
        if settings.EMBEDDINGS_PROVIDER != "openai":
            return []
        embeddings = self._get_openai_embeddings()
        if embeddings is None:
            return []
        vectors: List[List[float]] = []
        for text in texts:
            vector = await embeddings.aembed_query(text)
            vectors.append(list(map(float, vector)))
        return vectors

    def _get_minilm_model(self):  # type: ignore[override]
        if self._minilm_model is not None:
            return self._minilm_model

        if self._sentence_cls is None:
            try:
                module = import_module("sentence_transformers")
                self._sentence_cls = getattr(module, "SentenceTransformer")
            except (ImportError, AttributeError):
                return None

        self._minilm_model = self._sentence_cls("all-MiniLM-L6-v2")
        return self._minilm_model

    def _get_openai_embeddings(self):  # type: ignore[override]
        if self._openai_embeddings is not None:
            return self._openai_embeddings

        if self._openai_cls is None:
            try:
                module = import_module("langchain_openai")
                self._openai_cls = getattr(module, "OpenAIEmbeddings")
            except (ImportError, AttributeError):
                return None

        self._openai_embeddings = self._openai_cls(
            openai_api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small",
        )
        return self._openai_embeddings
