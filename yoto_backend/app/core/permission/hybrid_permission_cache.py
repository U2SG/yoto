"""
混合权限缓存模块

使用自定义缓存，
实现高性能的混合缓存策略。

功能特性：
- 简单查询：使用自定义缓存
- 复杂逻辑：使用自定义缓存
- 批量操作：批量失效、批量预加载
- 条件缓存：基于复杂条件的缓存策略
- 分层缓存：多级缓存架构
- 智能失效：基于业务逻辑的失效策略
- 缓存预热：预加载常用数据
- 详细监控：性能统计和分析
- 权限继承：复杂的权限计算逻辑
- 动态策略：自适应缓存配置
- 一致性保证：缓存一致性检查
- 分布式协调：多节点缓存同步

弃用警告：
- 兼容性函数将在v2.0.0版本中移除
- 请尽快迁移到新的API接口
- 迁移指南：请参考文档中的API迁移指南
"""

import time
import logging
import pickle
import hashlib
import threading
import json
import gzip
import warnings
from typing import Dict, List, Optional, Set, Any, Tuple, Union, Callable
from collections import OrderedDict, defaultdict, Counter
from functools import lru_cache, wraps
import redis
from dataclasses import dataclass, field
from enum import Enum

# 移除循环依赖，改为延迟导入
from app.core.permission.advanced_optimization import (
    advanced_get_permissions_from_cache,
    advanced_batch_get_permissions,
    get_advanced_optimizer,
)
import asyncio
from redis.cluster import RedisCluster

logger = logging.getLogger(__name__)

# ==================== 弃用警告系统 ====================


def deprecated(reason: str = None, version: str = "2.0.0", replacement: str = None):
    """
    弃用警告装饰器

    参数:
        reason (str): 弃用原因
        version (str): 移除版本
        replacement (str): 替代API
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 构建警告消息
            warning_msg = f"函数 {func.__name__} 已被弃用"
            if reason:
                warning_msg += f"，原因：{reason}"
            warning_msg += f"，将在版本 {version} 中移除"
            if replacement:
                warning_msg += f"，请使用 {replacement} 替代"

            # 记录警告日志
            logger.warning(warning_msg)

            # 显示弃用警告
            warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)

            return func(*args, **kwargs)

        return wrapper

    return decorator


# 弃用时间表
DEPRECATION_TIMELINE = {
    "current_version": "1.5.0",
    "deprecation_start": "1.5.0",
    "removal_version": "2.0.0",
    "migration_deadline": "1.9.0",
}


def get_deprecation_info():
    """获取弃用信息"""
    return {
        "current_version": DEPRECATION_TIMELINE["current_version"],
        "removal_version": DEPRECATION_TIMELINE["removal_version"],
        "migration_deadline": DEPRECATION_TIMELINE["migration_deadline"],
        "message": f"兼容性函数将在 {DEPRECATION_TIMELINE['removal_version']} 版本中移除，请在 {DEPRECATION_TIMELINE['migration_deadline']} 前完成迁移",
    }


# ==================== 监控装饰器 ====================


def monitored_cache(level: str):
    """缓存监控装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                logger.debug(
                    f"缓存操作 {level}: {func.__name__} 耗时 {response_time:.3f}s"
                )
                return result
            except Exception as e:
                logger.error(f"缓存操作失败 {level}: {func.__name__}, 错误: {e}")
                raise

        return wrapper

    return decorator


# ==================== 缓存级别枚举 ====================


class CacheLevel(Enum):
    """缓存级别枚举"""

    SIMPLE = "simple"  # 简单查询，使用lru_cache
    COMPLEX = "complex"  # 复杂查询，使用自定义缓存
    DISTRIBUTED = "distributed"  # 分布式查询，使用Redis
    HYBRID = "hybrid"  # 混合查询，多级缓存


# ==================== 缓存策略配置 ====================


@dataclass
class CacheStrategy:
    """缓存策略配置"""

    level: CacheLevel
    maxsize: int = 1000
    ttl: int = 300
    compression: bool = True
    monitoring: bool = True
    auto_tune: bool = True


# ==================== 复杂查询的自定义缓存 ====================


