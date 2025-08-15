"""
权限装饰器模块

包含所有权限校验相关的装饰器，提供灵活的权限控制接口
"""

import logging
import time
from functools import wraps
from typing import Callable, List, Optional, Set, Dict, Any
from flask import request, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from .hybrid_permission_cache import HybridPermissionCache, get_hybrid_cache
from .permission_registry import batch_register_permissions
from flask_jwt_extended import get_jwt

logger = logging.getLogger(__name__)

# ==================== 统一错误响应函数 ====================


def create_error_response(message: str, status_code: int = 403) -> tuple:
    """
    创建统一的错误响应格式

    参数:
        message: 错误消息
        status_code: HTTP状态码

    返回:
        tuple: (response_dict, status_code)
    """
    return {"error": message}, status_code


def unauthorized_error(message: str = "未授权访问") -> tuple:
    """创建401未授权错误响应"""
    return create_error_response(message, 401)


def forbidden_error(message: str = "权限不足") -> tuple:
    """创建403权限不足错误响应"""
    return create_error_response(message, 403)


# ==================== 装饰器实现 ====================


def _require_permission_base(
    permission_check_func: Callable,
    scope: str = None,
    scope_id_arg: str = None,
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
    permission_names: List[str] = None,
):
    """
    主装饰器 - 负责所有通用逻辑

    参数:
        permission_check_func (Callable): 权限检查函数，接收用户权限集合，返回bool
        scope (str): 权限作用域
        scope_id_arg (str): 作用域ID参数名
        resource_check (Callable): 资源检查函数
        group (str): 权限组
        description (str): 权限描述
        permission_names (List[str]): 权限名称列表，用于动态注册
    """

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # 获取用户ID
            user_id = get_jwt_identity()
            if not user_id:
                logger.warning("未授权访问：用户ID为空")
                return unauthorized_error()

            # 超级管理员直接放行 - 从JWT claim中获取超管状态
            try:
                jwt_data = get_jwt()
                is_super_admin = jwt_data.get("is_super_admin", False)

                if is_super_admin:
                    logger.debug(f"超级管理员直接放行: 用户 {user_id}")
                    return fn(*args, **kwargs)
            except Exception as e:
                logger.warning(f"超级管理员检查失败: 用户 {user_id}, 错误: {e}")
                # 继续执行权限检查，不因超级管理员检查失败而阻止访问

            # 完整地获取scope_id
            scope_id = _get_scope_id(scope_id_arg, kwargs)

            # 使用flask.g确保每个请求只调用一次get_permission
            # 简化缓存键：在同一次请求中，user_id, scope, scope_id通常是固定的
            # 真正需要区分的是权限检查函数本身
            cache_key = f"perm_check:{hash(permission_check_func)}"

            if not hasattr(g, "permission_cache"):
                g.permission_cache = {}

            # 检查是否已经查询过权限
            if cache_key in g.permission_cache:
                has_permission = g.permission_cache[cache_key]
            else:
                # 使用全局单例获取用户权限，避免每次创建新实例
                cache = get_hybrid_cache()

                # 获取用户权限 - 统一使用复杂权限查询
                # 对于所有类型的权限检查，都获取用户的所有权限集合
                user_permissions = cache._query_complex_permissions(
                    user_id, scope, scope_id
                )

                # 确保user_permissions是Set[str]类型
                if not isinstance(user_permissions, set):
                    user_permissions = set()

                # 使用传入的权限检查函数
                has_permission = permission_check_func(user_permissions)

                # 缓存结果到g中
                g.permission_cache[cache_key] = has_permission

            # 资源检查
            if resource_check and has_permission:
                try:
                    resource_result = resource_check(user_id, scope_id, **kwargs)
                    if not resource_result:
                        has_permission = False
                        logger.warning(f"资源检查失败: 用户 {user_id}")
                except Exception as e:
                    logger.error(f"资源检查异常: 用户 {user_id}, 错误: {e}")
                    has_permission = False

            # 权限不足处理
            if not has_permission:
                logger.warning(
                    f"权限不足: 用户 {user_id}, 作用域: {scope}, 作用域ID: {scope_id}"
                )
                return forbidden_error()

            # 记录性能
            response_time = time.time() - start_time
            if response_time > 0.5:
                logger.warning(
                    f"权限检查响应时间过长: {response_time:.3f}s, 用户: {user_id}"
                )

            # 动态权限注册 - 在权限检查通过后批量注册权限
            if has_permission and permission_names:
                try:
                    # 准备批量注册数据
                    permissions_data = [
                        {
                            "name": permission_name,
                            "group": group,
                            "description": description,
                        }
                        for permission_name in permission_names
                    ]

                    # 批量注册权限
                    batch_register_permissions(permissions_data)
                    logger.debug(f"批量注册权限成功: {permission_names}")

                except Exception as e:
                    logger.warning(f"批量权限注册失败: {permission_names}, 错误: {e}")

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _get_scope_id(scope_id_arg: str, kwargs: Dict[str, Any]) -> Optional[int]:
    """
    完整地获取scope_id

    支持从以下来源获取scope_id：
    1. kwargs (URL路径参数)
    2. request.args (查询参数)
    3. request.json (JSON请求体)
    4. request.form (表单数据)
    5. request.get_json() (兼容性方法)
    6. request.values (合并的请求数据)

    参数:
        scope_id_arg (str): 作用域ID参数名
        kwargs (Dict[str, Any]): 函数参数

    返回:
        Optional[int]: 作用域ID，如果未找到则返回None
    """
    if not scope_id_arg:
        return None

    # 1. 从kwargs中获取（URL路径参数）
    if scope_id_arg in kwargs:
        scope_id = kwargs[scope_id_arg]
        if scope_id is not None:
            try:
                return int(scope_id)
            except (ValueError, TypeError):
                logger.warning(f"无效的scope_id格式: {scope_id}")

    # 2. 从request.args中获取（查询参数）
    if hasattr(request, "args"):
        scope_id = request.args.get(scope_id_arg)
        if scope_id is not None:
            try:
                return int(scope_id)
            except (ValueError, TypeError):
                logger.warning(f"无效的scope_id格式: {scope_id}")

    # 3. 从request.json中获取（JSON请求体）
    try:
        if hasattr(request, "json") and request.json:
            scope_id = request.json.get(scope_id_arg)
            if scope_id is not None:
                try:
                    return int(scope_id)
                except (ValueError, TypeError):
                    logger.warning(f"无效的scope_id格式: {scope_id}")
    except Exception:
        # 忽略JSON解析错误
        pass

    # 4. 从request.form中获取（表单数据）
    if hasattr(request, "form") and request.form:
        scope_id = request.form.get(scope_id_arg)
        if scope_id is not None:
            try:
                return int(scope_id)
            except (ValueError, TypeError):
                logger.warning(f"无效的scope_id格式: {scope_id}")

    # 5. 从request.get_json()中获取（兼容性方法）
    try:
        json_data = request.get_json(silent=True)
        if json_data and scope_id_arg in json_data:
            scope_id = json_data[scope_id_arg]
            if scope_id is not None:
                try:
                    return int(scope_id)
                except (ValueError, TypeError):
                    logger.warning(f"无效的scope_id格式: {scope_id}")
    except Exception as e:
        logger.debug(f"获取JSON数据失败: {e}")

    # 6. 从request.values中获取（合并的请求数据）
    if hasattr(request, "values"):
        scope_id = request.values.get(scope_id_arg)
        if scope_id is not None:
            try:
                return int(scope_id)
            except (ValueError, TypeError):
                logger.warning(f"无效的scope_id格式: {scope_id}")

    # 7. 从request.headers中获取（如果scope_id在header中）
    if hasattr(request, "headers"):
        header_key = f"X-{scope_id_arg.replace('_', '-').upper()}"
        scope_id = request.headers.get(header_key)
        if scope_id is not None:
            try:
                return int(scope_id)
            except (ValueError, TypeError):
                logger.warning(f"无效的scope_id格式: {scope_id}")

    return None


