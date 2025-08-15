"""
权限缓存系统测试。
测试二级缓存、主动失效、批量刷新等功能。
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.permissions import (
    invalidate_user_permissions,
    invalidate_role_permissions,
    refresh_user_permissions,
    get_cache_stats,
    _get_permissions_from_cache,
    _set_permissions_to_cache,
    _make_perm_cache_key,
)


class TestPermissionCache:
    """权限缓存系统测试类"""

    def test_make_perm_cache_key(self):
        """测试缓存键生成"""
        # 测试全局权限缓存键
        key = _make_perm_cache_key(123, None, None)
        assert key == "perm:123:global:none"

        # 测试服务器权限缓存键
        key = _make_perm_cache_key(123, "server", 456)
        assert key == "perm:123:server:456"

        # 测试频道权限缓存键
        key = _make_perm_cache_key(123, "channel", 789)
        assert key == "perm:123:channel:789"

    @patch("app.core.permissions._get_redis_client")
    def test_get_permissions_from_cache_l1_hit(self, mock_redis):
        """测试L1缓存命中"""
        # 模拟L1缓存命中
        cache_key = "perm:123:server:456"
        expected_perms = {"read", "write"}

        # 直接设置L1缓存
        from app.core.permissions import _permission_cache

        _permission_cache[cache_key] = expected_perms

        # 测试获取权限
        perms = _get_permissions_from_cache(cache_key)
        assert perms == expected_perms

        # 清理测试数据
        _permission_cache.pop(cache_key, None)

    @patch("app.core.permissions._get_redis_client")
    def test_get_permissions_from_cache_l2_hit(self, mock_redis):
        """测试L2缓存命中"""
        # 模拟Redis客户端
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        cache_key = "perm:123:server:456"
        expected_perms = {"read", "write"}

        # 模拟Redis返回数据
        import pickle

        mock_client.get.return_value = pickle.dumps(expected_perms)

        # 测试获取权限
        perms = _get_permissions_from_cache(cache_key)
        assert perms == expected_perms

        # 验证L1缓存被更新
        from app.core.permissions import _permission_cache

        assert _permission_cache[cache_key] == expected_perms

        # 清理测试数据
        _permission_cache.pop(cache_key, None)

    @patch("app.core.permissions._get_redis_client")
    def test_get_permissions_from_cache_miss(self, mock_redis):
        """测试缓存未命中"""
        # 模拟Redis客户端
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        cache_key = "perm:123:server:456"

        # 模拟Redis返回None（缓存未命中）
        mock_client.get.return_value = None

        # 测试获取权限
        perms = _get_permissions_from_cache(cache_key)
        assert perms is None

    @patch("app.core.permissions._get_redis_client")
    def test_set_permissions_to_cache(self, mock_redis):
        """测试设置权限到缓存"""
        # 模拟Redis客户端
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        cache_key = "perm:123:server:456"
        perms = {"read", "write"}

        # 测试设置缓存
        _set_permissions_to_cache(cache_key, perms)

        # 验证L1缓存被设置
        from app.core.permissions import _permission_cache

        assert _permission_cache[cache_key] == perms

        # 验证Redis被调用
        mock_client.setex.assert_called_once()

        # 清理测试数据
        _permission_cache.pop(cache_key, None)

    @patch("app.core.permissions._invalidate_user_permissions")
    def test_invalidate_user_permissions(self, mock_invalidate):
        """测试用户权限失效"""
        user_id = 123

        # 测试调用
        invalidate_user_permissions(user_id)

        # 验证内部函数被调用
        mock_invalidate.assert_called_once_with(user_id)

    @patch("app.core.permissions._invalidate_role_permissions")
    def test_invalidate_role_permissions(self, mock_invalidate):
        """测试角色权限失效"""
        role_id = 456

        # 测试调用
        invalidate_role_permissions(role_id)

        # 验证内部函数被调用
        mock_invalidate.assert_called_once_with(role_id)

    @patch("app.core.permissions._batch_refresh_user_permissions")
    def test_refresh_user_permissions(self, mock_refresh):
        """测试用户权限刷新"""
        user_id = 123
        server_id = 456

        # 测试刷新所有权限
        refresh_user_permissions(user_id)
        mock_refresh.assert_called_with(user_id, None)

        # 测试刷新特定服务器权限
        refresh_user_permissions(user_id, server_id)
        mock_refresh.assert_called_with(user_id, server_id)

    @patch("app.core.permissions._get_redis_client")
    def test_get_cache_stats(self, mock_redis):
        """测试缓存统计"""
        # 模拟Redis客户端
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        # 模拟Redis统计信息
        mock_client.keys.return_value = [
            b"perm:123:server:456",
            b"perm:789:global:none",
        ]
        mock_client.memory_usage.return_value = 1024

        # 测试获取统计信息
        stats = get_cache_stats()

        # 验证返回结构
        assert "l1_cache_size" in stats
        assert "l1_cache_maxsize" in stats
        assert "l2_cache" in stats
        assert stats["l2_cache"]["total_keys"] == 2
        assert stats["l2_cache"]["memory_usage"] == 1024

    @patch("app.core.permissions._get_redis_client")
    def test_get_cache_stats_redis_error(self, mock_redis):
        """测试Redis错误时的缓存统计"""
        # 模拟Redis连接失败
        mock_redis.return_value = None

        # 测试获取统计信息
        stats = get_cache_stats()

        # 验证返回结构
        assert "l1_cache_size" in stats
        assert "l1_cache_maxsize" in stats
        assert "l2_cache" in stats
        assert "error" in stats["l2_cache"]
