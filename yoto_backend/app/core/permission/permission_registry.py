"""
权限注册模块

包含权限和角色的注册与管理功能

架构说明：
- 本地注册表（_permission_registry, _role_registry）仅用于启动时声明缓存
- 运行时数据源：数据库 + 多级缓存系统
- 设计原则：数据库作为权威数据源，缓存作为性能优化

使用场景：
- 启动时：initialize_permission_registry() 加载权限声明到本地注册表
- 运行时：所有数据操作直接面向数据库，通过多级缓存系统优化性能
- 测试时：invalidate_registry_cache() 用于重置测试状态

注意：本地注册表不参与运行时数据管理，仅作为启动时的权限声明记录
"""

import time
import logging
import warnings
from typing import Dict, List, Optional, Set, Any
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

from flask import current_app
from app.blueprints.roles.models import Permission, RolePermission
from app.core.extensions import db
from app.blueprints.roles.models import Role

logger = logging.getLogger(__name__)

# 本地注册表缓存 - 仅用于启动时的权限声明记录
# 注意：
# 1. 这是进程内缓存，多进程环境下不共享
# 2. 仅用于启动时声明，不作为运行时数据源
# 3. 运行时数据源：数据库 + 多级缓存系统
# 4. 生产环境建议：依赖数据库和多级缓存系统，而非此本地缓存
_permission_registry = set()  # 统一使用set，避免数据结构不一致
_role_registry = set()  # 简化为set，只存储名称


def register_permission(
    name: str, group: str = None, description: str = None, is_deprecated: bool = False
) -> Dict:
    """
    注册权限 - 统一版本

    参数:
        name (str): 权限名称
        group (str): 权限组
        description (str): 权限描述
        is_deprecated (bool): 是否已废弃

    返回:
        Dict: 权限信息
    """
    try:
        # 添加到本地注册表（仅用于启动时声明）
        _permission_registry.add(name)

        # 检查权限是否已存在
        try:
            # 检查是否在Flask应用上下文中
            from flask import current_app

            try:
                # 尝试访问current_app，如果成功说明在Flask上下文中
                _ = current_app.name
                existing_permission = (
                    db.session.query(Permission).filter(Permission.name == name).first()
                )
            except RuntimeError:
                # 不在Flask上下文中，跳过数据库操作
                logger.warning(f"不在Flask应用上下文中，跳过权限注册: {name}")
                return {}
        except Exception as e:
            logger.error(f"数据库查询失败: {e}")
            return {}

        if existing_permission:
            # 更新现有权限
            existing_permission.group = group or existing_permission.group
            existing_permission.description = (
                description or existing_permission.description
            )
            existing_permission.is_deprecated = is_deprecated
            db.session.commit()

            permission_info = {
                "id": existing_permission.id,
                "name": existing_permission.name,
                "group": existing_permission.group,
                "description": existing_permission.description,
                "is_deprecated": existing_permission.is_deprecated,
                "created_at": existing_permission.created_at,
                "updated_at": existing_permission.updated_at,
            }
        else:
            # 创建新权限
            new_permission = Permission(
                name=name,
                group=group,
                description=description,
                is_deprecated=is_deprecated,
            )
            db.session.add(new_permission)
            db.session.commit()

            permission_info = {
                "id": new_permission.id,
                "name": new_permission.name,
                "group": new_permission.group,
                "description": new_permission.description,
                "is_deprecated": new_permission.is_deprecated,
                "created_at": new_permission.created_at,
                "updated_at": new_permission.updated_at,
            }

        logger.info(f"权限注册成功: {name}")
        return permission_info

    except Exception as e:
        logger.error(f"权限注册失败: {name}, 错误: {e}")
        return {}


def register_permission_legacy(perm: str, group: str = None, description: str = None):
    """
    注册权限 - 旧版本（已废弃）

    警告：此函数已废弃，请使用 register_permission 函数。
    此函数仅用于向后兼容，将在未来版本中移除。

    参数:
        perm (str): 权限名称
        group (str): 权限组
        description (str): 权限描述

    返回:
        Dict: 注册结果
    """
    warnings.warn(
        "register_permission_legacy 已废弃，请使用 register_permission 函数。",
        DeprecationWarning,
        stacklevel=2,
    )

    # 调用新的实现
    result = register_permission(perm, group, description, False)

    # 为了向后兼容，返回旧格式的结果
    if result:
        return {
            "name": result["name"],
            "group": result["group"],
            "description": result["description"],
            "status": "registered",
        }
    else:
        return {
            "name": perm,
            "group": group,
            "description": description,
            "status": "error",
        }


