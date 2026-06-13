import hashlib
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def calculate_image_hash(image_data: bytes) -> str:
    try:
        sha256_hash = hashlib.sha256()
        sha256_hash.update(image_data)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error("Error calculating image hash: %s", e)
        raise


def get_prediction_cache_key(image_hash: str, fruit_type: str) -> str:
    cache_key_format = getattr(
        settings, "PREDICTION_CACHE_KEY_FORMAT", "prediction:{image_hash}:{fruit_type}"
    )
    return cache_key_format.format(image_hash=image_hash, fruit_type=fruit_type)


def get_cached_prediction(image_hash: str, fruit_type: str) -> Optional[Dict[str, Any]]:
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
    try:
        cache_key = get_prediction_cache_key(image_hash, fruit_type)
        cache.delete(cache_key)
        logger.info("Cache INVALIDATED: %s", cache_key)
        return True

    except Exception as e:
        logger.warning("Cache invalidation error: %s", e)
        return False


def invalidate_all_predictions(fruit_type: Optional[str] = None) -> int:
    try:
        if fruit_type:
            pattern = f"agrisynthia:prediction:*:{fruit_type}"
        else:
            pattern = "agrisynthia:prediction:*"

        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")

        cursor = 0
        keys_to_delete = []
        while True:
            cursor, keys = redis_conn.scan(cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break

        if keys_to_delete:
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
    try:
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")

        redis_info = redis_conn.info()

        prediction_keys = []
        cursor = 0
        while True:
            cursor, keys = redis_conn.scan(
                cursor, match="agrisynthia:prediction:*", count=100
            )
            prediction_keys.extend(keys)
            if cursor == 0:
                break
        prediction_count = len(prediction_keys)

        prediction_memory = 0
        if prediction_keys:
            for key in prediction_keys[:100]:
                try:
                    prediction_memory += redis_conn.memory_usage(key) or 0
                except BaseException:
                    pass

            if len(prediction_keys) > 100:
                prediction_memory = int(prediction_memory * len(prediction_keys) / 100)

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
