"""
权限模块循环依赖测试

验证权限模块的循环依赖问题是否已解决
"""

import pytest
import sys
import importlib
from unittest.mock import patch, MagicMock


def test_no_circular_dependency():
    """测试没有循环依赖"""

    # 测试可以正常导入各个模块
    try:
        # 测试查询模块导入
        from app.core.permission_queries import (
            optimized_single_user_query_v3,
            PermissionQuerier,
        )

        assert True, "查询模块导入成功"
    except ImportError as e:
        pytest.fail(f"查询模块导入失败: {e}")

    try:
        # 测试缓存模块导入
        from app.core.hybrid_permission_cache import (
            HybridPermissionCache,
            get_hybrid_cache,
        )

        assert True, "缓存模块导入成功"
    except ImportError as e:
        pytest.fail(f"缓存模块导入失败: {e}")

    try:
        # 测试管理模块导入
        from app.core.permission_manager import (
            PermissionManager,
            get_permission_manager,
        )

        assert True, "管理模块导入成功"
    except ImportError as e:
        pytest.fail(f"管理模块导入失败: {e}")


def test_query_module_pure_function():
    """测试查询模块的纯函数特性"""

    from app.core.permission_queries import refresh_user_permissions

    # 模拟数据库会话
    mock_db_session = MagicMock()

    # 测试查询函数只返回数据，不执行缓存操作
    with patch(
        "app.core.permission_queries.optimized_single_user_query_v3"
    ) as mock_query:
        mock_query.return_value = {"read_channel", "send_message"}

        result = refresh_user_permissions(1, mock_db_session)

        # 验证返回了查询结果
        assert result == {"read_channel", "send_message"}
        # 验证调用了查询函数，注意现在传递了server_id参数
        mock_query.assert_called_once_with(1, mock_db_session, "server", None)


def test_cache_module_refresh_function():
    """测试缓存模块的刷新功能"""

    from app.core.hybrid_permission_cache import HybridPermissionCache

    # 创建缓存实例
    cache = HybridPermissionCache()

    # 测试刷新方法存在
    assert hasattr(
        cache, "refresh_user_permissions"
    ), "缓存模块应该有refresh_user_permissions方法"
    assert hasattr(
        cache, "batch_refresh_user_permissions"
    ), "缓存模块应该有batch_refresh_user_permissions方法"
    assert hasattr(
        cache, "refresh_role_permissions"
    ), "缓存模块应该有refresh_role_permissions方法"


def test_manager_module_integration():
    """测试管理模块的集成功能"""

    from app.core.permission_manager import PermissionManager

    # 创建管理实例
    manager = PermissionManager()

    # 测试管理方法存在
    assert hasattr(
        manager, "on_user_role_changed"
    ), "管理模块应该有on_user_role_changed方法"
    assert hasattr(
        manager, "on_role_permissions_changed"
    ), "管理模块应该有on_role_permissions_changed方法"
    assert hasattr(
        manager, "on_user_permissions_changed"
    ), "管理模块应该有on_user_permissions_changed方法"
    assert hasattr(
        manager, "on_batch_permissions_changed"
    ), "管理模块应该有on_batch_permissions_changed方法"


def test_correct_call_chain():
    """测试正确的调用链"""

    # 模拟业务层调用
    with patch("app.core.permission_manager.refresh_user_permissions") as mock_refresh:
        from app.core.permission_manager import on_user_role_changed

        # 调用业务层接口
        on_user_role_changed(1, [1, 2, 3])

        # 验证调用了缓存刷新方法
        mock_refresh.assert_called_once_with(1)


def test_module_responsibilities():
    """测试模块职责分离"""

    # 查询模块应该只包含查询相关功能
    from app.core.permission_queries import (
        optimized_single_user_query_v3,
        batch_precompute_permissions,
    )

    # 验证查询模块的函数存在
    assert callable(optimized_single_user_query_v3), "查询函数应该可调用"
    assert callable(batch_precompute_permissions), "批量查询函数应该可调用"

    # 缓存模块应该包含缓存相关功能
    from app.core.hybrid_permission_cache import HybridPermissionCache

    # 验证缓存模块包含缓存管理功能
    cache = HybridPermissionCache()
    assert hasattr(cache, "complex_cache")
    assert hasattr(cache, "distributed_cache")

    # 管理模块应该包含业务逻辑
    from app.core.permission_manager import PermissionManager

    # 验证管理模块包含业务逻辑
    manager = PermissionManager()
    assert hasattr(manager, "stats")
    assert hasattr(manager, "on_user_role_changed")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