def register_role(name: str, server_id: int, is_active: bool = True) -> Dict:
    """
    注册角色 - 版本2

    参数:
        name (str): 角色名称
        server_id (int): 服务器ID
        is_active (bool): 是否激活

    返回:
        Dict: 角色信息
    """
    try:
        # 添加到本地注册表（仅用于启动时声明）
        role_key = f"{name}_{server_id}"
        _role_registry.add(role_key)

        # 检查角色是否已存在
        try:
            # 检查是否在Flask应用上下文中
            from flask import current_app

            try:
                # 尝试访问current_app，如果成功说明在Flask上下文中
                _ = current_app.name
                existing_role = (
                    db.session.query(Role)
                    .filter(and_(Role.name == name, Role.server_id == server_id))
                    .first()
                )
            except RuntimeError:
                # 不在Flask上下文中，跳过数据库操作
                logger.warning(f"不在Flask应用上下文中，跳过角色注册: {name}")
                return {}
        except Exception as e:
            logger.error(f"数据库查询失败: {e}")
            return {}

        if existing_role:
            # 更新现有角色
            existing_role.is_active = is_active
            db.session.commit()

            role_info = {
                "id": existing_role.id,
                "name": existing_role.name,
                "server_id": existing_role.server_id,
                "role_type": existing_role.role_type,
                "priority": existing_role.priority,
                "is_active": existing_role.is_active,
                "created_at": existing_role.created_at,
                "updated_at": existing_role.updated_at,
            }
        else:
            # 创建新角色
            new_role = Role(
                name=name,
                server_id=server_id,
                role_type="custom",
                priority=50,
                is_active=is_active,
            )
            db.session.add(new_role)
            db.session.commit()

            role_info = {
                "id": new_role.id,
                "name": new_role.name,
                "server_id": new_role.server_id,
                "role_type": new_role.role_type,
                "priority": new_role.priority,
                "is_active": new_role.is_active,
                "created_at": new_role.created_at,
                "updated_at": new_role.updated_at,
            }

        logger.info(f"角色注册成功: {name}")
        return role_info

    except Exception as e:
        logger.error(f"角色注册失败: {name}, 错误: {e}")
        return {}


def batch_register_permissions(permissions_data: List[Dict]) -> List[Dict]:
    """
    批量注册权限 - 使用SQLAlchemy高级特性优化版本

    使用真正的批量操作，避免N+1查询问题
    采用SQLAlchemy的高级特性：bulk_insert_mappings, bulk_update_mappings

    参数:
        permissions_data (List[Dict]): 权限数据列表

    返回:
        List[Dict]: 注册结果列表
    """
    if not permissions_data:
        return []

    try:
        # 提取所有权限名称
        permission_names = [
            perm_data.get("name")
            for perm_data in permissions_data
            if perm_data.get("name")
        ]
        if not permission_names:
            logger.warning("没有有效的权限名称，跳过批量注册")
            return []

        # 一次性查询所有已存在的权限
        existing_permissions = (
            db.session.query(Permission)
            .filter(Permission.name.in_(permission_names))
            .all()
        )
        existing_permissions_map = {perm.name: perm for perm in existing_permissions}

        # 分离需要插入和更新的权限
        to_insert = []
        to_update = []
        results = []

        for perm_data in permissions_data:
            name = perm_data.get("name")
            group = perm_data.get("group")
            description = perm_data.get("description")
            is_deprecated = perm_data.get("is_deprecated", False)

            if not name:
                logger.warning("权限名称不能为空，跳过")
                continue

            if name in existing_permissions_map:
                # 需要更新的权限
                existing_perm = existing_permissions_map[name]
                to_update.append(
                    {
                        "id": existing_perm.id,
                        "name": name,
                        "group": group,
                        "description": description,
                        "is_deprecated": is_deprecated,
                    }
                )
                results.append(
                    {
                        "id": existing_perm.id,
                        "name": name,
                        "group": group,
                        "description": description,
                        "is_deprecated": is_deprecated,
                        "status": "updated",
                    }
                )
            else:
                # 需要插入的权限
                to_insert.append(
                    {
                        "name": name,
                        "group": group,
                        "description": description,
                        "is_deprecated": is_deprecated,
                    }
                )
                results.append(
                    {
                        "name": name,
                        "group": group,
                        "description": description,
                        "is_deprecated": is_deprecated,
                        "status": "created",
                    }
                )

        # 使用SQLAlchemy的高级批量操作
        if to_insert:
            # 使用bulk_insert_mappings进行批量插入
            db.session.bulk_insert_mappings(Permission, to_insert)
            logger.info(f"批量插入 {len(to_insert)} 个权限")

        if to_update:
            # 使用bulk_update_mappings进行批量更新
            db.session.bulk_update_mappings(Permission, to_update)
            logger.info(f"批量更新 {len(to_update)} 个权限")

        # 一次性提交所有操作
        db.session.commit()

        # 更新本地注册表缓存
        for perm_data in permissions_data:
            name = perm_data.get("name")
            if name:
                _permission_registry.add(name)

        logger.info(
            f"批量注册权限完成: 创建 {len(to_insert)} 个，更新 {len(to_update)} 个"
        )
        return results

    except Exception as e:
        logger.error(f"批量注册权限失败: {e}")
        db.session.rollback()
        return []


