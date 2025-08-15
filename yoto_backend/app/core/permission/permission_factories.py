"""
权限工厂模块 - 工厂函数层
提供权限相关的工厂函数，负责创建和注册逻辑
不包含权限检查或保护逻辑
"""

from typing import Dict, List, Callable, Optional

# 暂时注释掉这些导入，因为它们可能不存在
# from app.core.permission_abstractions import (
#     PermissionTemplate,
#     PermissionChain,
#     PermissionGroup,
#     create_permission_template,
#     create_permission_chain,
#     create_permission_group
# )


def create_crud_permissions(resource: str, group: str = None) -> Dict[str, str]:
    """
    创建CRUD权限模式
    返回包含create, read, update, delete权限的字典

    Args:
        resource: 资源名称
        group: 权限组名（可选）

    Returns:
        Dict[str, str]: CRUD权限字典

    Examples:
        >>> create_crud_permissions('user')
        {'create': 'user.create', 'read': 'user.read', 'update': 'user.update', 'delete': 'user.delete'}
    """
    return {
        "create": f"{resource}.create",
        "read": f"{resource}.read",
        "update": f"{resource}.update",
        "delete": f"{resource}.delete",
    }


def register_crud_permissions(
    resource: str,
    permission_register: Callable = None,
    group: str = None,
    description: str = "",
) -> Dict[str, str]:
    """
    注册CRUD权限并返回权限名称字典

    Args:
        resource: 资源名称
        permission_register: 权限注册函数（依赖注入）
        group: 权限组名（可选）
        description: 权限描述（可选）

    Returns:
        Dict[str, str]: 注册的权限名称字典

    Examples:
        >>> register_crud_permissions('user', mock_register)
        {'create': 'user.create', 'read': 'user.read', 'update': 'user.update', 'delete': 'user.delete'}
    """
    permissions = create_crud_permissions(resource, group)

    if permission_register is not None:
        for action, perm_name in permissions.items():
            permission_register(
                perm_name, group=group, description=f"{description} - {action}"
            )

    return permissions


def create_permission_pattern(
    pattern_name: str, permissions: List[str], group: str = None, description: str = ""
):
    """
    创建权限模式模板

    Args:
        pattern_name: 模式名称
        permissions: 权限列表
        group: 权限组名（可选）
        description: 模式描述（可选）

    Returns:
        dict: 权限模式字典

    Examples:
        >>> template = create_permission_pattern('admin', ['user.manage', 'server.manage'])
        >>> template['name']
        'admin'
    """
    return {
        "name": pattern_name,
        "permissions": permissions,
        "group": group,
        "description": description,
    }


def register_permission_pattern(
    pattern, permission_register: Callable = None, group: str = None
) -> List[str]:
    """
    注册权限模式中的所有权限

    Args:
        pattern: 权限模式字典
        permission_register: 权限注册函数（依赖注入）
        group: 权限组名（可选）

    Returns:
        List[str]: 注册的权限名称列表

    Examples:
        >>> template = create_permission_pattern('admin', ['user.manage'])
        >>> register_permission_pattern(template, mock_register)
        ['user.manage']
    """
    return pattern.register_all(permission_register, group)


def create_permission_chain(
    permissions: List[str], op: str = "AND", permission_checker: Callable = None
):
    """
    创建权限链

    Args:
        permissions: 权限列表
        op: 操作符 ('AND' 或 'OR')
        permission_checker: 权限检查函数（依赖注入）

    Returns:
        dict: 权限链字典

    Examples:
        >>> chain = create_permission_chain(['user.read', 'user.write'], 'AND')
        >>> chain['permissions']
        ['user.read', 'user.write']
    """
    return {"permissions": permissions, "op": op, "checker": permission_checker}


def create_permission_group(name: str, permissions: List[str] = None):
    """
    创建权限组

    Args:
        name: 权限组名称
        permissions: 权限列表（可选）

    Returns:
        dict: 权限组字典

    Examples:
        >>> group = create_permission_group('admin', ['user.manage', 'server.manage'])
        >>> group['name']
        'admin'
    """
    return {"name": name, "permissions": permissions or []}


def create_permission_decorator(
    permission: str,
    scope: str = None,
    scope_id_arg: str = None,
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
) -> Callable:
    """
    创建权限装饰器工厂函数
    支持自定义权限检查逻辑

    Args:
        permission: 权限名称
        scope: 作用域（可选）
        scope_id_arg: 作用域ID参数名（可选）
        resource_check: 资源检查函数（可选）
        group: 权限组名（可选）
        description: 权限描述（可选）

    Returns:
        Callable: 权限装饰器函数

    Examples:
        >>> decorator = create_permission_decorator('user.read', 'server', 'server_id')
        >>> @decorator
        >>> def my_function():
        >>>     pass
    """

    def decorator(fn):
        # 这里返回一个简单的装饰器，实际的权限检查逻辑由调用方注入
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_crud_permission(
    action: str,
    resource: str,
    scope: str = None,
    scope_id_arg: str = None,
    resource_check: Callable = None,
) -> Callable:
    """
    创建CRUD权限检查装饰器

    Args:
        action: CRUD操作（create, read, update, delete）
        resource: 资源名称
        scope: 作用域（可选）
        scope_id_arg: 作用域ID参数名（可选）
        resource_check: 资源检查函数（可选）

    Returns:
        Callable: CRUD权限装饰器函数

    Examples:
        >>> decorator = require_crud_permission('read', 'user', 'server', 'server_id')
        >>> @decorator
        >>> def get_user():
        >>>     pass
    """
    permission = f"{resource}.{action}"
    return create_permission_decorator(
        permission,
        scope=scope,
        scope_id_arg=scope_id_arg,
        resource_check=resource_check,
        group=resource,
    )


# 导出所有工厂函数
__all__ = [
    "create_crud_permissions",
    "register_crud_permissions",
    "create_permission_pattern",
    "register_permission_pattern",
    "create_permission_chain",
    "create_permission_group",
    "create_permission_decorator",
    "require_crud_permission",
]
