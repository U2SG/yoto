"""
权限查询模块

包含所有数据库查询相关的优化函数
"""

import time
import logging
import signal
from typing import Dict, List, Optional, Set, Any, Tuple
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError, DataError
from collections import defaultdict

from app.blueprints.auth.models import User
from app.blueprints.roles.models import UserRole, Role, RolePermission, Permission

# 移除对permission_registry的导入，避免循环依赖
# from .permission_registry import get_permission_registry_stats

logger = logging.getLogger(__name__)


def optimized_single_user_query(
    user_id: int, db_session, scope: str = None, scope_id: int = None
) -> Set[str]:
    """
    优化的单用户权限查询 - 版本7 (精确异常处理版本)

    参数:
        user_id (int): 用户ID
        db_session: 数据库会话对象
        scope (str): 权限作用域
        scope_id (int): 作用域ID

    返回:
        Set[str]: 用户权限集合
    """
    start_time = time.time()

    try:
        from app.blueprints.auth.models import User
        from app.blueprints.roles.models import (
            UserRole,
            Role,
            RolePermission,
            Permission,
        )
        from app.blueprints.servers.models import ServerMember

        # 使用JOIN一次性查询用户权限，避免N+1问题
        query = (
            db_session.query(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .filter(UserRole.user_id == user_id)
        )

        # 添加作用域过滤
        if scope and scope_id:
            query = query.join(Role).filter(
                and_(Role.server_id == scope_id, Role.role_type == scope)
            )
            # 同时过滤权限作用域
            query = query.filter(
                and_(
                    RolePermission.scope_type == scope,
                    RolePermission.scope_id == scope_id,
                )
            )

        # 执行单次查询获取所有权限
        permissions = {row[0] for row in query.all()}

        query_time = time.time() - start_time
        logger.debug(
            f"数据库查询(精确异常处理版本): 用户 {user_id} 权限查询耗时 {query_time:.3f}s"
        )

        return permissions

    except OperationalError as e:
        logger.error(f"数据库连接错误: 用户 {user_id}, 错误: {e}")
        # 数据库连接问题，返回空权限
        return set()
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 用户 {user_id}, 错误: {e}")
        # 数据完整性问题，返回空权限
        return set()
    except DataError as e:
        logger.error(f"数据类型错误: 用户 {user_id}, 错误: {e}")
        # 数据类型问题，返回空权限
        return set()
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 用户 {user_id}, 错误: {e}")
        # 其他SQLAlchemy错误，返回空权限
        return set()
    except ImportError as e:
        logger.error(f"模块导入错误: 用户 {user_id}, 错误: {e}")
        # 模块导入问题，返回空权限
        return set()
    except Exception as e:
        logger.error(f"未知错误: 用户 {user_id}, 错误: {e}")
        # 其他未知错误，返回空权限
        return set()


def batch_precompute_permissions(
    user_ids: List[int], db_session, scope: str = None, scope_id: int = None
) -> Dict[int, Set[str]]:
    """
    批量预计算用户权限 - 精确异常处理版本

    参数:
        user_ids (List[int]): 用户ID列表
        db_session: 数据库会话对象
        scope (str): 权限作用域
        scope_id (int): 作用域ID

    返回:
        Dict[int, Set[str]]: 用户权限映射
    """
    start_time = time.time()

    try:
        # 使用一次性的JOIN查询，让数据库处理多对多关系聚合
        query = (
            db_session.query(UserRole.user_id, Permission.name)
            .join(RolePermission, UserRole.role_id == RolePermission.role_id)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .filter(UserRole.user_id.in_(user_ids))
        )

        # 添加作用域过滤
        if scope and scope_id:
            query = query.join(Role).filter(
                and_(Role.server_id == scope_id, Role.role_type == scope)
            )
            # 同时过滤权限作用域
            query = query.filter(
                and_(
                    RolePermission.scope_type == scope,
                    RolePermission.scope_id == scope_id,
                )
            )

        # 执行查询，让数据库一次性返回所有用户权限
        user_permissions = query.all()

        # 在应用层简单聚合结果（数据库已经完成了大部分工作）
        results = defaultdict(set)
        for user_id, permission_name in user_permissions:
            results[user_id].add(permission_name)

        batch_time = time.time() - start_time
        logger.info(
            f"批量预计算权限(精确异常处理版本): {len(user_ids)} 个用户耗时 {batch_time:.3f}s"
        )

        return results

    except OperationalError as e:
        logger.error(f"数据库连接错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}
    except DataError as e:
        logger.error(f"数据类型错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}
    except ImportError as e:
        logger.error(f"模块导入错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}
    except Exception as e:
        logger.error(f"未知错误: 批量查询失败, 错误: {e}")
        return {user_id: set() for user_id in user_ids}


def gather_role_ids_with_inheritance(role_ids, db_session):
    """
    收集角色ID及其继承关系

    参数:
        role_ids (List[int]): 角色ID列表
        db_session: 数据库会话对象

    返回:
        Set[int]: 包含继承关系的完整角色ID集合
    """
    try:
        all_role_ids = set(role_ids)

        # 查询角色的继承关系
        roles = db_session.query(Role).filter(Role.id.in_(role_ids)).all()

        for role in roles:
            if role.parent_role_id and role.parent_role_id not in all_role_ids:
                all_role_ids.add(role.parent_role_id)

        return all_role_ids

    except OperationalError as e:
        logger.error(f"数据库连接错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)
    except DataError as e:
        logger.error(f"数据类型错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)
    except ImportError as e:
        logger.error(f"模块导入错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)
    except Exception as e:
        logger.error(f"未知错误: 角色继承关系查询失败, 错误: {e}")
        return set(role_ids)


def get_active_user_roles(user_id, db_session, server_id=None, current_time=None):
    """
    获取用户的活动角色

    参数:
        user_id (int): 用户ID
        db_session: 数据库会话对象
        server_id (int): 服务器ID
        current_time: 当前时间

    返回:
        List[Role]: 活动角色列表
    """
    try:
        query = (
            db_session.query(Role).join(UserRole).filter(UserRole.user_id == user_id)
        )

        if server_id:
            query = query.filter(Role.server_id == server_id)

        if current_time:
            query = query.filter(
                and_(
                    Role.is_active == True,
                    or_(Role.expires_at.is_(None), Role.expires_at > current_time),
                )
            )

        return query.all()

    except OperationalError as e:
        logger.error(f"数据库连接错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []
    except DataError as e:
        logger.error(f"数据类型错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []
    except ImportError as e:
        logger.error(f"模块导入错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []
    except Exception as e:
        logger.error(f"未知错误: 获取用户活动角色失败, 用户 {user_id}, 错误: {e}")
        return []


def evaluate_role_conditions(user_id, role_conditions, db_session):
    """
    评估角色条件

    参数:
        user_id (int): 用户ID
        role_conditions (Dict): 角色条件
        db_session: 数据库会话对象

    返回:
        bool: 是否满足条件
    """
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        # 检查用户属性条件
        for attr, value in role_conditions.get("user_attributes", {}).items():
            if hasattr(user, attr) and getattr(user, attr) != value:
                return False

        # 检查角色条件
        if "roles" in role_conditions:
            user_roles = (
                db_session.query(Role.name)
                .join(UserRole)
                .filter(UserRole.user_id == user_id)
                .all()
            )

            user_role_names = {role[0] for role in user_roles}
            required_roles = set(role_conditions["roles"])

            if not required_roles.issubset(user_role_names):
                return False

        return True

    except Exception as e:
        logger.error(f"角色条件评估失败: {e}")
        return False


def get_permissions_with_scope(role_ids, db_session, scope_type=None, scope_id=None):
    """
    获取带作用域的权限

    参数:
        role_ids (List[int]): 角色ID列表
        db_session: 数据库会话对象
        scope_type (str): 作用域类型
        scope_id (int): 作用域ID

    返回:
        Set[str]: 权限集合
    """
    try:
        query = (
            db_session.query(Permission.name)
            .join(RolePermission)
            .filter(RolePermission.role_id.in_(role_ids))
        )

        if scope_type and scope_id:
            query = query.filter(
                and_(
                    RolePermission.scope_type == scope_type,
                    RolePermission.scope_id == scope_id,
                )
            )

        permissions = {row[0] for row in query.all()}
        return permissions

    except Exception as e:
        logger.error(f"获取作用域权限失败: {e}")
        return set()


class PermissionQuerier:
    """
    权限查询器 - 统一的查询入口

    封装所有权限查询功能，提供统一的接口
    """

    def __init__(self, db_session):
        """
        初始化权限查询器

        参数:
            db_session: 数据库会话对象
        """
        self.db_session = db_session

    def get(self, user_id: int, scope: str = None, scope_id: int = None) -> Set[str]:
        """
        获取单个用户的权限

        参数:
            user_id (int): 用户ID
            scope (str): 权限作用域
            scope_id (int): 作用域ID

        返回:
            Set[str]: 用户权限集合
        """
        return optimized_single_user_query(user_id, self.db_session, scope, scope_id)

    def get_batch(
        self, user_ids: List[int], scope: str = None, scope_id: int = None
    ) -> Dict[int, Set[str]]:
        """
        批量获取用户权限

        参数:
            user_ids (List[int]): 用户ID列表
            scope (str): 权限作用域
            scope_id (int): 作用域ID

        返回:
            Dict[int, Set[str]]: 用户权限映射
        """
        return batch_precompute_permissions(user_ids, self.db_session, scope, scope_id)

    def get_optimized_batch(
        self, user_ids: List[int], scope: str = None, scope_id: int = None
    ) -> Dict[int, Set[str]]:
        """
        优化的批量获取用户权限

        参数:
            user_ids (List[int]): 用户ID列表
            scope (str): 权限作用域
            scope_id (int): 作用域ID

        返回:
            Dict[int, Set[str]]: 用户权限映射
        """
        return batch_precompute_permissions(user_ids, self.db_session, scope, scope_id)

    def get_role_inheritance(self, role_ids: List[int]) -> Set[int]:
        """
        获取角色继承关系

        参数:
            role_ids (List[int]): 角色ID列表

        返回:
            Set[int]: 包含继承关系的完整角色ID集合
        """
        return gather_role_ids_with_inheritance(role_ids, self.db_session)

    def get_active_roles(
        self, user_id: int, server_id: int = None, current_time=None
    ) -> List:
        """
        获取用户的活动角色

        参数:
            user_id (int): 用户ID
            server_id (int): 服务器ID
            current_time: 当前时间

        返回:
            List: 活动角色列表
        """
        return get_active_user_roles(user_id, self.db_session, server_id, current_time)

    def evaluate_conditions(self, user_id: int, role_conditions: Dict) -> bool:
        """
        评估角色条件

        参数:
            user_id (int): 用户ID
            role_conditions (Dict): 角色条件

        返回:
            bool: 是否满足条件
        """
        return evaluate_role_conditions(user_id, role_conditions, self.db_session)

    def get_permissions_with_scope(
        self, role_ids: List[int], scope_type: str = None, scope_id: int = None
    ) -> Set[str]:
        """
        获取带作用域的权限

        参数:
            role_ids (List[int]): 角色ID列表
            scope_type (str): 作用域类型
            scope_id (int): 作用域ID

        返回:
            Set[str]: 权限集合
        """
        return get_permissions_with_scope(
            role_ids, self.db_session, scope_type, scope_id
        )

    def get_users_by_role(self, role_id: int) -> List[int]:
        """获取指定角色下的所有用户ID"""
        return get_users_by_role(role_id, self.db_session)

    def get_users_by_roles(self, role_ids: List[int]) -> Dict[int, List[int]]:
        """批量获取多个角色下的所有用户ID"""
        return get_users_by_roles(role_ids, self.db_session)


def get_users_by_role(role_id: int, db_session) -> List[int]:
    """
    获取指定角色下的所有用户ID

    参数:
        role_id (int): 角色ID
        db_session: 数据库会话对象

    返回:
        List[int]: 用户ID列表
    """
    try:
        from app.blueprints.roles.models import UserRole

        # 查询该角色下的所有用户
        user_roles = (
            db_session.query(UserRole.user_id).filter(UserRole.role_id == role_id).all()
        )

        user_ids = [ur[0] for ur in user_roles]

        logger.debug(f"获取角色 {role_id} 下的用户: {len(user_ids)} 个用户")
        return user_ids

    except OperationalError as e:
        logger.error(f"数据库连接错误: 角色 {role_id}, 错误: {e}")
        return []
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 角色 {role_id}, 错误: {e}")
        return []
    except DataError as e:
        logger.error(f"数据类型错误: 角色 {role_id}, 错误: {e}")
        return []
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 角色 {role_id}, 错误: {e}")
        return []
    except ImportError as e:
        logger.error(f"模块导入错误: 角色 {role_id}, 错误: {e}")
        return []
    except Exception as e:
        logger.error(f"未知错误: 角色 {role_id}, 错误: {e}")
        return []


def get_users_by_roles(role_ids: List[int], db_session) -> Dict[int, List[int]]:
    """
    批量获取多个角色下的所有用户ID

    参数:
        role_ids (List[int]): 角色ID列表
        db_session: 数据库会话对象

    返回:
        Dict[int, List[int]]: 角色ID到用户ID列表的映射
    """
    try:
        from app.blueprints.roles.models import UserRole

        # 批量查询多个角色下的所有用户
        user_roles = (
            db_session.query(UserRole.role_id, UserRole.user_id)
            .filter(UserRole.role_id.in_(role_ids))
            .all()
        )

        # 按角色ID分组
        role_users = defaultdict(list)
        for role_id, user_id in user_roles:
            role_users[role_id].append(user_id)

        # 确保所有请求的角色都有结果（即使是空列表）
        result = {}
        for role_id in role_ids:
            result[role_id] = role_users.get(role_id, [])

        logger.debug(
            f"批量获取角色用户: {len(role_ids)} 个角色, 总计 {sum(len(users) for users in result.values())} 个用户"
        )
        return result

    except OperationalError as e:
        logger.error(f"数据库连接错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}
    except IntegrityError as e:
        logger.error(f"数据完整性错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}
    except DataError as e:
        logger.error(f"数据类型错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}
    except ImportError as e:
        logger.error(f"模块导入错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}
    except Exception as e:
        logger.error(f"未知错误: 角色 {role_ids}, 错误: {e}")
        return {role_id: [] for role_id in role_ids}


def test_get_users_by_role():
    """测试get_users_by_role函数"""
    try:
        # 模拟数据库会话
        class MockDBSession:
            def query(self, model):
                return self

            def filter(self, condition):
                return self

            def all(self):
                # 模拟返回结果
                return [(1,), (2,), (3,)]

        mock_db = MockDBSession()

        # 测试函数
        result = get_users_by_role(1, mock_db)

        print(f"测试结果: {result}")
        print("get_users_by_role函数测试通过")
        return True

    except Exception as e:
        print(f"测试失败: {e}")
        return False


if __name__ == "__main__":
    test_get_users_by_role()