def batch_register_roles(roles_data: List[Dict]) -> List[Dict]:
    """
    批量注册角色 - 使用SQLAlchemy高级特性优化版本

    使用真正的批量操作，避免N+1查询问题
    采用SQLAlchemy的高级特性：bulk_insert_mappings, bulk_update_mappings

    参数:
        roles_data (List[Dict]): 角色数据列表

    返回:
        List[Dict]: 注册结果列表
    """
    if not roles_data:
        return []

    try:
        # 提取所有角色名称和服务器ID组合
        role_identifiers = []
        for role_data in roles_data:
            name = role_data.get("name")
            server_id = role_data.get("server_id")
            if name and server_id is not None:
                role_identifiers.append((name, server_id))
            elif name:
                logger.warning(f"角色 {name} 缺少有效的server_id，跳过")
                continue

        if not role_identifiers:
            logger.warning("没有有效的角色数据，跳过批量注册")
            return []

        # 一次性查询所有已存在的角色
        existing_roles = (
            db.session.query(Role)
            .filter(
                or_(
                    *[
                        and_(Role.name == name, Role.server_id == server_id)
                        for name, server_id in role_identifiers
                    ]
                )
            )
            .all()
        )
        existing_roles_map = {
            (role.name, role.server_id): role for role in existing_roles
        }

        # 分离需要插入和更新的角色
        to_insert = []
        to_update = []
        results = []

        for role_data in roles_data:
            name = role_data.get("name")
            server_id = role_data.get("server_id")
            is_active = role_data.get("is_active", True)

            if not name:
                logger.warning("角色名称不能为空，跳过")
                continue

            if server_id is None:
                logger.warning(f"角色 {name} 缺少有效的server_id，跳过")
                continue

            if (name, server_id) in existing_roles_map:
                # 需要更新的角色
                existing_role = existing_roles_map[(name, server_id)]
                to_update.append(
                    {
                        "id": existing_role.id,
                        "name": name,
                        "server_id": server_id,
                        "is_active": is_active,
                    }
                )
                results.append(
                    {
                        "id": existing_role.id,
                        "name": name,
                        "server_id": server_id,
                        "is_active": is_active,
                        "status": "updated",
                    }
                )
            else:
                # 需要插入的角色
                to_insert.append(
                    {
                        "name": name,
                        "server_id": server_id,
                        "role_type": "custom",
                        "priority": 50,
                        "is_active": is_active,
                    }
                )
                results.append(
                    {
                        "name": name,
                        "server_id": server_id,
                        "is_active": is_active,
                        "status": "created",
                    }
                )

        # 使用SQLAlchemy的高级批量操作
        if to_insert:
            # 使用bulk_insert_mappings进行批量插入
            db.session.bulk_insert_mappings(Role, to_insert)
            logger.info(f"批量插入 {len(to_insert)} 个角色")

        if to_update:
            # 使用bulk_update_mappings进行批量更新
            db.session.bulk_update_mappings(Role, to_update)
            logger.info(f"批量更新 {len(to_update)} 个角色")

        # 一次性提交所有操作
        db.session.commit()

        # 更新本地注册表缓存
        for role_data in roles_data:
            name = role_data.get("name")
            server_id = role_data.get("server_id")
            if name and server_id is not None:
                role_key = f"{name}_{server_id}"
                _role_registry.add(role_key)

        logger.info(
            f"批量注册角色完成: 创建 {len(to_insert)} 个，更新 {len(to_update)} 个"
        )
        return results

    except Exception as e:
        logger.error(f"批量注册角色失败: {e}")
        db.session.rollback()
        return []


