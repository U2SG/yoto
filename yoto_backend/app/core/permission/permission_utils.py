"""
权限工具模块 - 纯工具层
提供无状态、无外部依赖的权限工具函数
支持权限验证、键生成、哈希计算、集合操作等基础功能
"""

import logging
import redis
from typing import List, Dict, Set, Optional, Any
import hashlib
from flask import current_app

logger = logging.getLogger(__name__)


def create_redis_client(
    config: Optional[Dict[str, Any]] = None,
) -> Optional[redis.Redis]:
    """
    创建Redis客户端 - 支持集群感知

    参数:
        config (Optional[Dict[str, Any]]): Redis配置，如果为None则从Flask配置获取

    返回:
        Optional[redis.Redis]: Redis客户端实例，失败时返回None
    """
    try:
        if config is None:
            # 从Flask配置获取Redis连接信息
            try:
                redis_config = current_app.config.get("REDIS_CONFIG", {})
                startup_nodes = redis_config.get(
                    "startup_nodes", [{"host": "localhost", "port": 6379}]
                )
            except (RuntimeError, AttributeError):
                # 不在Flask应用上下文中，使用默认配置
                startup_nodes = [{"host": "localhost", "port": 6379}]
        else:
            startup_nodes = config.get(
                "startup_nodes", [{"host": "localhost", "port": 6379}]
            )

        # 尝试Redis集群连接，失败时降级到单节点
        try:
            # 确保节点配置格式正确
            valid_startup_nodes = []
            for node in startup_nodes:
                if isinstance(node, dict) and "host" in node and "port" in node:
                    valid_startup_nodes.append(
                        {"host": node["host"], "port": node["port"]}
                    )

            if len(valid_startup_nodes) > 1:
                # 如果有多个节点，尝试集群模式
                try:
                    redis_client = redis.RedisCluster(
                        startup_nodes=valid_startup_nodes,
                        decode_responses=True,
                        skip_full_coverage_check=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                    )
                    redis_client.ping()
                    logger.info("使用Redis集群客户端")
                    return redis_client
                except Exception as cluster_error:
                    logger.warning(
                        f"Redis集群连接失败，降级到单节点模式: {cluster_error}"
                    )

            # 降级到单节点Redis
            if config is None:
                try:
                    redis_config = current_app.config.get(
                        "REDIS_SINGLE_NODE_CONFIG",
                        {
                            "host": "localhost",
                            "port": 6379,
                            "db": 0,
                            "decode_responses": True,
                        },
                    )
                except (RuntimeError, AttributeError):
                    redis_config = {
                        "host": "localhost",
                        "port": 6379,
                        "db": 0,
                        "decode_responses": True,
                    }
            else:
                redis_config = {
                    "host": config.get("host", "localhost"),
                    "port": config.get("port", 6379),
                    "db": config.get("db", 0),
                    "decode_responses": True,
                }

            redis_client = redis.Redis(**redis_config)
            redis_client.ping()  # 测试连接
            logger.info("使用Redis单节点客户端")
            return redis_client
        except Exception as e:
            logger.error(f"Redis客户端创建失败: {e}")
            return None

    except Exception as e:
        logger.error(f"Redis客户端创建失败: {e}")
        return None


def test_redis_connection(redis_client: Optional[redis.Redis] = None) -> bool:
    """
    测试Redis连接

    参数:
        redis_client (Optional[redis.Redis]): Redis客户端，如果为None则创建新的

    返回:
        bool: 连接是否正常
    """
    try:
        if redis_client is None:
            redis_client = create_redis_client()

        if redis_client is None:
            return False

        redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis连接测试失败: {e}")
        return False


def get_redis_info(redis_client: Optional[redis.Redis] = None) -> Dict[str, Any]:
    """
    获取Redis连接信息

    参数:
        redis_client (Optional[redis.Redis]): Redis客户端，如果为None则创建新的

    返回:
        Dict[str, Any]: Redis连接信息
    """
    try:
        if redis_client is None:
            redis_client = create_redis_client()

        if redis_client is None:
            return {"status": "error", "message": "Redis客户端不可用"}

        # 测试连接
        redis_client.ping()

        # 获取Redis信息
        info = redis_client.info()

        return {
            "status": "success",
            "type": (
                "cluster" if isinstance(redis_client, redis.RedisCluster) else "single"
            ),
            "version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
        }
    except Exception as e:
        logger.error(f"获取Redis信息失败: {e}")
        return {"status": "error", "message": str(e)}


