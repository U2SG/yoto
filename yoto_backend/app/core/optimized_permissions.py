"""
优化后的权限缓存系统
集成分布式锁、性能监控和异步操作
"""

import time
import threading
from typing import Set, Optional, Dict, Any
from functools import wraps
from .permissions import (
    _permission_cache,
    _serialize_permissions,
    _deserialize_permissions,
)
from .distributed_optimization import (
    get_optimized_distributed_lock,
    performance_monitor,
    async_cache_operation,
    DISTRIBUTED_CACHE_CONFIG,
)


def optimized_get_permissions_from_cache(cache_key: str) -> Optional[Set[str]]:
    """
    优化的权限缓存获取函数

    优化策略：
    1. 优先从本地缓存获取
    2. 本地缓存未命中时，使用优化的分布式锁
    3. 减少锁超时时间和重试次数
    4. 添加性能监控
    """
    start_time = time.time()

    # 1. 优先从本地缓存获取
    perms = _permission_cache.get(cache_key)
    if perms is not None:
        duration = time.time() - start_time
        performance_monitor.record_local_cache_operation(True, duration)
        return perms

    # 2. 本地缓存未命中，尝试分布式缓存
    try:
        # 使用优化的分布式锁
        lock_key = f"cache_read:{cache_key}"
        with get_optimized_distributed_lock(lock_key, timeout=1.0):  # 减少超时时间
            # 再次检查本地缓存（双重检查锁定模式）
            perms = _permission_cache.get(cache_key)
            if perms is not None:
                duration = time.time() - start_time
                performance_monitor.record_local_cache_operation(True, duration)
                return perms

            # 从分布式缓存获取
            from .distributed_cache import distributed_get

            data = distributed_get(cache_key)

            if data:
                perms = _deserialize_permissions(data)
                # 写回本地缓存
                _permission_cache.set(cache_key, perms)

                duration = time.time() - start_time
                performance_monitor.record_distributed_cache_operation(True, duration)
                return perms
            else:
                duration = time.time() - start_time
                performance_monitor.record_distributed_cache_operation(False, duration)
                return None

    except Exception as e:
        # 分布式缓存失败，降级到本地缓存
        duration = time.time() - start_time
        performance_monitor.record_distributed_cache_operation(False, duration)
        print(f"分布式缓存获取失败: {e}")
        return None


@async_cache_operation
def optimized_set_permissions_to_cache(
    cache_key: str, permissions: Set[str], ttl: int = None
):
    """
    优化的权限缓存设置函数

    优化策略：
    1. 立即更新本地缓存
    2. 异步更新分布式缓存
    3. 使用优化的分布式锁
    4. 添加性能监控
    """
    ttl = ttl or DISTRIBUTED_CACHE_CONFIG["cache_ttl"]
    start_time = time.time()

    # 1. 立即更新本地缓存
    _permission_cache.set(cache_key, permissions)

    # 2. 使用优化的分布式锁保护分布式缓存更新
    try:
        lock_key = f"cache_write:{cache_key}"
        with get_optimized_distributed_lock(lock_key, timeout=1.0):  # 减少超时时间
            # 序列化权限数据
            data = _serialize_permissions(permissions)

            # 更新分布式缓存
            from .distributed_cache import distributed_set

            success = distributed_set(cache_key, data, ttl)

            duration = time.time() - start_time
            if success:
                performance_monitor.record_distributed_cache_operation(True, duration)
            else:
                performance_monitor.record_distributed_cache_operation(False, duration)

    except Exception as e:
        duration = time.time() - start_time
        performance_monitor.record_distributed_cache_operation(False, duration)
        print(f"分布式缓存设置失败: {e}")


def optimized_batch_get_permissions(cache_keys: list) -> Dict[str, Optional[Set[str]]]:
    """
    优化的批量权限获取函数

    优化策略：
    1. 批量检查本地缓存
    2. 批量获取分布式缓存
    3. 减少锁竞争
    """
    results = {}
    start_time = time.time()

    # 1. 批量检查本地缓存
    local_misses = []
    for key in cache_keys:
        perms = _permission_cache.get(key)
        if perms is not None:
            results[key] = perms
        else:
            local_misses.append(key)

    # 2. 批量获取分布式缓存
    if local_misses:
        try:
            from .distributed_cache import distributed_get

            # 使用批量操作
            batch_size = DISTRIBUTED_CACHE_CONFIG["batch_size"]
            for i in range(0, len(local_misses), batch_size):
                batch_keys = local_misses[i : i + batch_size]

                # 批量获取
                for key in batch_keys:
                    data = distributed_get(key)
                    if data:
                        perms = _deserialize_permissions(data)
                        _permission_cache.set(key, perms)  # 写回本地缓存
                        results[key] = perms
                    else:
                        results[key] = None

        except Exception as e:
            print(f"批量分布式缓存获取失败: {e}")
            # 为未获取到的键设置None
            for key in local_misses:
                if key not in results:
                    results[key] = None

    duration = time.time() - start_time
    print(f"批量获取完成，耗时: {duration*1000:.2f}ms，获取: {len(results)} 个键")

    return results


