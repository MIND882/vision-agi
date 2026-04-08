# memory/episodic.py
# ============================================================
# EPISODIC MEMORY — past experiences via ChromaDB.
# "What happened last time I got a similar query?"
#
# Uses cosine similarity to find relevant past sessions.
# Runs locally — no server needed (CHROMA_MODE=local).
# ============================================================

import json
import uuid
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import cfg


def _get_client() -> chromadb.ClientAPI:
    """Get ChromaDB client — local persistent mode for Phase 1."""
    if cfg.CHROMA_MODE == "http":
        return chromadb.HttpClient(
            host=cfg.CHROMA_HOST,
            port=cfg.CHROMA_PORT,
        )
    else:
        return chromadb.PersistentClient(
            path=cfg.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )


class EpisodicMemory:
    """
    Stores and retrieves past reasoning sessions.
    Each entry = one complete query-answer experience.
    """

    COLLECTION_NAME = "reasoning_episodes"

    def __init__(self):
        self.client     = _get_client()
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},   # cosine similarity search
        )

    def store(
        self,
        session_id:   str,
        raw_input:    str,
        synthesis:    str,
        what_worked:  str,
        what_failed:  str,
        score:        float,
        problem_type: str = "",
    ) -> None:
        """
        Store one reasoning episode.
        The raw_input becomes the searchable document.
        Metadata holds everything else.
        """
        try:
            self.collection.add(
                ids=[session_id],
                documents=[raw_input],      # this gets embedded for search
                metadatas=[{
                    "session_id":   session_id,
                    "synthesis":    synthesis[:500],    # truncate for storage
                    "what_worked":  what_worked[:200],
                    "what_failed":  what_failed[:200],
                    "score":        score,
                    "problem_type": problem_type,
                    "created_at":   datetime.now().isoformat(),
                }],
            )
            print(f"  [EPISODIC] Stored episode: '{raw_input[:50]}' (score={score:.2f})")
        except Exception as e:
            print(f"  [EPISODIC] Store failed: {e}")

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Find past episodes similar to the current query.
        Returns list of Memory dicts compatible with ReasoningState.
        """
        try:
            count = self.collection.count()
            if count == 0:
                return []

            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, count),
            )

            memories = []
            for i, doc in enumerate(results["documents"][0]):
                meta      = results["metadatas"][0][i]
                distance  = results["distances"][0][i]
                relevance = max(0.0, 1.0 - distance)   # cosine: 0=identical

                # Only return if relevance is meaningful
                if relevance < 0.3:
                    continue

                memories.append({
                    "memory_id": meta.get("session_id", str(uuid.uuid4())),
                    "source":    "episodic",
                    "content": (
                        f"Past query: {doc}\n"
                        f"Approach that worked: {meta.get('what_worked', '')}\n"
                        f"Quality score: {meta.get('score', 0):.2f}"
                    ),
                    "relevance":  round(relevance, 3),
                    "created_at": meta.get("created_at", ""),
                })

            return memories

        except Exception as e:
            print(f"  [EPISODIC] Search failed: {e}")
            return []

    def count(self) -> int:
        """Total episodes stored."""
        try:
            return self.collection.count()
        except Exception:
            return 0