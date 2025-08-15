"""
高级分布式权限系统优化
整合现有系统的优化策略，提供更高效的解决方案
"""

import time
import threading
import asyncio
from typing import Dict, Any, Optional, Set, List
from functools import wraps, lru_cache
from collections import defaultdict
import redis
from redis.exceptions import ConnectionError, TimeoutError
from flask import current_app, Flask
from threading import Lock
import os
import logging
import json

logger = logging.getLogger(__name__)


# 导入现有模块
# REMOVED: from app.core.permission.hybrid_permission_cache import HybridPermissionCache
from app.core.permission.permission_monitor import get_stats, PermissionMonitor
from app.core.common.distributed_lock import (
    OptimizedDistributedLock,
    create_optimized_distributed_lock,
)

# 全局混合缓存实例
# _hybrid_cache = HybridPermissionCache() # REMOVED
# _permission_cache = _hybrid_cache.l1_simple_cache # 替换为L1简单缓存 # REMOVED
_cache_monitor = PermissionMonitor()

# 全局高级优化器实例
_advanced_optimizer = None


# 兼容性函数 - 使用现有的PermissionMonitor方法
def _record_cache_operation(
    operation_type: str,
    cache_level: str,
    success: bool,
    duration: float = 0.0,
    cache_key: str = None,
):
    """记录缓存操作 - 使用现有的PermissionMonitor方法"""
    try:
        # 使用现有的record方法记录操作
        tags = {
            "operation": operation_type,
            "cache_level": cache_level,
            "success": str(success),
        }
        if cache_key:
            tags["cache_key"] = cache_key

        # 记录操作计数
        _cache_monitor.record(
            name=f"cache_operations.{operation_type}.{cache_level}",
            value=1,
            record_type=_cache_monitor.RecordType.COUNTER,
            tags=tags,
        )

        # 记录操作时长
        if duration > 0:
            _cache_monitor.record(
                name=f"cache_duration.{operation_type}.{cache_level}",
                value=duration,
                record_type=_cache_monitor.RecordType.HISTOGRAM,
                tags=tags,
            )

        # 记录成功率
        success_rate = 1.0 if success else 0.0
        _cache_monitor.record(
            name=f"cache_success_rate.{operation_type}.{cache_level}",
            value=success_rate,
            record_type=_cache_monitor.RecordType.GAUGE,
            tags=tags,
        )
    except Exception as e:
        logger.warning(f"记录缓存操作失败: {e}")


# 为兼容性添加record_operation方法到_cache_monitor
_cache_monitor.record_operation = _record_cache_operation

# REMOVED: _serialize_permissions
# def _serialize_permissions(permissions):
#     """序列化权限集合的辅助函数"""
#     return _hybrid_cache.distributed_cache._serialize_permissions(permissions)

# REMOVED: _deserialize_permissions
# def _deserialize_permissions(data):
#     """反序列化权限集合的辅助函数"""
#     return _hybrid_cache.distributed_cache._deserialize_permissions(data)

# REMOVED: get_distributed_cache
# def get_distributed_cache():
#     """获取分布式缓存实例的辅助函数"""
#     return _hybrid_cache.distributed_cache.redis_client

# REMOVED: distributed_get
# def distributed_get(key):
#     """分布式获取的辅助函数"""
#     return _hybrid_cache.distributed_cache_get(key)

# REMOVED: distributed_set
# def distributed_set(key, value, ttl):
#     """分布式设置的辅助函数"""
#     return _hybrid_cache.distributed_cache_set(key, value, ttl)

# REMOVED: distributed_delete
# def distributed_delete(key):
#     """分布式删除的辅助函数"""
#     return _hybrid_cache.distributed_cache_delete(key)

# REMOVED: distributed_lock
# def distributed_lock(lock_key, timeout=1.0):
#     """分布式锁的辅助函数"""
#     return OptimizedDistributedLock(lock_key, timeout=timeout)

# ==================== 应用工厂模式支持 ====================


