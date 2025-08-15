"""
权限抽象模块 - 高级抽象层
提供权限模板、权限链、权限组等高级抽象概念
支持依赖注入的权限检查逻辑
"""

from typing import Callable, List, Dict, Any, Optional, Set
from functools import wraps
from app.core.permission_utils import (
    validate_permission_structure,
    create_permission_key,
)

# 权限模式定义
PERMISSION_PATTERNS = {
    "crud": {
        "create": "create",
        "read": "read",
        "update": "update",
        "delete": "delete",
    },
    "message": {
        "send": "message.send",
        "edit": "message.edit",
        "delete": "message.delete",
        "pin": "message.pin",
        "react": "message.react",
        "search": "message.search",
    },
    "server": {
        "view": "server.view",
        "manage": "server.manage",
        "invite": "server.invite",
        "kick": "server.kick",
        "ban": "server.ban",
    },
    "channel": {
        "view": "channel.view",
        "send": "channel.send",
        "manage": "channel.manage",
        "join": "channel.join",
        "leave": "channel.leave",
    },
    "role": {
        "view": "role.view",
        "assign": "role.assign",
        "manage": "role.manage",
        "delete": "role.delete",
    },
}


class PermissionTemplate:
    """权限模板类 - 用于快速创建标准权限组合"""

    def __init__(self, name: str, permissions: List[str], description: str = ""):
        self.name = name
        self.permissions = permissions
        self.description = description

    def register_all(
        self, permission_checker: Callable = None, group: str = None
    ) -> List[str]:
        """
        注册模板中的所有权限

        Args:
            permission_checker: 权限注册函数（依赖注入）
            group: 权限组名

        Returns:
            List[str]: 注册的权限名称列表
        """
        if permission_checker is None:
            # 如果没有提供注册函数，只返回权限名称列表
            return self.permissions

        registered = []
        for perm in self.permissions:
            if validate_permission_structure(perm):
                # 调用注入的权限注册函数
                permission_checker(
                    perm, group=group, description=f"{self.description} - {perm}"
                )
                registered.append(perm)
        return registered

    def validate_permissions(self) -> Dict[str, bool]:
        """验证模板中的所有权限结构"""
        return {perm: validate_permission_structure(perm) for perm in self.permissions}


class PermissionChain:
    """权限链类 - 支持多级权限检查（依赖注入版本）"""

    def __init__(
        self,
        permissions: List[str],
        op: str = "AND",
        permission_checker: Callable = None,
    ):
        """
        初始化权限链

        Args:
            permissions: 权限列表
            op: 操作符 ('AND' 或 'OR')
            permission_checker: 权限检查函数（依赖注入）
        """
        self.permissions = permissions
        self.op = op.upper()
        self.permission_checker = permission_checker

    def __call__(self, fn):
        """装饰器实现 - 真正的权限检查逻辑"""

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if self.permission_checker is None:
                # 如果没有权限检查函数，直接执行原函数
                return fn(*args, **kwargs)

            # 执行权限检查
            if self._check_permissions(*args, **kwargs):
                return fn(*args, **kwargs)
            else:
                # 权限检查失败，返回403错误
                from flask import jsonify

                return jsonify({"error": "权限不足"}), 403

        return wrapper

    def _check_permissions(self, *args, **kwargs) -> bool:
        """
        检查权限链中的所有权限

        Args:
            *args, **kwargs: 传递给权限检查函数的参数

        Returns:
            bool: 权限检查结果
        """
        if not self.permissions:
            return True

        results = []
        for permission in self.permissions:
            try:
                # 调用注入的权限检查函数
                result = self.permission_checker(permission, *args, **kwargs)
                results.append(result)

                # 短路求值优化
                if self.op == "AND" and not result:
                    return False  # AND操作，遇到False直接返回
                elif self.op == "OR" and result:
                    return True  # OR操作，遇到True直接返回

            except Exception as e:
                # 权限检查出错，记录日志但不中断
                print(f"权限检查出错: {permission}, 错误: {e}")
                results.append(False)

        # 根据操作符返回最终结果
        if self.op == "AND":
            return all(results)
        elif self.op == "OR":
            return any(results)
        else:
            return False

    def add_permission(self, permission: str):
        """添加权限到链"""
        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission: str):
        """从链中移除权限"""
        if permission in self.permissions:
            self.permissions.remove(permission)

    def set_permission_checker(self, checker: Callable):
        """设置权限检查函数（依赖注入）"""
        self.permission_checker = checker


class PermissionGroup:
    """权限组类 - 管理相关权限的集合"""

    def __init__(self, name: str, permissions: List[str] = None):
        self.name = name
        self.permissions = permissions or []

    def add_permission(self, permission: str):
        """添加权限到组"""
        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission: str):
        """从组中移除权限"""
        if permission in self.permissions:
            self.permissions.remove(permission)

    def register_all(
        self, permission_checker: Callable = None, description_prefix: str = ""
    ):
        """
        注册组中的所有权限

        Args:
            permission_checker: 权限注册函数（依赖注入）
            description_prefix: 描述前缀
        """
        if permission_checker is None:
            return

        for perm in self.permissions:
            if validate_permission_structure(perm):
                permission_checker(
                    perm, group=self.name, description=f"{description_prefix} - {perm}"
                )

    def get_permissions(self) -> List[str]:
        """获取组中的所有权限"""
        return self.permissions.copy()

    def validate_permissions(self) -> Dict[str, bool]:
        """验证组中的所有权限结构"""
        return {perm: validate_permission_structure(perm) for perm in self.permissions}


# 预定义的权限模板
CRUD_TEMPLATE = PermissionTemplate(
    "crud", ["create", "read", "update", "delete"], "标准CRUD操作权限"
)

MESSAGE_TEMPLATE = PermissionTemplate(
    "message",
    [
        "message.send",
        "message.edit",
        "message.delete",
        "message.pin",
        "message.react",
        "message.search",
    ],
    "消息操作权限",
)

SERVER_TEMPLATE = PermissionTemplate(
    "server",
    ["server.view", "server.manage", "server.invite", "server.kick", "server.ban"],
    "服务器管理权限",
)

CHANNEL_TEMPLATE = PermissionTemplate(
    "channel",
    ["channel.view", "channel.send", "channel.manage", "channel.join", "channel.leave"],
    "频道操作权限",
)

ROLE_TEMPLATE = PermissionTemplate(
    "role", ["role.view", "role.assign", "role.manage", "role.delete"], "角色管理权限"
)


# 工厂函数
def create_permission_template(
    name: str, permissions: List[str], description: str = ""
) -> PermissionTemplate:
    """创建权限模板"""
    return PermissionTemplate(name, permissions, description)


def create_permission_chain(
    permissions: List[str], op: str = "AND", permission_checker: Callable = None
) -> PermissionChain:
    """创建权限链"""
    return PermissionChain(permissions, op, permission_checker)


def create_permission_group(
    name: str, permissions: List[str] = None
) -> PermissionGroup:
    """创建权限组"""
    return PermissionGroup(name, permissions)


# 导出所有抽象类和函数
__all__ = [
    "PermissionTemplate",
    "PermissionChain",
    "PermissionGroup",
    "PERMISSION_PATTERNS",
    "CRUD_TEMPLATE",
    "MESSAGE_TEMPLATE",
    "SERVER_TEMPLATE",
    "CHANNEL_TEMPLATE",
    "ROLE_TEMPLATE",
    "create_permission_template",
    "create_permission_chain",
    "create_permission_group",
]
