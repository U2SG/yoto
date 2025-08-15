"""
分布式系统优化配置
针对Redis分布式集群和分布式锁的性能优化
"""

import time
import threading
import asyncio
from typing import Dict, Any, Optional, List
from functools import wraps
import redis
from redis.exceptions import ConnectionError, TimeoutError

# 分布式缓存优化配置
DISTRIBUTED_CACHE_CONFIG = {
    # Redis连接优化
    "connection_pool_size": 50,
    "socket_timeout": 1.0,  # 减少超时时间
    "socket_connect_timeout": 1.0,
    "retry_on_timeout": True,
    "health_check_interval": 30,
    # 分布式锁优化
    "lock_timeout": 3.0,  # 减少锁超时时间
    "lock_retry_interval": 0.05,  # 减少重试间隔
    "lock_retry_count": 3,  # 减少重试次数
    # 批量操作优化
    "batch_size": 100,
    "batch_timeout": 2.0,
    # 缓存优化
    "cache_ttl": 300,
    "local_cache_size": 1000,
    "compression_threshold": 1024,  # 1KB以上才压缩
    # 性能监控
    "enable_monitoring": True,
    "monitoring_interval": 60,
}


class DistributedOptimizer:
    """分布式系统优化器"""

    def __init__(self):
        self.connection_pool = None
        self.health_monitor = None
        self.performance_stats = {}
        self._lock = threading.Lock()

    def optimize_redis_connection(self, redis_url: str = None) -> redis.Redis:
        """优化Redis连接"""
        if self.connection_pool is None:
            try:
                self.connection_pool = redis.ConnectionPool.from_url(
                    redis_url or "redis://localhost:6379/0",
                    max_connections=DISTRIBUTED_CACHE_CONFIG["connection_pool_size"],
                    socket_timeout=DISTRIBUTED_CACHE_CONFIG["socket_timeout"],
                    socket_connect_timeout=DISTRIBUTED_CACHE_CONFIG[
                        "socket_connect_timeout"
                    ],
                    retry_on_timeout=DISTRIBUTED_CACHE_CONFIG["retry_on_timeout"],
                    health_check_interval=DISTRIBUTED_CACHE_CONFIG[
                        "health_check_interval"
                    ],
                )
            except Exception as e:
                print(f"Redis连接池创建失败: {e}")
                return None

        return redis.Redis(connection_pool=self.connection_pool)

    def optimized_distributed_lock(
        self,
        key: str,
        timeout: float = None,
        retry_interval: float = None,
        retry_count: int = None,
    ):
        """优化的分布式锁"""
        timeout = timeout or DISTRIBUTED_CACHE_CONFIG["lock_timeout"]
        retry_interval = (
            retry_interval or DISTRIBUTED_CACHE_CONFIG["lock_retry_interval"]
        )
        retry_count = retry_count or DISTRIBUTED_CACHE_CONFIG["lock_retry_count"]

        from .common.distributed_lock import OptimizedDistributedLock

        return OptimizedDistributedLock(None, key, timeout, retry_interval, retry_count)

    def batch_operations(self, operations: List[Dict], batch_size: int = None):
        """批量操作优化"""
        batch_size = batch_size or DISTRIBUTED_CACHE_CONFIG["batch_size"]

        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]
            yield batch


# OptimizedDistributedLock 现在从 app.core.common.distributed_lock 导入


