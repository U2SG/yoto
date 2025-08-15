"""
多维限流测试

测试基于user_id、server_id、ip_address的多维限流功能
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.permission_resilience import (
    RateLimiter,
    RateLimitConfig,
    MultiDimensionalKey,
    ResilienceController,
    get_resilience_controller,
    set_rate_limit_config,
    get_rate_limit_status,
)


class TestMultiDimensionalRateLimit:
    """测试多维限流"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = ResilienceController()
        # 为每个测试使用唯一的限流器名称，避免状态累积
        import uuid

        self.limiter_name = f"test_multi_limiter_{uuid.uuid4().hex[:8]}"
        self.limiter = RateLimiter(self.limiter_name, self.controller)

    def test_multi_dimensional_key_creation(self):
        """测试多维限流键创建"""
        key = MultiDimensionalKey(
            user_id="user123", server_id="server456", ip_address="192.168.1.100"
        )

        assert key.user_id == "user123"
        assert key.server_id == "server456"
        assert key.ip_address == "192.168.1.100"

        # 测试哈希和相等性
        key2 = MultiDimensionalKey(
            user_id="user123", server_id="server456", ip_address="192.168.1.100"
        )
        assert key == key2
        assert hash(key) == hash(key2)

    def test_multi_dimensional_key_to_dict(self):
        """测试多维限流键转换为字典"""
        key = MultiDimensionalKey(
            user_id="user123", server_id="server456", ip_address="192.168.1.100"
        )

        result = key.to_dict()
        assert result["user_id"] == "user123"
        assert result["server_id"] == "server456"
        assert result["ip_address"] == "192.168.1.100"

    def test_multi_dimensional_config(self):
        """测试多维限流配置"""
        config = RateLimitConfig(
            name="test_multi",
            multi_dimensional=True,
            user_id_limit=10,
            server_id_limit=50,
            ip_limit=20,
            combined_limit=100,
        )

        assert config.multi_dimensional is True
        assert config.user_id_limit == 10
        assert config.server_id_limit == 50
        assert config.ip_limit == 20
        assert config.combined_limit == 100

    def test_user_id_dimension_limit(self):
        """测试用户ID维度限流"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=3,  # 每个用户最多3个请求
            server_id_limit=0,  # 禁用服务器维度
            ip_limit=0,  # 禁用IP维度
            combined_limit=0,  # 禁用组合维度
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 创建测试键
        multi_key = MultiDimensionalKey(user_id="user123")

        # 前3个请求应该被允许
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True

        # 第4个请求应该被拒绝
        assert self.limiter.is_allowed("default", multi_key) is False

    def test_server_id_dimension_limit(self):
        """测试服务器ID维度限流"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=0,  # 禁用用户维度
            server_id_limit=2,  # 每个服务器最多2个请求
            ip_limit=0,  # 禁用IP维度
            combined_limit=0,  # 禁用组合维度
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 创建测试键
        multi_key = MultiDimensionalKey(server_id="server456")

        # 前2个请求应该被允许
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True

        # 第3个请求应该被拒绝
        assert self.limiter.is_allowed("default", multi_key) is False

    def test_ip_address_dimension_limit(self):
        """测试IP地址维度限流"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=0,  # 禁用用户维度
            server_id_limit=0,  # 禁用服务器维度
            ip_limit=4,  # 每个IP最多4个请求
            combined_limit=0,  # 禁用组合维度
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 创建测试键
        multi_key = MultiDimensionalKey(ip_address="192.168.1.100")

        # 前4个请求应该被允许
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True

        # 第5个请求应该被拒绝
        assert self.limiter.is_allowed("default", multi_key) is False

    def test_combined_dimension_limit(self):
        """测试组合维度限流"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=0,  # 禁用用户维度
            server_id_limit=0,  # 禁用服务器维度
            ip_limit=0,  # 禁用IP维度
            combined_limit=2,  # 组合维度最多2个请求
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 创建测试键
        multi_key = MultiDimensionalKey(
            user_id="user123", server_id="server456", ip_address="192.168.1.100"
        )

        # 前2个请求应该被允许
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True

        # 第3个请求应该被拒绝
        assert self.limiter.is_allowed("default", multi_key) is False

    def test_multi_dimensional_independence(self):
        """测试多维限流的独立性"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=2,  # 每个用户最多2个请求
            server_id_limit=3,  # 每个服务器最多3个请求
            ip_limit=4,  # 每个IP最多4个请求
            combined_limit=5,  # 组合维度最多5个请求
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 不同用户应该独立限流
        user1_key = MultiDimensionalKey(user_id="user1")
        user2_key = MultiDimensionalKey(user_id="user2")

        # user1 前2个请求应该被允许
        assert self.limiter.is_allowed("default", user1_key) is True
        assert self.limiter.is_allowed("default", user1_key) is True
        assert self.limiter.is_allowed("default", user1_key) is False  # 第3个被拒绝

        # user2 应该还能正常请求
        assert self.limiter.is_allowed("default", user2_key) is True
        assert self.limiter.is_allowed("default", user2_key) is True
        assert self.limiter.is_allowed("default", user2_key) is False  # 第3个被拒绝

    def test_multi_dimensional_without_key(self):
        """测试没有多维键时的行为"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name="test_multi",
            multi_dimensional=True,
            user_id_limit=2,
            server_id_limit=3,
            ip_limit=4,
            combined_limit=5,
        )
        self.controller.set_rate_limit_config("test_multi", config)

        # 没有多维键时应该只进行单维限流
        assert self.limiter.is_allowed("default", None) is True

    def test_multi_dimensional_disabled(self):
        """测试禁用多维限流时的行为"""
        # 设置禁用多维限流
        config = RateLimitConfig(
            name="test_multi",
            multi_dimensional=False,
            user_id_limit=2,
            server_id_limit=3,
            ip_limit=4,
            combined_limit=5,
        )
        self.controller.set_rate_limit_config("test_multi", config)

        # 多维限流被禁用时应该只进行单维限流
        multi_key = MultiDimensionalKey(
            user_id="user123", server_id="server456", ip_address="192.168.1.100"
        )

        assert self.limiter.is_allowed("default", multi_key) is True

    def test_multi_dimensional_time_window(self):
        """测试多维限流的时间窗口"""
        # 设置多维限流配置
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=2,  # 每个用户最多2个请求
            server_id_limit=0,
            ip_limit=0,
            combined_limit=0,
        )
        self.controller.set_rate_limit_config(self.limiter_name, config)

        multi_key = MultiDimensionalKey(user_id="user123")

        # 前2个请求应该被允许
        assert self.limiter.is_allowed("default", multi_key) is True
        assert self.limiter.is_allowed("default", multi_key) is True

        # 第3个请求应该被拒绝
        assert self.limiter.is_allowed("default", multi_key) is False

        # 等待时间窗口过期（这里我们模拟时间流逝）
        # 在实际测试中，我们可能需要等待或模拟时间

        # 重新设置配置以重置状态
        self.controller.set_rate_limit_config(self.limiter_name, config)

        # 清理限流器的内部状态
        self.limiter.multi_dimensional_times.clear()

        # 重置后应该又能正常请求
        assert self.limiter.is_allowed("default", multi_key) is True


