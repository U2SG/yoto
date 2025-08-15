"""
测试权限系统主模块功能完整性

验证所有子模块功能都已正确集成到主模块中
"""

import pytest
from unittest.mock import Mock, patch
from app.core.permissions_refactored import (
    PermissionSystem,
    get_permission_system,
    # 基础功能
    check_permission,
    batch_check_permissions,
    register_permission,
    register_role,
    assign_permissions_to_role,
    assign_roles_to_user,
    invalidate_user_cache,
    invalidate_role_cache,
    get_system_stats,
    get_optimization_suggestions,
    process_maintenance,
    # 缓存刷新功能
    refresh_user_permissions,
    batch_refresh_user_permissions,
    refresh_role_permissions,
    warm_up_cache,
    # 失效管理功能
    add_delayed_invalidation,
    execute_smart_batch_invalidation,
    execute_global_smart_batch_invalidation,
    trigger_background_invalidation_processing,
    trigger_smart_batch_invalidation,
    trigger_global_smart_batch_invalidation,
    trigger_delayed_invalidation_processing,
    get_redis_connection_status,
    # 监控功能
    get_events_summary,
    get_values_summary,
    clear_alerts,
)


class TestPermissionsRefactoredCompleteness:
    """测试权限系统主模块功能完整性"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.system = PermissionSystem()

    def test_all_cache_refresh_functions_exist(self):
        """测试所有缓存刷新函数都存在"""
        # 验证方法存在
        assert hasattr(self.system, "refresh_user_permissions")
        assert hasattr(self.system, "batch_refresh_user_permissions")
        assert hasattr(self.system, "refresh_role_permissions")
        assert hasattr(self.system, "warm_up_cache")

        # 验证便捷函数存在
        assert "refresh_user_permissions" in globals()
        assert "batch_refresh_user_permissions" in globals()
        assert "refresh_role_permissions" in globals()
        assert "warm_up_cache" in globals()

    def test_all_invalidation_functions_exist(self):
        """测试所有失效管理函数都存在"""
        # 验证方法存在
        assert hasattr(self.system, "add_delayed_invalidation")
        assert hasattr(self.system, "execute_smart_batch_invalidation")
        assert hasattr(self.system, "execute_global_smart_batch_invalidation")
        assert hasattr(self.system, "trigger_background_invalidation_processing")
        assert hasattr(self.system, "trigger_smart_batch_invalidation")
        assert hasattr(self.system, "trigger_global_smart_batch_invalidation")
        assert hasattr(self.system, "trigger_delayed_invalidation_processing")
        assert hasattr(self.system, "get_redis_connection_status")

        # 验证便捷函数存在
        assert "add_delayed_invalidation" in globals()
        assert "execute_smart_batch_invalidation" in globals()
        assert "execute_global_smart_batch_invalidation" in globals()
        assert "trigger_background_invalidation_processing" in globals()
        assert "trigger_smart_batch_invalidation" in globals()
        assert "trigger_global_smart_batch_invalidation" in globals()
        assert "trigger_delayed_invalidation_processing" in globals()
        assert "get_redis_connection_status" in globals()

    def test_all_monitor_functions_exist(self):
        """测试所有监控函数都存在"""
        # 验证方法存在
        assert hasattr(self.system, "get_events_summary")
        assert hasattr(self.system, "get_values_summary")
        assert hasattr(self.system, "clear_alerts")

        # 验证便捷函数存在
        assert "get_events_summary" in globals()
        assert "get_values_summary" in globals()
        assert "clear_alerts" in globals()

    def test_cache_refresh_functions_callable(self):
        """测试缓存刷新函数可调用"""
        with patch(
            "app.core.hybrid_permission_cache.refresh_user_permissions"
        ) as mock_refresh:
            mock_refresh.return_value = {"status": "success"}
            result = self.system.refresh_user_permissions(123)
            assert result == {"status": "success"}
            mock_refresh.assert_called_once_with(123, False)

    def test_invalidation_functions_callable(self):
        """测试失效管理函数可调用"""
        with patch(
            "app.core.permission_invalidation.add_delayed_invalidation"
        ) as mock_add:
            mock_add.return_value = {"status": "success"}
            result = self.system.add_delayed_invalidation("user", 123, 300)
            assert result == {"status": "success"}
            mock_add.assert_called_once_with("user", 123, 300)

    def test_monitor_functions_callable(self):
        """测试监控函数可调用"""
        with patch("app.core.permission_monitor.get_events_summary") as mock_events:
            mock_events.return_value = {"total_events": 10}
            result = self.system.get_events_summary()
            assert result == {"total_events": 10}
            mock_events.assert_called_once()

    def test_convenience_functions_work(self):
        """测试便捷函数正常工作"""
        with patch("app.core.permissions_refactored.get_permission_system") as mock_get:
            mock_system = Mock()
            mock_system.refresh_user_permissions.return_value = {"status": "success"}
            mock_get.return_value = mock_system

            result = refresh_user_permissions(123)
            assert result == {"status": "success"}
            mock_system.refresh_user_permissions.assert_called_once_with(123, False)

    def test_system_initialization(self):
        """测试系统初始化"""
        # 验证系统实例化成功
        system = PermissionSystem()
        assert system is not None
        assert hasattr(system, "cache")
        assert hasattr(system, "monitor")

    def test_get_permission_system_singleton(self):
        """测试权限系统单例模式"""
        system1 = get_permission_system()
        system2 = get_permission_system()
        assert system1 is system2

    def test_all_imports_available(self):
        """测试所有导入都可用"""
        # 验证所有函数都可以导入
        from app.core.permissions_refactored import (
            refresh_user_permissions,
            batch_refresh_user_permissions,
            refresh_role_permissions,
            warm_up_cache,
            add_delayed_invalidation,
            execute_smart_batch_invalidation,
            execute_global_smart_batch_invalidation,
            trigger_background_invalidation_processing,
            trigger_smart_batch_invalidation,
            trigger_global_smart_batch_invalidation,
            trigger_delayed_invalidation_processing,
            get_redis_connection_status,
            get_events_summary,
            get_values_summary,
            clear_alerts,
        )

        # 验证函数都是可调用的
        assert callable(refresh_user_permissions)
        assert callable(batch_refresh_user_permissions)
        assert callable(refresh_role_permissions)
        assert callable(warm_up_cache)
        assert callable(add_delayed_invalidation)
        assert callable(execute_smart_batch_invalidation)
        assert callable(execute_global_smart_batch_invalidation)
        assert callable(trigger_background_invalidation_processing)
        assert callable(trigger_smart_batch_invalidation)
        assert callable(trigger_global_smart_batch_invalidation)
        assert callable(trigger_delayed_invalidation_processing)
        assert callable(get_redis_connection_status)
        assert callable(get_events_summary)
        assert callable(get_values_summary)
        assert callable(clear_alerts)


def test_function_coverage():
    """测试函数覆盖完整性"""
    # 验证所有子模块的主要功能都已集成
    expected_functions = [
        # 基础功能
        "check_permission",
        "batch_check_permissions",
        "register_permission",
        "register_role",
        "assign_permissions_to_role",
        "assign_roles_to_user",
        "invalidate_user_cache",
        "invalidate_role_cache",
        "get_system_stats",
        "get_optimization_suggestions",
        "process_maintenance",
        # 缓存刷新功能
        "refresh_user_permissions",
        "batch_refresh_user_permissions",
        "refresh_role_permissions",
        "warm_up_cache",
        # 失效管理功能
        "add_delayed_invalidation",
        "execute_smart_batch_invalidation",
        "execute_global_smart_batch_invalidation",
        "trigger_background_invalidation_processing",
        "trigger_smart_batch_invalidation",
        "trigger_global_smart_batch_invalidation",
        "trigger_delayed_invalidation_processing",
        "get_redis_connection_status",
        # 监控功能
        "get_events_summary",
        "get_values_summary",
        "clear_alerts",
    ]

    for func_name in expected_functions:
        assert func_name in globals(), f"函数 {func_name} 未找到"


def test_class_methods_coverage():
    """测试类方法覆盖完整性"""
    system = PermissionSystem()

    expected_methods = [
        # 基础方法
        "check_permission",
        "batch_check_permissions",
        "register_permission",
        "register_role",
        "assign_permissions_to_role",
        "assign_roles_to_user",
        "invalidate_user_cache",
        "invalidate_role_cache",
        "get_system_stats",
        "get_optimization_suggestions",
        "process_maintenance",
        # 缓存刷新方法
        "refresh_user_permissions",
        "batch_refresh_user_permissions",
        "refresh_role_permissions",
        "warm_up_cache",
        # 失效管理方法
        "add_delayed_invalidation",
        "execute_smart_batch_invalidation",
        "execute_global_smart_batch_invalidation",
        "trigger_background_invalidation_processing",
        "trigger_smart_batch_invalidation",
        "trigger_global_smart_batch_invalidation",
        "trigger_delayed_invalidation_processing",
        "get_redis_connection_status",
        # 监控方法
        "get_events_summary",
        "get_values_summary",
        "clear_alerts",
    ]

    for method_name in expected_methods:
        assert hasattr(system, method_name), f"方法 {method_name} 未找到"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
