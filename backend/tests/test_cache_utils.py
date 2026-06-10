"""Tests for Redis cache utility functions with graceful degradation."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.utils.cache import (
    cache_get,
    cache_set,
    cache_delete,
    cache_delete_pattern,
    cache_push_list,
    cache_get_list,
    cached,
)


class TestCacheGet:
    def test_get_returns_none_when_redis_unavailable(self):
        assert cache_get("test:key") is None

    def test_get_returns_none_on_exception(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.get.side_effect = Exception("Connection refused")
            mock_get.return_value = mock_redis
            assert cache_get("test:key") is None

    def test_get_returns_parsed_json(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.get.return_value = json.dumps({"a": 1})
            mock_get.return_value = mock_redis
            assert cache_get("test:key") == {"a": 1}

    def test_get_returns_none_on_miss(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.get.return_value = None
            mock_get.return_value = mock_redis
            assert cache_get("test:key") is None


class TestCacheSet:
    def test_set_returns_false_when_redis_unavailable(self):
        assert cache_set("test:key", {"data": 1}) is False

    def test_set_calls_setex(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_get.return_value = mock_redis
            result = cache_set("test:key", {"data": 1}, ttl=300)
            assert result is True
            mock_redis.setex.assert_called_once_with(
                "test:key", 300, json.dumps({"data": 1}, ensure_ascii=False, default=str)
            )

    def test_set_returns_false_on_exception(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.setex.side_effect = Exception("OOM")
            mock_get.return_value = mock_redis
            assert cache_set("test:key", "x") is False

    def test_set_handles_non_serializable(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_get.return_value = mock_redis
            result = cache_set("test:key", {"d": "string"}, ttl=60)
            assert result is True
            mock_redis.setex.assert_called_once()


class TestCacheDelete:
    def test_delete_returns_false_when_redis_unavailable(self):
        assert cache_delete("test:key") is False

    def test_delete_calls_delete(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_get.return_value = mock_redis
            assert cache_delete("test:key") is True
            mock_redis.delete.assert_called_once_with("test:key")


class TestCacheDeletePattern:
    def test_delete_pattern_returns_false_when_redis_unavailable(self):
        assert cache_delete_pattern("dashboard:*") is False

    def test_delete_pattern_with_matching_keys(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.keys.return_value = ["dashboard:overview", "dashboard:trend:30"]
            mock_get.return_value = mock_redis
            assert cache_delete_pattern("dashboard:*") is True
            mock_redis.keys.assert_called_once_with("dashboard:*")
            mock_redis.delete.assert_called_once_with("dashboard:overview", "dashboard:trend:30")

    def test_delete_pattern_no_matching_keys(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.keys.return_value = []
            mock_get.return_value = mock_redis
            assert cache_delete_pattern("dashboard:*") is True
            mock_redis.delete.assert_not_called()


class TestCacheList:
    def test_push_list_returns_false_when_redis_unavailable(self):
        assert cache_push_list("test:list", {"x": 1}) is False

    def test_push_list_calls_lpush_and_ltrim(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_get.return_value = mock_redis
            assert cache_push_list("test:list", {"x": 1}, max_len=100) is True
            mock_redis.lpush.assert_called_once()
            mock_redis.ltrim.assert_called_once_with("test:list", 0, 99)

    def test_get_list_returns_empty_when_redis_unavailable(self):
        assert cache_get_list("test:list") == []

    def test_get_list_parses_items(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.lrange.return_value = [json.dumps({"a": 1}), json.dumps({"b": 2})]
            mock_get.return_value = mock_redis
            result = cache_get_list("test:list", 0, 5)
            assert result == [{"a": 1}, {"b": 2}]


class TestCachedDecorator:
    def test_decorator_caches_result(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_redis.get.return_value = None  # miss on first call
            mock_get.return_value = mock_redis

            call_count = 0

            @cached(ttl=60)
            def compute(x: int):
                nonlocal call_count
                call_count += 1
                return x * 2

            # First call: miss, executes function
            result1 = compute(5)
            assert result1 == 10
            assert call_count == 1

            # Verify setex was called to cache the result
            mock_redis.setex.assert_called_once()

    def test_decorator_returns_cached_value(self):
        with patch("app.utils.cache.get_redis") as mock_get:
            mock_redis = MagicMock()
            mock_get.return_value = mock_redis

            @cached(ttl=60)
            def compute(x: int):
                return x * 2

            # Set up cached value for the key
            # compute:5
            def get_side_effect(key):
                if key == "compute:5":
                    return json.dumps(20)
                return None

            mock_redis.get.side_effect = get_side_effect

            result = compute(5)
            assert result == 20
            # setex should NOT be called since we returned cached
            assert mock_redis.setex.call_count == 0

    def test_decorator_bypasses_cache_when_redis_unavailable(self):
        # When get_redis returns None, the decorator should just call the function
        call_count = 0

        @cached(ttl=60)
        def compute(x: int):
            nonlocal call_count
            call_count += 1
            return x * 2

        result = compute(3)
        assert result == 6
        assert call_count == 1
