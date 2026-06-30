"""MemPalace integration module for AI Validation Council.

Phase 1: In-memory dict backend with sentence-transformers semantic search.
Phase 4: Swap to real MemPalace MCP calls.
"""

from __future__ import annotations

import datetime
import json
import threading
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


class CouncilMemoryManager:
    """Orchestrates agent memory using the MemPalace palace metaphor.

    Wings  -> projects / agents
    Rooms  -> topics / analysis_ids
    Drawers-> verbatim text chunks

    Phase 1: In-memory dict backend (local wrapper).
    Phase 4: Replace with MemPalace MCP server calls.
    """

    AGENT_WINGS: dict[str, str] = {
        "market_analyst": "council_market_analyst",
        "devils_advocate": "council_devils_advocate",
    }

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        storage_path: str | None = None,
    ) -> None:
        self._model: SentenceTransformer = SentenceTransformer(model_name)
        self._embedding_dim: int = self._model.get_embedding_dimension()
        self._lock = threading.Lock()
        self._palace: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._diaries: dict[str, list[dict[str, Any]]] = {}
        self._storage_path: str | None = storage_path
        if storage_path:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Populate in-memory state from a JSON file if it exists.

        Embeddings are recomputed on demand; the persisted payload omits
        ``embedding`` vectors (they're deterministic for a given model).
        """
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        if not path.exists():
            return
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        with self._lock:
            self._palace = payload.get("palace", {})
            self._diaries = payload.get("diaries", {})

    def _persist_to_disk(self) -> None:
        """Snapshot ``palace`` + ``diaries`` to ``storage_path`` if set."""
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"palace": self._palace, "diaries": self._diaries}
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
            tmp.replace(path)
        except OSError:
            return

    def ensure_wings(self) -> None:
        # TODO Phase 4: Swap to MCP mempalace_list_wings + create missing wings
        with self._lock:
            for wing in self.AGENT_WINGS.values():
                self._palace.setdefault(wing, {})

    def _get_wing_for_agent(self, agent_name: str) -> str:
        key = agent_name.lower().replace(" ", "_")
        if key not in self.AGENT_WINGS:
            raise ValueError(f"Unknown agent: {agent_name}")
        return self.AGENT_WINGS[key]

    def store_agent_output(
        self,
        agent_name: str,
        analysis_id: str,
        output_dict: dict[str, Any],
    ) -> str:
        # TODO Phase 4: Swap to MCP mempalace_add_drawer(wing, room, content)
        wing = self._get_wing_for_agent(agent_name)
        content = json.dumps(output_dict, ensure_ascii=False, sort_keys=True)
        drawer_id = str(uuid.uuid4())
        embedding = self._encode(content)

        with self._lock:
            self._palace.setdefault(wing, {}).setdefault(analysis_id, [])
            self._palace[wing][analysis_id].append(
                {
                    "id": drawer_id,
                    "content": content,
                    "embedding": embedding,
                    "metadata": {
                        "agent_name": agent_name,
                        "analysis_id": analysis_id,
                        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    },
                }
            )

        self._persist_to_disk()
        return drawer_id

    def recall_past_analysis(
        self,
        agent_name: str,
        analysis_id: str | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search agent's wing for past analyses.

        If analysis_id is provided, returns drawers from that specific room.
        If not, performs semantic search across the entire wing.
        """
        # TODO Phase 4: Swap to MCP mempalace_search(query, wing, limit)
        wing = self._get_wing_for_agent(agent_name)

        with self._lock:
            rooms = self._palace.get(wing, {})

        if analysis_id is not None:
            drawers = rooms.get(analysis_id, [])
            return [
                {
                    "id": d["id"],
                    "content": json.loads(d["content"]),
                    "metadata": d["metadata"],
                }
                for d in drawers
            ]

        if query is None:
            return []

        query_emb = self._encode(query)
        candidates: list[tuple[float, dict[str, Any]]] = []

        for room_drawers in rooms.values():
            for drawer in room_drawers:
                score = self._cosine_similarity(query_emb, drawer["embedding"])
                candidates.append((score, drawer))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:limit]

        return [
            {
                "id": d["id"],
                "content": json.loads(d["content"]),
                "score": float(score),
                "metadata": d["metadata"],
            }
            for score, d in top
        ]

    def store_diary_entry(
        self,
        agent_name: str,
        entry_text: str,
        topic: str = "general",
    ) -> None:
        # TODO Phase 4: Swap to MCP mempalace_diary_write(agent_name, entry, topic)
        with self._lock:
            self._diaries.setdefault(agent_name, []).append(
                {
                    "entry": entry_text,
                    "topic": topic,
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                }
            )
        self._persist_to_disk()

    def read_recent_diary(
        self,
        agent_name: str,
        n_entries: int = 5,
    ) -> list[dict[str, Any]]:
        # TODO Phase 4: Swap to MCP mempalace_diary_read(agent_name, last_n)
        with self._lock:
            entries = self._diaries.get(agent_name, [])
            return entries[-n_entries:]

    def _encode(self, text: str) -> np.ndarray:
        emb = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return emb

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))