def assign_permissions_to_role_v2(
    role_id: int,
    permission_ids: List[int],
    scope_type: str = None,
    scope_id: int = None,
) -> List[Dict]:
    """
    为角色分配权限 - 版本2 - 优化版本

    使用真正的批量操作，避免N+1查询问题

    参数:
        role_id (int): 角色ID
        permission_ids (List[int]): 权限ID列表
        scope_type (str): 作用域类型
        scope_id (int): 作用域ID

    返回:
        List[Dict]: 分配结果列表
    """
    if not permission_ids:
        return []

    try:
        # 一次性查询所有已存在的角色权限关系
        existing_role_permissions = (
            db.session.query(RolePermission)
            .filter(
                and_(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id.in_(permission_ids),
                    RolePermission.scope_type == scope_type,
                    RolePermission.scope_id == scope_id,
                )
            )
            .all()
        )

        # 创建已存在关系的集合，用于快速查找
        existing_perm_ids = {rp.permission_id for rp in existing_role_permissions}

        # 计算需要新增的权限ID
        new_permission_ids = [
            pid for pid in permission_ids if pid not in existing_perm_ids
        ]

        # 批量创建新的角色权限关系
        new_role_permissions = []
        results = []

        for permission_id in new_permission_ids:
            role_permission = RolePermission(
                role_id=role_id,
                permission_id=permission_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            new_role_permissions.append(role_permission)
            results.append(
                {
                    "role_id": role_id,
                    "permission_id": permission_id,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "status": "assigned",
                }
            )

        # 批量添加所有新关系
        if new_role_permissions:
            db.session.add_all(new_role_permissions)
        db.session.commit()

        # 失效相关缓存
        # from .permission_cache import invalidate_role_permissions
        # invalidate_role_permissions(role_id)

        logger.info(f"为角色 {role_id} 分配了 {len(results)} 个权限")
        return results

    except Exception as e:
        logger.error(f"为角色分配权限失败: {e}")
        db.session.rollback()
        return []


def assign_roles_to_user_v2(
    user_id: int, role_ids: List[int], server_id: int
) -> List[Dict]:
    """
    为用户分配角色 - 版本2 - 优化版本

    使用真正的批量操作，避免N+1查询问题

    参数:
        user_id (int): 用户ID
        role_ids (List[int]): 角色ID列表
        server_id (int): 服务器ID

    返回:
        List[Dict]: 分配结果列表
    """
    if not role_ids:
        return []

    try:
        from app.blueprints.roles.models import UserRole
        from app.core.extensions import db

        # 一次性查询所有已存在的用户角色关系
        existing_user_roles = (
            db.session.query(UserRole)
            .filter(and_(UserRole.user_id == user_id, UserRole.role_id.in_(role_ids)))
            .all()
        )

        # 创建已存在关系的集合，用于快速查找
        existing_role_ids = {ur.role_id for ur in existing_user_roles}

        # 计算需要新增的角色ID
        new_role_ids = [rid for rid in role_ids if rid not in existing_role_ids]

        # 批量创建新的用户角色关系
        new_user_roles = []
        results = []

        for role_id in new_role_ids:
            user_role = UserRole(user_id=user_id, role_id=role_id)
            new_user_roles.append(user_role)
            results.append(
                {"user_id": user_id, "role_id": role_id, "status": "assigned"}
            )

        # 批量添加所有新关系
        if new_user_roles:
            db.session.add_all(new_user_roles)
        db.session.commit()

        # 失效相关缓存
        # from .permission_cache import invalidate_user_permissions
        # invalidate_user_permissions(user_id)

        logger.info(f"为用户 {user_id} 分配了 {len(results)} 个角色")
        return results

    except Exception as e:
        logger.error(f"为用户分配角色失败: {e}")
        db.session.rollback()
        return []


def get_permission_registry_stats() -> Dict:
    """
    获取权限注册统计

    注意：此函数从数据库获取真实数据，而非依赖本地缓存
    确保数据的一致性和准确性

    返回:
        Dict: 注册统计信息
    """
    try:
        # 检查是否在Flask应用上下文中
        from flask import current_app

        try:
            # 尝试访问current_app，如果成功说明在Flask上下文中
            _ = current_app.name
        except RuntimeError:
            # 不在Flask上下文中，返回本地注册表统计
            logger.warning("不在Flask应用上下文中，返回本地注册表统计")
            return {
                "permissions": {
                    "total": len(_permission_registry),
                    "active": len(_permission_registry),
                    "deprecated": 0,
                    "groups": {},
                },
                "roles": {
                    "total": len(_role_registry),
                    "active": len(_role_registry),
                    "inactive": 0,
                },
                "local_registry": {
                    "permissions": len(_permission_registry),
                    "roles": len(_role_registry),
                    "note": "本地注册表仅用于启动时声明，不作为主要数据源",
                },
                "note": "数据来自本地注册表，因为不在Flask应用上下文中",
            }

        # 权限统计 - 从数据库获取真实数据
        total_permissions = db.session.query(func.count(Permission.id)).scalar()
        active_permissions = (
            db.session.query(func.count(Permission.id))
            .filter(Permission.is_deprecated == False)
            .scalar()
        )
        deprecated_permissions = (
            db.session.query(func.count(Permission.id))
            .filter(Permission.is_deprecated == True)
            .scalar()
        )

        # 角色统计 - 从数据库获取真实数据
        total_roles = db.session.query(func.count(Role.id)).scalar()
        active_roles = (
            db.session.query(func.count(Role.id))
            .filter(Role.is_active == True)
            .scalar()
        )
        inactive_roles = (
            db.session.query(func.count(Role.id))
            .filter(Role.is_active == False)
            .scalar()
        )

        # 按组统计权限 - 从数据库获取真实数据
        permission_groups = (
            db.session.query(Permission.group, func.count(Permission.id))
            .group_by(Permission.group)
            .all()
        )

        # 本地注册表统计（仅用于参考，不作为主要数据源）
        local_permission_count = len(_permission_registry)
        local_role_count = len(_role_registry)

        return {
            "permissions": {
                "total": total_permissions,
                "active": active_permissions,
                "deprecated": deprecated_permissions,
                "groups": dict(permission_groups),
            },
            "roles": {
                "total": total_roles,
                "active": active_roles,
                "inactive": inactive_roles,
            },
            "local_registry": {
                "permissions": local_permission_count,
                "roles": local_role_count,
                "note": "本地注册表仅用于启动时声明，不作为主要数据源",
            },
        }

    except Exception as e:
        logger.error(f"获取权限注册统计失败: {e}")
        return {}


def invalidate_registry_cache(permission_id: int = None, role_id: int = None):
    """
    失效本地注册缓存 - 仅用于测试和调试

    注意：此函数主要用于测试场景，用于重置应用的初始状态
    在生产环境中通常无需调用，因为：
    1. 本地注册表仅用于启动时声明，不作为运行时数据源
    2. 实际数据源是数据库和多级缓存系统
    3. 应用重启时会通过 initialize_permission_registry 重新加载

    参数:
        permission_id (int): 权限ID（仅用于日志记录）
        role_id (int): 角色ID（仅用于日志记录）
    """
    if permission_id:
        logger.debug(f"测试场景：权限 {permission_id} 的本地注册缓存已标记为失效")

    if role_id:
        logger.debug(f"测试场景：角色 {role_id} 的本地注册缓存已标记为失效")

    if not permission_id and not role_id:
        # 清空本地注册表（仅用于测试场景重置初始状态）
        _permission_registry.clear()
        _role_registry.clear()
        logger.info("测试场景：已清空本地权限注册缓存（仅用于启动时声明）")
        logger.debug("注意：此操作仅用于测试，生产环境中无需调用")


def list_registered_permissions() -> List[Dict]:
    """
    列出所有注册的权限

    注意：此函数从数据库获取真实数据，确保数据一致性
    本地注册表仅用于启动时声明，不作为主要数据源

    返回:
        List[Dict]: 权限列表
    """
    try:
        # 检查是否在Flask应用上下文中
        from flask import current_app

        try:
            # 尝试访问current_app，如果成功说明在Flask上下文中
            _ = current_app.name
        except RuntimeError:
            # 不在Flask上下文中，返回本地注册表数据
            logger.warning("不在Flask应用上下文中，返回本地注册表权限列表")
            return [
                {
                    "name": perm_name,
                    "group": "unknown",
                    "description": "权限来自本地注册表",
                    "is_deprecated": False,
                    "note": "数据来自本地注册表，因为不在Flask应用上下文中",
                }
                for perm_name in _permission_registry
            ]

        # 从数据库获取真实数据
        permissions = db.session.query(Permission).all()

        return [
            {
                "id": perm.id,
                "name": perm.name,
                "group": perm.group,
                "description": perm.description,
                "is_deprecated": perm.is_deprecated,
                "created_at": perm.created_at,
                "updated_at": perm.updated_at,
            }
            for perm in permissions
        ]

    except Exception as e:
        logger.error(f"列出注册权限失败: {e}")
        return []


def list_registered_roles() -> List[Dict]:
    """
    列出所有注册的角色

    注意：此函数从数据库获取真实数据，确保数据一致性
    本地注册表仅用于启动时声明，不作为主要数据源

    返回:
        List[Dict]: 角色列表
    """
    try:
        # 检查是否在Flask应用上下文中
        from flask import current_app

        try:
            # 尝试访问current_app，如果成功说明在Flask上下文中
            _ = current_app.name
        except RuntimeError:
            # 不在Flask上下文中，返回本地注册表数据
            logger.warning("不在Flask应用上下文中，返回本地注册表角色列表")
            return [
                {
                    "name": role_name.split("_")[0] if "_" in role_name else role_name,
                    "server_id": (
                        int(role_name.split("_")[1])
                        if "_" in role_name and role_name.split("_")[1].isdigit()
                        else 0
                    ),
                    "role_type": "custom",
                    "priority": 50,
                    "is_active": True,
                    "note": "数据来自本地注册表，因为不在Flask应用上下文中",
                }
                for role_name in _role_registry
            ]

        # 从数据库获取真实数据
        roles = db.session.query(Role).all()

        return [
            {
                "id": role.id,
                "name": role.name,
                "server_id": role.server_id,
                "role_type": role.role_type,
                "priority": role.priority,
                "is_active": role.is_active,
                "created_at": role.created_at,
                "updated_at": role.updated_at,
            }
            for role in roles
        ]

    except Exception as e:
        logger.error(f"列出注册角色失败: {e}")
        return []


def initialize_permission_registry():
    """
    初始化权限注册表

    在应用启动时调用，用于加载权限声明到本地注册表
    注意：这只是为了向后兼容，实际数据源是数据库和多级缓存系统
    """
    try:
        # 从数据库加载所有权限名称到本地注册表
        permissions = db.session.query(Permission.name).all()
        for perm in permissions:
            _permission_registry.add(perm[0])

        # 从数据库加载所有角色名称到本地注册表
        roles = db.session.query(Role.name, Role.server_id).all()
        for role in roles:
            role_key = f"{role[0]}_{role[1]}"
            _role_registry.add(role_key)

        logger.info(
            f"权限注册表初始化完成: {len(_permission_registry)} 个权限, {len(_role_registry)} 个角色"
        )

    except Exception as e:
        logger.error(f"权限注册表初始化失败: {e}")


def get_local_registry_info() -> Dict:
    """
    获取本地注册表信息 - 仅用于调试和监控

    注意：此函数仅用于开发调试和系统监控
    不作为业务数据源，因为：
    1. 本地注册表仅用于启动时声明
    2. 运行时数据源是数据库和多级缓存系统
    3. 此函数返回的数据可能与实际业务数据不一致

    返回:
        Dict: 本地注册表信息（仅用于调试）
    """
    return {
        "permissions": {
            "count": len(_permission_registry),
            "names": list(_permission_registry),
        },
        "roles": {"count": len(_role_registry), "names": list(_role_registry)},
        "note": "本地注册表仅用于启动时声明，不作为主要数据源",
        "warning": "此信息仅用于调试，不应作为业务决策依据",
    }


# 在文件末尾添加权限组相关的方法


def register_group(name: str, description: str = None, is_active: bool = True) -> Dict:
    """
    注册权限组

    参数:
        name (str): 权限组名称
        description (str): 权限组描述
        is_active (bool): 是否激活

    返回:
        Dict: 权限组信息
    """
    try:
        from app.blueprints.roles.models import PermissionGroup

        # 检查权限组是否已存在
        existing_group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == name)
            .first()
        )

        if existing_group:
            # 更新现有权限组
            existing_group.description = description or existing_group.description
            existing_group.is_active = is_active
            db.session.commit()

            group_info = {
                "id": existing_group.id,
                "name": existing_group.name,
                "description": existing_group.description,
                "is_active": existing_group.is_active,
                "created_at": existing_group.created_at,
                "updated_at": existing_group.updated_at,
            }
        else:
            # 创建新权限组
            new_group = PermissionGroup(
                name=name, description=description, is_active=is_active
            )
            db.session.add(new_group)
            db.session.commit()

            group_info = {
                "id": new_group.id,
                "name": new_group.name,
                "description": new_group.description,
                "is_active": new_group.is_active,
                "created_at": new_group.created_at,
                "updated_at": new_group.updated_at,
            }

        logger.info(f"权限组注册成功: {name}")
        return group_info

    except Exception as e:
        logger.error(f"权限组注册失败: {name}, error: {e}")
        db.session.rollback()
        raise