class AdvancedOptimization:
    """一个封装了高级分布式优化器的扩展类，用于支持 init_app 模式"""

    def __init__(self, app: Flask = None):
        self.optimizer = None
        self.config = {}
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """
        使用 Flask app 对象来初始化高级分布式优化器。
        【核心修改】此方法现在依赖于首先初始化韧性模块。
        """
        if self.optimizer:
            return

        # 1. 【依赖注入】从 app.extensions 获取 Redis 客户端
        self.redis_client = app.extensions.get("redis_client")
        if self.redis_client is None:
            # 如果Redis客户端不可用，记录警告但不阻止应用启动
            logger.warning(
                "The Redis client was not found in app.extensions. "
                "Advanced optimization features will be disabled."
            )
            # 创建一个None客户端，允许应用继续运行
            self.redis_client = None

        # 2. 从 Flask app 配置中获取高级优化配置
        self.config = app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
        if not self.config:
            logger.warning(
                "ADVANCED_OPTIMIZATION_CONFIG is not configured in the Flask app. "
                "Using default configuration."
            )
            # 使用默认配置
            self.config = {
                "connection_pool_size": 100,
                "socket_timeout": 0.5,
                "socket_connect_timeout": 0.5,
                "retry_on_timeout": True,
                "health_check_interval": 15,
                "lock_timeout": 2.0,
                "lock_retry_interval": 0.02,
                "lock_retry_count": 2,
                "local_cache_size": 2000,
                "distributed_cache_ttl": 600,
                "compression_threshold": 512,
                "batch_size": 200,
                "batch_timeout": 1.0,
                "max_concurrent_batches": 10,
                "preload_enabled": True,
                "preload_batch_size": 50,
                "preload_ttl": 1800,
                "smart_invalidation": True,
                "invalidation_batch_size": 100,
                "delayed_invalidation_delay": 5,
                "enable_advanced_monitoring": True,
                "monitoring_interval": 30,
            }

        # 3. 创建优化器实例并存储
        self.optimizer = AdvancedDistributedOptimizer(self.config, self.redis_client)

        # 将自身实例存入 app 扩展中，方便全局访问
        if "advanced_optimization" not in app.extensions:
            app.extensions["advanced_optimization"] = self


# ==================== 全局实例 ====================
# 【核心修改】创建一个未初始化的全局实例
advanced_optimization_ext = AdvancedOptimization()


def get_advanced_optimizer() -> "AdvancedDistributedOptimizer":
    """获取全局高级分布式优化器实例。必须在 init_app 调用后才能工作。"""
    try:
        from flask import current_app

        if "advanced_optimization" in current_app.extensions:
            return current_app.extensions["advanced_optimization"].optimizer
        else:
            # 如果扩展未初始化，返回None而不是抛出错误
            logger.warning(
                "Advanced optimization system not initialized, returning None"
            )
            return None
    except RuntimeError:
        # 如果没有Flask应用上下文，返回None
        logger.warning("No Flask app context, advanced optimization not available")
        return None


def get_advanced_optimization_config() -> dict:
    """获取已加载的高级优化配置。"""
    try:
        from flask import current_app

        if "advanced_optimization" in current_app.extensions:
            return current_app.extensions["advanced_optimization"].config
        else:
            # 如果扩展未初始化，返回默认配置
            logger.warning(
                "Advanced optimization system not initialized, using default config"
            )
            return {
                "connection_pool_size": 100,
                "socket_timeout": 0.5,
                "socket_connect_timeout": 0.5,
                "retry_on_timeout": True,
                "health_check_interval": 15,
                "lock_timeout": 2.0,
                "lock_retry_interval": 0.02,
                "lock_retry_count": 2,
                "local_cache_size": 2000,
                "distributed_cache_ttl": 600,
                "compression_threshold": 512,
                "batch_size": 200,
                "batch_timeout": 1.0,
                "max_concurrent_batches": 10,
                "preload_enabled": True,
                "preload_batch_size": 50,
                "preload_ttl": 1800,
                "smart_invalidation": True,
                "invalidation_batch_size": 100,
                "delayed_invalidation_delay": 5,
                "enable_advanced_monitoring": True,
                "monitoring_interval": 30,
            }
    except RuntimeError:
        # 如果没有Flask应用上下文，返回默认配置
        logger.warning("No Flask app context, using default config")
        return {
            "connection_pool_size": 100,
            "socket_timeout": 0.5,
            "socket_connect_timeout": 0.5,
            "retry_on_timeout": True,
            "health_check_interval": 15,
            "lock_timeout": 2.0,
            "lock_retry_interval": 0.02,
            "lock_retry_count": 2,
            "local_cache_size": 2000,
            "distributed_cache_ttl": 600,
            "compression_threshold": 512,
            "batch_size": 200,
            "batch_timeout": 1.0,
            "max_concurrent_batches": 10,
            "preload_enabled": True,
            "preload_batch_size": 50,
            "preload_ttl": 1800,
            "smart_invalidation": True,
            "invalidation_batch_size": 100,
            "delayed_invalidation_delay": 5,
            "enable_advanced_monitoring": True,
            "monitoring_interval": 30,
        }


