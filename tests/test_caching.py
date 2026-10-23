"""Unit Tests for Multi-tier Caching Engine."""

import pytest
from agentic_framework.core.caching import cache


def test_cache_exact_hash_and_retrieval():
    cache.clear()
    model = "deepseek/deepseek-v4-flash-0731"
    messages = [{"role": "user", "content": "Hello framework"}]
    tools = []
    temp = 0.0

    key = cache.compute_llm_key(model, messages, temp, tools)
    assert isinstance(key, str) and len(key) == 64

    # Miss
    assert cache.get_llm_response(key) is None

    # Set
    cache.set_llm_response(key, {"content": "Hello World", "tool_calls": []}, tokens=120)

    # Hit
    cached = cache.get_llm_response(key)
    assert cached is not None
    assert cached["content"] == "Hello World"

    # Stats
    stats = cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["tokens_saved"] >= 120