def assign_permission_to_group(group_name: str, permission_name: str) -> Dict:
    """
    为权限组分配权限

    参数:
        group_name (str): 权限组名称
        permission_name (str): 权限名称

    返回:
        Dict: 分配结果
    """
    try:
        from app.blueprints.roles.models import (
            PermissionGroup,
            Permission,
            GroupToPermissionMapping,
        )

        # 查找权限组
        group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == group_name)
            .first()
        )
        if not group:
            raise ValueError(f"权限组不存在: {group_name}")

        # 查找权限
        permission = (
            db.session.query(Permission)
            .filter(Permission.name == permission_name)
            .first()
        )
        if not permission:
            raise ValueError(f"权限不存在: {permission_name}")

        # 检查是否已经分配
        existing_mapping = (
            db.session.query(GroupToPermissionMapping)
            .filter(
                GroupToPermissionMapping.group_id == group.id,
                GroupToPermissionMapping.permission_id == permission.id,
            )
            .first()
        )

        if existing_mapping:
            return {
                "success": True,
                "message": f"权限 {permission_name} 已经分配给权限组 {group_name}",
                "mapping_id": existing_mapping.id,
            }

        # 创建新的映射
        mapping = GroupToPermissionMapping(
            group_id=group.id, permission_id=permission.id
        )
        db.session.add(mapping)
        db.session.commit()

        logger.info(f"权限分配成功: {permission_name} -> {group_name}")
        return {
            "success": True,
            "message": f"权限 {permission_name} 已分配给权限组 {group_name}",
            "mapping_id": mapping.id,
        }

    except Exception as e:
        logger.error(f"权限分配失败: {permission_name} -> {group_name}, error: {e}")
        db.session.rollback()
        raise


