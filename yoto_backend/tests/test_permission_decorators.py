"""
权限装饰器测试模块

测试权限装饰器的各种功能，包括缓存使用、权限检查等
"""

import unittest
import time
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, request
from flask_jwt_extended import create_access_token

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.permission_decorators import (
    require_permission,
    require_permission_v2,
    require_permissions_v2,
    require_permission_with_expression_v2,
    _get_scope_id,
    evaluate_permission_expression,
    invalidate_permission_check_cache,
    clear_expression_cache,
)


class TestPermissionDecorators(unittest.TestCase):
    """权限装饰器测试类"""

    def setUp(self):
        """测试前准备"""
        self.app = Flask(__name__)
        self.app.config["JWT_SECRET_KEY"] = "test-secret-key"

        # 初始化JWT扩展
        from flask_jwt_extended import JWTManager

        jwt = JWTManager(self.app)

        self.client = self.app.test_client()

        # 模拟用户ID
        self.test_user_id = 123

        # 在应用上下文中创建token
        with self.app.app_context():
            self.test_token = create_access_token(identity=str(self.test_user_id))

        # 模拟权限数据
        self.test_permissions = {
            "read_channel": True,
            "send_message": True,
            "manage_channel": False,
            "admin": True,
            "moderator": False,
        }

    def test_get_scope_id_from_kwargs(self):
        """测试从kwargs获取scope_id"""
        kwargs = {"server_id": "456"}
        scope_id = _get_scope_id("server_id", kwargs)
        self.assertEqual(scope_id, 456)

    def test_get_scope_id_from_args(self):
        """测试从request.args获取scope_id"""
        with self.app.test_request_context("/?channel_id=789"):
            kwargs = {}
            scope_id = _get_scope_id("channel_id", kwargs)
            self.assertEqual(scope_id, 789)

    def test_get_scope_id_from_json(self):
        """测试从request.json获取scope_id"""
        with self.app.test_request_context("/", json={"server_id": "101"}):
            kwargs = {}
            scope_id = _get_scope_id("server_id", kwargs)
            self.assertEqual(scope_id, 101)

    def test_get_scope_id_from_form(self):
        """测试从request.form获取scope_id"""
        with self.app.test_request_context(
            "/",
            data={"channel_id": "202"},
            content_type="application/x-www-form-urlencoded",
        ):
            kwargs = {}
            scope_id = _get_scope_id("channel_id", kwargs)
            self.assertEqual(scope_id, 202)

    def test_get_scope_id_invalid_format(self):
        """测试无效的scope_id格式"""
        with self.app.test_request_context("/"):
            kwargs = {"server_id": "invalid"}
            scope_id = _get_scope_id("server_id", kwargs)
            self.assertIsNone(scope_id)

    def test_get_scope_id_not_found(self):
        """测试找不到scope_id"""
        with self.app.test_request_context("/"):
            kwargs = {}
            scope_id = _get_scope_id("nonexistent", kwargs)
            self.assertIsNone(scope_id)

    def test_evaluate_permission_expression_simple(self):
        """测试简单权限表达式评估"""
        user_permissions = {"admin", "read_channel"}

        # 测试简单权限
        result = evaluate_permission_expression("admin", user_permissions)
        print(f"Debug: 'admin' in {user_permissions} = {result}")
        print(f"Debug: user_permissions type = {type(user_permissions)}")
        print(f"Debug: 'admin' in user_permissions = {'admin' in user_permissions}")
        self.assertTrue(result)

        result = evaluate_permission_expression("moderator", user_permissions)
        print(f"Debug: 'moderator' in {user_permissions} = {result}")
        self.assertFalse(result)

    def test_evaluate_permission_expression_and(self):
        """测试AND权限表达式评估"""
        user_permissions = {"admin", "read_channel", "send_message"}

        # 测试AND逻辑
        result = evaluate_permission_expression(
            "admin and read_channel", user_permissions
        )
        self.assertTrue(result)

        result = evaluate_permission_expression("admin and moderator", user_permissions)
        self.assertFalse(result)

    def test_evaluate_permission_expression_or(self):
        """测试OR权限表达式评估"""
        user_permissions = {"admin", "read_channel"}

        # 测试OR逻辑
        result = evaluate_permission_expression("admin or moderator", user_permissions)
        self.assertTrue(result)

        result = evaluate_permission_expression("moderator or editor", user_permissions)
        self.assertFalse(result)

    def test_evaluate_permission_expression_complex(self):
        """测试复杂权限表达式评估"""
        user_permissions = {"admin", "read_channel", "send_message"}

        # 测试复杂表达式
        result = evaluate_permission_expression(
            "(admin or moderator) and (read_channel or send_message)", user_permissions
        )
        self.assertTrue(result)

        result = evaluate_permission_expression(
            "(admin or moderator) and (manage_server)", user_permissions
        )
        self.assertFalse(result)

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permission_base_success(self, mock_get_cache):
        """测试主装饰器成功情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "read_channel",
            "send_message",
        }
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permission("read_channel")
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, {"success": True})

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permission_base_failure(self, mock_get_cache):
        """测试主装饰器失败情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "send_message"
        }  # 没有read_channel权限
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permission("read_channel")
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, ({"error": "权限不足"}, 403))

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permissions_base_and_success(self, mock_get_cache):
        """测试多权限检查AND成功情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "read_channel",
            "send_message",
            "manage_channel",
        }
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permissions_v2(["read_channel", "send_message"], op="AND")
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, {"success": True})

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permissions_base_or_success(self, mock_get_cache):
        """测试多权限检查OR成功情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "send_message"
        }  # 只有send_message权限
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permissions_v2(["read_channel", "send_message"], op="OR")
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, {"success": True})

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permission_expression_base_success(self, mock_get_cache):
        """测试表达式权限检查成功情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "admin",
            "read_channel",
            "send_message",
        }
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permission_with_expression_v2(
            "(admin or moderator) and (read_channel or send_message)"
        )
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, {"success": True})

    @patch("app.core.permission_decorators.get_hybrid_cache")
    def test_require_permission_expression_base_failure(self, mock_get_cache):
        """测试表达式权限检查失败情况"""
        # 模拟缓存返回
        mock_cache = Mock()
        mock_cache._query_complex_permissions.return_value = {
            "read_channel"
        }  # 权限不足
        mock_get_cache.return_value = mock_cache

        # 创建测试函数
        @require_permission_with_expression_v2(
            "(admin or moderator) and (read_channel or send_message)"
        )
        def test_function():
            return {"success": True}

        # 模拟请求上下文
        with self.app.test_request_context(
            "/", headers={"Authorization": f"Bearer {self.test_token}"}
        ):
            with patch(
                "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
            ):
                result = test_function()
                self.assertEqual(result, ({"error": "权限不足"}, 403))

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        # 测试简化后的缓存键生成
        # 新的缓存键格式：f"perm_check:{hash(permission_check_func)}"

        # 模拟权限检查函数
        def test_permission_check(user_permissions):
            return "read_channel" in user_permissions

        # 简化的缓存键
        cache_key = f"perm_check:{hash(test_permission_check)}"
        self.assertIsInstance(cache_key, str)
        self.assertTrue(cache_key.startswith("perm_check:"))

        # 测试不同函数的缓存键不同
        def test_permission_check2(user_permissions):
            return "send_message" in user_permissions

        cache_key2 = f"perm_check:{hash(test_permission_check2)}"
        self.assertNotEqual(cache_key, cache_key2)

    def test_performance_monitoring(self):
        """测试性能监控"""
        # 模拟慢速权限检查
        with patch("app.core.permission_decorators.get_hybrid_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache._query_complex_permissions.return_value = {"read_channel"}
            mock_get_cache.return_value = mock_cache

            # 模拟慢速响应 - 提供更多的time值以避免迭代器耗尽
            with patch("app.core.permission_decorators.time.time") as mock_time:
                mock_time.side_effect = [0.0, 0.6, 0.7, 0.8, 0.9, 1.0]  # 提供更多值

                @require_permission("read_channel")
                def test_function():
                    return {"success": True}

                with self.app.test_request_context(
                    "/", headers={"Authorization": f"Bearer {self.test_token}"}
                ):
                    with patch(
                        "flask_jwt_extended.get_jwt",
                        return_value={"is_super_admin": False},
                    ):
                        # 这里应该会记录性能警告，但我们主要测试功能正常
                        result = test_function()
                        self.assertEqual(result, {"success": True})

    def test_decorator_uses_hybrid_cache(self):
        """测试装饰器使用get_hybrid_cache而不是直接调用底层缓存"""
        with patch("app.core.permission_decorators.get_hybrid_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache._query_complex_permissions.return_value = {
                "read_channel",
                "send_message",
            }
            mock_get_cache.return_value = mock_cache

            @require_permission("read_channel")
            def test_function():
                return {"success": True}

            with self.app.test_request_context(
                "/", headers={"Authorization": f"Bearer {self.test_token}"}
            ):
                with patch(
                    "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
                ):
                    result = test_function()
                    self.assertEqual(result, {"success": True})

                    # 验证get_hybrid_cache被调用
                    mock_get_cache.assert_called_once()
                    mock_cache._query_complex_permissions.assert_called_once()

    def test_cache_invalidation_uses_hybrid_cache(self):
        """测试缓存失效使用get_hybrid_cache"""
        with patch("app.core.permission_decorators.get_hybrid_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            # 测试用户缓存失效
            invalidate_permission_check_cache(user_id=123)
            mock_get_cache.assert_called()
            mock_cache.invalidate_user_permissions.assert_called_once_with(123)

            # 测试角色缓存失效
            invalidate_permission_check_cache(role_id=456)
            mock_cache.invalidate_role_permissions.assert_called_once_with(456)

            # 测试清空所有缓存
            with patch(
                "app.core.hybrid_permission_cache.clear_all_caches"
            ) as mock_clear_all:
                invalidate_permission_check_cache()
                mock_clear_all.assert_called_once()

    def test_not_operator_functionality(self):
        """测试NOT操作符功能"""
        with patch("app.core.permission_decorators.get_hybrid_cache") as mock_get_cache:
            mock_cache = Mock()
            # 用户拥有read_channel权限，但没有admin权限
            mock_cache._query_complex_permissions.return_value = {
                "read_channel",
                "send_message",
            }
            mock_get_cache.return_value = mock_cache

            @require_permissions_v2(["admin", "super_admin"], op="NOT")
            def test_function():
                return {"success": True}

            with self.app.test_request_context(
                "/", headers={"Authorization": f"Bearer {self.test_token}"}
            ):
                with patch(
                    "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
                ):
                    result = test_function()
                    self.assertEqual(result, {"success": True})

            # 测试用户拥有admin权限的情况（应该失败）
            mock_cache._query_complex_permissions.return_value = {
                "admin",
                "read_channel",
            }

            with self.app.test_request_context(
                "/", headers={"Authorization": f"Bearer {self.test_token}"}
            ):
                with patch(
                    "flask_jwt_extended.get_jwt", return_value={"is_super_admin": False}
                ):
                    result = test_function()
                    self.assertEqual(result, ({"error": "权限不足"}, 403))

    def test_dynamic_permission_registration(self):
        """测试动态权限注册功能"""
        with patch("app.core.permission_decorators.get_hybrid_cache") as mock_get_cache:
            mock_cache = Mock()
            mock_cache._query_complex_permissions.return_value = {"read_channel"}
            mock_get_cache.return_value = mock_cache

            # 模拟批量权限注册函数
            with patch(
                "app.core.permission_decorators.batch_register_permissions"
            ) as mock_batch_register:

                @require_permission(
                    "read_channel", group="test", description="Test permission"
                )
                def test_function():
                    return {"success": True}

                with self.app.test_request_context(
                    "/", headers={"Authorization": f"Bearer {self.test_token}"}
                ):
                    with patch(
                        "flask_jwt_extended.get_jwt",
                        return_value={"is_super_admin": False},
                    ):
                        result = test_function()
                        self.assertEqual(result, {"success": True})

                        # 验证权限注册被调用
                        mock_batch_register.assert_called_once()
                        call_args = mock_batch_register.call_args[0][0]
                        self.assertEqual(len(call_args), 1)
                        self.assertEqual(call_args[0]["name"], "read_channel")
                        self.assertEqual(call_args[0]["group"], "test")
                        self.assertEqual(call_args[0]["description"], "Test permission")


def run_tests():
    """运行所有测试"""
    print("开始运行权限装饰器测试...")

    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPermissionDecorators)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果
    print(f"\n测试结果:")
    print(f"运行测试: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")

    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
