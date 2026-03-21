# -*- coding: utf-8 -*-
"""
Cache utilities for detection results.

This module provides:
- Image hashing (SHA256)
- Cache key generation
- Cache operations with error handling
- Cache statistics
"""
import hashlib
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def calculate_image_hash(image_data: bytes) -> str:
    """
    Calculate SHA256 hash of image data.

    Args:
        image_data: Raw image bytes

    Returns:
        str: Hexadecimal SHA256 hash
    """
    try:
        sha256_hash = hashlib.sha256()
        sha256_hash.update(image_data)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error("Error calculating image hash: %s", e)
        raise


def get_prediction_cache_key(image_hash: str, fruit_type: str) -> str:
    """
    Generate cache key for prediction results.

    Format: prediction:{image_hash}:{fruit_type}

    Args:
        image_hash: SHA256 hash of image
        fruit_type: Type of fruit (mandalina, elma, etc.)

    Returns:
        str: Cache key
    """
    cache_key_format = getattr(
        settings, "PREDICTION_CACHE_KEY_FORMAT", "prediction:{image_hash}:{fruit_type}"
    )
    return cache_key_format.format(image_hash=image_hash, fruit_type=fruit_type)


def get_cached_prediction(image_hash: str, fruit_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached prediction result.

    Args:
        image_hash: SHA256 hash of image
        fruit_type: Type of fruit

    Returns:
        dict or None: Cached prediction data or None if not found
    """
    try:
        cache_key = get_prediction_cache_key(image_hash, fruit_type)
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.info("Cache HIT: %s", cache_key)
            return cached_result
        else:
            logger.info("Cache MISS: %s", cache_key)
            return None

    except Exception as e:
        logger.warning("Cache retrieval error (Redis unavailable?): %s", e)
        return None


def set_cached_prediction(
    image_hash: str,
    fruit_type: str,
    prediction_data: Dict[str, Any],
    timeout: Optional[int] = None,
) -> bool:
    """
    Cache prediction result.

    Args:
        image_hash: SHA256 hash of image
        fruit_type: Type of fruit
        prediction_data: Prediction results to cache
        timeout: Cache timeout in seconds (default: 24 hours)

    Returns:
        bool: True if successfully cached, False otherwise
    """
    try:
        cache_key = get_prediction_cache_key(image_hash, fruit_type)

        if timeout is None:
            timeout = getattr(settings, "PREDICTION_CACHE_TIMEOUT", 86400)

        cache.set(cache_key, prediction_data, timeout)
        logger.info("Cache SET: %s (timeout=%ss)", cache_key, timeout)
        return True

    except Exception as e:
        logger.warning("Cache set error (Redis unavailable?): %s", e)
        return False


def invalidate_prediction_cache(image_hash: str, fruit_type: str) -> bool:
    """
    Invalidate (delete) a cached prediction.

    Args:
        image_hash: SHA256 hash of image
        fruit_type: Type of fruit

    Returns:
        bool: True if successfully invalidated, False otherwise
    """
    try:
        cache_key = get_prediction_cache_key(image_hash, fruit_type)
        cache.delete(cache_key)
        logger.info("Cache INVALIDATED: %s", cache_key)
        return True

    except Exception as e:
        logger.warning("Cache invalidation error: %s", e)
        return False


def invalidate_all_predictions(fruit_type: Optional[str] = None) -> int:
    """
    Invalidate all cached predictions, optionally filtered by fruit type.

    Args:
        fruit_type: If provided, only invalidate predictions for this fruit type

    Returns:
        int: Number of keys deleted
    """
    try:
        if fruit_type:
            pattern = f"farmvision:prediction:*:{fruit_type}"
        else:
            pattern = "farmvision:prediction:*"

        # Get all matching keys using SCAN (non-blocking alternative to KEYS)
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")

        # Use SCAN instead of KEYS to avoid blocking Redis
        cursor = 0
        keys_to_delete = []
        while True:
            cursor, keys = redis_conn.scan(cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break

        if keys_to_delete:
            # Delete keys in batches to avoid overwhelming Redis
            batch_size = 1000
            total_deleted = 0
            for i in range(0, len(keys_to_delete), batch_size):
                batch = keys_to_delete[i : i + batch_size]
                total_deleted += redis_conn.delete(*batch)

            logger.info(
                "Cache BULK INVALIDATED: %s keys (pattern=%s)", total_deleted, pattern
            )
            return total_deleted
        else:
            logger.info("No cache keys found for pattern: %s", pattern)
            return 0

    except Exception as e:
        logger.warning("Bulk cache invalidation error: %s", e)
        return 0


def get_cache_statistics() -> Dict[str, Any]:
    """
    Get cache statistics including hit/miss ratios and memory usage.

    Returns:
        dict: Cache statistics
    """
    try:
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")

        # Get Redis info
        redis_info = redis_conn.info()

        # Count prediction cache keys using SCAN to avoid blocking Redis
        prediction_keys = []
        cursor = 0
        while True:
            cursor, keys = redis_conn.scan(
                cursor, match="farmvision:prediction:*", count=100
            )
            prediction_keys.extend(keys)
            if cursor == 0:
                break
        prediction_count = len(prediction_keys)

        # Calculate memory usage for prediction keys
        prediction_memory = 0
        if prediction_keys:
            for key in prediction_keys[:100]:  # Sample first 100 keys
                try:
                    prediction_memory += redis_conn.memory_usage(key) or 0
                except BaseException:
                    pass

            # Estimate total memory
            if len(prediction_keys) > 100:
                prediction_memory = int(prediction_memory * len(prediction_keys) / 100)

        # Get hit/miss stats
        keyspace_hits = redis_info.get("keyspace_hits", 0)
        keyspace_misses = redis_info.get("keyspace_misses", 0)
        total_requests = keyspace_hits + keyspace_misses

        hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0

        stats = {
            "redis_available": True,
            "prediction_keys_count": prediction_count,
            "prediction_memory_bytes": prediction_memory,
            "prediction_memory_mb": round(prediction_memory / (1024 * 1024), 2),
            "keyspace_hits": keyspace_hits,
            "keyspace_misses": keyspace_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "total_memory_used_mb": round(
                redis_info.get("used_memory", 0) / (1024 * 1024), 2
            ),
            "total_memory_peak_mb": round(
                redis_info.get("used_memory_peak", 0) / (1024 * 1024), 2
            ),
            "connected_clients": redis_info.get("connected_clients", 0),
            "uptime_seconds": redis_info.get("uptime_in_seconds", 0),
        }

        logger.info("Cache statistics retrieved: %s prediction keys", prediction_count)
        return stats

    except Exception as e:
        logger.warning("Cache statistics error (Redis unavailable?): %s", e)
        return {
            "redis_available": False,
            "error": str(e),
            "message": "Redis bağlantısı kurulamadı",
        }
