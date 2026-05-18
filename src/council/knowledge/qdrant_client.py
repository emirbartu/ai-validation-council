"""Async Qdrant client for the AI Validation Council.

Provides a thin wrapper around ``qdrant_client.AsyncQdrantClient`` with
lazy collection management for the ``shallow_data`` collection.
"""

from __future__ import annotations

import os

from qdrant_client import AsyncQdrantClient as _AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

__all__ = ["AsyncQdrantClient", "get_qdrant_client"]

DEFAULT_QDRANT_URL = "http://localhost:6333"
QDRANT_URL = os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL)

_client_instance: AsyncQdrantClient | None = None


class AsyncQdrantClient:
    """Thin async wrapper around Qdrant with lazy collection creation."""

    def __init__(self, url: str) -> None:
        self._client = _AsyncQdrantClient(url=url)
        self._collections_ensured: set[str] = set()

    async def ensure_collection(self, collection_name: str = "shallow_data") -> None:
        """Create the collection if it does not already exist.

        The collection is configured for ``all-MiniLM-L6-v2`` embeddings
        (384 dimensions, cosine distance).  Creation is idempotent and
        guarded by an in-memory set so that the existence check is only
        performed once per process lifetime.
        """
        if collection_name in self._collections_ensured:
            return

        exists = await self._client.collection_exists(collection_name=collection_name)
        if not exists:
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

        self._collections_ensured.add(collection_name)

    async def upsert_points(
        self,
        collection_name: str,
        points: list[PointStruct],
    ) -> None:
        """Batch upsert points into *collection_name*."""
        await self.ensure_collection(collection_name)
        await self._client.upsert(
            collection_name=collection_name,
            points=points,
        )

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 20,
    ) -> list[ScoredPoint]:
        """Perform semantic search in *collection_name*.

        Returns a list of scored points sorted by relevance.
        """
        await self.ensure_collection(collection_name)
        response = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        )
        return response.points


async def get_qdrant_client() -> AsyncQdrantClient:
    """Return the module-level singleton ``AsyncQdrantClient``."""
    global _client_instance  # noqa: PLW0603
    if _client_instance is None:
        _client_instance = AsyncQdrantClient(url=QDRANT_URL)
    return _client_instance