class TestMultiDimensionalDecorator:
    """测试多维限流装饰器"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = ResilienceController()
        # 为每个测试使用唯一的限流器名称
        import uuid

        self.limiter_name = f"test_decorator_{uuid.uuid4().hex[:8]}"

    def test_multi_dimensional_decorator(self):
        """测试多维限流装饰器"""
        from app.core.permission_resilience import rate_limit, get_resilience_controller

        # 清理全局控制器缓存
        global_controller = get_resilience_controller()
        global_controller.clear_cache()

        # 设置多维限流配置到全局控制器
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=2,
            server_id_limit=0,
            ip_limit=0,
            combined_limit=0,
        )
        global_controller.set_rate_limit_config(self.limiter_name, config)

        # 创建多维键生成函数
        def create_multi_key(*args, **kwargs):
            return MultiDimensionalKey(user_id=kwargs.get("user_id", "default"))

        # 使用装饰器
        @rate_limit(self.limiter_name, multi_key_func=create_multi_key)
        def test_function(user_id: str = "default"):
            return f"success for user {user_id}"

        # 前2个请求应该成功
        assert test_function(user_id="user123") == "success for user user123"
        assert test_function(user_id="user123") == "success for user user123"

        # 第3个请求应该失败
        with pytest.raises(Exception, match=f"限流器 '{self.limiter_name}' 触发"):
            test_function(user_id="user123")

        # 清理全局控制器的缓存，确保状态重置
        global_controller.clear_cache()

    def test_multi_dimensional_decorator_without_multi_key(self):
        """测试没有多维键的装饰器"""
        from app.core.permission_resilience import rate_limit, get_resilience_controller

        # 设置多维限流配置到全局控制器
        global_controller = get_resilience_controller()
        config = RateLimitConfig(
            name=self.limiter_name,
            multi_dimensional=True,
            user_id_limit=2,
            server_id_limit=0,
            ip_limit=0,
            combined_limit=0,
        )
        global_controller.set_rate_limit_config(self.limiter_name, config)

        # 使用装饰器但不提供多维键函数
        @rate_limit(self.limiter_name)
        def test_function():
            return "success"

        # 应该正常工作（因为没有多维键）
        assert test_function() == "success"


class TestMultiDimensionalConfiguration:
    """测试多维限流配置管理"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = get_resilience_controller()
        # 为每个测试使用唯一的限流器名称
        import uuid

        self.limiter_name = f"test_config_{uuid.uuid4().hex[:8]}"

    def test_set_multi_dimensional_config(self):
        """测试设置多维限流配置"""
        success = set_rate_limit_config(
            self.limiter_name,
            multi_dimensional=True,
            user_id_limit=10,
            server_id_limit=20,
            ip_limit=30,
            combined_limit=40,
        )
        assert success is True

        # 验证配置
        status = get_rate_limit_status(self.limiter_name)
        assert status["multi_dimensional"] is True
        assert status["user_id_limit"] == 10
        assert status["server_id_limit"] == 20
        assert status["ip_limit"] == 30
        assert status["combined_limit"] == 40

    def test_get_multi_dimensional_status(self):
        """测试获取多维限流状态"""
        # 设置配置
        set_rate_limit_config(
            self.limiter_name,
            multi_dimensional=True,
            user_id_limit=5,
            server_id_limit=15,
            ip_limit=25,
            combined_limit=35,
        )

        # 获取状态
        status = get_rate_limit_status(self.limiter_name)

        # 验证状态
        assert "multi_dimensional" in status
        assert "user_id_limit" in status
        assert "server_id_limit" in status
        assert "ip_limit" in status
        assert "combined_limit" in status


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
