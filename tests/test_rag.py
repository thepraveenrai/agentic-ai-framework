"""Unit Tests for Codebase RAG and AST Retrieval."""

from pathlib import Path
import pytest
from agentic_framework.rag.indexer import CodebaseIndexer
from agentic_framework.rag.embeddings import embedding_engine, cosine_similarity
from agentic_framework.rag.vector_store import VectorStore
from agentic_framework.rag.retriever import CodeRetriever


def test_embedding_and_cosine_similarity():
    v1 = embedding_engine.embed_text("def calculate_discount(price, discount)")
    v2 = embedding_engine.embed_text("def calculate_discount_price(p, d)")
    v3 = embedding_engine.embed_text("database connection pool initialization")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert len(v1) == 128
    assert sim_related > sim_unrelated


def test_codebase_indexing_and_symbol_extraction():
    demo_dir = Path(__file__).parent.parent / "demo_target_project"
    if not demo_dir.exists():
        demo_dir = Path(__file__).parent.parent / "examples" / "demo_target_project"
    indexer = CodebaseIndexer(demo_dir)
    chunks = indexer.index_codebase()

    assert len(chunks) > 0
    symbols = [c.symbol_name for c in chunks if c.symbol_name]
    assert "calculate_discount" in symbols or "calculate_bulk_price" in symbols


def test_hybrid_code_retriever():
    demo_dir = Path(__file__).parent.parent / "demo_target_project"
    if not demo_dir.exists():
        demo_dir = Path(__file__).parent.parent / "examples" / "demo_target_project"
    retriever = CodeRetriever(demo_dir)
    retriever.initialize_index(force_rebuild=True)

    results = retriever.search("calculate_bulk_price quantity zero", top_k=2)
    assert len(results) > 0
    assert "calculator.py" in results[0]["file_path"]
