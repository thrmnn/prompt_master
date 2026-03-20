"""LRU caching layer for variations and recommendations.

Thread-safe, simple LRU cache keyed by content hashes. Used by the
intelligence layer to avoid redundant API calls when the user revisits
a section whose content hasn't changed.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """Simple, thread-safe LRU cache for variations and recommendations.

    Items are evicted in least-recently-used order when ``max_size`` is exceeded.
    All public methods are safe to call from multiple threads.

    Usage::

        cache = LRUCache(max_size=50)
        key = cache.content_key("Role", "You are an expert ...")
        cache.put(key, some_variations)
        result = cache.get(key)  # moves key to most-recently-used
    """

    def __init__(self, max_size: int = 50) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries to retain.
        """
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key, or ``None`` if not present.

        Accessing a key moves it to the most-recently-used position.

        Args:
            key: Cache key (typically from ``content_key()``).

        Returns:
            The cached value, or None if not found.
        """
        with self._lock:
            if key not in self._store:
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            return self._store[key]

    def put(self, key: str, value: Any) -> None:
        """Insert or update a cache entry.

        If the cache exceeds ``max_size``, the least-recently-used entry
        is evicted.

        Args:
            key: Cache key.
            value: Value to store.
        """
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
            else:
                self._store[key] = value
                if len(self._store) > self._max_size:
                    self._store.popitem(last=False)

    def content_key(self, section_name: str, content: str) -> str:
        """Generate a deterministic cache key from section name + content hash.

        Uses SHA-256 truncated to 16 hex chars for a compact but collision-resistant
        key.

        Args:
            section_name: The prompt section name (e.g. "Role").
            content: The raw text content of that section.

        Returns:
            A string key like ``"Role:a1b2c3d4e5f67890"``.
        """
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return f"{section_name}:{digest}"

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        """Return the number of items currently in the cache."""
        with self._lock:
            return len(self._store)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists without affecting LRU ordering."""
        with self._lock:
            return key in self._store
