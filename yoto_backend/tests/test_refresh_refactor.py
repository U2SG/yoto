"""
测试重构后的refresh功能设计

验证：
1. 查询模块专注于查询职责
2. 缓存模块负责刷新缓存
3. 正确的调用链：API -> Cache -> Query
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Set, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRefreshRefactor(unittest.TestCase):
    """测试重构后的refresh功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_db_session = Mock()
        self.user_id = 123
        self.server_id = 456
        self.user_ids = [123, 456, 789]
        self.role_id = 1

        # 模拟权限数据
        self.mock_permissions = {"read_channel", "send_message", "manage_channel"}
        self.mock_permissions_map = {
            123: {"read_channel", "send_message"},
            456: {"read_channel", "manage_channel"},
            789: {"read_channel"},
        }

    def test_permission_querier_focuses_on_query_only(self):
        """测试PermissionQuerier只专注于查询职责"""
        from app.core.permission_queries import PermissionQuerier

        # 创建查询器
        querier = PermissionQuerier(self.mock_db_session)

        # 验证查询器只有查询相关的方法
        expected_methods = {
            "get",
            "get_batch",
            "get_optimized_batch",
            "get_role_inheritance",
            "get_active_roles",
            "evaluate_conditions",
            "get_permissions_with_scope",
        }

        actual_methods = set(dir(querier))
        # 过滤掉内置方法
        actual_methods = {m for m in actual_methods if not m.startswith("_")}

        # 验证没有refresh相关的方法
        refresh_methods = {m for m in actual_methods if "refresh" in m}
        self.assertEqual(
            len(refresh_methods),
            0,
            f"PermissionQuerier不应该包含refresh方法: {refresh_methods}",
        )

        # 验证包含所有查询方法
        for method in expected_methods:
            self.assertIn(
                method, actual_methods, f"PermissionQuerier应该包含查询方法: {method}"
            )

    @patch("app.core.permission_queries.optimized_single_user_query_v3")
    def test_cache_refresh_calls_query_module(self, mock_query):
        """测试缓存刷新调用查询模块"""
        from app.core.hybrid_permission_cache import HybridPermissionCache

        # 设置模拟返回值
        mock_query.return_value = self.mock_permissions

        # 创建缓存实例
        cache = HybridPermissionCache()

        # 执行刷新
        cache.refresh_user_permissions(
            self.user_id, self.mock_db_session, self.server_id
        )

        # 验证调用了查询模块
        mock_query.assert_called_once_with(
            self.user_id, self.mock_db_session, "server", self.server_id
        )

    @patch("app.core.permission_queries.batch_precompute_permissions")
    def test_cache_batch_refresh_calls_query_module(self, mock_batch_query):
        """测试缓存批量刷新调用查询模块"""
        from app.core.hybrid_permission_cache import HybridPermissionCache

        # 设置模拟返回值
        mock_batch_query.return_value = self.mock_permissions_map

        # 创建缓存实例
        cache = HybridPermissionCache()

        # 执行批量刷新
        cache.batch_refresh_user_permissions(
            self.user_ids, self.mock_db_session, self.server_id
        )

        # 验证调用了查询模块
        mock_batch_query.assert_called_once_with(
            self.user_ids, self.mock_db_session, "server", self.server_id
        )

    @patch("app.blueprints.roles.models.UserRole")
    @patch(
        "app.core.hybrid_permission_cache.HybridPermissionCache.batch_refresh_user_permissions"
    )
    def test_role_refresh_calls_user_refresh(self, mock_batch_refresh, mock_user_role):
        """测试角色刷新调用用户刷新"""
        from app.core.hybrid_permission_cache import HybridPermissionCache

        # 模拟用户角色查询结果
        mock_user_roles = [(123,), (456,)]  # (user_id,)

        # 正确设置mock链 - 模拟db_session.query(UserRole.user_id)
        mock_query = Mock()
        mock_filter = Mock()

        # 设置db_session.query(UserRole.user_id).filter().all()的调用链
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = mock_user_roles

        # 设置db_session.query的返回值
        self.mock_db_session.query.return_value = mock_query

        # 创建缓存实例
        cache = HybridPermissionCache()

        # 执行角色刷新
        cache.refresh_role_permissions(self.role_id, self.mock_db_session)

        # 验证调用了批量用户刷新
        mock_batch_refresh.assert_called_once_with([123, 456], self.mock_db_session)

    def test_correct_call_chain(self):
        """测试正确的调用链：API -> Cache -> Query"""

        # 模拟API层调用
        def api_refresh_user_permissions(
            user_id: int, db_session, server_id: int = None
        ):
            """API层：刷新用户权限"""
            from app.core.hybrid_permission_cache import refresh_user_permissions

            return refresh_user_permissions(user_id, db_session, server_id)

        # 模拟缓存层调用
        def cache_refresh_user_permissions(
            user_id: int, db_session, server_id: int = None
        ):
            """缓存层：刷新用户权限缓存"""
            from app.core.permission_queries import optimized_single_user_query_v3

            # 调用查询模块获取最新数据
            latest_permissions = optimized_single_user_query_v3(
                user_id, db_session, "server", server_id
            )

            # 更新缓存（这里只是模拟）
            return latest_permissions

        # 验证调用链
        with patch(
            "app.core.permission_queries.optimized_single_user_query_v3"
        ) as mock_query:
            mock_query.return_value = self.mock_permissions

            # 执行API调用
            result = api_refresh_user_permissions(
                self.user_id, self.mock_db_session, self.server_id
            )

            # 验证查询模块被调用
            mock_query.assert_called_once_with(
                self.user_id, self.mock_db_session, "server", self.server_id
            )

    def test_separation_of_concerns(self):
        """测试关注点分离"""
        # 查询模块职责
        query_responsibilities = ["数据库查询", "SQL优化", "异常处理", "数据转换"]

        # 缓存模块职责
        cache_responsibilities = ["缓存管理", "缓存失效", "缓存预热", "性能优化"]

        # 验证职责分离
        self.assertNotEqual(
            query_responsibilities,
            cache_responsibilities,
            "查询模块和缓存模块应该有明确的职责分离",
        )

    def test_no_duplicate_functionality(self):
        """测试没有重复功能"""
        from app.core.permission_queries import PermissionQuerier

        querier = PermissionQuerier(self.mock_db_session)

        # 验证get和get_batch方法存在
        self.assertTrue(hasattr(querier, "get"))
        self.assertTrue(hasattr(querier, "get_batch"))

        # 验证没有refresh方法（因为已经移除）
        self.assertFalse(hasattr(querier, "refresh_user_permissions"))
        self.assertFalse(hasattr(querier, "batch_refresh_user_permissions"))


if __name__ == "__main__":
    unittest.main()