class ComplexPermissionCache:
    """复杂权限缓存 - 处理复杂的业务逻辑，支持分策略缓存"""

    def __init__(self, maxsize: int = 10000):
        self.maxsize = maxsize
        self.lock = threading.RLock()

        # 优化缓存策略配置 - 提高命中率
        self.strategies = {
            "user_permissions": CacheStrategy(
                CacheLevel.COMPLEX, maxsize=8000, ttl=900
            ),  # 增加容量和TTL
            "role_permissions": CacheStrategy(
                CacheLevel.COMPLEX, maxsize=5000, ttl=1200
            ),  # 增加容量和TTL
            "inheritance_tree": CacheStrategy(
                CacheLevel.COMPLEX, maxsize=3000, ttl=2400
            ),  # 增加容量和TTL
            "conditional_permissions": CacheStrategy(
                CacheLevel.COMPLEX, maxsize=2000, ttl=600
            ),  # 增加容量和TTL
        }

        # 为每种策略创建独立的缓存实例
        self.strategy_caches = {}
        self.strategy_stats = {}

        for strategy_name, strategy_config in self.strategies.items():
            self.strategy_caches[strategy_name] = {
                "cache": OrderedDict(),
                "access_patterns": defaultdict(int),
                "creation_times": {},
                "last_access_times": {},
                "hit_count": 0,
                "miss_count": 0,
                "maxsize": strategy_config.maxsize,
                "ttl": strategy_config.ttl,
            }
            self.strategy_stats[strategy_name] = {
                "hits": 0,
                "misses": 0,
                "size": 0,
                "maxsize": strategy_config.maxsize,
            }

    def _get_strategy_cache(self, strategy_name: str = "user_permissions"):
        """获取指定策略的缓存实例"""
        if strategy_name not in self.strategy_caches:
            # 如果策略不存在，使用默认策略
            strategy_name = "user_permissions"
        return self.strategy_caches[strategy_name]

    def _get_strategy_config(self, strategy_name: str = "user_permissions"):
        """获取指定策略的配置"""
        return self.strategies.get(strategy_name, self.strategies["user_permissions"])

    @monitored_cache("complex_get")
    def get(
        self, key: str, strategy_name: str = "user_permissions"
    ) -> Optional[Set[str]]:
        """获取缓存值 - 支持分策略缓存"""
        strategy_cache = self._get_strategy_cache(strategy_name)

        with self.lock:
            if key in strategy_cache["cache"]:
                # 检查TTL
                strategy_config = self._get_strategy_config(strategy_name)
                current_time = time.time()
                creation_time = strategy_cache["creation_times"].get(key, 0)

                if current_time - creation_time > strategy_config.ttl:
                    # 缓存已过期，删除
                    del strategy_cache["cache"][key]
                    if key in strategy_cache["creation_times"]:
                        del strategy_cache["creation_times"][key]
                    if key in strategy_cache["last_access_times"]:
                        del strategy_cache["last_access_times"][key]
                    strategy_cache["miss_count"] += 1
                    return None

                # 更新访问时间
                strategy_cache["last_access_times"][key] = current_time
                strategy_cache["cache"].move_to_end(key)
                strategy_cache["hit_count"] += 1
                strategy_cache["access_patterns"][key] += 1

                # 更新统计
                self.strategy_stats[strategy_name]["hits"] += 1
                return strategy_cache["cache"][key]

            strategy_cache["miss_count"] += 1
            self.strategy_stats[strategy_name]["misses"] += 1
            return None

    @monitored_cache("complex_set")
    def set(self, key: str, value: Set[str], strategy_name: str = "user_permissions"):
        """设置缓存值 - 支持分策略缓存"""
        strategy_cache = self._get_strategy_cache(strategy_name)
        strategy_config = self._get_strategy_config(strategy_name)

        with self.lock:
            if key in strategy_cache["cache"]:
                # 更新现有值
                strategy_cache["cache"].move_to_end(key)
                strategy_cache["last_access_times"][key] = time.time()
            else:
                # 检查容量限制
                if len(strategy_cache["cache"]) >= strategy_cache["maxsize"]:
                    self._evict_lru(strategy_name)

                strategy_cache["creation_times"][key] = time.time()
                strategy_cache["last_access_times"][key] = time.time()

            strategy_cache["cache"][key] = value

            # 更新统计
            self.strategy_stats[strategy_name]["size"] = len(strategy_cache["cache"])

    def _evict_lru(self, strategy_name: str = "user_permissions"):
        """淘汰最近最少使用的项 - 分策略"""
        strategy_cache = self._get_strategy_cache(strategy_name)

        if not strategy_cache["cache"]:
            return

        # 找到最久未访问的项并移除
        lru_key, _ = strategy_cache["cache"].popitem(last=False)

        # 清理相关的时间记录
        if lru_key in strategy_cache["creation_times"]:
            del strategy_cache["creation_times"][lru_key]
        if lru_key in strategy_cache["last_access_times"]:
            del strategy_cache["last_access_times"][lru_key]

        # 更新统计
        self.strategy_stats[strategy_name]["size"] = len(strategy_cache["cache"])

    def batch_get(
        self, keys: List[str], strategy_name: str = "user_permissions"
    ) -> Dict[str, Optional[Set[str]]]:
        """批量获取缓存值 - 支持分策略"""
        with self.lock:
            result = {}
            for key in keys:
                result[key] = self.get(key, strategy_name)
            return result

    def batch_set(
        self,
        key_value_pairs: Dict[str, Set[str]],
        strategy_name: str = "user_permissions",
    ):
        """批量设置缓存值 - 支持分策略"""
        with self.lock:
            for key, value in key_value_pairs.items():
                self.set(key, value, strategy_name)

    def remove_pattern(
        self, pattern: str, strategy_name: str = "user_permissions"
    ) -> int:
        """按模式移除缓存项 - 支持分策略"""
        strategy_cache = self._get_strategy_cache(strategy_name)

        with self.lock:
            keys_to_remove = []
            for key in strategy_cache["cache"].keys():
                if pattern in key:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del strategy_cache["cache"][key]
                if key in strategy_cache["creation_times"]:
                    del strategy_cache["creation_times"][key]
                if key in strategy_cache["last_access_times"]:
                    del strategy_cache["last_access_times"][key]

            # 更新统计
            self.strategy_stats[strategy_name]["size"] = len(strategy_cache["cache"])
            return len(keys_to_remove)

    def get_stats(self, strategy_name: str = None) -> Dict[str, Any]:
        """获取缓存统计 - 支持分策略"""
        with self.lock:
            if strategy_name:
                # 获取指定策略的统计
                strategy_cache = self._get_strategy_cache(strategy_name)
                total_requests = (
                    strategy_cache["hit_count"] + strategy_cache["miss_count"]
                )
                hit_rate = strategy_cache["hit_count"] / max(total_requests, 1)

                return {
                    "strategy": strategy_name,
                    "size": len(strategy_cache["cache"]),
                    "maxsize": strategy_cache["maxsize"],
                    "hits": strategy_cache["hit_count"],
                    "misses": strategy_cache["miss_count"],
                    "hit_rate": hit_rate,
                    "access_patterns": dict(strategy_cache["access_patterns"]),
                    "avg_age": self._calculate_average_age(strategy_name),
                }
            else:
                # 获取所有策略的统计
                all_stats = {}
                for strategy in self.strategies.keys():
                    all_stats[strategy] = self.get_stats(strategy)
                return all_stats

    def _calculate_average_age(self, strategy_name: str = "user_permissions") -> float:
        """计算平均缓存年龄 - 分策略"""
        strategy_cache = self._get_strategy_cache(strategy_name)

        if not strategy_cache["creation_times"]:
            return 0.0

        current_time = time.time()
        ages = [
            current_time - creation_time
            for creation_time in strategy_cache["creation_times"].values()
        ]
        return sum(ages) / len(ages)

    def clear(self, strategy_name: str = None):
        """清空缓存 - 支持分策略"""
        with self.lock:
            if strategy_name:
                # 清空指定策略的缓存
                strategy_cache = self._get_strategy_cache(strategy_name)
                strategy_cache["cache"].clear()
                strategy_cache["access_patterns"].clear()
                strategy_cache["creation_times"].clear()
                strategy_cache["last_access_times"].clear()
                strategy_cache["hit_count"] = 0
                strategy_cache["miss_count"] = 0
                self.strategy_stats[strategy_name]["size"] = 0
            else:
                # 清空所有策略的缓存
                for strategy in self.strategies.keys():
                    self.clear(strategy)

    def remove(self, key: str, strategy_name: str = "user_permissions") -> bool:
        """移除指定键 - 线程安全，支持分策略"""
        strategy_cache = self._get_strategy_cache(strategy_name)

        with self.lock:
            if key in strategy_cache["cache"]:
                del strategy_cache["cache"][key]
                if key in strategy_cache["creation_times"]:
                    del strategy_cache["creation_times"][key]
                if key in strategy_cache["last_access_times"]:
                    del strategy_cache["last_access_times"][key]

                # 更新统计
                self.strategy_stats[strategy_name]["size"] = len(
                    strategy_cache["cache"]
                )
                return True
            return False

    def get_strategy_info(self) -> Dict[str, Any]:
        """获取所有策略的详细信息"""
        with self.lock:
            info = {
                "strategies": {},
                "total_size": 0,
                "total_hits": 0,
                "total_misses": 0,
            }

            for strategy_name in self.strategies.keys():
                strategy_cache = self._get_strategy_cache(strategy_name)
                strategy_config = self._get_strategy_config(strategy_name)

                total_requests = (
                    strategy_cache["hit_count"] + strategy_cache["miss_count"]
                )
                hit_rate = strategy_cache["hit_count"] / max(total_requests, 1)

                info["strategies"][strategy_name] = {
                    "maxsize": strategy_config.maxsize,
                    "ttl": strategy_config.ttl,
                    "size": len(strategy_cache["cache"]),
                    "hits": strategy_cache["hit_count"],
                    "misses": strategy_cache["miss_count"],
                    "hit_rate": hit_rate,
                    "utilization": len(strategy_cache["cache"])
                    / strategy_config.maxsize,
                }

                info["total_size"] += len(strategy_cache["cache"])
                info["total_hits"] += strategy_cache["hit_count"]
                info["total_misses"] += strategy_cache["miss_count"]

            total_requests = info["total_hits"] + info["total_misses"]
            info["overall_hit_rate"] = info["total_hits"] / max(total_requests, 1)

            return info


# ==================== 分布式缓存管理器 ====================


class DistributedCacheManager:
    """分布式缓存管理器 - 使用Redis集群"""

    def __init__(self):
        self.redis_client = None
        self.stats = Counter()  # 使用Counter替代字典

    def _get_redis_client(self):
        """获取Redis客户端"""
        if self.redis_client is None:
            try:
                from flask import current_app

                if current_app:
                    self.redis_client = current_app.extensions.get("redis_client")
                    if self.redis_client is None:
                        logger.warning("无法从应用扩展获取Redis客户端")
                        return None
                else:
                    logger.warning("当前不在应用上下文中")
                    return None
            except Exception as e:
                logger.error(f"获取Redis客户端失败: {e}")
                return None
        return self.redis_client

    def _get_redis_pipeline(self):
        """获取Redis管道"""
        redis_client = self._get_redis_client()
        if not redis_client:
            return None

        try:
            return redis_client.pipeline()
        except Exception as e:
            logger.error(f"创建Redis管道失败: {e}")
            return None

    @monitored_cache("redis_get")
    def get(self, key: str) -> Optional[Set[str]]:
        """从Redis获取权限数据"""
        redis_client = self._get_redis_client()
        if not redis_client:
            return None

        try:
            data = redis_client.get(key)
            if data is not None:
                self.stats["hits"] += 1
                return self._deserialize_permissions(data)
            else:
                self.stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Redis获取失败: {e}")
            return None

    @monitored_cache("redis_set")
    def set(self, key: str, value: Set[str], ttl: int = 300):
        """设置权限数据到Redis"""
        redis_client = self._get_redis_client()
        if not redis_client:
            return False

        try:
            data = self._serialize_permissions(value)
            redis_client.setex(key, ttl, data)
            self.stats["sets"] += 1
            return True
        except Exception as e:
            logger.error(f"Redis设置失败: {e}")
            return False

    def batch_get(self, keys: List[str]) -> Dict[str, Optional[Set[str]]]:
        """批量获取权限数据"""
        pipeline = self._get_redis_pipeline()
        if not pipeline:
            return {}

        try:
            # 批量获取
            for key in keys:
                pipeline.get(key)

            # 执行批量操作
            results = pipeline.execute()

            # 处理结果
            data = {}
            for i, key in enumerate(keys):
                result = results[i]
                if result is not None:
                    self.stats["hits"] += 1
                    data[key] = self._deserialize_permissions(result)
                else:
                    self.stats["misses"] += 1
                    data[key] = None

            self.stats["batch_operations"] += 1
            return data
        except Exception as e:
            logger.error(f"Redis批量获取失败: {e}")
            return {}

    def batch_set(self, key_value_pairs: Dict[str, Set[str]], ttl: int = 300):
        """批量设置权限数据"""
        pipeline = self._get_redis_pipeline()
        if not pipeline:
            return False

        try:
            # 批量设置
            for key, value in key_value_pairs.items():
                data = self._serialize_permissions(value)
                pipeline.setex(key, ttl, data)

            # 执行批量操作
            pipeline.execute()
            self.stats["sets"] += len(key_value_pairs)
            self.stats["batch_operations"] += 1
            return True
        except Exception as e:
            logger.error(f"Redis批量设置失败: {e}")
            return False

    def batch_delete(self, keys: List[str]) -> bool:
        """批量删除缓存值 - 使用管道优化"""
        # 检查空列表
        if not keys:
            return True

        pipeline = self._get_redis_pipeline()
        if not pipeline:
            return False

        try:
            # 批量删除
            pipeline.delete(*keys)

            # 执行批量操作
            pipeline.execute()
            self.stats["deletes"] += len(keys)
            self.stats["batch_operations"] += 1
            return True
        except Exception as e:
            logger.error(f"Redis批量删除失败: {e}")
            return False

    def scan_keys(self, pattern: str, batch_size: int = 100) -> List[str]:
        """扫描Redis键，使用SCAN命令优化"""
        redis_client = self.redis_client
        if not redis_client:
            return []

        try:
            keys = []
            cursor = 0

            while True:
                cursor, batch_keys = redis_client.scan(
                    cursor=cursor, match=pattern, count=batch_size
                )
                keys.extend(batch_keys)

                if cursor == 0:
                    break

            return keys
        except Exception as e:
            logger.error(f"Redis键扫描失败: {e}")
            return []

    def invalidate_pattern(self, pattern: str) -> int:
        """按模式失效缓存"""
        keys = self.scan_keys(pattern)
        if keys:
            self.batch_delete(keys)
            return len(keys)
        return 0

    def _serialize_permissions(self, permissions: Set[str]) -> bytes:
        """序列化权限数据"""
        data = json.dumps(list(permissions), ensure_ascii=False).encode("utf-8")
        return gzip.compress(data)

    def _deserialize_permissions(self, data: bytes) -> Set[str]:
        """反序列化权限数据"""
        try:
            uncompressed = gzip.decompress(data)
            permissions_list = json.loads(uncompressed.decode("utf-8"))
            return set(permissions_list)
        except Exception as e:
            logger.error(f"权限数据反序列化失败: {e}")
            return set()


