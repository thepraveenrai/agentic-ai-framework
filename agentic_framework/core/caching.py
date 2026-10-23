"""Multi-Tier Caching System for LLM Invocations, AST Indexing, and Tools.

Reduces API cost, eliminates latency for repeated queries, and caches project
file structures across agent reasoning loops.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from agentic_framework.config import settings
from agentic_framework.observability.logger import logger


class FrameworkCache:
    """Intelligent cache supporting exact matching, TTL expiry, and stats."""

    _instance: Optional["FrameworkCache"] = None

    def __new__(cls) -> "FrameworkCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_cache()
        return cls._instance

    def _init_cache(self) -> None:
        self.enabled = settings.CACHE_ENABLED
        self.ttl = settings.CACHE_TTL_SECONDS
        self.cache_dir = Path(settings.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.llm_cache_file = self.cache_dir / "llm_cache.json"
        self.file_hash_cache_file = self.cache_dir / "file_hashes.json"

        # In-memory stores
        self._llm_store: Dict[str, Dict[str, Any]] = {}
        self._file_hashes: Dict[str, str] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "tokens_saved": 0,
            "cost_saved_usd": 0.0,
        }

        self._load_cache()

    def _load_cache(self) -> None:
        """Load persisted cache from disk."""
        if self.llm_cache_file.exists():
            try:
                with open(self.llm_cache_file, "r", encoding="utf-8") as f:
                    self._llm_store = json.load(f)
            except Exception:
                self._llm_store = {}

        if self.file_hash_cache_file.exists():
            try:
                with open(self.file_hash_cache_file, "r", encoding="utf-8") as f:
                    self._file_hashes = json.load(f)
            except Exception:
                self._file_hashes = {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            with open(self.llm_cache_file, "w", encoding="utf-8") as f:
                json.dump(self._llm_store, f, indent=2)
            with open(self.file_hash_cache_file, "w", encoding="utf-8") as f:
                json.dump(self._file_hashes, f, indent=2)
        except Exception:
            pass

    def compute_llm_key(
        self,
        model: str,
        messages: list,
        temperature: float,
        tools: Optional[list] = None,
    ) -> str:
        """Compute deterministic SHA-256 hash for LLM request parameters."""
        serialized = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "tools": tools or [],
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_llm_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached LLM response if valid and not expired."""
        if not self.enabled:
            return None

        entry = self._llm_store.get(cache_key)
        if not entry:
            self._stats["misses"] += 1
            return None

        # Check TTL
        created_at = entry.get("timestamp", 0)
        if (time.time() - created_at) > self.ttl:
            del self._llm_store[cache_key]
            self._stats["misses"] += 1
            return None

        # Cache Hit!
        self._stats["hits"] += 1
        saved_tokens = entry.get("tokens", 0)
        self._stats["tokens_saved"] += saved_tokens
        # Estimated cost saved ($0.20 per 1M tokens)
        self._stats["cost_saved_usd"] += round(saved_tokens * 0.0000002, 6)
        return entry.get("response")

    def set_llm_response(
        self, cache_key: str, response: Dict[str, Any], tokens: int = 0
    ) -> None:
        """Store LLM response into cache."""
        if not self.enabled:
            return

        self._llm_store[cache_key] = {
            "timestamp": time.time(),
            "response": response,
            "tokens": tokens,
        }
        self._save_cache()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        return self._file_hashes.get(file_path)

    def set_file_hash(self, file_path: str, file_hash: str) -> None:
        self._file_hashes[file_path] = file_hash
        self._save_cache()

    def is_file_modified(self, file_path: Path) -> bool:
        """Check if file on disk has changed since last hash computation."""
        if not file_path.exists():
            return True
        try:
            content = file_path.read_bytes()
            current_hash = hashlib.sha256(content).hexdigest()
            cached_hash = self.get_file_hash(str(file_path))
            if cached_hash != current_hash:
                self.set_file_hash(str(file_path), current_hash)
                return True
            return False
        except Exception:
            return True

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss and resource saving metrics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
        return {
            **self._stats,
            "total_queries": total,
            "hit_rate_pct": round(hit_rate, 2),
            "cached_entries": len(self._llm_store),
        }

    def clear(self) -> None:
        """Clear all in-memory and disk cache."""
        self._llm_store.clear()
        self._file_hashes.clear()
        if self.llm_cache_file.exists():
            self.llm_cache_file.unlink()
        if self.file_hash_cache_file.exists():
            self.file_hash_cache_file.unlink()
        logger.info("🧹 Cache cleared successfully")


cache = FrameworkCache()