def validate_permission_structure(permission: str) -> bool:
    """
    验证权限结构是否符合规范
    格式: resource.action 或 resource.subresource.action

    Args:
        permission: 权限字符串

    Returns:
        bool: 权限结构是否有效

    Examples:
        >>> validate_permission_structure('user.read')
        True
        >>> validate_permission_structure('user')
        False
        >>> validate_permission_structure('user.read.write')
        True
    """
    parts = permission.split(".")
    if len(parts) < 2:
        return False
    return all(part and part.isalnum() for part in parts)


def create_permission_key(
    permission: str, scope: str = None, scope_id: int = None
) -> str:
    """
    创建权限缓存键

    Args:
        permission: 权限字符串
        scope: 作用域（可选）
        scope_id: 作用域ID（可选）

    Returns:
        str: 权限缓存键

    Examples:
        >>> create_permission_key('user.read')
        'user.read'
        >>> create_permission_key('user.read', 'server', 123)
        'user.read:server:123'
    """
    key_parts = [permission]
    if scope:
        key_parts.append(scope)
    if scope_id:
        key_parts.append(str(scope_id))
    return ":".join(key_parts)


def batch_validate_permissions(permissions: List[str]) -> Dict[str, bool]:
    """
    批量验证权限结构
    返回权限名到验证结果的映射

    Args:
        permissions: 权限字符串列表

    Returns:
        Dict[str, bool]: 权限名到验证结果的映射

    Examples:
        >>> batch_validate_permissions(['user.read', 'user', 'user.read.write'])
        {'user.read': True, 'user': False, 'user.read.write': True}
    """
    results = {}
    for perm in permissions:
        results[perm] = validate_permission_structure(perm)
    return results


def create_permission_hash(permissions: Set[str]) -> str:
    """
    创建权限集合的哈希值
    用于缓存键生成和权限比较

    Args:
        permissions: 权限集合

    Returns:
        str: 权限集合的MD5哈希值

    Examples:
        >>> create_permission_hash({'user.read', 'user.write'})
        'a1b2c3d4e5f6...'
    """
    sorted_perms = sorted(permissions)
    perm_str = "|".join(sorted_perms)
    return hashlib.md5(perm_str.encode()).hexdigest()


def merge_permission_sets(*permission_sets: Set[str]) -> Set[str]:
    """
    合并多个权限集合
    自动去重

    Args:
        *permission_sets: 多个权限集合

    Returns:
        Set[str]: 合并后的权限集合

    Examples:
        >>> merge_permission_sets({'user.read'}, {'user.write'}, {'user.read'})
        {'user.read', 'user.write'}
    """
    merged = set()
    for perm_set in permission_sets:
        merged.update(perm_set)
    return merged


def filter_permissions_by_group(permissions: Set[str], group: str) -> Set[str]:
    """
    按组过滤权限

    Args:
        permissions: 权限集合
        group: 权限组名

    Returns:
        Set[str]: 过滤后的权限集合

    Examples:
        >>> filter_permissions_by_group({'user.read', 'server.manage', 'user.write'}, 'user')
        {'user.read', 'user.write'}
    """
    return {perm for perm in permissions if perm.startswith(f"{group}.")}


def get_permission_hierarchy(permission: str) -> List[str]:
    """
    获取权限层次结构
    例如: server.manage.users -> ['server', 'server.manage', 'server.manage.users']

    Args:
        permission: 权限字符串

    Returns:
        List[str]: 权限层次结构列表

    Examples:
        >>> get_permission_hierarchy('server.manage.users')
        ['server', 'server.manage', 'server.manage.users']
        >>> get_permission_hierarchy('user.read')
        ['user', 'user.read']
    """
    parts = permission.split(".")
    hierarchy = []
    for i in range(1, len(parts) + 1):
        hierarchy.append(".".join(parts[:i]))
    return hierarchy


# 导出所有纯工具函数
__all__ = [
    "validate_permission_structure",
    "create_permission_key",
    "batch_validate_permissions",
    "create_permission_hash",
    "merge_permission_sets",
    "filter_permissions_by_group",
    "get_permission_hierarchy",
]