def require_permission(
    permission,
    scope=None,
    scope_id_arg=None,
    op="AND",
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """
    权限校验装饰器 - 基础版本

    参数:
        permission (str): 所需权限名称
        scope (str): 权限作用域
        scope_id_arg (str): 作用域ID参数名
        op (str): 操作符 ('AND', 'OR') - 单权限检查中未使用
        resource_check (Callable): 资源检查函数
        group (str): 权限组
        description (str): 权限描述
    """

    # 简单的权限检查函数：检查指定权限是否在用户权限集合中
    def check_permission(user_permissions: Set[str]) -> bool:
        return permission in user_permissions

    return _require_permission_base(
        permission_check_func=check_permission,
        scope=scope,
        scope_id_arg=scope_id_arg,
        resource_check=resource_check,
        group=group,
        description=description,
        permission_names=[permission],  # 传递权限名称用于动态注册
    )


def require_permissions(
    permissions: List[str],
    scope=None,
    scope_id_arg=None,
    op="AND",
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """
    多权限校验装饰器

    支持同时检查多个权限，支持AND/OR/NOT逻辑：
    - AND: 用户必须拥有所有指定权限
    - OR: 用户必须拥有至少一个指定权限
    - NOT: 用户不能拥有任何指定权限

    使用主装饰器统一处理通用逻辑
    """

    # 多权限检查函数：根据操作符检查多个权限
    def check_permissions(user_permissions: Set[str]) -> bool:
        if op == "AND":
            return all(perm in user_permissions for perm in permissions)
        elif op == "OR":
            return any(perm in user_permissions for perm in permissions)
        elif op == "NOT":
            return all(perm not in user_permissions for perm in permissions)
        else:
            return False

    return _require_permission_base(
        permission_check_func=check_permissions,
        scope=scope,
        scope_id_arg=scope_id_arg,
        resource_check=resource_check,
        group=group,
        description=description,
        permission_names=permissions,  # 传递权限名称列表用于动态注册
    )


def require_permission_with_expression(
    expression: str,
    scope=None,
    scope_id_arg=None,
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """
    表达式权限校验装饰器

    支持复杂的权限表达式，如: (admin OR moderator) AND (read OR write)
    使用主装饰器统一处理通用逻辑
    """

    # 表达式权限检查函数：使用evaluate_permission_expression评估表达式
    def check_expression(user_permissions: Set[str]) -> bool:
        return evaluate_permission_expression(expression, user_permissions)

    # 从表达式中提取权限名称（简单实现）
    def extract_permissions_from_expression(expr: str) -> List[str]:
        """从表达式中提取权限名称"""
        import re

        # 简单的正则表达式提取权限名称
        # 假设权限名称是字母、数字、下划线的组合
        permissions = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr)
        # 过滤掉操作符和括号
        operators = {"and", "or", "not", "AND", "OR", "NOT"}
        return [p for p in permissions if p.lower() not in operators and p not in "()"]

    permission_names = extract_permissions_from_expression(expression)

    return _require_permission_base(
        permission_check_func=check_expression,
        scope=scope,
        scope_id_arg=scope_id_arg,
        resource_check=resource_check,
        group=group,
        description=description,
        permission_names=permission_names,  # 传递从表达式中提取的权限名称
    )


# 保持向后兼容的别名
def require_permission_v2(
    permission,
    scope=None,
    scope_id_arg=None,
    op="AND",
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """权限校验装饰器 - 增强版本（别名）"""
    return require_permission(
        permission, scope, scope_id_arg, op, resource_check, group, description
    )


def require_permissions_v2(
    permissions: List[str],
    scope=None,
    scope_id_arg=None,
    op="AND",
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """多权限校验装饰器（别名）"""
    return require_permissions(
        permissions, scope, scope_id_arg, op, resource_check, group, description
    )


def require_permission_with_expression_v2(
    expression: str,
    scope=None,
    scope_id_arg=None,
    resource_check: Callable = None,
    group: str = None,
    description: str = None,
):
    """表达式权限校验装饰器（别名）"""
    return require_permission_with_expression(
        expression, scope, scope_id_arg, resource_check, group, description
    )


# 表达式缓存
_expression_cache = {}


def evaluate_permission_expression(expression: str, user_permissions: Set[str]) -> bool:
    """
    评估权限表达式 - 使用安全的AST解析和缓存机制

    支持的操作符: and, or, not, ()
    示例: (admin or moderator) and (read or write)

    参数:
        expression (str): 权限表达式
        user_permissions (Set[str]): 用户权限集合

    返回:
        bool: 表达式评估结果
    """
    import ast

    # 检查缓存
    cache_key = (expression, frozenset(user_permissions))
    if cache_key in _expression_cache:
        return _expression_cache[cache_key]

    def safe_eval(node, permissions):
        """安全地评估AST节点"""
        if isinstance(node, ast.Name):
            # 变量名 - 检查是否在权限集合中
            return node.id in permissions
        elif isinstance(node, ast.BoolOp):
            # 布尔操作 (and, or)
            if isinstance(node.op, ast.And):
                return all(safe_eval(value, permissions) for value in node.values)
            elif isinstance(node.op, ast.Or):
                return any(safe_eval(value, permissions) for value in node.values)
        elif isinstance(node, ast.UnaryOp):
            # 一元操作 (not)
            if isinstance(node.op, ast.Not):
                return not safe_eval(node.operand, permissions)
        elif isinstance(node, ast.Constant):
            # 常量
            return bool(node.value)
        elif isinstance(node, ast.Expression):
            # 表达式
            return safe_eval(node.body, permissions)

        # 默认返回False
        return False

    try:
        # 预处理表达式 - 将AND/OR转换为Python语法
        processed_expr = expression.lower()

        # 解析AST
        tree = ast.parse(processed_expr, mode="eval")

        # 安全评估
        result = safe_eval(tree, user_permissions)

        # 缓存结果
        _expression_cache[cache_key] = result

        return result

    except (SyntaxError, ValueError, TypeError) as e:
        logger.error(f"权限表达式解析失败: {expression}, 错误: {e}")
        return False
    except Exception as e:
        logger.error(f"权限表达式评估失败: {expression}, 错误: {e}")
        return False


def clear_expression_cache():
    """清空表达式缓存"""
    global _expression_cache
    _expression_cache.clear()
    logger.info("权限表达式缓存已清空")


def invalidate_permission_check_cache(user_id: int = None, role_id: int = None):
    """
    失效权限检查缓存

    参数:
        user_id (int): 用户ID，为None时失效所有用户缓存
        role_id (int): 角色ID，为None时失效所有角色缓存
    """
    if user_id:
        # 使用全局单例进行缓存失效
        cache = get_hybrid_cache()
        cache.invalidate_user_permissions(user_id)
        logger.info(f"已失效用户 {user_id} 的权限检查缓存")

    if role_id:
        # 使用全局单例进行角色缓存失效
        cache = get_hybrid_cache()
        cache.invalidate_role_permissions(role_id)
        logger.info(f"已失效角色 {role_id} 的权限检查缓存")

    if not user_id and not role_id:
        # 失效所有缓存
        from .hybrid_permission_cache import clear_all_caches

        clear_all_caches()
        logger.info("已失效所有权限检查缓存")
