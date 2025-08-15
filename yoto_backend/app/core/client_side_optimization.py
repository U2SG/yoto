"""
客户端压力转移优化模块

将部分服务器压力转移到客户端，提升系统性能
"""

import time
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ClientCacheStrategy(Enum):
    """客户端缓存策略"""

    AGGRESSIVE = "aggressive"  # 激进缓存，缓存所有权限
    BALANCED = "balanced"  # 平衡缓存，缓存常用权限
    CONSERVATIVE = "conservative"  # 保守缓存，只缓存关键权限


@dataclass
class ClientPermissionCache:
    """客户端权限缓存"""

    user_id: str
    resource_type: str
    resource_id: str
    permissions: List[str]
    level: int
    expires_at: float
    last_updated: float
    access_count: int = 0

    def is_valid(self) -> bool:
        """检查缓存是否有效"""
        return time.time() < self.expires_at

    def is_frequently_accessed(self) -> bool:
        """检查是否频繁访问"""
        return self.access_count > 5

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


class ClientSideOptimizer:
    """客户端优化器"""

    def __init__(self, strategy: ClientCacheStrategy = ClientCacheStrategy.BALANCED):
        self.strategy = strategy
        self.cache = {}  # 客户端权限缓存
        self.access_patterns = {}  # 访问模式统计
        self.prefetch_queue = []  # 预取队列
        self.last_sync_time = 0
        self.sync_interval = 300  # 5分钟同步一次

    def get_cached_permission(
        self, user_id: str, resource_type: str, resource_id: str, action: str
    ) -> Optional[Dict]:
        """获取缓存的权限"""
        cache_key = f"{user_id}:{resource_type}:{resource_id}"

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if cached.is_valid():
                cached.access_count += 1
                logger.info(f"客户端缓存命中: {cache_key}")
                return {
                    "level": cached.level,
                    "permissions": cached.permissions,
                    "cached": True,
                    "access_count": cached.access_count,
                }
            else:
                # 缓存过期，删除
                del self.cache[cache_key]

        return None

    def cache_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        permissions: Dict,
        ttl: int = 3600,
    ):
        """缓存权限到客户端"""
        cache_key = f"{user_id}:{resource_type}:{resource_id}"

        # 根据策略决定是否缓存
        if not self._should_cache(permissions, resource_type):
            return

        cached = ClientPermissionCache(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            permissions=permissions.get("permissions", []),
            level=permissions.get("level", 0),
            expires_at=time.time() + ttl,
            last_updated=time.time(),
        )

        self.cache[cache_key] = cached
        logger.info(f"客户端缓存权限: {cache_key}")

    def _should_cache(self, permissions: Dict, resource_type: str) -> bool:
        """根据策略决定是否缓存"""
        if self.strategy == ClientCacheStrategy.AGGRESSIVE:
            return True
        elif self.strategy == ClientCacheStrategy.BALANCED:
            # 只缓存常用资源类型
            return resource_type in ["server", "channel"]
        elif self.strategy == ClientCacheStrategy.CONSERVATIVE:
            # 只缓存高级权限
            return permissions.get("level", 0) >= 3
        return False

    def prefetch_permissions(self, user_id: str, access_patterns: List[Dict]):
        """预取权限"""
        for pattern in access_patterns:
            resource_type = pattern.get("resource_type")
            resource_id = pattern.get("resource_id")

            if resource_type and resource_id:
                self.prefetch_queue.append(
                    {
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "priority": pattern.get("frequency", 1),
                    }
                )

        # 按优先级排序
        self.prefetch_queue.sort(key=lambda x: x["priority"], reverse=True)
        logger.info(f"预取队列已更新，共 {len(self.prefetch_queue)} 项")

    def get_prefetch_batch(self, batch_size: int = 10) -> List[Dict]:
        """获取预取批次"""
        batch = self.prefetch_queue[:batch_size]
        self.prefetch_queue = self.prefetch_queue[batch_size:]
        return batch

    def update_access_pattern(
        self, user_id: str, resource_type: str, resource_id: str, action: str
    ):
        """更新访问模式"""
        pattern_key = f"{user_id}:{resource_type}:{resource_id}:{action}"

        if pattern_key in self.access_patterns:
            self.access_patterns[pattern_key]["count"] += 1
            self.access_patterns[pattern_key]["last_access"] = time.time()
        else:
            self.access_patterns[pattern_key] = {
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "count": 1,
                "first_access": time.time(),
                "last_access": time.time(),
            }

    def get_frequent_patterns(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取频繁访问模式"""
        user_patterns = [
            pattern
            for key, pattern in self.access_patterns.items()
            if pattern["user_id"] == user_id
        ]

        # 按访问次数排序
        user_patterns.sort(key=lambda x: x["count"], reverse=True)
        return user_patterns[:limit]

    def should_sync_with_server(self) -> bool:
        """判断是否需要与服务器同步"""
        return time.time() - self.last_sync_time > self.sync_interval

    def sync_with_server(self, server_permissions: List[Dict]):
        """与服务器同步权限"""
        for perm in server_permissions:
            cache_key = (
                f"{perm['user_id']}:{perm['resource_type']}:{perm['resource_id']}"
            )

            if cache_key in self.cache:
                # 更新现有缓存
                cached = self.cache[cache_key]
                cached.permissions = perm.get("permissions", [])
                cached.level = perm.get("level", 0)
                cached.last_updated = time.time()
            else:
                # 创建新缓存
                self.cache_permission(
                    perm["user_id"], perm["resource_type"], perm["resource_id"], perm
                )

        self.last_sync_time = time.time()
        logger.info(f"与服务器同步完成，更新了 {len(server_permissions)} 个权限")

    def cleanup_expired_cache(self):
        """清理过期缓存"""
        expired_keys = []
        for key, cached in self.cache.items():
            if not cached.is_valid():
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total_cache = len(self.cache)
        valid_cache = sum(1 for cached in self.cache.values() if cached.is_valid())
        frequent_cache = sum(
            1 for cached in self.cache.values() if cached.is_frequently_accessed()
        )

        return {
            "total_cache": total_cache,
            "valid_cache": valid_cache,
            "frequent_cache": frequent_cache,
            "prefetch_queue_size": len(self.prefetch_queue),
            "access_patterns_count": len(self.access_patterns),
        }


class ClientPermissionValidator:
    """客户端权限验证器"""

    def __init__(self, optimizer: ClientSideOptimizer):
        self.optimizer = optimizer
        self.validation_cache = {}  # 验证结果缓存

    def validate_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        required_level: int,
    ) -> Tuple[bool, str]:
        """验证权限"""
        # 首先检查客户端缓存
        cached = self.optimizer.get_cached_permission(
            user_id, resource_type, resource_id, action
        )

        if cached:
            # 客户端验证
            if cached["level"] >= required_level:
                return True, "客户端验证通过"
            else:
                return (
                    False,
                    f"权限不足，需要{required_level}级别，当前{cached['level']}",
                )

        # 客户端没有缓存，需要服务器验证
        return False, "需要服务器验证"

    def batch_validate(self, requests: List[Dict]) -> List[Dict]:
        """批量验证权限"""
        results = []

        for req in requests:
            user_id = req["user_id"]
            resource_type = req["resource_type"]
            resource_id = req["resource_id"]
            action = req["action"]
            required_level = req["required_level"]

            allowed, reason = self.validate_permission(
                user_id, resource_type, resource_id, action, required_level
            )

            results.append(
                {
                    "request_id": req.get("request_id"),
                    "allowed": allowed,
                    "reason": reason,
                    "cached": "客户端缓存" in reason,
                }
            )

        return results


class ClientSideOptimizationManager:
    """客户端优化管理器"""

    def __init__(self):
        self.optimizer = ClientSideOptimizer()
        self.validator = ClientPermissionValidator(self.optimizer)
        self.background_tasks = []

    def setup_client_optimization(self, user_id: str, user_permissions: List[Dict]):
        """设置客户端优化"""
        # 缓存用户权限
        for perm in user_permissions:
            self.optimizer.cache_permission(
                perm["user_id"], perm["resource_type"], perm["resource_id"], perm
            )

        # 分析访问模式并预取
        frequent_patterns = self.optimizer.get_frequent_patterns(user_id)
        self.optimizer.prefetch_permissions(user_id, frequent_patterns)

        logger.info(f"客户端优化设置完成，用户: {user_id}")

    def get_optimization_report(self) -> Dict:
        """获取优化报告"""
        cache_stats = self.optimizer.get_cache_stats()

        return {
            "cache_stats": cache_stats,
            "strategy": self.optimizer.strategy.value,
            "last_sync": self.optimizer.last_sync_time,
            "background_tasks": len(self.background_tasks),
        }


# 全局实例
_client_optimizer = None


def get_client_optimizer() -> ClientSideOptimizationManager:
    """获取客户端优化管理器"""
    global _client_optimizer
    if _client_optimizer is None:
        _client_optimizer = ClientSideOptimizationManager()
    return _client_optimizer