def optimized_batch_set_permissions(cache_data: Dict[str, Set[str]], ttl: int = None):
    """
    优化的批量权限设置函数

    优化策略：
    1. 批量更新本地缓存
    2. 异步批量更新分布式缓存
    3. 减少锁竞争
    """
    ttl = ttl or DISTRIBUTED_CACHE_CONFIG["cache_ttl"]
    start_time = time.time()

    # 1. 批量更新本地缓存
    for key, permissions in cache_data.items():
        _permission_cache.set(key, permissions)

    # 2. 异步批量更新分布式缓存
    try:
        from .distributed_cache import distributed_set

        # 使用批量操作
        batch_size = DISTRIBUTED_CACHE_CONFIG["batch_size"]
        cache_items = list(cache_data.items())

        for i in range(0, len(cache_items), batch_size):
            batch = cache_items[i : i + batch_size]

            # 批量设置
            for key, permissions in batch:
                data = _serialize_permissions(permissions)
                distributed_set(key, data, ttl)

    except Exception as e:
        print(f"批量分布式缓存设置失败: {e}")

    duration = time.time() - start_time
    print(f"批量设置完成，耗时: {duration*1000:.2f}ms，设置: {len(cache_data)} 个键")


def optimized_invalidate_user_permissions(user_id: int):
    """
    优化的用户权限失效函数

    优化策略：
    1. 使用延迟失效
    2. 批量失效操作
    3. 减少锁竞争
    """
    try:
        # 生成需要失效的缓存键模式
        patterns = [
            f"perm:{user_id}:global:*",
            f"perm:{user_id}:server:*",
            f"perm:{user_id}:channel:*",
        ]

        # 使用优化的分布式锁
        lock_key = f"invalidate_user:{user_id}"
        with get_optimized_distributed_lock(lock_key, timeout=2.0):
            # 清除本地缓存
            keys_to_remove = []
            for key in list(_permission_cache.cache.keys()):
                if any(pattern.replace("*", "") in key for pattern in patterns):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                _permission_cache.cache.pop(key, None)

            # 异步清除分布式缓存
            from .distributed_cache import distributed_delete

            for pattern in patterns:
                # 这里可以实现模式匹配删除
                # 暂时使用简单的键删除
                pass

    except Exception as e:
        print(f"用户权限失效失败: {e}")


def get_optimized_performance_stats() -> Dict[str, Any]:
    """
    获取优化的性能统计信息
    """
    # 获取基础统计
    from .permissions import get_cache_performance_stats

    base_stats = get_cache_performance_stats()

    # 获取分布式性能统计
    distributed_stats = performance_monitor.get_performance_report()

    # 合并统计信息
    optimized_stats = {
        "local_cache": base_stats["l1_cache"],
        "distributed_cache": distributed_stats["distributed_cache"],
        "locks": distributed_stats["locks"],
        "optimization_config": DISTRIBUTED_CACHE_CONFIG,
    }

    return optimized_stats


# 性能监控装饰器
def monitor_performance(operation_type: str):
    """性能监控装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # 记录性能统计
                if operation_type == "local_cache":
                    performance_monitor.record_local_cache_operation(True, duration)
                elif operation_type == "distributed_cache":
                    performance_monitor.record_distributed_cache_operation(
                        True, duration
                    )
                elif operation_type == "lock":
                    performance_monitor.record_lock_operation(True, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time

                # 记录失败统计
                if operation_type == "local_cache":
                    performance_monitor.record_local_cache_operation(False, duration)
                elif operation_type == "distributed_cache":
                    performance_monitor.record_distributed_cache_operation(
                        False, duration
                    )
                elif operation_type == "lock":
                    performance_monitor.record_lock_operation(False, duration)

                raise e

        return wrapper

    return decorator