def async_cache_operation(func):
    """异步缓存操作装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 立即执行本地操作
        local_result = func(*args, **kwargs)

        # 异步执行分布式操作
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def async_distributed_operation():
            try:
                # 这里可以添加异步的分布式缓存操作
                pass
            except Exception as e:
                print(f"异步分布式操作失败: {e}")

        # 创建异步任务但不等待
        loop.create_task(async_distributed_operation())

        return local_result

    return wrapper


class CachePerformanceMonitor:
    """缓存性能监控器"""

    def __init__(self):
        self.stats = {
            "local_cache": {"hits": 0, "misses": 0, "avg_time": 0},
            "distributed_cache": {"hits": 0, "misses": 0, "avg_time": 0},
            "locks": {"acquired": 0, "timeouts": 0, "avg_time": 0},
        }
        self._lock = threading.Lock()

    def record_local_cache_operation(self, hit: bool, duration: float):
        """记录本地缓存操作"""
        with self._lock:
            if hit:
                self.stats["local_cache"]["hits"] += 1
            else:
                self.stats["local_cache"]["misses"] += 1

            # 更新平均时间
            total_ops = (
                self.stats["local_cache"]["hits"] + self.stats["local_cache"]["misses"]
            )
            current_avg = self.stats["local_cache"]["avg_time"]
            self.stats["local_cache"]["avg_time"] = (
                current_avg * (total_ops - 1) + duration
            ) / total_ops

    def record_distributed_cache_operation(self, hit: bool, duration: float):
        """记录分布式缓存操作"""
        with self._lock:
            if hit:
                self.stats["distributed_cache"]["hits"] += 1
            else:
                self.stats["distributed_cache"]["misses"] += 1

            # 更新平均时间
            total_ops = (
                self.stats["distributed_cache"]["hits"]
                + self.stats["distributed_cache"]["misses"]
            )
            current_avg = self.stats["distributed_cache"]["avg_time"]
            self.stats["distributed_cache"]["avg_time"] = (
                current_avg * (total_ops - 1) + duration
            ) / total_ops

    def record_lock_operation(self, acquired: bool, duration: float):
        """记录锁操作"""
        with self._lock:
            if acquired:
                self.stats["locks"]["acquired"] += 1
            else:
                self.stats["locks"]["timeouts"] += 1

            # 更新平均时间
            total_ops = (
                self.stats["locks"]["acquired"] + self.stats["locks"]["timeouts"]
            )
            current_avg = self.stats["locks"]["avg_time"]
            self.stats["locks"]["avg_time"] = (
                current_avg * (total_ops - 1) + duration
            ) / total_ops

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        with self._lock:
            report = {
                "local_cache": {
                    "hit_rate": self.stats["local_cache"]["hits"]
                    / max(
                        self.stats["local_cache"]["hits"]
                        + self.stats["local_cache"]["misses"],
                        1,
                    ),
                    "avg_time_ms": self.stats["local_cache"]["avg_time"] * 1000,
                    "total_operations": self.stats["local_cache"]["hits"]
                    + self.stats["local_cache"]["misses"],
                },
                "distributed_cache": {
                    "hit_rate": self.stats["distributed_cache"]["hits"]
                    / max(
                        self.stats["distributed_cache"]["hits"]
                        + self.stats["distributed_cache"]["misses"],
                        1,
                    ),
                    "avg_time_ms": self.stats["distributed_cache"]["avg_time"] * 1000,
                    "total_operations": self.stats["distributed_cache"]["hits"]
                    + self.stats["distributed_cache"]["misses"],
                },
                "locks": {
                    "success_rate": self.stats["locks"]["acquired"]
                    / max(
                        self.stats["locks"]["acquired"]
                        + self.stats["locks"]["timeouts"],
                        1,
                    ),
                    "avg_time_ms": self.stats["locks"]["avg_time"] * 1000,
                    "total_operations": self.stats["locks"]["acquired"]
                    + self.stats["locks"]["timeouts"],
                },
            }
            return report


# 全局优化器实例
distributed_optimizer = DistributedOptimizer()
performance_monitor = CachePerformanceMonitor()


def get_optimized_distributed_lock(key: str, timeout: float = None):
    """获取优化的分布式锁"""
    return distributed_optimizer.optimized_distributed_lock(key, timeout)


def get_performance_report() -> Dict[str, Any]:
    """获取性能报告"""
    return performance_monitor.get_performance_report()
