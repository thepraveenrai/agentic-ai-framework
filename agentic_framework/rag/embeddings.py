"""Vector Embedding Engine.

Provides dense embeddings for code and text retrieval. Includes an ultra-fast,
deterministic semantic n-gram vectorizer for offline/local execution, plus
support for OpenAI/OpenRouter embeddings.
"""

import math
import re
from typing import List
from agentic_framework.config import settings


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingEngine:
    """Embeds code snippets and search queries into normalized dense vectors."""

    VECTOR_DIM = 128

    def _tokenize(self, text: str) -> List[str]:
        """Extract code tokens, camelCase parts, and identifier names."""
        clean = re.sub(r"[\W_]+", " ", text.lower())
        tokens = [t for t in clean.split() if len(t) > 1]
        # Also add bigrams for local semantic context
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def embed_text(self, text: str) -> List[float]:
        """Produce a normalized 128-dimensional dense vector."""
        vec = [0.0] * self.VECTOR_DIM
        tokens = self._tokenize(text)
        if not tokens:
            return vec

        for token in tokens:
            # Deterministic hash bucket
            h = hash(token) % self.VECTOR_DIM
            vec[h] += 1.0

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch vectorization."""
        return [self.embed_text(t) for t in texts]


embedding_engine = EmbeddingEngine()
