"""Vector Store for Codebase RAG.

Stores code chunks with their embedding vectors and metadata, allowing fast
cosine similarity searches and symbol lookups.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from agentic_framework.rag.indexer import CodeChunk
from agentic_framework.rag.embeddings import embedding_engine, cosine_similarity
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class VectorStore:
    """In-memory and file-backed vector store for code retrieval."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (Path(settings.CACHE_DIR) / "rag_index.json")
        self.chunks: List[CodeChunk] = []
        self.vectors: List[List[float]] = []

    def clear(self) -> None:
        self.chunks.clear()
        self.vectors.clear()

    def add_chunks(self, chunks: List[CodeChunk]) -> None:
        """Add and vectorize code chunks."""
        if not chunks:
            return

        texts = [
            f"{c.file_path} {c.symbol_name or ''} {c.symbol_type or ''}\n{c.content}"
            for c in chunks
        ]
        new_vectors = embedding_engine.embed_batch(texts)
        self.chunks.extend(chunks)
        self.vectors.extend(new_vectors)

    def similarity_search(
        self, query: str, top_k: int = 5, file_filter: Optional[str] = None
    ) -> List[Tuple[CodeChunk, float]]:
        """Query vector store using cosine similarity."""
        if not self.chunks:
            return []

        q_vec = embedding_engine.embed_text(query)
        scored: List[Tuple[CodeChunk, float]] = []

        for chunk, vec in zip(self.chunks, self.vectors):
            if file_filter and file_filter not in chunk.file_path:
                continue

            score = cosine_similarity(q_vec, vec)
            scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def save(self) -> None:
        """Persist index to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "chunks": [c.__dict__ for c in self.chunks],
            "vectors": self.vectors,
        }
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to persist RAG index: {e}")

    def load(self) -> bool:
        """Load index from disk if present."""
        if not self.storage_path.exists():
            return False

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.chunks = [CodeChunk(**c) for c in data.get("chunks", [])]
            self.vectors = data.get("vectors", [])
            return True
        except Exception:
            return False


vector_store = VectorStore()
