"""Embedding pipeline for the AI Validation Council.

Chunks collected text, generates sentence embeddings with
``sentence-transformers``, and upserts them into Qdrant.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer

from council.knowledge.qdrant_client import get_qdrant_client

if TYPE_CHECKING:
    from council.models.data import CollectedData, HNStory, RedditPost

__all__ = ["EmbeddingPipeline"]


class EmbeddingPipeline:
    """Async pipeline for chunking, embedding, and upserting collected data."""

    _model: SentenceTransformer | None = None

    def __init__(self, collection_name: str = "shallow_data") -> None:
        self.collection_name = collection_name

    def _ensure_model(self) -> SentenceTransformer:
        """Lazy-load the embedding model on first use."""
        if self._model is None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    @staticmethod
    def chunk_text(text: str, max_chars: int = 500, overlap: int = 50) -> list[dict]:
        """Split *text* into overlapping chunks.

        Each chunk is a dict with ``text``, ``index``, ``char_start``, and
        ``char_end`` keys.  The overlap ensures semantic context is not lost
        at chunk boundaries.
        """
        if not text or max_chars <= 0:
            return []

        chunks: list[dict] = []
        start = 0
        index = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + max_chars, text_len)
            chunks.append(
                {
                    "text": text[start:end],
                    "index": index,
                    "char_start": start,
                    "char_end": end,
                }
            )

            next_start = start + max_chars - overlap
            if next_start <= start:
                break
            start = next_start
            index += 1

        return chunks

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode *texts* into normalized 384-dimensional vectors.

        Returns one float list per input string, suitable for cosine
        similarity search in Qdrant.
        """
        model = self._ensure_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [emb.tolist() for emb in embeddings]

    def prepare_points_from_posts(
        self,
        posts: list[RedditPost] | list[HNStory],
        source_type: str,
    ) -> list[PointStruct]:
        """Chunk, embed, and package *posts* as Qdrant PointStruct objects."""
        all_chunks_meta: list[tuple[dict, RedditPost | HNStory]] = []

        for post in posts:
            post_text = post.text or post.title
            chunks = self.chunk_text(post_text)
            for chunk in chunks:
                all_chunks_meta.append((chunk, post))

        if not all_chunks_meta:
            return []

        texts = [chunk["text"] for chunk, _ in all_chunks_meta]
        embeddings = self.embed_texts(texts)

        points: list[PointStruct] = []
        for (chunk, post), vector in zip(all_chunks_meta, embeddings, strict=True):
            post_id = str(post.id)
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{source_type}:{post_id}:{chunk['index']}",
                )
            )

            if source_type == "reddit":
                payload = {
                    "source": source_type,
                    "title": post.title,
                    "text": chunk["text"],
                    "url": post.url,
                    "score": post.score,
                    "subreddit": post.subreddit,
                    "timestamp": post.created_utc,
                }
            else:
                payload = {
                    "source": source_type,
                    "title": post.title,
                    "text": chunk["text"],
                    "url": post.url,
                    "score": post.score,
                    "by": post.by,
                    "timestamp": post.time,
                }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        return points

    async def ingest_collected_data(self, collected_data: CollectedData) -> dict:
        """Ingest all posts from *collected_data* into Qdrant.

        Returns a summary dict with counts per source and total points
        upserted.
        """
        reddit_points = self.prepare_points_from_posts(
            collected_data.reddit_posts,
            "reddit",
        )
        hn_points = self.prepare_points_from_posts(
            collected_data.hn_stories,
            "hn",
        )

        client = await get_qdrant_client()

        if reddit_points:
            await client.upsert_points(self.collection_name, reddit_points)
        if hn_points:
            await client.upsert_points(self.collection_name, hn_points)

        return {
            "reddit": len(reddit_points),
            "hn": len(hn_points),
            "total": len(reddit_points) + len(hn_points),
        }
