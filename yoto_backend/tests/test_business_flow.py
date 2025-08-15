"""
权限系统业务流程测试
"""

import pytest
import time
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.core.permission_business_flow import (
        PermissionBusinessFlow,
        PermissionRequest,
        PermissionResult,
        PermissionLevel,
        ResourceType,
        require_permission,
        get_permission_business_flow,
    )
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在正确的目录下运行测试")
    sys.exit(1)


class TestPermissionBusinessFlow:
    """权限业务流程测试"""

    def test_initialization(self):
        """测试初始化"""
        flow = PermissionBusinessFlow()
        assert flow.ml_monitor is not None
        assert flow.performance_viz is not None
        assert flow.request_count == 0
        assert flow.cache_hit_count == 0

    def test_generate_cache_key(self):
        """测试缓存键生成"""
        flow = PermissionBusinessFlow()
        request = PermissionRequest(
            user_id="user_123",
            resource_type=ResourceType.SERVER,
            resource_id="server_456",
            action="read",
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
            request_id="req_123",
        )

        cache_key = flow._generate_cache_key(request)
        expected_key = "perm:user_123:server:server_456:read"
        assert cache_key == expected_key

    def test_validate_permissions(self):
        """测试权限验证"""
        flow = PermissionBusinessFlow()
        request = PermissionRequest(
            user_id="user_123",
            resource_type=ResourceType.SERVER,
            resource_id="server_456",
            action="read",
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
            request_id="req_123",
        )

        # 测试有足够权限的情况
        permissions = {"level": PermissionLevel.ADMIN}
        allowed, reason = flow._validate_permissions(request, permissions)
        assert allowed is True
        assert "权限验证通过" in reason

        # 测试权限不足的情况
        permissions = {"level": PermissionLevel.NONE}
        allowed, reason = flow._validate_permissions(request, permissions)
        assert allowed is False
        assert "权限不足" in reason

        # 测试权限数据不存在的情况
        allowed, reason = flow._validate_permissions(request, None)
        assert allowed is False
        assert "权限数据不存在" in reason

    def test_update_statistics(self):
        """测试统计更新"""
        flow = PermissionBusinessFlow()

        # 初始状态
        assert flow.request_count == 0
        assert flow.cache_hit_count == 0

        # 更新统计
        flow._update_statistics(cache_hit=True)
        assert flow.request_count == 1
        assert flow.cache_hit_count == 1

        flow._update_statistics(cache_hit=False)
        assert flow.request_count == 2
        assert flow.cache_hit_count == 1

    def test_check_permission_success(self):
        """测试权限检查成功"""
        flow = PermissionBusinessFlow()

        # 模拟缓存中有权限数据
        with patch.object(flow, "_get_permissions_with_fallback") as mock_get:
            mock_get.return_value = {"level": PermissionLevel.ADMIN}

            request = PermissionRequest(
                user_id="user_123",
                resource_type=ResourceType.SERVER,
                resource_id="server_456",
                action="read",
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
                request_id="req_123",
            )

            result = flow.check_permission(request)

            assert result.allowed is True
            assert result.cached is True
            assert result.response_time > 0
            assert result.optimization_applied is False

    def test_check_permission_failure(self):
        """测试权限检查失败"""
        flow = PermissionBusinessFlow()

        # 模拟缓存中没有权限数据
        with patch.object(flow, "_get_permissions_with_fallback") as mock_get:
            mock_get.return_value = None

            request = PermissionRequest(
                user_id="user_123",
                resource_type=ResourceType.SERVER,
                resource_id="server_456",
                action="read",
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
                request_id="req_123",
            )

            result = flow.check_permission(request)

            assert result.allowed is False
            assert result.cached is False
            assert "权限数据不存在" in result.reason

    def test_set_permissions(self):
        """测试设置权限"""
        flow = PermissionBusinessFlow()

        # 模拟设置权限成功
        with patch(
            "app.core.advanced_optimization.advanced_set_permissions_to_cache"
        ) as mock_set:
            mock_set.return_value = None

            success = flow.set_permissions(
                user_id="user_123",
                resource_type=ResourceType.SERVER,
                resource_id="server_456",
                permissions={"level": PermissionLevel.ADMIN},
            )

            assert success is True

    def test_get_performance_report(self):
        """测试获取性能报告"""
        flow = PermissionBusinessFlow()

        # 模拟一些请求
        flow._update_statistics(cache_hit=True)
        flow._update_statistics(cache_hit=False)

        report = flow.get_performance_report()

        assert "timestamp" in report
        assert "requests" in report
        assert report["requests"]["total"] == 2
        assert report["requests"]["cache_hits"] == 1
        assert report["requests"]["cache_hit_rate"] == 0.5

    def test_get_optimization_status(self):
        """测试获取优化状态"""
        flow = PermissionBusinessFlow()

        status = flow.get_optimization_status()

        assert "current_config" in status
        assert "optimization_history" in status
        assert "optimization_count" in status