def assign_group_to_role(
    role_id: int, group_name: str, scope_type: str = None, scope_id: int = None
) -> Dict:
    """
    为角色分配权限组

    参数:
        role_id (int): 角色ID
        group_name (str): 权限组名称
        scope_type (str): 作用域类型
        scope_id (int): 作用域ID

    返回:
        Dict: 分配结果
    """
    try:
        from app.blueprints.roles.models import (
            Role,
            PermissionGroup,
            RoleToGroupMapping,
        )

        # 查找角色
        role = db.session.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ValueError(f"角色不存在: {role_id}")

        # 查找权限组
        group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == group_name)
            .first()
        )
        if not group:
            raise ValueError(f"权限组不存在: {group_name}")

        # 检查是否已经分配
        existing_mapping = (
            db.session.query(RoleToGroupMapping)
            .filter(
                RoleToGroupMapping.role_id == role_id,
                RoleToGroupMapping.group_id == group.id,
                RoleToGroupMapping.scope_type == scope_type,
                RoleToGroupMapping.scope_id == scope_id,
            )
            .first()
        )

        if existing_mapping:
            return {
                "success": True,
                "message": f"权限组 {group_name} 已经分配给角色 {role_id}",
                "mapping_id": existing_mapping.id,
            }

        # 创建新的映射
        mapping = RoleToGroupMapping(
            role_id=role_id, group_id=group.id, scope_type=scope_type, scope_id=scope_id
        )
        db.session.add(mapping)
        db.session.commit()

        # 获取权限组中的所有权限
        permissions = [p.name for p in group.permissions]

        logger.info(
            f"权限组分配成功: {group_name} -> 角色 {role_id}, 权限: {permissions}"
        )
        return {
            "success": True,
            "message": f"权限组 {group_name} 已分配给角色 {role_id}",
            "mapping_id": mapping.id,
            "permissions": permissions,
        }

    except Exception as e:
        logger.error(f"权限组分配失败: {group_name} -> 角色 {role_id}, error: {e}")
        db.session.rollback()
        raise