# 【删除】全局配置加载 - 配置应该只在初始化应用程序之后，通过已初始化的扩展来访问


class AdvancedDistributedOptimizer:
    """
    高级分布式优化器，负责协调各种优化策略。
    这是一个核心类，管理后台任务、批量处理和智能失效。
    """

    def __init__(self, config: dict, redis_client):
        """
        初始化优化器。
        【依赖注入】接收一个 redis_client 实例。
        """
        self.config = config
        self.redis_client = redis_client  # 使用注入的客户端
        self.batch_queue = asyncio.Queue(
            maxsize=self.config.get("max_concurrent_batches", 10)
        )
        self.permission_update_queue = asyncio.Queue()
        self.user_permission_cache = {}  # 用户权限的内存缓存
        self.user_cache_lock = Lock()
        self.stop_event = asyncio.Event()
        self.background_tasks = []

        # 【新增】性能统计
        self._stats = defaultdict(int)

        # 启动后台任务
        self._start_background_tasks()

    def create_lock(self, lock_key: str, **kwargs) -> "OptimizedDistributedLock":
        """【新增】一个创建锁的工厂方法"""
        # 从配置获取锁参数
        timeout = kwargs.get("timeout", self.config.get("lock_timeout", 2.0))
        retry_interval = kwargs.get(
            "retry_interval", self.config.get("lock_retry_interval", 0.02)
        )
        retry_count = kwargs.get("retry_count", self.config.get("lock_retry_count", 3))

        return create_optimized_distributed_lock(
            redis_client=self.redis_client,
            lock_key=lock_key,
            timeout=timeout,
            retry_interval=retry_interval,
            retry_count=retry_count,
        )

    def _start_background_tasks(self):
        """启动后台优化任务"""
        # 启动批量处理任务
        threading.Thread(target=self._batch_processor, daemon=True).start()

        # 启动智能失效任务
        threading.Thread(target=self._smart_invalidation_processor, daemon=True).start()

        # 启动预加载任务
        if self.config.get("preload_enabled", False):
            threading.Thread(target=self._preload_processor, daemon=True).start()

    def _smart_invalidation_processor(self):
        """智能失效处理器"""
        logger.info("智能失效处理器已启动")

        while not self.stop_event.is_set():
            try:
                # 获取智能失效分析
                analysis = self._get_smart_invalidation_analysis()

                if analysis["should_process"]:
                    # 执行智能批量失效
                    result = self._execute_smart_batch_invalidation(analysis)
                    logger.info(f"智能失效处理完成: {result['processed_count']} 个键")

                    # 更新统计
                    self._stats["smart_invalidation_runs"] += 1
                    self._stats["smart_invalidation_processed"] += result[
                        "processed_count"
                    ]

                # 等待下次处理
                sleep_time = self.config.get(
                    "smart_invalidation_interval", 300
                )  # 默认5分钟
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"智能失效处理器错误: {e}")
                time.sleep(60)  # 错误后等待1分钟再重试

    def _preload_processor(self):
        """预加载处理器"""
        logger.info("预加载处理器已启动")

        while not self.stop_event.is_set():
            try:
                # 执行预加载策略
                preload_result = self._execute_preload_strategy()

                if preload_result["success"]:
                    logger.info(f"预加载完成: {preload_result['preloaded_count']} 个键")
                    self._stats["preload_runs"] += 1
                    self._stats["preloaded_keys"] += preload_result["preloaded_count"]
                else:
                    logger.warning(f"预加载失败: {preload_result['error']}")

                # 等待下次预加载
                sleep_time = self.config.get("preload_interval", 3600)  # 默认1小时
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"预加载处理器错误: {e}")
                time.sleep(300)  # 错误后等待5分钟再重试

    def _get_smart_invalidation_analysis(self) -> Dict[str, Any]:
        """获取智能失效分析"""
        try:
            # 获取缓存失效统计
            from .permission_invalidation import get_invalidation_statistics

            stats = get_invalidation_statistics()

            # 分析队列状态
            queue_length = stats.get("queue_length", 0)
            processing_rate = stats.get("processing_rate", 0)
            queue_growth_rate = stats.get("queue_growth_rate", 0)

            # 智能判断是否需要处理
            should_process = (
                queue_length > self.config.get("min_queue_size", 50)
                or queue_growth_rate > self.config.get("max_growth_rate", 0.1)
                or processing_rate < self.config.get("min_processing_rate", 10)
            )

            return {
                "should_process": should_process,
                "queue_length": queue_length,
                "processing_rate": processing_rate,
                "queue_growth_rate": queue_growth_rate,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"获取智能失效分析失败: {e}")
            return {"should_process": False, "error": str(e), "timestamp": time.time()}

    def _execute_smart_batch_invalidation(
        self, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行智能批量失效"""
        try:
            from .permission_invalidation import execute_smart_batch_invalidation

            # 根据分析结果选择策略
            if analysis["queue_growth_rate"] > 0.2:
                strategy = "aggressive"  # 激进策略
            elif analysis["processing_rate"] < 5:
                strategy = "conservative"  # 保守策略
            else:
                strategy = "auto"  # 自动策略

            # 执行批量失效
            result = execute_smart_batch_invalidation(
                keys=[], strategy=strategy  # 空列表表示处理所有待失效的键
            )

            return {
                "success": True,
                "processed_count": result.get("processed_count", 0),
                "strategy": strategy,
                "execution_time": result.get("execution_time", 0),
            }

        except Exception as e:
            logger.error(f"执行智能批量失效失败: {e}")
            return {"success": False, "error": str(e), "processed_count": 0}

    def _execute_preload_strategy(self) -> Dict[str, Any]:
        """执行预加载策略"""
        try:
            # 获取预加载配置
            preload_config = self.config.get("preload", {})
            enabled = preload_config.get("enabled", False)

            if not enabled:
                return {"success": True, "preloaded_count": 0, "reason": "disabled"}

            # 获取热门用户和角色
            hot_users = self._get_hot_users()
            hot_roles = self._get_hot_roles()

            preloaded_count = 0

            # 预加载用户权限
            for user_id in hot_users:
                try:
                    self._preload_user_permissions(user_id)
                    preloaded_count += 1
                except Exception as e:
                    logger.warning(f"预加载用户 {user_id} 权限失败: {e}")

            # 预加载角色权限
            for role_id in hot_roles:
                try:
                    self._preload_role_permissions(role_id)
                    preloaded_count += 1
                except Exception as e:
                    logger.warning(f"预加载角色 {role_id} 权限失败: {e}")

            return {
                "success": True,
                "preloaded_count": preloaded_count,
                "hot_users_count": len(hot_users),
                "hot_roles_count": len(hot_roles),
            }

        except Exception as e:
            logger.error(f"执行预加载策略失败: {e}")
            return {"success": False, "error": str(e), "preloaded_count": 0}

    def _get_hot_users(self) -> List[int]:
        """获取热门用户列表"""
        try:
            # 从Redis获取热门用户统计
            redis_client = self.redis_client
            if not redis_client:
                return []

            # 获取最近24小时的用户访问统计
            hot_users_key = "hot_users:24h"
            hot_users = redis_client.zrevrange(hot_users_key, 0, 9)  # 获取前10名

            return [int(uid) for uid in hot_users if uid.isdigit()]

        except Exception as e:
            logger.warning(f"获取热门用户失败: {e}")
            return []

    def _get_hot_roles(self) -> List[int]:
        """获取热门角色列表"""
        try:
            # 从Redis获取热门角色统计
            redis_client = self.redis_client
            if not redis_client:
                return []

            # 获取最近24小时的角色访问统计
            hot_roles_key = "hot_roles:24h"
            hot_roles = redis_client.zrevrange(hot_roles_key, 0, 9)  # 获取前10名

            return [int(rid) for rid in hot_roles if rid.isdigit()]

        except Exception as e:
            logger.warning(f"获取热门角色失败: {e}")
            return []

    def _preload_user_permissions(self, user_id: int):
        """预加载用户权限"""
        try:
            # 延迟导入以避免循环依赖
            from .hybrid_permission_cache import get_hybrid_cache

            hybrid_cache = get_hybrid_cache()

            # 构建缓存键
            cache_key = f"user_permissions:{user_id}"

            # 检查是否已经在缓存中
            if hybrid_cache.l1_simple_cache.get(cache_key) is not None:
                return  # 已经在缓存中，跳过

            # 从数据库获取用户权限
            from .permission_queries import get_user_permissions

            permissions = get_user_permissions(user_id)

            if permissions:
                # 设置到缓存
                hybrid_cache.l1_simple_cache.set(cache_key, permissions, ttl=300)
                logger.debug(f"预加载用户 {user_id} 权限成功")

        except Exception as e:
            logger.warning(f"预加载用户 {user_id} 权限失败: {e}")

    def _preload_role_permissions(self, role_id: int):
        """预加载角色权限"""
        try:
            # 延迟导入以避免循环依赖
            from .hybrid_permission_cache import get_hybrid_cache

            hybrid_cache = get_hybrid_cache()

            # 构建缓存键
            cache_key = f"role_permissions:{role_id}"

            # 检查是否已经在缓存中
            if hybrid_cache.l1_simple_cache.get(cache_key) is not None:
                return  # 已经在缓存中，跳过

            # 从数据库获取角色权限
            from .permission_queries import get_role_permissions

            permissions = get_role_permissions(role_id)

            if permissions:
                # 设置到缓存
                hybrid_cache.l1_simple_cache.set(cache_key, permissions, ttl=300)
                logger.debug(f"预加载角色 {role_id} 权限成功")

        except Exception as e:
            logger.warning(f"预加载角色 {role_id} 权限失败: {e}")

    def _batch_processor(self):
        """批量处理器"""
        logger.info("批量处理器已启动")

        while not self.stop_event.is_set():
            try:
                # 处理批量操作队列
                batch_result = self._process_batch_operations()

                if batch_result["processed_count"] > 0:
                    logger.debug(
                        f"批量处理完成: {batch_result['processed_count']} 个操作"
                    )
                    self._stats["batch_operations"] += batch_result["processed_count"]

                time.sleep(0.1)  # 避免过度占用CPU

            except Exception as e:
                logger.error(f"批量处理器错误: {e}")
                time.sleep(1)  # 错误后等待1秒再重试

    def _process_batch_operations(self) -> Dict[str, Any]:
        """处理批量操作"""
        try:
            # 获取批量操作队列
            redis_client = self.redis_client
            if not redis_client:
                return {"processed_count": 0}

            batch_queue_key = "batch_operations"
            batch_size = self.config.get("batch_size", 100)

            # 获取一批操作
            try:
                operations = redis_client.lrange(batch_queue_key, 0, batch_size - 1)
                # 确保operations是列表类型
                if not isinstance(operations, (list, tuple)):
                    logger.warning(f"Redis返回的操作数据格式不正确: {type(operations)}")
                    return {"processed_count": 0}
            except Exception as e:
                logger.warning(f"获取批量操作队列失败: {e}")
                return {"processed_count": 0}

            if not operations:
                return {"processed_count": 0}

            processed_count = 0

            for operation_data in operations:
                try:
                    # 确保operation_data是字符串
                    if isinstance(operation_data, bytes):
                        operation_data = operation_data.decode("utf-8")
                    elif not isinstance(operation_data, str):
                        logger.warning(
                            f"跳过无效的操作数据格式: {type(operation_data)}"
                        )
                        continue

                    operation = json.loads(operation_data)
                    operation_type = operation.get("type")

                    if operation_type == "set_permissions":
                        # 批量设置权限
                        self._execute_batch_set_permissions(operation)
                        processed_count += 1
                    elif operation_type == "invalidate_permissions":
                        # 批量失效权限
                        self._execute_batch_invalidate_permissions(operation)
                        processed_count += 1
                    else:
                        logger.warning(f"未知的操作类型: {operation_type}")

                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析失败: {e}, 数据: {operation_data}")
                    continue
                except Exception as e:
                    logger.warning(f"处理批量操作失败: {e}")
                    continue

            # 从队列中移除已处理的操作
            if processed_count > 0:
                try:
                    redis_client.ltrim(batch_queue_key, processed_count, -1)
                except Exception as e:
                    logger.warning(f"移除已处理的操作失败: {e}")

            return {"processed_count": processed_count}

        except Exception as e:
            logger.error(f"处理批量操作失败: {e}")
            return {"processed_count": 0}

    def _execute_batch_set_permissions(self, operation: Dict[str, Any]):
        """执行批量设置权限操作"""
        try:
            cache_data = operation.get("cache_data", {})
            ttl = operation.get("ttl", 300)

            # 验证cache_data格式
            if not isinstance(cache_data, dict):
                logger.warning(f"缓存数据格式不正确: {type(cache_data)}")
                return

            # 调用批量设置函数
            try:
                advanced_batch_set_permissions(cache_data, ttl)
            except Exception as e:
                logger.error(f"调用批量设置权限函数失败: {e}")

        except Exception as e:
            logger.error(f"执行批量设置权限失败: {e}")

    def _execute_batch_invalidate_permissions(self, operation: Dict[str, Any]):
        """执行批量失效权限操作"""
        try:
            user_id = operation.get("user_id")
            if user_id is not None:
                try:
                    advanced_invalidate_user_permissions(user_id)
                except Exception as e:
                    logger.error(f"调用用户权限失效函数失败: {e}")
            else:
                logger.warning("批量失效操作缺少user_id")

        except Exception as e:
            logger.error(f"执行批量失效权限失败: {e}")


# 使用通用分布式锁模块
# OptimizedDistributedLock 现在从 app.core.common.distributed_lock 导入


def advanced_get_permissions_from_cache(cache_key: str) -> Optional[Set[str]]:
    """
    高级优化的权限缓存获取函数

    优化策略：
    1. 优先从L1本地缓存获取
    2. 使用优化的分布式锁
    3. 双重检查锁定模式
    4. 从L2分布式缓存获取
    5. 智能预加载
    6. 性能监控
    """
    start_time = time.time()

    # 获取优化器
    optimizer = get_advanced_optimizer()

    # 1. 优先从L1本地缓存获取
    try:
        # 延迟导入以避免循环依赖
        from app.core.permission.hybrid_permission_cache import get_hybrid_cache

        hybrid_cache = get_hybrid_cache()

        # 从L1简单缓存获取
        perms = hybrid_cache.l1_simple_cache.get(cache_key)
        if perms is not None:
            duration = time.time() - start_time
            _cache_monitor.record(
                "cache_get", duration, tags={"level": "l1", "success": "true"}
            )
            return perms
    except Exception as e:
        logging.warning(f"L1缓存获取失败: {e}")

    # 2. 检查预加载缓存
    if hasattr(optimizer, "preload_cache") and cache_key in optimizer.preload_cache:
        perms = optimizer.preload_cache[cache_key]
        # 写回L1缓存
        try:
            hybrid_cache.l1_simple_cache.set(cache_key, perms)
        except Exception as e:
            logging.warning(f"预加载缓存写回失败: {e}")
        duration = time.time() - start_time
        _cache_monitor.record(
            "cache_get", duration, tags={"level": "l1", "success": "true"}
        )
        return perms

    # 3. 使用优化的分布式锁进行双重检查锁定
    try:
        lock_key = f"cache_read:{cache_key}"

        # 检查优化器是否可用
        if optimizer is not None:
            # 【修正】通过工厂方法创建锁
            with optimizer.create_lock(lock_key, timeout=1.0) as lock:
                # 再次检查L1缓存（双重检查锁定模式）
                try:
                    perms = hybrid_cache.l1_simple_cache.get(cache_key)
                    if perms is not None:
                        duration = time.time() - start_time
                        _cache_monitor.record(
                            "cache_get",
                            duration,
                            tags={"level": "l1", "success": "true"},
                        )
                        return perms
                except Exception as e:
                    logging.warning(f"L1缓存双重检查失败: {e}")

                # 从L2分布式缓存获取（现在在hybrid_permission_cache中已经包含双重检查锁定）
                try:
                    data = hybrid_cache.distributed_cache_get(cache_key)

                    if data:
                        # 写回L1缓存
                        try:
                            hybrid_cache.l1_simple_cache.set(cache_key, data)
                        except Exception as e:
                            logging.warning(f"L2到L1缓存写回失败: {e}")

                        duration = time.time() - start_time
                        _cache_monitor.record(
                            "cache_get",
                            duration,
                            tags={"level": "l2", "success": "true"},
                        )
                        return data
                    else:
                        duration = time.time() - start_time
                        _cache_monitor.record(
                            "cache_get",
                            duration,
                            tags={"level": "l2", "success": "false"},
                        )
                        return None
                except Exception as e:
                    logging.error(f"L2分布式缓存获取失败: {e}")
                    duration = time.time() - start_time
                    _cache_monitor.record(
                        "cache_get", duration, tags={"level": "l2", "success": "false"}
                    )
                    return None
        else:
            # 如果优化器不可用，直接进行缓存操作
            logging.warning("高级优化器不可用，使用基础缓存操作")
            try:
                perms = hybrid_cache.l1_simple_cache.get(cache_key)
                if perms is not None:
                    duration = time.time() - start_time
                    _cache_monitor.record(
                        "cache_get", duration, tags={"level": "l1", "success": "true"}
                    )
                    return perms

                data = hybrid_cache.distributed_cache_get(cache_key)
                if data:
                    try:
                        hybrid_cache.l1_simple_cache.set(cache_key, data)
                    except Exception as e:
                        logging.warning(f"L2到L1缓存写回失败: {e}")

                    duration = time.time() - start_time
                    _cache_monitor.record(
                        "cache_get", duration, tags={"level": "l2", "success": "true"}
                    )
                    return data
                else:
                    duration = time.time() - start_time
                    _cache_monitor.record(
                        "cache_get", duration, tags={"level": "l2", "success": "false"}
                    )
                    return None
            except Exception as e:
                logging.error(f"基础缓存操作失败: {e}")
                duration = time.time() - start_time
                _cache_monitor.record(
                    "cache_get", duration, tags={"level": "l2", "success": "false"}
                )
                return None

    except Exception as e:
        duration = time.time() - start_time
        _cache_monitor.record(
            "cache_get", duration, tags={"level": "l2", "success": "false"}
        )
        logging.error(f"高级分布式缓存获取失败: {e}")
        return None


def advanced_set_permissions_to_cache(
    cache_key: str, permissions: Set[str], ttl: int = None
):
    """
    高级优化的权限缓存设置函数

    优化策略：
    1. 智能TTL管理
    2. 并发写入
    3. 性能监控
    4. 错误处理
    """
    start_time = time.time()

    # 获取优化器
    optimizer = get_advanced_optimizer()
    ttl = ttl or optimizer.config.get("distributed_cache_ttl", 3600)

    try:
        # 延迟导入以避免循环依赖
        from app.core.permission.hybrid_permission_cache import get_hybrid_cache

        hybrid_cache = get_hybrid_cache()

        # 1. 设置L1本地缓存
        try:
            hybrid_cache.l1_simple_cache.set(cache_key, permissions)
        except Exception as e:
            logging.warning(f"L1缓存设置失败: {e}")

        # 2. 设置L2分布式缓存
        try:
            hybrid_cache.distributed_cache_set(cache_key, permissions, ttl)
        except Exception as e:
            logging.error(f"L2分布式缓存设置失败: {e}")

        # 3. 更新预加载缓存
        if hasattr(optimizer, "preload_cache"):
            optimizer.preload_cache[cache_key] = permissions

        duration = time.time() - start_time
        _cache_monitor.record(
            "cache_set", duration, tags={"level": "hybrid", "success": "true"}
        )

    except Exception as e:
        duration = time.time() - start_time
        _cache_monitor.record(
            "cache_set", duration, tags={"level": "hybrid", "success": "false"}
        )
        logging.error(f"高级缓存设置失败: {e}")


async def advanced_batch_get_permissions(cache_keys: List[str]) -> Dict[str, Set[str]]:
    """
    高级批量获取权限。
    这个函数协调预加载、缓存检查和后台批量数据库查询。
    """
    optimizer = get_advanced_optimizer()
    if not optimizer:
        # 如果优化器未初始化，则返回空结果
        return {key: set() for key in cache_keys}

    results = {}
    missed_keys = []

    # 1. 首先检查预加载缓存
    for key in cache_keys:
        if key in optimizer.preload_cache:
            results[key] = optimizer.preload_cache[key]
        else:
            missed_keys.append(key)

    if not missed_keys:
        return results

    # 2. 对于未命中的键，使用后台批处理队列
    future = asyncio.get_running_loop().create_future()
    batch_item = (missed_keys, future)

    try:
        await optimizer.batch_queue.put(batch_item)
        # 等待后台任务完成并返回结果
        batch_results = await asyncio.wait_for(
            future, timeout=optimizer.config.get("batch_timeout", 1.0)
        )
        results.update(batch_results)
    except asyncio.TimeoutError:
        logging.warning(f"批量获取权限超时: {missed_keys}")
        for key in missed_keys:
            results[key] = set()  # 超时后返回空结果
    except Exception as e:
        logging.error(f"批量获取权限时发生错误: {e}", exc_info=True)
        for key in missed_keys:
            results[key] = set()

    return results


def advanced_batch_set_permissions(cache_data: Dict[str, Set[str]], ttl: int = None):
    """
    高级批量权限设置函数

    优化策略：
    1. 智能批量分组
    2. 并发处理
    3. 异步操作
    4. 性能监控
    """
    # 【修正】从优化器获取配置
    optimizer = get_advanced_optimizer()
    ttl = ttl or optimizer.config.get("distributed_cache_ttl", 3600)
    start_time = time.time()

    # 1. 批量更新本地缓存
    # 【依赖注入】从优化器获取客户端
    optimizer = get_advanced_optimizer()
    if optimizer is not None:
        redis_client = optimizer.redis_client
        for key, permissions in cache_data.items():
            redis_client.set(key, permissions)  # 直接从注入的客户端设置
    else:
        logging.warning("高级优化器不可用，跳过批量缓存设置")
        return

    # 2. 异步批量更新分布式缓存
    try:

        # 【修正】从优化器获取配置
        optimizer = get_advanced_optimizer()
        batch_size = optimizer.config.get("batch_size", 100)
        cache_items = list(cache_data.items())

        # 并发批量设置
        def batch_set_worker(batch, ttl):
            for key, permissions in batch:
                try:
                    # 【依赖注入】从优化器获取客户端
                    redis_client.set(key, permissions, ex=ttl)  # 直接从注入的客户端设置
                except Exception as e:
                    print(f"批量设置键 {key} 失败: {e}")

        threads = []
        for i in range(0, len(cache_items), batch_size):
            batch = cache_items[i : i + batch_size]
            thread = threading.Thread(target=batch_set_worker, args=(batch, ttl))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

    except Exception as e:
        print(f"高级批量分布式缓存设置失败: {e}")

    duration = time.time() - start_time
    print(
        f"高级批量设置完成，耗时: {duration*1000:.2f}ms，设置: {len(cache_data)} 个键"
    )


def advanced_invalidate_user_permissions(user_id: int):
    """
    高级用户权限失效函数

    优化策略：
    1. 智能延迟失效
    2. 批量失效操作
    3. 减少锁竞争
    4. 性能监控
    """
    try:
        # 生成需要失效的缓存键模式
        patterns = [
            f"perm:{user_id}:global:*",
            f"perm:{user_id}:server:*",
            f"perm:{user_id}:channel:*",
        ]

        # 使用优化的分布式锁
        optimizer = get_advanced_optimizer()
        if optimizer is not None:
            lock_key = f"invalidate_user:{user_id}"
            with optimizer.create_lock(lock_key, timeout=2.0):
                # 清除本地缓存
                # 【依赖注入】从优化器获取客户端
                redis_client = optimizer.redis_client
                keys_to_remove = []
                for key in list(
                    redis_client.scan_iter(f"perm:{user_id}:*")
                ):  # 使用scan_iter遍历所有匹配的键
                    if any(
                        pattern.replace("*", "") in key.decode() for pattern in patterns
                    ):
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    redis_client.delete(key)  # 直接从注入的客户端删除

                # 异步清除分布式缓存
                for pattern in patterns:
                    # 这里可以实现模式匹配删除
                    # 暂时使用简单的键删除
                    pass
        else:
            # 如果优化器不可用，跳过分布式锁操作
            logging.warning("高级优化器不可用，跳过用户权限失效操作")

    except Exception as e:
        print(f"高级用户权限失效失败: {e}")


def get_advanced_performance_stats() -> Dict[str, Any]:
    """
    获取高级性能统计信息
    """
    # 获取基础统计（避免应用上下文依赖）
    try:
        # from .permissions import get_cache_performance_stats # Original line commented out
        base_stats = get_stats()  # Use new helper function

        # 确保返回的是字典类型，避免类型混用
        local_cache_stats = base_stats.get("l1_cache", {})
        if not isinstance(local_cache_stats, dict):
            local_cache_stats = {}

        distributed_cache_stats = base_stats.get("l2_cache", {})
        if not isinstance(distributed_cache_stats, dict):
            distributed_cache_stats = {}

    except Exception as e:
        # 如果无法获取基础统计，使用默认值
        print(f"无法获取基础缓存统计: {e}")
        local_cache_stats = {"hit_rate": 0.0, "avg_time_ms": 0.0, "total_operations": 0}
        distributed_cache_stats = {
            "hit_rate": 0.0,
            "avg_time_ms": 0.0,
            "total_operations": 0,
        }

    # 获取高级统计
    optimizer = get_advanced_optimizer()
    if optimizer is not None:
        advanced_stats = {
            "local_cache": local_cache_stats,
            "distributed_cache": distributed_cache_stats,
            "optimization_config": optimizer.config,
            "advanced_stats": dict(optimizer._stats),
        }
    else:
        advanced_stats = {
            "local_cache": local_cache_stats,
            "distributed_cache": distributed_cache_stats,
            "optimization_config": {},
            "advanced_stats": {},
        }

    return advanced_stats


# 全局高级分布式优化器实例
# 【核心修改】移除此处的全局实例化
# _advanced_optimizer = AdvancedDistributedOptimizer()


# 性能监控装饰器
def advanced_monitor_performance(operation_type: str):
    """高级性能监控装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # 记录高级统计
                optimizer = get_advanced_optimizer()
                if optimizer is not None:
                    optimizer._stats[f"{operation_type}_success"] += 1
                    optimizer._stats[f"{operation_type}_total_time"] += duration

                return result
            except Exception as e:
                duration = time.time() - start_time

                # 记录失败统计
                optimizer = get_advanced_optimizer()
                if optimizer is not None:
                    optimizer._stats[f"{operation_type}_failure"] += 1
                    optimizer._stats[f"{operation_type}_total_time"] += duration

                raise e

        return wrapper

    return decorator
