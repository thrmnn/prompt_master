"""Tests for LRUCache — eviction, access refresh, and content keys."""

from prompt_master.tui.cache import LRUCache


# ---------------------------------------------------------------------------
# Basic put / get
# ---------------------------------------------------------------------------


class TestPutAndGet:
    def test_store_and_retrieve(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", "v1")
        assert cache.get("k1") == "v1"

    def test_multiple_items(self):
        cache = LRUCache(max_size=10)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_overwrite_same_key(self):
        cache = LRUCache(max_size=10)
        cache.put("k", "old")
        cache.put("k", "new")
        assert cache.get("k") == "new"


# ---------------------------------------------------------------------------
# Missing key
# ---------------------------------------------------------------------------


class TestGetMissing:
    def test_returns_none_for_absent_key(self):
        cache = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_returns_none_after_eviction(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        assert cache.get("a") is None


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------


class TestLRUEviction:
    def test_oldest_evicted(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Cache is full — inserting a new item should evict "a" (oldest)
        cache.put("d", 4)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_max_size_one(self):
        cache = LRUCache(max_size=1)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_eviction_respects_order(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # evicts a
        cache.put("e", 5)  # evicts b
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") == 3


# ---------------------------------------------------------------------------
# Access refreshes recency
# ---------------------------------------------------------------------------


class TestAccessRefreshes:
    def test_get_makes_item_most_recent(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Access "a" to refresh it — it should now be most recent
        cache.get("a")
        # Insert two new items to evict the two oldest (b, c)
        cache.put("d", 4)  # evicts b (oldest unused)
        cache.put("e", 5)  # evicts c
        assert cache.get("a") == 1  # still present — was refreshed
        assert cache.get("b") is None
        assert cache.get("c") is None

    def test_put_refreshes_existing(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Update "a" — should refresh its position
        cache.put("a", 10)
        cache.put("d", 4)  # evicts b
        cache.put("e", 5)  # evicts c
        assert cache.get("a") == 10


# ---------------------------------------------------------------------------
# Content key generation
# ---------------------------------------------------------------------------


class TestContentKey:
    def test_same_content_same_key(self):
        cache = LRUCache(max_size=10)
        key1 = cache.content_key("Role", "You are an expert.")
        key2 = cache.content_key("Role", "You are an expert.")
        assert key1 == key2

    def test_different_content_different_key(self):
        cache = LRUCache(max_size=10)
        key1 = cache.content_key("Role", "You are an expert.")
        key2 = cache.content_key("Role", "You are a beginner.")
        assert key1 != key2

    def test_different_section_different_key(self):
        cache = LRUCache(max_size=10)
        key1 = cache.content_key("Role", "same content")
        key2 = cache.content_key("Task", "same content")
        assert key1 != key2

    def test_key_is_string(self):
        cache = LRUCache(max_size=10)
        key = cache.content_key("Role", "content")
        assert isinstance(key, str)
        assert len(key) > 0