def get_group_permissions(group_name: str) -> List[str]:
    """
    获取权限组中的所有权限

    参数:
        group_name (str): 权限组名称

    返回:
        List[str]: 权限列表
    """
    try:
        from app.blueprints.roles.models import PermissionGroup

        group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == group_name)
            .first()
        )
        if not group:
            return []

        return [p.name for p in group.permissions]

    except Exception as e:
        logger.error(f"获取权限组权限失败: {group_name}, error: {e}")
        return []


def get_role_groups(
    role_id: int, scope_type: str = None, scope_id: int = None
) -> List[Dict]:
    """
    获取角色的所有权限组

    参数:
        role_id (int): 角色ID
        scope_type (str): 作用域类型
        scope_id (int): 作用域ID

    返回:
        List[Dict]: 权限组列表
    """
    try:
        from app.blueprints.roles.models import Role, RoleToGroupMapping

        query = db.session.query(RoleToGroupMapping).filter(
            RoleToGroupMapping.role_id == role_id
        )

        if scope_type is not None:
            query = query.filter(RoleToGroupMapping.scope_type == scope_type)

        if scope_id is not None:
            query = query.filter(RoleToGroupMapping.scope_id == scope_id)

        mappings = query.all()

        groups = []
        for mapping in mappings:
            group = mapping.group
            groups.append(
                {
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "is_active": group.is_active,
                    "permissions": [p.name for p in group.permissions],
                }
            )

        return groups

    except Exception as e:
        logger.error(f"获取角色权限组失败: 角色 {role_id}, error: {e}")
        return []


