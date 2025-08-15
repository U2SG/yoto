"""
重构后权限缓存系统测试。
测试二级缓存、主动失效、批量刷新等功能。
"""

import pytest
from unittest.mock import patch, MagicMock

# 使用重构后的权限系统
from app.core.permission_cache import (
    invalidate_user_permissions,
    invalidate_role_permissions,
    get_cache_stats,
    get_permissions_from_cache,
    set_permissions_to_cache,
    _make_perm_cache_key,
)

from app.core.permission_queries import refresh_user_permissions


class TestPermissionCacheRefactored:
    """重构后权限缓存系统测试类"""

    def test_make_perm_cache_key(self):
        """测试缓存键生成"""
        # 测试全局权限缓存键
        key = _make_perm_cache_key(123, None, None)
        assert key == "user_perm:123"

        # 测试服务器权限缓存键
        key = _make_perm_cache_key(123, "server", 456)
        assert key == "user_perm:123:server:456"

        # 测试频道权限缓存键
        key = _make_perm_cache_key(123, "channel", 789)
        assert key == "user_perm:123:channel:789"

    def test_cache_set_get(self):
        """测试缓存设置和获取"""
        cache_key = _make_perm_cache_key(1, "server", 1)
        permissions = {"read_channel", "send_message"}

        # 设置缓存
        set_permissions_to_cache(cache_key, permissions)

        # 获取缓存
        cached_permissions = get_permissions_from_cache(cache_key)
        assert cached_permissions == permissions

    def test_cache_invalidation(self):
        """测试缓存失效"""
        cache_key = _make_perm_cache_key(1, "server", 1)
        permissions = {"read_channel", "send_message"}

        # 设置缓存
        set_permissions_to_cache(cache_key, permissions)

        # 验证缓存存在
        cached_permissions = get_permissions_from_cache(cache_key)
        assert cached_permissions == permissions

        # 失效用户缓存
        invalidate_user_permissions(1)

        # 验证缓存已清除
        cached_permissions = get_permissions_from_cache(cache_key)
        assert cached_permissions is None

    def test_role_cache_invalidation(self):
        """测试角色缓存失效"""
        # 这个测试主要验证函数可以被调用，具体实现依赖于Redis
        invalidate_role_permissions(1)
        assert True  # 如果没有异常就表示通过

    def test_cache_stats(self):
        """测试缓存统计"""
        stats = get_cache_stats()
        assert "lru" in stats
        assert "redis" in stats

    def test_user_permissions_refresh(self, mocker):
        """测试用户权限刷新"""
        # 模拟数据库查询函数
        mock_query = mocker.patch(
            "app.core.permission_queries.optimized_single_user_query_v3"
        )
        mock_query.return_value = {"read_channel", "send_message"}

        # 刷新用户权限
        refresh_user_permissions(1, 1)

        # 验证数据库查询函数被调用
        mock_query.assert_called_once_with(1, "server", 1)
