"""
隔离的权限缓存模块

避免对其他业务缓存造成影响：
- 独立的Redis数据库
- 命名空间前缀
- 资源限制
- 监控和告警
"""

import time
import logging
import json
import gzip
import pickle
import threading
import hashlib
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from functools import wraps
from collections import OrderedDict, defaultdict
import redis

logger = logging.getLogger(__name__)

# ==================== 配置常量 ====================

# 权限缓存专用配置
PERMISSION_CACHE_CONFIG = {
    "redis_db": 1,  # 使用独立的Redis数据库
    "redis_max_connections": 5,  # 限制连接数
    "lru_maxsize": 1000,  # 限制LRU缓存大小
    "memory_limit_mb": 100,  # 内存限制
    "key_prefix": "yoto:permission:",  # 键前缀
    "ttl_default": 300,  # 默认TTL
    "batch_size": 50,  # 批量操作大小
    "scan_batch_size": 100,  # 扫描批次大小
}

# ==================== 监控装饰器 ====================


def monitored_cache(level: str):
    """缓存监控装饰器 - 权限专用"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                logger.debug(
                    f"权限缓存操作 {level}: {func.__name__} 耗时 {response_time:.3f}s"
                )
                return result
            except Exception as e:
                logger.error(f"权限缓存操作失败 {level}: {func.__name__}, 错误: {e}")
                raise

        return wrapper

    return decorator


# ==================== 隔离的缓存键生成 ====================


def _make_perm_cache_key(user_id, scope, scope_id):
    """生成权限缓存键 - 带命名空间前缀"""
    prefix = PERMISSION_CACHE_CONFIG["key_prefix"]
    if scope and scope_id:
        return f"{prefix}user_perm:{user_id}:{scope}:{scope_id}"
    elif scope:
        return f"{prefix}user_perm:{user_id}:{scope}"
    else:
        return f"{prefix}user_perm:{user_id}"


def _make_user_perm_pattern(user_id):
    """生成用户权限模式 - 带命名空间前缀"""
    prefix = PERMISSION_CACHE_CONFIG["key_prefix"]
    return f"{prefix}user_perm:{user_id}:*"


def _make_role_perm_pattern(role_id):
    """生成角色权限模式 - 带命名空间前缀"""
    prefix = PERMISSION_CACHE_CONFIG["key_prefix"]
    return f"{prefix}role_perm:{role_id}:*"


def _make_permission_cache_key(
    permission_name: str, user_id: int = None, scope: str = None, scope_id: int = None
) -> str:
    """生成权限缓存键 - 带命名空间前缀"""
    prefix = PERMISSION_CACHE_CONFIG["key_prefix"]
    parts = [prefix, "perm", permission_name]
    if user_id is not None:
        parts.append(f"user:{user_id}")
    if scope:
        parts.append(f"scope:{scope}")
    if scope_id is not None:
        parts.append(f"scope_id:{scope_id}")
    return ":".join(parts)


# ==================== 序列化与反序列化 ====================


def _compress_permissions(permissions: Set[str]) -> bytes:
    """压缩权限数据 - 使用pickle（原始版本）"""
    try:
        data = pickle.dumps(permissions)
        return data
    except Exception as e:
        logger.error(f"权限数据压缩失败: {e}")
        return b""


def _decompress_permissions(data: bytes) -> Set[str]:
    """解压权限数据 - 使用pickle（原始版本）"""
    try:
        if not data:
            return set()
        return pickle.loads(data)
    except Exception as e:
        logger.error(f"权限数据解压失败: {e}")
        return set()


def _serialize_permissions(permissions: Set[str]) -> bytes:
    """序列化权限数据"""
    return _compress_permissions(permissions)


def _deserialize_permissions(data: bytes) -> Set[str]:
    """反序列化权限数据"""
    return _decompress_permissions(data)


# ==================== 安全序列化（新版本） ====================


def safe_serialize_permissions(permissions: Set[str]) -> bytes:
    """安全序列化权限数据 - 使用 JSON + gzip"""
    try:
        data = list(permissions)
        json_str = json.dumps(data, ensure_ascii=False)
        compressed = gzip.compress(json_str.encode("utf-8"))
        return compressed
    except Exception as e:
        logger.error(f"权限数据序列化失败: {e}")
        return b""


def safe_deserialize_permissions(data: bytes) -> Set[str]:
    """安全反序列化权限数据 - 使用 JSON + gzip"""
    try:
        if not data:
            return set()
        decompressed = gzip.decompress(data)
        json_str = decompressed.decode("utf-8")
        permissions_list = json.loads(json_str)
        return set(permissions_list)
    except Exception as e:
        logger.error(f"权限数据反序列化失败: {e}")
        return set()


# ==================== 隔离的Redis客户端管理 ====================

_permission_redis_client = None
_permission_redis_lock = threading.Lock()


def _get_permission_redis_client():
    """获取权限专用Redis客户端 - 线程安全"""
    global _permission_redis_client
    if _permission_redis_client is None:
        with _permission_redis_lock:
            if _permission_redis_client is None:  # 双重检查锁定
                try:
                    config = PERMISSION_CACHE_CONFIG
                    _permission_redis_client = redis.Redis(
                        host="localhost",
                        port=6379,
                        db=config["redis_db"],  # 使用独立数据库
                        decode_responses=False,
                        socket_timeout=1,
                        socket_connect_timeout=1,
                        max_connections=config["redis_max_connections"],  # 限制连接数
                        retry_on_timeout=True,
                        health_check_interval=30,
                    )
                    # 测试连接
                    _permission_redis_client.ping()
                    logger.info(f"权限Redis连接成功 (DB:{config['redis_db']})")
                except Exception as e:
                    logger.error(f"权限Redis连接失败: {e}")
                    _permission_redis_client = None
    return _permission_redis_client


def _get_permission_redis_pipeline():
    """获取权限专用Redis管道 - 线程安全"""
    client = _get_permission_redis_client()
    if client:
        return client.pipeline()
    return None


# ==================== 隔离的Redis批量操作 ====================


def _permission_redis_batch_get(keys: List[str]) -> Dict[str, Optional[bytes]]:
    """批量获取权限Redis缓存 - 线程安全"""
    pipeline = _get_permission_redis_pipeline()
    if not pipeline:
        return {}

    try:
        for key in keys:
            pipeline.get(key)
        results = pipeline.execute()
        return dict(zip(keys, results))
    except Exception as e:
        logger.error(f"权限Redis批量获取失败: {e}")
        return {}


def _permission_redis_batch_set(
    key_value_pairs: Dict[str, bytes], ttl: int = None
) -> bool:
    """批量设置权限Redis缓存 - 线程安全"""
    pipeline = _get_permission_redis_pipeline()
    if not pipeline:
        return False

    if ttl is None:
        ttl = PERMISSION_CACHE_CONFIG["ttl_default"]

    try:
        for key, value in key_value_pairs.items():
            pipeline.setex(key, ttl, value)
        pipeline.execute()
        return True
    except Exception as e:
        logger.error(f"权限Redis批量设置失败: {e}")
        return False


def _permission_redis_batch_delete(keys: List[str]) -> bool:
    """批量删除权限Redis缓存 - 线程安全"""
    pipeline = _get_permission_redis_pipeline()
    if not pipeline:
        return False

    try:
        for key in keys:
            pipeline.delete(key)
        pipeline.execute()
        return True
    except Exception as e:
        logger.error(f"权限Redis批量删除失败: {e}")
        return False


def _permission_redis_scan_keys(pattern: str, batch_size: int = None) -> List[str]:
    """扫描权限Redis键 - 线程安全"""
    client = _get_permission_redis_client()
    if not client:
        return []

    if batch_size is None:
        batch_size = PERMISSION_CACHE_CONFIG["scan_batch_size"]

    try:
        keys = []
        cursor = 0
        while True:
            cursor, batch = client.scan(cursor, match=pattern, count=batch_size)
            keys.extend(batch)
            if cursor == 0:
                break
        return keys
    except Exception as e:
        logger.error(f"权限Redis键扫描失败: {e}")
        return []


# ==================== 资源限制的LRU缓存 ====================


class IsolatedLRUPermissionCache:
    """隔离的LRU权限缓存 - 带资源限制"""

    def __init__(self, maxsize=None):
        if maxsize is None:
            maxsize = PERMISSION_CACHE_CONFIG["lru_maxsize"]

        self.maxsize = maxsize
        self.cache = OrderedDict()
        self.access_times = {}
        self.hit_count = 0
        self.miss_count = 0
        self.creation_time = time.time()
        self.memory_limit = PERMISSION_CACHE_CONFIG["memory_limit_mb"] * 1024 * 1024
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Set[str]]:
        """获取缓存值 - 线程安全"""
        with self._lock:
            if key in self.cache:
                self.access_times[key] = time.time()
                self.cache.move_to_end(key)
                self.hit_count += 1
                return self.cache[key]
            self.miss_count += 1
            return None

    def set(self, key: str, value: Set[str]):
        """设置缓存值 - 带内存限制"""
        with self._lock:
            # 检查内存使用
            if self._get_memory_usage() > self.memory_limit:
                self._evict_lru()

            if key in self.cache:
                self.access_times[key] = time.time()
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.maxsize:
                    self._evict_lru()
                self.access_times[key] = time.time()

            self.cache[key] = value

    def remove(self, key: str) -> bool:
        """精确移除缓存项"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.access_times[key]
                return True
            return False

    def remove_pattern(self, pattern: str) -> int:
        """按模式移除缓存项"""
        with self._lock:
            keys_to_remove = []
            for key in self.cache.keys():
                if pattern in key:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.cache[key]
                del self.access_times[key]

            return len(keys_to_remove)

    def batch_get(self, keys: List[str]) -> Dict[str, Optional[Set[str]]]:
        """批量获取缓存值"""
        with self._lock:
            result = {}
            for key in keys:
                result[key] = self.get(key)
            return result

    def batch_set(self, key_value_pairs: Dict[str, Set[str]]):
        """批量设置缓存值"""
        with self._lock:
            for key, value in key_value_pairs.items():
                self.set(key, value)

    def batch_remove(self, keys: List[str]) -> int:
        """批量移除缓存项"""
        with self._lock:
            removed_count = 0
            for key in keys:
                if self.remove(key):
                    removed_count += 1
            return removed_count

    def _evict_lru(self):
        """淘汰最近最少使用的缓存项"""
        with self._lock:
            if not self.cache:
                return
            lru_key = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_key]
            del self.access_times[lru_key]

    def _get_memory_usage(self) -> int:
        """估算内存使用量"""
        total_size = 0
        for key, value in self.cache.items():
            # 估算键和值的大小
            total_size += len(key.encode("utf-8"))
            total_size += sum(len(perm.encode("utf-8")) for perm in value)
        return total_size

    def clear(self):
        """清空缓存"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
            self.hit_count = 0
            self.miss_count = 0
            self.creation_time = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = self.hit_count / max(total_requests, 1)
            memory_usage = self._get_memory_usage()

            return {
                "size": len(self.cache),
                "maxsize": self.maxsize,
                "hits": self.hit_count,
                "misses": self.miss_count,
                "hit_rate": hit_rate,
                "memory_usage_bytes": memory_usage,
                "memory_limit_bytes": self.memory_limit,
                "memory_usage_percent": (memory_usage / self.memory_limit) * 100,
                "creation_time": self.creation_time,
                "uptime": time.time() - self.creation_time,
            }


# ==================== 隔离的缓存操作函数 ====================


@monitored_cache("l1")
def _get_permissions_from_isolated_cache(cache_key: str) -> Optional[Set[str]]:
    """从隔离缓存获取权限"""
    # 先尝试从LRU缓存获取
    lru_cache = getattr(_get_permissions_from_isolated_cache, "_lru_cache", None)
    if lru_cache is None:
        _get_permissions_from_isolated_cache._lru_cache = IsolatedLRUPermissionCache()
        lru_cache = _get_permissions_from_isolated_cache._lru_cache

    result = lru_cache.get(cache_key)
    if result is not None:
        return result

    # LRU缓存未命中，尝试Redis
    redis_client = _get_permission_redis_client()
    if redis_client:
        try:
            data = redis_client.get(cache_key)
            if data:
                permissions = _deserialize_permissions(data)
                # 回填LRU缓存
                lru_cache.set(cache_key, permissions)
                return permissions
        except Exception as e:
            logger.error(f"权限Redis获取失败: {e}")

    return None


@monitored_cache("l1")
def _set_permissions_to_isolated_cache(
    cache_key: str, permissions: Set[str], ttl: int = None
):
    """设置权限到隔离缓存"""
    if ttl is None:
        ttl = PERMISSION_CACHE_CONFIG["ttl_default"]

    # 设置LRU缓存
    lru_cache = getattr(_set_permissions_to_isolated_cache, "_lru_cache", None)
    if lru_cache is None:
        _set_permissions_to_isolated_cache._lru_cache = IsolatedLRUPermissionCache()
        lru_cache = _set_permissions_to_isolated_cache._lru_cache

    lru_cache.set(cache_key, permissions)

    # 设置Redis缓存
    redis_client = _get_permission_redis_client()
    if redis_client:
        try:
            data = _serialize_permissions(permissions)
            redis_client.setex(cache_key, ttl, data)
        except Exception as e:
            logger.error(f"权限Redis设置失败: {e}")


def _invalidate_user_permissions_isolated(user_id: int):
    """失效用户权限缓存 - 隔离版本"""
    # 清除LRU缓存中相关的键
    lru_cache = getattr(_get_permissions_from_isolated_cache, "_lru_cache", None)
    if lru_cache:
        pattern = _make_user_perm_pattern(user_id)
        lru_cache.remove_pattern(pattern)

    # 失效Redis缓存
    redis_client = _get_permission_redis_client()
    if redis_client:
        try:
            pattern = _make_user_perm_pattern(user_id)
            keys = _permission_redis_scan_keys(pattern)
            if keys:
                _permission_redis_batch_delete(keys)
        except Exception as e:
            logger.error(f"权限Redis失效用户权限失败: {e}")


def _invalidate_role_permissions_isolated(role_id: int):
    """失效角色权限缓存 - 隔离版本"""
    # 失效Redis缓存
    redis_client = _get_permission_redis_client()
    if redis_client:
        try:
            pattern = _make_role_perm_pattern(role_id)
            keys = _permission_redis_scan_keys(pattern)
            if keys:
                _permission_redis_batch_delete(keys)
        except Exception as e:
            logger.error(f"权限Redis失效角色权限失败: {e}")


# ==================== 隔离的缓存统计 ====================


def get_isolated_cache_stats():
    """获取隔离缓存统计"""
    # 获取LRU缓存统计
    lru_cache = getattr(_get_permissions_from_isolated_cache, "_lru_cache", None)
    lru_stats = lru_cache.get_stats() if lru_cache else {}

    # Redis统计
    redis_stats = {
        "connected": _get_permission_redis_client() is not None,
        "keys": 0,
        "db": PERMISSION_CACHE_CONFIG["redis_db"],
    }

    if redis_stats["connected"]:
        try:
            redis_client = _get_permission_redis_client()
            redis_stats["keys"] = redis_client.dbsize()
        except Exception as e:
            logger.error(f"获取权限Redis统计失败: {e}")

    return {"lru": lru_stats, "redis": redis_stats, "config": PERMISSION_CACHE_CONFIG}


def get_isolated_cache_performance_stats():
    """获取隔离缓存性能统计"""
    stats = get_isolated_cache_stats()

    # 计算命中率
    lru_hit_rate = stats["lru"].get("hit_rate", 0)
    memory_usage_percent = stats["lru"].get("memory_usage_percent", 0)

    return {
        "lru_hit_rate": lru_hit_rate,
        "lru_size": stats["lru"].get("size", 0),
        "lru_maxsize": stats["lru"].get("maxsize", 0),
        "memory_usage_percent": memory_usage_percent,
        "redis_connected": stats["redis"]["connected"],
        "redis_keys": stats["redis"]["keys"],
        "redis_db": stats["redis"]["db"],
        "overall_performance": (
            "good"
            if lru_hit_rate > 0.8 and memory_usage_percent < 80
            else "needs_optimization"
        ),
    }


# ==================== 便捷函数 ====================


def clear_isolated_caches():
    """清空隔离缓存"""
    # 清空LRU缓存
    lru_cache = getattr(_get_permissions_from_isolated_cache, "_lru_cache", None)
    if lru_cache:
        lru_cache.clear()

    # 清空Redis缓存
    redis_client = _get_permission_redis_client()
    if redis_client:
        try:
            # 清空权限相关的键
            pattern = f"{PERMISSION_CACHE_CONFIG['key_prefix']}*"
            keys = _permission_redis_scan_keys(pattern)
            if keys:
                _permission_redis_batch_delete(keys)
        except Exception as e:
            logger.error(f"清空权限Redis缓存失败: {e}")

    logger.info("隔离缓存已清空")


def get_isolated_cache_info():
    """获取隔离缓存信息"""
    stats = get_isolated_cache_stats()
    performance = get_isolated_cache_performance_stats()

    return {
        "stats": stats,
        "performance": performance,
        "redis_connected": _get_permission_redis_client() is not None,
        "isolation_level": "high",
    }


# ==================== 测试函数 ====================


def test_isolated_cache_functionality():
    """测试隔离缓存功能"""
    print("=== 隔离缓存功能测试 ===")

    # 1. 测试隔离的缓存键生成
    cache_key = _make_perm_cache_key(1, "server", 1)
    print(f"隔离缓存键生成: {cache_key}")
    print(f"键前缀: {PERMISSION_CACHE_CONFIG['key_prefix']}")

    # 2. 测试隔离的LRU缓存
    lru_cache = IsolatedLRUPermissionCache(maxsize=3)
    lru_cache.set("key1", {"perm1", "perm2"})
    lru_cache.set("key2", {"perm3", "perm4"})
    lru_cache.set("key3", {"perm5", "perm6"})
    lru_cache.set("key4", {"perm7", "perm8"})  # 触发LRU淘汰

    result = lru_cache.get("key1")
    print(f"隔离LRU缓存测试: {result is None}")  # key1应该被淘汰

    # 3. 测试内存限制
    stats = lru_cache.get_stats()
    print(f"内存使用: {stats['memory_usage_bytes']} bytes")
    print(f"内存限制: {stats['memory_limit_bytes']} bytes")
    print(f"内存使用率: {stats['memory_usage_percent']:.2f}%")

    # 4. 测试隔离缓存统计
    isolated_stats = get_isolated_cache_stats()
    print(f"隔离缓存统计: {isolated_stats}")

    print("隔离缓存功能测试完成")


if __name__ == "__main__":
    test_isolated_cache_functionality()