def list_permission_groups() -> List[Dict]:
    """
    列出所有权限组

    返回:
        List[Dict]: 权限组列表
    """
    try:
        from app.blueprints.roles.models import PermissionGroup

        groups = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.is_active == True)
            .all()
        )

        return [group.to_dict() for group in groups]

    except Exception as e:
        logger.error(f"列出权限组失败: {e}")
        return []


def remove_permission_from_group(group_name: str, permission_name: str) -> Dict:
    """
    从权限组中移除权限

    参数:
        group_name (str): 权限组名称
        permission_name (str): 权限名称

    返回:
        Dict: 移除结果
    """
    try:
        from app.blueprints.roles.models import (
            PermissionGroup,
            Permission,
            GroupToPermissionMapping,
        )

        # 查找权限组
        group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == group_name)
            .first()
        )
        if not group:
            raise ValueError(f"权限组不存在: {group_name}")

        # 查找权限
        permission = (
            db.session.query(Permission)
            .filter(Permission.name == permission_name)
            .first()
        )
        if not permission:
            raise ValueError(f"权限不存在: {permission_name}")

        # 查找并删除映射
        mapping = (
            db.session.query(GroupToPermissionMapping)
            .filter(
                GroupToPermissionMapping.group_id == group.id,
                GroupToPermissionMapping.permission_id == permission.id,
            )
            .first()
        )

        if not mapping:
            return {
                "success": True,
                "message": f"权限 {permission_name} 不在权限组 {group_name} 中",
            }

        db.session.delete(mapping)
        db.session.commit()

        logger.info(f"权限移除成功: {permission_name} 从 {group_name}")
        return {
            "success": True,
            "message": f"权限 {permission_name} 已从权限组 {group_name} 中移除",
        }

    except Exception as e:
        logger.error(f"权限移除失败: {permission_name} 从 {group_name}, error: {e}")
        db.session.rollback()
        raise


def remove_group_from_role(
    role_id: int, group_name: str, scope_type: str = None, scope_id: int = None
) -> Dict:
    """
    从角色中移除权限组

    参数:
        role_id (int): 角色ID
        group_name (str): 权限组名称
        scope_type (str): 作用域类型
        scope_id (int): 作用域ID

    返回:
        Dict: 移除结果
    """
    try:
        from app.blueprints.roles.models import PermissionGroup, RoleToGroupMapping

        # 查找权限组
        group = (
            db.session.query(PermissionGroup)
            .filter(PermissionGroup.name == group_name)
            .first()
        )
        if not group:
            raise ValueError(f"权限组不存在: {group_name}")

        # 查找并删除映射
        query = db.session.query(RoleToGroupMapping).filter(
            RoleToGroupMapping.role_id == role_id,
            RoleToGroupMapping.group_id == group.id,
        )

        if scope_type is not None:
            query = query.filter(RoleToGroupMapping.scope_type == scope_type)

        if scope_id is not None:
            query = query.filter(RoleToGroupMapping.scope_id == scope_id)

        mapping = query.first()

        if not mapping:
            return {
                "success": True,
                "message": f"权限组 {group_name} 不在角色 {role_id} 中",
            }

        db.session.delete(mapping)
        db.session.commit()

        logger.info(f"权限组移除成功: {group_name} 从角色 {role_id}")
        return {
            "success": True,
            "message": f"权限组 {group_name} 已从角色 {role_id} 中移除",
        }

    except Exception as e:
        logger.error(f"权限组移除失败: {group_name} 从角色 {role_id}, error: {e}")
        db.session.rollback()
        raise
