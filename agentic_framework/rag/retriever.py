"""Hybrid Code Retriever for Codebase RAG.

Combines exact lexical/symbol matching with dense vector semantics
to provide relevant code context to the AI agents.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from agentic_framework.config import settings
from agentic_framework.rag.indexer import CodebaseIndexer, CodeChunk
from agentic_framework.rag.vector_store import vector_store
from agentic_framework.observability.logger import logger


class CodeRetriever:
    """Retrieves relevant code snippets and symbols from target project."""

    def __init__(self, target_dir: Optional[Path] = None):
        self.target_dir = (target_dir or settings.get_target_path()).resolve()
        self.indexer = CodebaseIndexer(self.target_dir)

    def initialize_index(self, force_rebuild: bool = True) -> int:
        """Index codebase to keep RAG fresh with current target project files."""
        if not hasattr(self, "target_dir") or not self.target_dir:
            self.target_dir = settings.get_target_path().resolve()
        self.indexer = CodebaseIndexer(self.target_dir)
        chunks = self.indexer.index_codebase()
        vector_store.clear()
        vector_store.add_chunks(chunks)
        vector_store.save()
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Hybrid search combining symbol matching and vector similarity."""
        if not vector_store.chunks:
            self.initialize_index()

        results: List[Dict[str, Any]] = []
        q_lower = query.lower()
        q_tokens = set(q_lower.split())

        # Vector search
        vector_matches = vector_store.similarity_search(query, top_k=top_k * 2)

        # Lexical scoring
        for chunk, v_score in vector_matches:
            lexical_score = 0.0
            content_lower = chunk.content.lower()

            if chunk.symbol_name and chunk.symbol_name.lower() in q_lower:
                lexical_score += 0.5

            token_hits = sum(1 for t in q_tokens if t in content_lower)
            lexical_score += (token_hits / max(1, len(q_tokens))) * 0.5

            # Combined hybrid score (60% vector, 40% lexical)
            hybrid_score = (v_score * 0.6) + (lexical_score * 0.4)

            results.append({
                "chunk_id": chunk.chunk_id,
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "symbol_name": chunk.symbol_name,
                "symbol_type": chunk.symbol_type,
                "language": chunk.language,
                "content": chunk.content,
                "relevance_score": round(hybrid_score, 3),
            })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_k]

    def format_context_for_prompt(self, query: str, top_k: int = 4) -> str:
        """Format retrieved code chunks into clean markdown for LLM prompt injection."""
        matches = self.search(query, top_k=top_k)
        if not matches:
            return "No matching code context found in codebase."

        context_blocks = []
        for idx, m in enumerate(matches, 1):
            symbol_info = f" (Symbol: {m['symbol_name']})" if m["symbol_name"] else ""
            block = (
                f"### Context [{idx}] {m['file_path']}:{m['start_line']}-{m['end_line']}{symbol_info}\n"
                f"```{m['language']}\n"
                f"{m['content']}\n"
                f"```"
            )
            context_blocks.append(block)

        return "\n\n".join(context_blocks)


retriever = CodeRetriever()