class TestPermissionDecorator:
    """权限装饰器测试"""

    def test_require_permission_decorator(self):
        """测试权限装饰器"""
        # 模拟权限检查成功
        with patch(
            "app.core.permission_business_flow.get_permission_business_flow"
        ) as mock_get_flow:
            mock_flow = MagicMock()
            mock_result = MagicMock()
            mock_result.allowed = True
            mock_result.reason = "权限验证通过"
            mock_result.response_time = 0.1
            mock_flow.check_permission.return_value = mock_result
            mock_get_flow.return_value = mock_flow

            # 测试装饰器函数
            @require_permission(ResourceType.SERVER, "read", PermissionLevel.READ)
            def test_function(user_id="user_123", resource_id="server_456"):
                return "success"

            result = test_function()
            assert result == "success"

    def test_require_permission_decorator_failure(self):
        """测试权限装饰器失败"""
        # 模拟权限检查失败
        with patch(
            "app.core.permission_business_flow.get_permission_business_flow"
        ) as mock_get_flow:
            mock_flow = MagicMock()
            mock_result = MagicMock()
            mock_result.allowed = False
            mock_result.reason = "权限不足"
            mock_flow.check_permission.return_value = mock_result
            mock_get_flow.return_value = mock_flow

            # 测试装饰器函数
            @require_permission(ResourceType.SERVER, "read", PermissionLevel.READ)
            def test_function(user_id="user_123", resource_id="server_456"):
                return "success"

            with pytest.raises(PermissionError):
                test_function()


class TestBusinessFunctions:
    """业务函数测试"""

    def test_get_server_info(self):
        """测试获取服务器信息"""
        # 模拟权限检查成功
        with patch(
            "app.core.permission_business_flow.get_permission_business_flow"
        ) as mock_get_flow:
            mock_flow = MagicMock()
            mock_result = MagicMock()
            mock_result.allowed = True
            mock_result.reason = "权限验证通过"
            mock_result.response_time = 0.1
            mock_flow.check_permission.return_value = mock_result
            mock_get_flow.return_value = mock_flow

            from app.core.permission_business_flow import get_server_info

            result = get_server_info(user_id="user_123", server_id="server_456")
            assert result["server_id"] == "server_456"
            assert result["name"] == "测试服务器"

    def test_send_message(self):
        """测试发送消息"""
        # 模拟权限检查成功
        with patch(
            "app.core.permission_business_flow.get_permission_business_flow"
        ) as mock_get_flow:
            mock_flow = MagicMock()
            mock_result = MagicMock()
            mock_result.allowed = True
            mock_result.reason = "权限验证通过"
            mock_result.response_time = 0.1
            mock_flow.check_permission.return_value = mock_result
            mock_get_flow.return_value = mock_flow

            from app.core.permission_business_flow import send_message

            result = send_message(
                user_id="user_123", channel_id="channel_456", message="Hello"
            )
            assert result["message_id"] == "msg_123"
            assert result["content"] == "Hello"

    def test_manage_user(self):
        """测试管理用户"""
        # 模拟权限检查成功
        with patch(
            "app.core.permission_business_flow.get_permission_business_flow"
        ) as mock_get_flow:
            mock_flow = MagicMock()
            mock_result = MagicMock()
            mock_result.allowed = True
            mock_result.reason = "权限验证通过"
            mock_result.response_time = 0.1
            mock_flow.check_permission.return_value = mock_result
            mock_get_flow.return_value = mock_flow

            from app.core.permission_business_flow import manage_user

            result = manage_user(
                user_id="admin_123", target_user_id="user_456", action="ban"
            )
            assert result["action"] == "ban"
            assert result["target_user"] == "user_456"


class TestIntegration:
    """集成测试"""

    def test_end_to_end_workflow(self):
        """测试端到端工作流程"""
        flow = PermissionBusinessFlow()

        # 1. 设置权限
        success = flow.set_permissions(
            user_id="user_123",
            resource_type=ResourceType.SERVER,
            resource_id="server_456",
            permissions={"level": PermissionLevel.ADMIN},
        )
        assert success is True

        # 2. 检查权限
        request = PermissionRequest(
            user_id="user_123",
            resource_type=ResourceType.SERVER,
            resource_id="server_456",
            action="read",
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
            request_id="req_123",
        )

        result = flow.check_permission(request)
        assert result.allowed is True

        # 3. 获取性能报告
        report = flow.get_performance_report()
        assert "requests" in report

        # 4. 获取优化状态
        status = flow.get_optimization_status()
        assert "current_config" in status

    def test_performance_monitoring(self):
        """测试性能监控"""
        flow = PermissionBusinessFlow()

        # 模拟多次请求
        for i in range(10):
            request = PermissionRequest(
                user_id=f"user_{i}",
                resource_type=ResourceType.SERVER,
                resource_id=f"server_{i}",
                action="read",
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
                request_id=f"req_{i}",
            )

            # 模拟权限检查
            with patch.object(flow, "_get_permissions_with_fallback") as mock_get:
                mock_get.return_value = {"level": PermissionLevel.ADMIN}
                result = flow.check_permission(request)

        # 检查统计
        assert flow.request_count == 10
        assert flow.cache_hit_count == 10


if __name__ == "__main__":
    pytest.main([__file__])