# ==================== 混合缓存管理器 ====================


class HybridPermissionCache:
    """混合权限缓存管理器"""

    def __init__(self, app=None, distributed_lock_manager=None):
        # 创建L1简单权限缓存实例，作为处理简单、高频查询的唯一缓存
        self.l1_simple_cache = ComplexPermissionCache(maxsize=5000)
        self.complex_cache = ComplexPermissionCache()
        self.distributed_cache = DistributedCacheManager()

        # 依赖注入分布式锁管理器
        self._distributed_lock_manager = distributed_lock_manager

        # 使用Counter替代字典，避免类型混用
        self.stats = Counter(
            {
                "simple_requests": 0,
                "complex_requests": 0,
                "distributed_requests": 0,
                "hybrid_requests": 0,
                "basic_requests": 0,  # 添加basic_requests统计
                "cache_hits": 0,
                "cache_misses": 0,
            }
        )

        # 缓存策略映射
        self.strategy_mapping = {
            "basic": self._get_simple_permission,
            "simple": self._get_simple_permission,  # 添加simple别名
            "complex": self._get_complex_permission,
            "distributed": self._get_distributed_permission,
            "hybrid": self._get_hybrid_permission,
        }

        # 初始化所有策略的统计键
        self._init_stats_keys()

        self.redis_client = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """延迟初始化，从 app.extensions 获取依赖"""
        self.redis_client = app.extensions.get("redis_client")
        if self.redis_client is None:
            logger.warning(
                "HybridPermissionCache 未能获取到Redis客户端，分布式缓存将不可用"
            )

        # 分布式锁管理器是可选的，如果没有则使用无锁模式
        if self._distributed_lock_manager is None:
            logger.warning("HybridPermissionCache 未配置分布式锁管理器，将使用无锁模式")

        # 将自身实例存入app扩展中，方便全局访问
        if "hybrid_cache" not in app.extensions:
            app.extensions["hybrid_cache"] = self

    def _init_stats_keys(self):
        """初始化所有策略的统计键"""
        for strategy in self.strategy_mapping.keys():
            stats_key = f"{strategy}_requests"
            # Counter会自动处理不存在的键，但为了明确性，我们确保键存在
            if stats_key not in self.stats:
                self.stats[stats_key] = 0

    # ==================== 简单权限查询方法 ====================

    def check_basic_permission(self, user_id: int, permission: str) -> bool:
        """
        检查基础权限 - 使用L1简单缓存

        适用于：
        - 简单的权限检查
        - 高频访问的权限
        - 支持精确失效的权限
        """
        # 构建缓存键
        cache_key = f"basic_perm:{{{user_id}}}:{permission}"

        # 查询L1缓存
        result = self.l1_simple_cache.get(cache_key)
        if result is not None:
            return result

        # 基础权限集合
        basic_permissions = {
            "read_channel",
            "read_message",
            "view_member_list",
            "send_message",
            "edit_message",
            "delete_message",
            "create_channel",
            "manage_channel",
            "manage_server",
        }

        # 计算权限结果
        result = permission in basic_permissions

        # 缓存结果到L1缓存
        self.l1_simple_cache.set(cache_key, result)
        return result

    def is_user_active(self, user_id: int) -> bool:
        """检查用户是否活跃 - 使用L1简单缓存"""
        # 构建缓存键
        cache_key = f"user_active:{{{user_id}}}"

        # 查询L1缓存
        result = self.l1_simple_cache.get(cache_key)
        if result is not None:
            return result

        # 模拟检查
        result = user_id > 0 and user_id < 1000000

        # 缓存结果到L1缓存
        self.l1_simple_cache.set(cache_key, result)
        return result

    def get_user_role_level(self, user_id: int) -> int:
        """获取用户角色等级 - 使用L1简单缓存"""
        # 构建缓存键
        cache_key = f"user_role:{{{user_id}}}"

        # 查询L1缓存
        result = self.l1_simple_cache.get(cache_key)
        if result is not None:
            return result

        # 模拟角色等级计算
        result = (user_id % 5) + 1

        # 缓存结果到L1缓存
        self.l1_simple_cache.set(cache_key, result)
        return result

    def check_permission_inheritance(
        self, user_id: int, permission: str, parent_permission: str
    ) -> bool:
        """检查权限继承 - 使用L1简单缓存"""
        # 构建缓存键
        cache_key = f"inheritance:{{{user_id}}}:{permission}:{parent_permission}"

        # 查询L1缓存
        result = self.l1_simple_cache.get(cache_key)
        if result is not None:
            return result

        # 模拟权限继承逻辑
        inheritance_rules = {
            "manage_server": ["manage_channel", "create_channel"],
            "manage_channel": ["send_message", "edit_message"],
            "admin": ["manage_server", "manage_channel"],
        }

        if parent_permission in inheritance_rules:
            result = permission in inheritance_rules[parent_permission]
        else:
            result = False

        # 缓存结果到L1缓存
        self.l1_simple_cache.set(cache_key, result)
        return result

    @monitored_cache("hybrid")
    def get_permission(
        self,
        user_id: int,
        permission: str,
        strategy: str = "hybrid",
        scope: str = None,
        scope_id: int = None,
    ) -> Union[bool, Set[str]]:
        """
        获取权限 - 根据策略选择缓存方式

        参数:
            user_id: 用户ID
            permission: 权限名称
            strategy: 缓存策略 ('basic', 'complex', 'distributed', 'hybrid')
            scope: 权限作用域
            scope_id: 作用域ID

        返回:
            bool 或 Set[str]: 权限检查结果
        """
        if strategy not in self.strategy_mapping:
            raise ValueError(f"不支持的缓存策略: {strategy}")

        # 更新统计 - Counter会自动处理
        stats_key = f"{strategy}_requests"
        self.stats[stats_key] += 1

        return self.strategy_mapping[strategy](user_id, permission, scope, scope_id)

    def _get_simple_permission(
        self, user_id: int, permission: str, scope: str = None, scope_id: int = None
    ) -> bool:
        """获取简单权限 - 使用实例的simple_cache"""
        try:
            # 构建缓存键
            cache_key = f"basic_perm:{{{user_id}}}:{permission}"

            # 查询实例的simple_cache
            result = self.l1_simple_cache.get(cache_key)
            if result is not None:
                return result

            # 基础权限集合
            basic_permissions = {
                "read_channel",
                "read_message",
                "view_member_list",
                "send_message",
                "edit_message",
                "delete_message",
                "create_channel",
                "manage_channel",
                "manage_server",
            }

            # 计算权限结果
            result = permission in basic_permissions

            # 缓存结果到实例的simple_cache
            self.l1_simple_cache.set(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"简单权限查询失败: {e}")
            return False

    def _get_complex_permission(
        self, user_id: int, permission: str, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """获取复杂权限 - 使用统一缓存键"""
        # 使用统一的缓存键 - 所有策略使用相同前缀
        cache_key = f"perm:{_make_perm_cache_key(user_id, scope, scope_id)}"

        # 1. 查询复杂缓存（L1）
        result = self.complex_cache.get(cache_key, strategy_name="user_permissions")
        if result is not None:
            self.stats["cache_hits"] += 1
            return result

        # 2. 查询分布式缓存（L2）
        result = self.distributed_cache.get(cache_key)
        if result is not None:
            self.stats["cache_hits"] += 1
            # 回填到复杂缓存（L1）
            self.complex_cache.set(cache_key, result, strategy_name="user_permissions")
            return result

        self.stats["cache_misses"] += 1

        # 3. 查询数据库
        permissions = self._query_complex_permissions(user_id, scope, scope_id)

        # 4. 同时缓存到所有层级，并维护用户索引
        self.complex_cache.set(cache_key, permissions, strategy_name="user_permissions")
        self.distributed_cache.set(cache_key, permissions, ttl=600)

        # 添加到用户索引
        self._add_to_user_index(user_id, cache_key)

        return permissions

    def _get_distributed_permission(
        self, user_id: int, permission: str, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """获取分布式权限 - 使用统一缓存键"""
        # 使用统一的缓存键 - 所有策略使用相同前缀
        cache_key = f"perm:{_make_perm_cache_key(user_id, scope, scope_id)}"

        # 1. 查询复杂缓存（L1）
        result = self.complex_cache.get(cache_key, strategy_name="role_permissions")
        if result is not None:
            self.stats["cache_hits"] += 1
            return result

        # 2. 查询分布式缓存（L2）
        result = self.distributed_cache.get(cache_key)
        if result is not None:
            self.stats["cache_hits"] += 1
            # 回填到复杂缓存（L1）
            self.complex_cache.set(cache_key, result, strategy_name="role_permissions")
            return result

        self.stats["cache_misses"] += 1

        # 3. 模拟分布式权限查询
        permissions = self._query_distributed_permissions(user_id, scope, scope_id)

        # 4. 同时缓存到所有层级，并维护用户索引
        self.complex_cache.set(cache_key, permissions, strategy_name="role_permissions")
        self.distributed_cache.set(cache_key, permissions, ttl=600)

        # 添加到用户索引
        self._add_to_user_index(user_id, cache_key)

        return permissions

    def _get_hybrid_permission(
        self, user_id: int, permission: str, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """获取混合权限 - L1->L2->高级优化->DB统一查询路径"""
        # 使用统一的缓存键
        cache_key = f"perm:{_make_perm_cache_key(user_id, scope, scope_id)}"

        # 1. 先查简单权限 (lru_cache)
        if self._is_simple_permission(permission):
            simple_result = self._get_simple_permission(
                user_id, permission, scope, scope_id
            )
            if simple_result:
                return {permission}

        # 2. 查询复杂缓存（L1）
        result = self.complex_cache.get(
            cache_key, strategy_name="conditional_permissions"
        )
        if result is not None:
            self.stats["cache_hits"] += 1
            return result

        # 3. 查询分布式缓存（L2）
        result = self.distributed_cache.get(cache_key)
        if result is not None:
            self.stats["cache_hits"] += 1
            # 回填到复杂缓存（L1）
            self.complex_cache.set(
                cache_key, result, strategy_name="conditional_permissions"
            )
            return result

        self.stats["cache_misses"] += 1

        # 4. 【核心修改】通过高级优化模块获取权限，而不是直接查询数据库
        permissions = advanced_get_permissions_from_cache(cache_key)

        # 5. 同时缓存到所有层级，并维护用户索引
        if permissions is not None:
            self.complex_cache.set(
                cache_key, permissions, strategy_name="conditional_permissions"
            )
            self.distributed_cache.set(cache_key, permissions, ttl=600)
            self._add_to_user_index(user_id, cache_key)

        return permissions if permissions is not None else set()

    def _is_simple_permission(self, permission: str) -> bool:
        """判断是否为简单权限"""
        simple_permissions = {
            "read_channel",
            "read_message",
            "view_member_list",
            "send_message",
            "edit_message",
            "delete_message",
        }
        return permission in simple_permissions

    def _query_complex_permissions(
        self, user_id: int, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """查询复杂权限 - 智能缓存策略"""
        # 模拟复杂权限查询逻辑，但增加缓存友好的设计

        # 1. 基础权限（所有用户都有）
        base_permissions = {"read_channel", "send_message"}

        # 2. 基于用户角色的权限（缓存友好）
        user_role = user_id % 5  # 模拟用户角色
        if user_role == 0:  # 管理员
            base_permissions.update(
                {"manage_server", "manage_channel", "create_channel", "admin"}
            )
        elif user_role == 1:  # 版主
            base_permissions.update(
                {"manage_channel", "edit_message", "delete_message"}
            )
        elif user_role == 2:  # 普通用户
            base_permissions.update({"read_message", "view_member_list"})
        elif user_role == 3:  # VIP用户
            base_permissions.update({"premium_feature", "advanced_search"})
        else:  # 新用户
            base_permissions.update({"read_channel"})

        # 3. 基于作用域的权限（缓存友好）
        if scope == "server":
            base_permissions.update({"manage_server", "create_channel"})
        elif scope == "channel":
            base_permissions.update({"edit_message", "delete_message"})

        # 4. 基于作用域ID的权限（有限变化）
        if scope_id and scope_id > 50:  # 高级服务器/频道
            base_permissions.add("premium_feature")

        return base_permissions

    def _query_distributed_permissions(
        self, user_id: int, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """查询分布式权限"""
        # 模拟分布式权限查询
        permissions = self._query_complex_permissions(user_id, scope, scope_id)

        # 添加分布式特定权限
        if scope_id and scope_id > 1000:
            permissions.add("premium_feature")

        return permissions

    def _query_hybrid_permissions(
        self, user_id: int, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """查询混合权限"""
        # 合并所有权限查询逻辑
        permissions = self._query_complex_permissions(user_id, scope, scope_id)
        permissions.update(
            self._query_distributed_permissions(user_id, scope, scope_id)
        )

        # 添加混合特定逻辑
        if user_id > 100 and scope_id and scope_id < 500:
            permissions.add("hybrid_feature")

        return permissions

    def _batch_query_from_db(
        self,
        user_ids: List[int],
        permission: str,
        scope: str = None,
        scope_id: int = None,
    ) -> Dict[int, Set[str]]:
        """批量查询数据库 - 使用真正的批量数据库查询"""
        try:
            # 导入真正的批量查询函数
            from .permission_queries import batch_precompute_permissions

            # 使用真正的批量数据库查询
            results = batch_precompute_permissions(user_ids, scope, scope_id)

            logger.debug(
                f"批量数据库查询: {len(user_ids)} 个用户, 命中 {len(results)} 个结果"
            )
            return results

        except ImportError:
            # 如果导入失败，使用模拟数据作为后备
            logger.warning("无法导入permission_queries模块，使用模拟数据")
            results = {}
            for user_id in user_ids:
                base_permissions = {"read_channel", "send_message", "manage_channel"}

                if scope == "server":
                    base_permissions.update({"manage_server", "create_channel"})
                elif scope == "channel":
                    base_permissions.update({"edit_message", "delete_message"})

                if user_id % 3 == 0:
                    base_permissions.add("hybrid_feature")

                results[user_id] = base_permissions

            return results
        except Exception as e:
            logger.error(f"批量数据库查询失败: {e}")
            return {user_id: set() for user_id in user_ids}

    @monitored_cache("batch")
    def batch_get_permissions(
        self,
        user_ids: List[int],
        permission: str,
        strategy: str = "hybrid",
        scope: str = None,
        scope_id: int = None,
    ) -> Dict[int, Union[bool, Set[str]]]:
        """批量获取权限 - 增强版，集成高级优化"""
        # 1. 为所有 user_id 构建批量的缓存键
        cache_keys = {}
        for uid in user_ids:
            cache_key = _make_perm_cache_key(uid, scope, scope_id)
            cache_keys[uid] = f"perm:{cache_key}"

        # 2. 批量从 L1 (complex_cache) 获取
        l1_cache_keys = list(cache_keys.values())
        l1_results = self.complex_cache.batch_get(
            l1_cache_keys, strategy_name="user_permissions"
        )

        # 3. 找出 L1 未命中的，批量从 L2 (redis) 获取
        l1_missed_keys = [k for k, v in l1_results.items() if v is None]
        l2_results = {}
        if l1_missed_keys:
            l2_results = self.distributed_cache.batch_get(l1_missed_keys)

        # 合并 L1 和 L2 的结果
        all_cache_results = l1_results.copy()
        all_cache_results.update(l2_results)

        # 4. 找出 L2 仍然未命中的，通过高级优化模块进行批量获取
        l2_missed_keys = [k for k, v in l2_results.items() if v is None]
        db_results_by_key = {}
        if l2_missed_keys:
            optimizer = get_advanced_optimizer()
            if optimizer and optimizer.loop:
                # 从同步代码安全地调用异步函数
                future = asyncio.run_coroutine_threadsafe(
                    advanced_batch_get_permissions(l2_missed_keys), optimizer.loop
                )
                try:
                    # 设置超时以避免无限期阻塞
                    db_results_by_key = future.result(
                        timeout=optimizer.config.get("batch_timeout", 1.0) + 0.5
                    )
                except Exception as e:
                    logger.error(f"批量获取权限失败: {e}", exc_info=True)
                    db_results_by_key = {key: set() for key in l2_missed_keys}
            else:
                # 如果优化器或其事件循环不可用，则退回到旧逻辑
                l2_missed_uids = [
                    uid for uid, key in cache_keys.items() if key in l2_missed_keys
                ]
                db_results_by_uid = self._batch_query_from_db(
                    l2_missed_uids, permission, scope, scope_id
                )
                # 需要将结果的键从uid转换回cache_key
                uid_to_key_map = {uid: key for uid, key in cache_keys.items()}
                db_results_by_key = {
                    uid_to_key_map[uid]: perms
                    for uid, perms in db_results_by_uid.items()
                }

        # 5. 合并所有结果，并批量回填 L1 和 L2
        final_results = {}
        cache_updates_l1 = {}
        cache_updates_l2 = {}

        for uid, cache_key in cache_keys.items():
            perms = all_cache_results.get(cache_key) or db_results_by_key.get(cache_key)
            if perms is not None:
                final_results[uid] = perms
                if cache_key in l2_missed_keys:
                    cache_updates_l1[cache_key] = perms
                    cache_updates_l2[cache_key] = perms
            else:
                final_results[uid] = set()

        # 批量回填缓存
        if cache_updates_l1:
            self.complex_cache.batch_set(
                cache_updates_l1, strategy_name="user_permissions"
            )
        if cache_updates_l2:
            self.distributed_cache.batch_set(cache_updates_l2)

            # 维护用户索引
            for uid, cache_key in cache_keys.items():
                if uid in db_results_by_key:
                    self._add_to_user_index(uid, cache_key)

        return final_results

    @monitored_cache("invalidate")
    def invalidate_user_permissions(self, user_id: int):
        """失效用户权限缓存 - 使用索引机制"""
        # 失效简单权限缓存（使用实例的simple_cache）

        # 失效基础权限缓存
        pattern = f"basic_perm:{user_id}:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效用户活跃状态缓存
        pattern = f"user_active:{user_id}"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效用户角色缓存
        pattern = f"user_role:{user_id}"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效权限继承缓存
        pattern = f"inheritance:{user_id}:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 使用索引机制失效复杂权限缓存
        cache_keys = self._get_user_cache_keys(user_id)
        if cache_keys:
            # 从复杂缓存中移除
            for cache_key in cache_keys:
                self.complex_cache.remove(cache_key)

            # 从分布式缓存中批量删除
            if cache_keys:
                self.distributed_cache.batch_delete(cache_keys)

        # 清空用户索引
        self._clear_user_index(user_id)

        logger.info(f"失效用户 {user_id} 的权限缓存，共 {len(cache_keys)} 个缓存键")

    @monitored_cache("invalidate_precise")
    def invalidate_user_permissions_precise(self, user_id: int):
        """
        精确失效用户权限缓存 - 使用索引机制

        使用精确的缓存键索引匹配，不再使用"缓存污染"策略
        """
        # 失效简单权限缓存（使用实例的simple_cache，支持精确失效）

        # 失效基础权限缓存
        pattern = f"basic_perm:{user_id}:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效用户活跃状态缓存
        pattern = f"user_active:{user_id}"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效用户角色缓存
        pattern = f"user_role:{user_id}"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效权限继承缓存
        pattern = f"inheritance:{user_id}:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 使用索引机制失效复杂权限缓存（支持精确失效）
        cache_keys = self._get_user_cache_keys(user_id)
        if cache_keys:
            # 从复杂缓存中移除
            for cache_key in cache_keys:
                self.complex_cache.remove(cache_key)

            # 从分布式缓存中批量删除
            if cache_keys:
                self.distributed_cache.batch_delete(cache_keys)

        # 清空用户索引
        self._clear_user_index(user_id)

        logger.info(f"精确失效用户 {user_id} 的权限缓存，共 {len(cache_keys)} 个缓存键")

    def invalidate_role_permissions(self, role_id: int):
        """
        失效角色权限缓存 - 修复版本

        正确的逻辑：
        1. 找到所有拥有该角色的用户
        2. 对这些用户逐个执行权限失效操作
        3. 确保用户权限缓存得到正确更新
        """
        try:
            # 导入查询模块获取该角色下的所有用户
            from .permission_queries import get_users_by_role

            # 获取该角色下的所有用户
            user_ids = get_users_by_role(
                role_id, None
            )  # 传入None作为db_session，让函数内部处理

            if user_ids:
                # 对每个用户执行权限失效操作
                for user_id in user_ids:
                    self.invalidate_user_permissions(user_id)

                logger.info(
                    f"已失效角色 {role_id} 的权限缓存，涉及 {len(user_ids)} 个用户"
                )
            else:
                logger.warning(f"角色 {role_id} 下没有找到用户")

        except ImportError as e:
            logger.error(f"导入查询模块失败，无法获取角色用户列表: {e}")
            # 如果无法获取用户列表，记录错误但不影响其他功能
        except Exception as e:
            logger.error(f"失效角色权限缓存失败: {e}")

    def invalidate_role_permissions_legacy(self, role_id: int):
        """
        失效角色权限缓存 - 旧版本（已废弃）

        注意：此方法无法正确失效用户权限缓存，因为用户权限存储在perm:{hash}键中
        建议使用invalidate_role_permissions方法替代
        """
        logger.warning(
            f"invalidate_role_permissions_legacy已废弃，请使用invalidate_role_permissions"
        )

        # 失效简单权限缓存（使用实例的simple_cache）

        # 失效基础权限缓存（角色相关的用户）
        pattern = f"basic_perm:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效权限继承缓存（角色相关的用户）
        pattern = f"inheritance:*"
        self.l1_simple_cache.remove_pattern(pattern)

        # 失效复杂权限缓存
        pattern = f"role_perm:{role_id}:*"
        self.complex_cache.remove_pattern(pattern, strategy_name="role_permissions")

        # 失效分布式权限缓存
        pattern = f"role_perm:{role_id}:*"
        self.distributed_cache.invalidate_pattern(pattern)

        logger.info(f"已失效角色 {role_id} 的权限缓存（旧版本方法）")

    def batch_invalidate_permissions(
        self, user_ids: List[int] = None, role_ids: List[int] = None
    ):
        """
        批量失效权限缓存

        参数:
            user_ids (List[int]): 用户ID列表
            role_ids (List[int]): 角色ID列表
        """
        try:
            # 失效用户权限
            if user_ids:
                for user_id in user_ids:
                    self.invalidate_user_permissions(user_id)

            # 失效角色权限
            if role_ids:
                for role_id in role_ids:
                    self.invalidate_role_permissions(role_id)

            logger.info(
                f"批量失效完成: 用户 {len(user_ids) if user_ids else 0} 个, 角色 {len(role_ids) if role_ids else 0} 个"
            )

        except Exception as e:
            logger.error(f"批量失效失败: {e}")

    def invalidate_keys(
        self, keys: List[str], cache_level: str = "all"
    ) -> Dict[str, Any]:
        """
        批量失效指定的缓存键

        参数:
            keys (List[str]): 要失效的缓存键列表
            cache_level (str): 缓存级别 ('l1', 'l2', 'all')

        返回:
            Dict[str, Any]: 失效结果统计
        """
        results = {
            "total_keys": len(keys),
            "l1_invalidated": 0,
            "l2_invalidated": 0,
            "failed_keys": [],
            "execution_time": 0,
        }

        start_time = time.time()

        try:
            # 失效L1缓存（LRU）
            if cache_level in ["l1", "all"]:
                for key in keys:
                    try:
                        # 从L1简单缓存的所有策略中移除
                        for strategy_name in self.l1_simple_cache.strategies.keys():
                            if self.l1_simple_cache.remove(key, strategy_name):
                                results["l1_invalidated"] += 1

                        # 从所有策略的复杂缓存中移除
                        for strategy_name in self.complex_cache.strategies.keys():
                            if self.complex_cache.remove(key, strategy_name):
                                results["l1_invalidated"] += 1
                    except Exception as e:
                        logger.warning(f"L1缓存失效失败 {key}: {e}")
                        results["failed_keys"].append(key)

            # 失效L2缓存（Redis）
            if cache_level in ["l2", "all"]:
                try:
                    success = self.distributed_cache.batch_delete(keys)
                    if success:
                        results["l2_invalidated"] = len(keys)
                    else:
                        results["failed_keys"].extend(keys)
                except Exception as e:
                    logger.error(f"L2缓存批量失效失败: {e}")
                    results["failed_keys"].extend(keys)

            results["execution_time"] = time.time() - start_time
            logger.info(
                f"批量失效完成: L1 {results['l1_invalidated']} 个, L2 {results['l2_invalidated']} 个, 失败 {len(results['failed_keys'])} 个"
            )

        except Exception as e:
            logger.error(f"批量失效操作失败: {e}")
            results["failed_keys"] = keys
            results["execution_time"] = time.time() - start_time

        return results

    def get_redis_client(self):
        """
        获取Redis客户端实例

        返回:
            Redis客户端实例或None
        """
        return self.distributed_cache.redis_client if self.distributed_cache else None

    def get_cache_instance(self, cache_type: str = "complex"):
        """
        获取指定类型的缓存实例

        参数:
            cache_type (str): 缓存类型 ('simple', 'complex', 'distributed')

        返回:
            缓存实例或None
        """
        if cache_type == "simple":
            return self.l1_simple_cache
        elif cache_type == "complex":
            return self.complex_cache
        elif cache_type == "distributed":
            return self.distributed_cache
        else:
            logger.warning(f"未知的缓存类型: {cache_type}")
            return None

    def get_distributed_cache_stats(self) -> Dict[str, Any]:
        """
        获取分布式缓存集群统计信息

        返回:
            Dict: 包含集群节点信息、健康状态和操作统计
        """
        try:
            if self.distributed_cache and self.distributed_cache.redis_client:
                return {
                    "connected": True,
                    "keys": self.distributed_cache.redis_client.dbsize(),
                }
            return {"connected": False, "error": "分布式缓存未初始化"}
        except Exception as e:
            logger.error(f"获取分布式缓存统计失败: {e}")
            return {"connected": False, "error": str(e)}

    def distributed_cache_get(self, key: str) -> Optional[bytes]:
        """
        从分布式缓存获取数据（带双重检查锁定模式）

        参数:
            key (str): 缓存键

        返回:
            Optional[bytes]: 缓存值，如果不存在返回None
        """
        try:
            if not self.distributed_cache or not self.distributed_cache.redis_client:
                return None

            # 双重检查锁定模式
            # 第一次检查：无锁快速检查
            data = self.distributed_cache.redis_client.get(key)
            if data is not None:
                return data

            # 第二次检查：使用分布式锁保护
            lock_key = f"cache_read:{key}"
            try:
                # 使用依赖注入的分布式锁
                if self._distributed_lock_manager is not None:
                    with self._distributed_lock_manager.create_lock(
                        lock_key, timeout=1.0
                    ) as lock:
                        # 再次检查缓存（双重检查锁定模式）
                        data = self.distributed_cache.redis_client.get(key)
                        if data is not None:
                            return data

                        # 如果缓存中没有数据，返回None
                        return None
                else:
                    # 如果没有分布式锁管理器，降级到无锁模式
                    logger.warning("分布式锁管理器未注入，使用无锁模式")
                    return self.distributed_cache.redis_client.get(key)

            except Exception as e:
                logger.warning(f"分布式锁获取失败，降级到无锁模式: {e}")
                # 降级到无锁模式
                return self.distributed_cache.redis_client.get(key)

        except Exception as e:
            logger.error(f"从分布式缓存获取数据失败: {e}")
            return None

    def distributed_cache_set(self, key: str, value: bytes, ttl: int = 300) -> bool:
        """
        向分布式缓存设置数据

        参数:
            key (str): 缓存键
            value (bytes): 缓存值
            ttl (int): 过期时间（秒）

        返回:
            bool: 操作是否成功
        """
        try:
            if self.distributed_cache and self.distributed_cache.redis_client:
                self.distributed_cache.redis_client.setex(key, ttl, value)
                return True
            return False
        except Exception as e:
            logger.error(f"向分布式缓存设置数据失败: {e}")
            return False

    def distributed_cache_delete(self, key: str) -> bool:
        """
        从分布式缓存删除数据

        参数:
            key (str): 缓存键

        返回:
            bool: 操作是否成功
        """
        try:
            if self.distributed_cache and self.distributed_cache.redis_client:
                self.distributed_cache.redis_client.delete(key)
                return True
            return False
        except Exception as e:
            logger.error(f"从分布式缓存删除数据失败: {e}")
            return False

    @monitored_cache("warmup")
    def warm_up_cache(self, user_ids: List[int] = None, permissions: List[str] = None):
        """预热缓存"""
        if user_ids is None:
            user_ids = list(range(1, 11))  # 用户1-10

        if permissions is None:
            permissions = ["read_channel", "send_message", "manage_channel"]

        # 真实的服务器和频道ID - 模拟真实世界场景
        REAL_SERVERS = [1001, 1002, 1003, 1004, 1005]  # 固定的服务器ID
        REAL_CHANNELS = [2001, 2002, 2003, 2004, 2005]  # 固定的频道ID

        print("开始缓存预热...")
        warmed_count = 0

        for user_id in user_ids:
            # 预热简单权限
            for permission in permissions:
                try:
                    self.get_permission(user_id, permission)
                    warmed_count += 1
                except Exception as e:
                    logger.warning(
                        f"预热简单权限失败: user_id={user_id}, permission={permission}, error={e}"
                    )

            # 预热复杂权限 - 使用真实的服务器ID
            for server_id in REAL_SERVERS:
                try:
                    self.get_permission(
                        user_id, "manage_server", "complex", "server", server_id
                    )
                    warmed_count += 1
                except Exception as e:
                    logger.warning(
                        f"预热复杂权限失败: user_id={user_id}, server_id={server_id}, error={e}"
                    )

            # 预热混合权限 - 使用真实的频道ID
            for channel_id in REAL_CHANNELS:
                try:
                    self.get_permission(
                        user_id, "edit_message", "hybrid", "channel", channel_id
                    )
                    warmed_count += 1
                except Exception as e:
                    logger.warning(
                        f"预热混合权限失败: user_id={user_id}, channel_id={channel_id}, error={e}"
                    )

        print(f"缓存预热完成，预热了 {warmed_count} 个权限查询")
        return warmed_count

    def get_performance_analysis(self) -> Dict[str, Any]:
        """获取性能分析 - 兼容版本"""
        stats = self.get_stats()

        # 从兼容格式中提取统计信息
        lru_stats = stats["lru"]
        redis_stats = stats["redis"]

        # 计算命中率
        total_requests = lru_stats["hits"] + lru_stats["misses"]
        cache_hit_rate = lru_stats["hit_rate"] if total_requests > 0 else 0.0

        # 分析缓存效率
        efficiency_analysis = {
            "overall_hit_rate": cache_hit_rate,
            "simple_cache_efficiency": "high" if cache_hit_rate > 0.8 else "medium",
            "complex_cache_efficiency": (
                "high" if lru_stats["hit_rate"] > 0.7 else "medium"
            ),
            "redis_efficiency": "high" if redis_stats["connected"] else "medium",
            "recommendations": [],
            "optimization_suggestions": [],
        }

        # 生成优化建议
        if cache_hit_rate < 0.6:
            efficiency_analysis["recommendations"].append("建议增加缓存预热")
            efficiency_analysis["optimization_suggestions"].append(
                "增加预热用户数量和权限类型"
            )

        if lru_stats["hit_rate"] < 0.5:
            efficiency_analysis["recommendations"].append("建议优化复杂权限查询")
            efficiency_analysis["optimization_suggestions"].append(
                "增加复杂缓存容量和TTL"
            )

        if not redis_stats["connected"]:
            efficiency_analysis["recommendations"].append("建议检查Redis连接和配置")
            efficiency_analysis["optimization_suggestions"].append(
                "优化Redis连接池配置"
            )

        # 添加性能优化建议
        if lru_stats["size"] > lru_stats["maxsize"] * 0.8:
            efficiency_analysis["optimization_suggestions"].append(
                "考虑增加复杂缓存容量"
            )

        if lru_stats["misses"] > lru_stats["hits"]:
            efficiency_analysis["optimization_suggestions"].append(
                "考虑增加缓存预热频率"
            )

        return efficiency_analysis

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计 - 兼容permission_cache.py接口

        返回:
            Dict[str, Any]: 兼容的统计格式 {'lru': {...}, 'redis': {...}}
        """
        # 获取L1简单缓存统计
        l1_simple_stats = self.l1_simple_cache.get_stats()

        # 获取复杂缓存统计（分策略）
        complex_stats_all = self.complex_cache.get_stats()
        # 使用user_permissions策略的统计作为主要统计
        complex_stats = complex_stats_all.get("user_permissions", {})

        # 获取分布式缓存统计
        distributed_stats = self.distributed_cache.stats

        # 兼容permission_cache.py的返回格式
        lru_stats = {
            "size": complex_stats.get("size", 0),
            "maxsize": complex_stats.get("maxsize", 0),
            "hits": complex_stats.get("hits", 0),
            "misses": complex_stats.get("misses", 0),
            "hit_rate": complex_stats.get("hit_rate", 0.0),
            "access_patterns": complex_stats.get("access_patterns", {}),
            "avg_age": complex_stats.get("avg_age", 0.0),
        }

        # Redis统计（兼容格式）
        redis_stats = {
            "connected": self.distributed_cache.redis_client is not None,
            "keys": 0,  # 需要额外查询Redis键数量
        }

        if redis_stats["connected"]:
            try:
                redis_client = self.distributed_cache.redis_client
                if redis_client:
                    redis_stats["keys"] = redis_client.dbsize()
            except Exception as e:
                logger.error(f"获取Redis统计失败: {e}")

        return {
            "lru": lru_stats,
            "redis": redis_stats,
            "l1_simple_cache": l1_simple_stats,  # 添加L1简单缓存统计
            "complex_cache_strategies": complex_stats_all,  # 添加分策略统计
        }

    @monitored_cache("refresh")
    def refresh_user_permissions(self, user_id: int, db_session, server_id: int = None):
        """
        刷新用户权限缓存

        参数:
            user_id (int): 用户ID
            db_session: 数据库会话对象
            server_id (int): 服务器ID
        """
        try:
            # 导入查询模块获取最新数据
            from .permission_queries import optimized_single_user_query_v3

            # 获取最新权限数据，正确处理server_id参数
            scope = "server" if server_id else None
            scope_id = server_id
            latest_permissions = optimized_single_user_query_v3(
                user_id, db_session, scope, scope_id
            )

            # 更新缓存，使用正确的缓存键
            cache_key = f"perm:{_make_perm_cache_key(user_id, scope, scope_id)}"
            self.complex_cache.set(
                cache_key, latest_permissions, strategy_name="user_permissions"
            )
            self.distributed_cache.set(cache_key, latest_permissions, ttl=600)

            # 添加到用户索引
            self._add_to_user_index(user_id, cache_key)

            logger.info(f"已刷新用户 {user_id} 的权限缓存")

        except Exception as e:
            logger.error(f"刷新用户权限缓存失败: {e}")

    @monitored_cache("batch_refresh")
    def batch_refresh_user_permissions(
        self, user_ids: List[int], db_session, server_id: int = None
    ):
        """
        批量刷新用户权限缓存

        参数:
            user_ids (List[int]): 用户ID列表
            db_session: 数据库会话对象
            server_id (int): 服务器ID
        """
        try:
            # 导入查询模块获取最新数据
            from .permission_queries import batch_precompute_permissions

            # 获取最新权限数据，正确处理server_id参数
            scope = "server" if server_id else None
            scope_id = server_id
            latest_permissions_map = batch_precompute_permissions(
                user_ids, db_session, scope, scope_id
            )

            # 批量更新缓存
            cache_updates_l1 = {}
            cache_updates_l2 = {}

            for user_id, permissions in latest_permissions_map.items():
                cache_key = f"perm:{_make_perm_cache_key(user_id, scope, scope_id)}"
                cache_updates_l1[cache_key] = permissions
                cache_updates_l2[cache_key] = permissions

                # 添加到用户索引
                self._add_to_user_index(user_id, cache_key)

            # 批量更新缓存
            if cache_updates_l1:
                self.complex_cache.batch_set(
                    cache_updates_l1, strategy_name="user_permissions"
                )
            if cache_updates_l2:
                self.distributed_cache.batch_set(cache_updates_l2)

            logger.info(f"已批量刷新 {len(user_ids)} 个用户的权限缓存")

        except Exception as e:
            logger.error(f"批量刷新用户权限缓存失败: {e}")

    def refresh_role_permissions(self, role_id: int, db_session):
        """
        刷新角色权限缓存

        参数:
            role_id (int): 角色ID
            db_session: 数据库会话对象
        """
        try:
            # 使用查询模块获取该角色下的所有用户，避免直接依赖数据库模型
            from .permission_queries import get_users_by_role

            # 获取该角色下的所有用户
            user_ids = get_users_by_role(role_id, db_session)

            if user_ids:
                # 批量刷新这些用户的权限缓存
                self.batch_refresh_user_permissions(user_ids, db_session)

            logger.info(f"已刷新角色 {role_id} 的权限缓存，涉及 {len(user_ids)} 个用户")

        except ImportError as e:
            logger.error(f"导入查询模块失败: {e}")
            # 如果导入失败，记录错误但不影响其他功能
        except Exception as e:
            logger.error(f"刷新角色权限缓存失败: {e}")

    # ==================== 用户索引管理方法 ====================

    def _add_to_user_index(self, user_id: int, cache_key: str):
        """将缓存键添加到用户索引中"""
        try:
            redis_client = self.distributed_cache.redis_client
            if redis_client:
                index_key = f"user_index:{{{user_id}}}"
                redis_client.sadd(index_key, cache_key)
                # 设置索引的过期时间，避免索引永久存在
                redis_client.expire(index_key, 3600)  # 1小时过期
        except Exception as e:
            logger.warning(
                f"添加用户索引失败: user_id={user_id}, cache_key={cache_key}, error={e}"
            )

    def _remove_from_user_index(self, user_id: int, cache_key: str):
        """从用户索引中移除缓存键"""
        try:
            redis_client = self.distributed_cache.redis_client
            if redis_client:
                index_key = f"user_index:{{{user_id}}}"
                redis_client.srem(index_key, cache_key)
        except Exception as e:
            logger.warning(
                f"移除用户索引失败: user_id={user_id}, cache_key={cache_key}, error={e}"
            )

    def _get_user_cache_keys(self, user_id: int) -> List[str]:
        """获取用户的所有缓存键"""
        try:
            redis_client = self.distributed_cache.redis_client
            if redis_client:
                index_key = f"user_index:{{{user_id}}}"
                keys = redis_client.smembers(index_key)
                return [
                    key.decode("utf-8") if isinstance(key, bytes) else key
                    for key in keys
                ]
        except Exception as e:
            logger.warning(f"获取用户缓存键失败: user_id={user_id}, error={e}")
        return []

    def _clear_user_index(self, user_id: int):
        """清空用户索引"""
        try:
            redis_client = self.distributed_cache.redis_client
            if redis_client:
                index_key = f"user_index:{{{user_id}}}"
                redis_client.delete(index_key)
        except Exception as e:
            logger.warning(f"清空用户索引失败: user_id={user_id}, error={e}")


# ==================== 缓存键生成函数 ====================


def _make_perm_cache_key(user_id, scope, scope_id):
    """
    生成优化的权限缓存key，使用MD5哈希。

    根据用户ID、作用域和作用域ID生成唯一的缓存键，使用MD5哈希提高分布性。

    参数:
        user_id (int): 用户ID
        scope (str): 作用域类型，如'server'、'channel'或None
        scope_id (int): 作用域ID，如服务器ID或频道ID

    返回:
        str: MD5哈希的缓存键

    示例:
        >>> _make_perm_cache_key(123, 'server', 456)
        'perm:5d41402abc4b2a76b9719d911017c592'
    """
    key_string = f"{user_id}:{scope or 'global'}:{scope_id or 'none'}"
    return f"perm:{{{hashlib.md5(key_string.encode()).hexdigest()}}}"


# ==================== 全局实例 ====================

# 创建一个未初始化的全局实例，供应用工厂使用
hybrid_cache = HybridPermissionCache()


def get_hybrid_cache() -> HybridPermissionCache:
    """获取混合缓存实例"""
    return hybrid_cache


# ==================== 便捷函数 ====================


@deprecated(
    reason="全局便捷函数，建议使用HybridPermissionCache实例",
    replacement="HybridPermissionCache().get_permission()",
)
@monitored_cache("convenience")
def get_permission(
    user_id: int,
    permission: str,
    strategy: str = "hybrid",
    scope: str = None,
    scope_id: int = None,
) -> Union[bool, Set[str]]:
    """
    获取权限的便捷函数

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的get_permission方法
    - 迁移示例：cache = HybridPermissionCache(); result = cache.get_permission(user_id, permission)
    """
    return hybrid_cache.get_permission(user_id, permission, strategy, scope, scope_id)


@deprecated(
    reason="全局便捷函数，建议使用HybridPermissionCache实例",
    replacement="HybridPermissionCache().batch_get_permissions()",
)
@monitored_cache("convenience_batch")
def batch_get_permissions(
    user_ids: List[int],
    permission: str,
    strategy: str = "hybrid",
    scope: str = None,
    scope_id: int = None,
) -> Dict[int, Union[bool, Set[str]]]:
    """
    批量获取权限的便捷函数

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的batch_get_permissions方法
    - 迁移示例：cache = HybridPermissionCache(); results = cache.batch_get_permissions(user_ids, permission)
    """
    return hybrid_cache.batch_get_permissions(
        user_ids, permission, strategy, scope, scope_id
    )


@monitored_cache("convenience_invalidate")
def invalidate_user_permissions(user_id: int):
    """失效用户权限缓存的便捷函数"""
    hybrid_cache.invalidate_user_permissions(user_id)


@monitored_cache("convenience_invalidate_precise")
def invalidate_user_permissions_precise(user_id: int):
    """精确失效用户权限缓存的便捷函数"""
    hybrid_cache.invalidate_user_permissions_precise(user_id)


def invalidate_role_permissions(role_id: int):
    """失效角色权限缓存的便捷函数"""
    hybrid_cache.invalidate_role_permissions(role_id)


def invalidate_role_permissions_legacy(role_id: int):
    """失效角色权限缓存的便捷函数（旧版本，已废弃）"""
    hybrid_cache.invalidate_role_permissions_legacy(role_id)


def batch_invalidate_permissions(
    user_ids: List[int] = None, role_ids: List[int] = None
):
    """批量失效权限缓存的便捷函数"""
    hybrid_cache.batch_invalidate_permissions(user_ids, role_ids)


@monitored_cache("convenience_warmup")
def warm_up_cache(user_ids: List[int] = None, permissions: List[str] = None):
    """缓存预热的便捷函数"""
    hybrid_cache.warm_up_cache(user_ids, permissions)


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计的便捷函数"""
    return hybrid_cache.get_stats()


def get_performance_analysis() -> Dict[str, Any]:
    """获取性能分析的便捷函数"""
    return hybrid_cache.get_performance_analysis()


def clear_all_caches():
    """清空所有缓存的便捷函数"""
    # 清空全局单例的所有缓存
    hybrid_cache.l1_simple_cache.clear()
    hybrid_cache.complex_cache.clear()

    # 清空Redis缓存（可选，谨慎使用）
    # hybrid_cache.distributed_cache.clear_all()

    logger.info("所有缓存已清空")


def get_cache_health_check() -> Dict[str, Any]:
    """获取缓存健康检查的便捷函数"""
    health_check = {
        "simple_cache_healthy": True,
        "complex_cache_healthy": True,
        "redis_cache_healthy": True,
        "issues": [],
    }

    try:
        # 检查L1简单缓存
        stats = hybrid_cache.l1_simple_cache.get_stats()
        if stats["size"] > stats["maxsize"] * 0.9:
            health_check["issues"].append("L1简单缓存接近容量上限")
    except Exception as e:
        health_check["simple_cache_healthy"] = False
        health_check["issues"].append(f"L1简单缓存异常: {e}")

    try:
        # 检查复杂缓存
        stats = hybrid_cache.complex_cache.get_stats()
        if stats["size"] > stats["maxsize"] * 0.9:
            health_check["issues"].append("复杂缓存接近容量上限")
    except Exception as e:
        health_check["complex_cache_healthy"] = False
        health_check["issues"].append(f"复杂缓存异常: {e}")

    try:
        # 检查Redis缓存
        redis_client = hybrid_cache.distributed_cache.redis_client
        if not redis_client:
            health_check["redis_cache_healthy"] = False
            health_check["issues"].append("Redis连接失败")
        else:
            # 测试Redis连接
            try:
                redis_client.ping()
                health_check["redis_cache_healthy"] = True
            except Exception as e:
                health_check["redis_cache_healthy"] = False
                health_check["issues"].append(f"Redis连接测试失败: {e}")
    except Exception as e:
        health_check["redis_cache_healthy"] = False
        health_check["issues"].append(f"Redis缓存异常: {e}")

    return health_check


@monitored_cache("convenience_refresh")
def refresh_user_permissions(user_id: int, db_session, server_id: int = None):
    """刷新用户权限缓存的便捷函数"""
    hybrid_cache.refresh_user_permissions(user_id, db_session, server_id)


@monitored_cache("convenience_batch_refresh")
def batch_refresh_user_permissions(
    user_ids: List[int], db_session, server_id: int = None
):
    """批量刷新用户权限缓存的便捷函数"""
    hybrid_cache.batch_refresh_user_permissions(user_ids, db_session, server_id)


@monitored_cache("convenience_refresh_role")
def refresh_role_permissions(role_id: int, db_session):
    """刷新角色权限缓存的便捷函数"""
    hybrid_cache.refresh_role_permissions(role_id, db_session)


# ==================== 简单权限查询便捷函数 ====================


def check_basic_permission(user_id: int, permission: str) -> bool:
    """检查基础权限的便捷函数"""
    return hybrid_cache.check_basic_permission(user_id, permission)


def is_user_active(user_id: int) -> bool:
    """检查用户是否活跃的便捷函数"""
    return hybrid_cache.is_user_active(user_id)


def get_user_role_level(user_id: int) -> int:
    """获取用户角色等级的便捷函数"""
    return hybrid_cache.get_user_role_level(user_id)


def check_permission_inheritance(
    user_id: int, permission: str, parent_permission: str
) -> bool:
    """检查权限继承的便捷函数"""
    return hybrid_cache.check_permission_inheritance(
        user_id, permission, parent_permission
    )


# ==================== 兼容性函数 ====================

# 为了与permission_cache.py保持接口一致性，添加以下兼容性函数
# 注意：这些函数已被弃用，将在v2.0.0版本中移除


@deprecated(
    reason="全局状态依赖，建议使用HybridPermissionCache实例",
    replacement="HybridPermissionCache().complex_cache",
)
def get_lru_cache():
    """
    兼容性函数：获取LRU缓存实例

    返回:
        ComplexPermissionCache: 复杂权限缓存实例

    注意：此函数用于与permission_cache.py保持接口一致性
    在hybrid_permission_cache.py中，LRU缓存被ComplexPermissionCache替代

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的complex_cache属性
    - 迁移示例：cache = HybridPermissionCache(); lru_cache = cache.complex_cache
    """
    return hybrid_cache.complex_cache


@deprecated(
    reason="直接缓存操作，建议使用HybridPermissionCache实例方法",
    replacement="HybridPermissionCache().get_permission()",
)
@monitored_cache("compatibility_get")
def get_permissions_from_cache(cache_key: str) -> Optional[Set[str]]:
    """
    兼容性函数：从缓存获取权限

    参数:
        cache_key (str): 缓存键

    返回:
        Optional[Set[str]]: 权限集合，如果未找到则返回None

    注意：此函数用于与permission_cache.py保持接口一致性

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的get_permission方法
    - 迁移示例：cache = HybridPermissionCache(); permissions = cache.get_permission(user_id, permission)
    """
    try:
        # 解析缓存键格式：perm:{hash}
        if cache_key.startswith("perm:"):
            # 从缓存键中提取信息（简化处理）
            # 实际使用时可能需要更复杂的解析逻辑
            return hybrid_cache.complex_cache.get(
                cache_key, strategy_name="user_permissions"
            )
        else:
            # 直接查询复杂缓存
            return hybrid_cache.complex_cache.get(
                cache_key, strategy_name="user_permissions"
            )
    except Exception as e:
        logger.error(f"兼容性缓存获取失败: {e}")
        return None


@deprecated(
    reason="直接缓存操作，建议使用HybridPermissionCache实例方法",
    replacement="HybridPermissionCache().get_permission() 会自动缓存",
)
@monitored_cache("compatibility_set")
def set_permissions_to_cache(cache_key: str, permissions: Set[str], ttl: int = 300):
    """
    兼容性函数：设置权限到缓存

    参数:
        cache_key (str): 缓存键
        permissions (Set[str]): 权限集合
        ttl (int): 过期时间（秒）

    注意：此函数用于与permission_cache.py保持接口一致性

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的get_permission方法，会自动缓存
    - 迁移示例：cache = HybridPermissionCache(); cache.get_permission(user_id, permission)
    """
    try:
        # 设置到复杂缓存
        hybrid_cache.complex_cache.set(cache_key, permissions)

        # 设置到分布式缓存
        hybrid_cache.distributed_cache.set(cache_key, permissions, ttl)

        logger.debug(f"兼容性缓存设置成功: {cache_key}")
    except Exception as e:
        logger.error(f"兼容性缓存设置失败: {e}")


@deprecated(
    reason="兼容性接口，建议使用HybridPermissionCache实例方法",
    replacement="HybridPermissionCache().get_stats()",
)
def get_cache_performance_stats() -> Dict[str, Any]:
    """
    兼容性函数：获取缓存性能统计

    返回:
        Dict[str, Any]: 性能统计信息

    注意：此函数用于与permission_cache.py保持接口一致性

    弃用警告：
    - 此函数将在v2.0.0版本中移除
    - 建议使用HybridPermissionCache实例的get_stats方法
    - 迁移示例：cache = HybridPermissionCache(); stats = cache.get_stats()
    """
    try:
        # 获取基础统计
        stats = get_cache_stats()

        # 计算命中率
        lru_hit_rate = stats["lru"]["hit_rate"]

        return {
            "lru_hit_rate": lru_hit_rate,
            "lru_size": stats["lru"]["size"],
            "lru_maxsize": stats["lru"]["maxsize"],
            "redis_connected": stats["redis"]["connected"],
            "redis_keys": stats["redis"]["keys"],
            "overall_performance": (
                "good" if lru_hit_rate > 0.8 else "needs_optimization"
            ),
        }
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        return {
            "lru_hit_rate": 0.0,
            "lru_size": 0,
            "lru_maxsize": 0,
            "redis_connected": False,
            "redis_keys": 0,
            "overall_performance": "error",
        }
