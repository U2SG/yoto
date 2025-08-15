"""
角色服务层

负责协调角色注册、分配和缓存失效操作
避免循环依赖，保持模块职责清晰
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.blueprints.roles.models import Role, UserRole, RolePermission
from app.core.extensions import db
from .permission_registry import (
    register_role_v2,
    batch_register_roles,
    assign_permissions_to_role_v2,
    assign_roles_to_user_v2,
)

logger = logging.getLogger(__name__)


class RoleService:
    """角色服务类"""

    def __init__(self, db_session: Session = None):
        self.db_session = db_session or db.session

    def register_role(self, name: str, server_id: int, is_active: bool = True) -> Dict:
        """
        注册角色并处理缓存失效

        参数:
            name (str): 角色名称
            server_id (int): 服务器ID
            is_active (bool): 是否激活

        返回:
            Dict: 角色信息
        """
        try:
            # 注册角色
            role_info = register_role_v2(name, server_id, is_active)

            if role_info:
                # 失效相关缓存
                self._invalidate_role_cache(role_info.get("id"))
                logger.info(f"角色注册成功: {name}, ID: {role_info.get('id')}")

            return role_info

        except Exception as e:
            logger.error(f"角色注册失败: {name}, 错误: {e}")
            return {}

    def batch_register_roles(self, roles_data: List[Dict]) -> List[Dict]:
        """
        批量注册角色并处理缓存失效

        参数:
            roles_data (List[Dict]): 角色数据列表

        返回:
            List[Dict]: 注册结果列表
        """
        try:
            # 批量注册角色
            results = batch_register_roles(roles_data)

            # 失效相关缓存
            for result in results:
                if result.get("status") in ["created", "updated"]:
                    # 这里需要查询角色ID来失效缓存
                    role = (
                        self.db_session.query(Role)
                        .filter(
                            Role.name == result.get("name"),
                            Role.server_id == result.get("server_id"),
                        )
                        .first()
                    )
                    if role:
                        self._invalidate_role_cache(role.id)

            logger.info(f"批量注册角色完成: {len(results)} 个")
            return results

        except Exception as e:
            logger.error(f"批量注册角色失败: {e}")
            return []

    def assign_permissions_to_role(
        self,
        role_id: int,
        permission_ids: List[int],
        scope_type: str = None,
        scope_id: int = None,
    ) -> List[Dict]:
        """
        为角色分配权限并处理缓存失效

        参数:
            role_id (int): 角色ID
            permission_ids (List[int]): 权限ID列表
            scope_type (str): 作用域类型
            scope_id (int): 作用域ID

        返回:
            List[Dict]: 分配结果列表
        """
        try:
            # 分配权限
            results = assign_permissions_to_role_v2(
                role_id, permission_ids, scope_type, scope_id
            )

            if results:
                # 失效相关缓存
                self._invalidate_role_cache(role_id)
                logger.info(f"为角色 {role_id} 分配了 {len(results)} 个权限")

            return results

        except Exception as e:
            logger.error(f"为角色分配权限失败: {e}")
            return []

    def assign_roles_to_user(
        self, user_id: int, role_ids: List[int], server_id: int
    ) -> List[Dict]:
        """
        为用户分配角色并处理缓存失效

        参数:
            user_id (int): 用户ID
            role_ids (List[int]): 角色ID列表
            server_id (int): 服务器ID

        返回:
            List[Dict]: 分配结果列表
        """
        try:
            # 分配角色
            results = assign_roles_to_user_v2(user_id, role_ids, server_id)

            if results:
                # 失效相关缓存
                self._invalidate_user_cache(user_id)
                logger.info(f"为用户 {user_id} 分配了 {len(results)} 个角色")

            return results

        except Exception as e:
            logger.error(f"为用户分配角色失败: {e}")
            return []

    def _invalidate_role_cache(self, role_id: int):
        """失效角色相关缓存"""
        try:
            # 延迟导入，避免循环依赖
            from .hybrid_permission_cache import invalidate_role_permissions

            invalidate_role_permissions(role_id)
            logger.debug(f"已失效角色 {role_id} 的缓存")
        except ImportError:
            logger.warning("缓存模块不可用，跳过缓存失效")
        except Exception as e:
            logger.error(f"失效角色缓存失败: {e}")

    def _invalidate_user_cache(self, user_id: int):
        """失效用户相关缓存"""
        try:
            # 延迟导入，避免循环依赖
            from .hybrid_permission_cache import invalidate_user_permissions

            invalidate_user_permissions(user_id)
            logger.debug(f"已失效用户 {user_id} 的缓存")
        except ImportError:
            logger.warning("缓存模块不可用，跳过缓存失效")
        except Exception as e:
            logger.error(f"失效用户缓存失败: {e}")


# 全局服务实例
_role_service = None


def get_role_service() -> RoleService:
    """获取角色服务实例"""
    global _role_service
    if _role_service is None:
        _role_service = RoleService()
    return _role_service
