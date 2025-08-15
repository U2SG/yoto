"""
权限管理模块

负责处理权限变更时的缓存刷新，解决循环依赖问题。
建立正确的调用链：API -> Permission Manager -> Cache Module -> Query Module
"""

import logging
from typing import List, Optional, Dict, Set
from flask import current_app

from .hybrid_permission_cache import (
    refresh_user_permissions,
    batch_refresh_user_permissions,
    refresh_role_permissions,
    invalidate_user_permissions,
    invalidate_role_permissions,
)

logger = logging.getLogger(__name__)


class PermissionManager:
    """
    权限管理器

    负责处理权限变更时的缓存刷新，避免循环依赖
    """

    def __init__(self):
        self.stats = {
            "refresh_operations": 0,
            "invalidate_operations": 0,
            "batch_operations": 0,
        }

    def on_user_role_changed(self, user_id: int, role_ids: List[int] = None):
        """
        用户角色变更时的处理

        参数:
            user_id (int): 用户ID
            role_ids (List[int]): 变更的角色ID列表，None表示刷新所有角色
        """
        try:
            # 刷新用户权限缓存
            refresh_user_permissions(user_id)
            self.stats["refresh_operations"] += 1

            # 如果指定了角色ID，也刷新角色缓存
            if role_ids:
                for role_id in role_ids:
                    invalidate_role_permissions(role_id)
                    self.stats["invalidate_operations"] += 1

            logger.info(f"用户 {user_id} 角色变更，已刷新权限缓存")

        except Exception as e:
            logger.error(f"用户角色变更处理失败: {e}")

    def on_role_permissions_changed(self, role_id: int, user_ids: List[int] = None):
        """
        角色权限变更时的处理

        参数:
            role_id (int): 角色ID
            user_ids (List[int]): 受影响的用户ID列表，None表示刷新所有相关用户
        """
        try:
            # 失效角色权限缓存
            invalidate_role_permissions(role_id)
            self.stats["invalidate_operations"] += 1

            # 如果指定了用户ID，刷新这些用户的权限缓存
            if user_ids:
                batch_refresh_user_permissions(user_ids)
                self.stats["batch_operations"] += 1

            logger.info(f"角色 {role_id} 权限变更，已刷新相关缓存")

        except Exception as e:
            logger.error(f"角色权限变更处理失败: {e}")

    def on_user_permissions_changed(self, user_id: int):
        """
        用户权限直接变更时的处理

        参数:
            user_id (int): 用户ID
        """
        try:
            # 刷新用户权限缓存
            refresh_user_permissions(user_id)
            self.stats["refresh_operations"] += 1

            logger.info(f"用户 {user_id} 权限直接变更，已刷新缓存")

        except Exception as e:
            logger.error(f"用户权限变更处理失败: {e}")

    def on_batch_permissions_changed(self, user_ids: List[int]):
        """
        批量权限变更时的处理

        参数:
            user_ids (List[int]): 用户ID列表
        """
        try:
            # 批量刷新用户权限缓存
            batch_refresh_user_permissions(user_ids)
            self.stats["batch_operations"] += 1

            logger.info(f"批量权限变更，已刷新 {len(user_ids)} 个用户的缓存")

        except Exception as e:
            logger.error(f"批量权限变更处理失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()


# 全局权限管理器实例
_permission_manager = PermissionManager()


def get_permission_manager() -> PermissionManager:
    """获取权限管理器实例"""
    return _permission_manager


# 便捷函数
def on_user_role_changed(user_id: int, role_ids: List[int] = None):
    """用户角色变更时的便捷函数"""
    _permission_manager.on_user_role_changed(user_id, role_ids)


def on_role_permissions_changed(role_id: int, user_ids: List[int] = None):
    """角色权限变更时的便捷函数"""
    _permission_manager.on_role_permissions_changed(role_id, user_ids)


def on_user_permissions_changed(user_id: int):
    """用户权限直接变更时的便捷函数"""
    _permission_manager.on_user_permissions_changed(user_id)


def on_batch_permissions_changed(user_ids: List[int]):
    """批量权限变更时的便捷函数"""
    _permission_manager.on_batch_permissions_changed(user_ids)
