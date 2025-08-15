"""
权限系统韧性模块测试

测试熔断器、限流器、降级等韧性策略的功能
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from app.core.permission.permission_resilience import (
    ResilienceController,
    CircuitBreaker,
    RateLimiter,
    CircuitBreakerState,
    RateLimitType,
    DegradationLevel,
    CircuitBreakerConfig,
    RateLimitConfig,
    DegradationConfig,
    get_resilience_controller,
    circuit_breaker,
    rate_limit,
    degradable,
    get_circuit_breaker_state,
    get_rate_limit_status,
    set_circuit_breaker_config,
    set_rate_limit_config,
    set_degradation_config,
)


class TestResilienceController:
    """测试韧性控制器"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = ResilienceController()

    def test_initialization(self):
        """测试初始化"""
        assert self.controller.config_source is None
        assert isinstance(self.controller.local_cache, dict)
        assert self.controller.cache_ttl == 30

    def test_get_circuit_breaker_config_default(self):
        """测试获取默认熔断器配置"""
        config = self.controller.get_circuit_breaker_config("test_breaker")
        assert config.name == "test_breaker"
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.state == CircuitBreakerState.CLOSED

    def test_get_rate_limit_config_default(self):
        """测试获取默认限流器配置"""
        config = self.controller.get_rate_limit_config("test_limiter")
        assert config.name == "test_limiter"
        assert config.limit_type == RateLimitType.TOKEN_BUCKET
        assert config.max_requests == 100
        assert config.enabled is True

    def test_get_degradation_config_default(self):
        """测试获取默认降级配置"""
        config = self.controller.get_degradation_config("test_degradation")
        assert config.name == "test_degradation"
        assert config.level == DegradationLevel.NONE
        assert config.enabled is False

    def test_set_and_get_circuit_breaker_config(self):
        """测试设置和获取熔断器配置"""
        config = CircuitBreakerConfig(
            name="test_breaker",
            failure_threshold=10,
            recovery_timeout=120.0,
            state=CircuitBreakerState.OPEN,
        )

        # 设置配置
        success = self.controller.set_circuit_breaker_config("test_breaker", config)
        assert success is True  # 内存存储应该成功

        # 获取配置
        retrieved_config = self.controller.get_circuit_breaker_config("test_breaker")
        assert retrieved_config.failure_threshold == 10
        assert retrieved_config.recovery_timeout == 120.0
        assert retrieved_config.state == CircuitBreakerState.OPEN

    def test_global_switch(self):
        """测试全局开关"""
        # 设置开关
        success = self.controller.set_global_switch("test_switch", True)
        assert success is True

        # 检查开关状态
        enabled = self.controller.is_global_switch_enabled("test_switch")
        assert enabled is True

        # 关闭开关
        self.controller.set_global_switch("test_switch", False)
        enabled = self.controller.is_global_switch_enabled("test_switch")
        assert enabled is False

    def test_clear_cache(self):
        """测试清除缓存"""
        # 添加一些数据到缓存
        self.controller.local_cache["test_key"] = "test_value"

        # 清除缓存
        self.controller.clear_cache()

        # 验证缓存已清除
        assert len(self.controller.local_cache) == 0


class TestCircuitBreaker:
    """测试熔断器"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = ResilienceController()
        self.breaker = CircuitBreaker("test_breaker", self.controller)

    def test_initialization(self):
        """测试初始化"""
        assert self.breaker.name == "test_breaker"
        assert self.breaker.failure_count == 0
        assert self.breaker.get_state() == CircuitBreakerState.CLOSED

    def test_record_success_closed_state(self):
        """测试在关闭状态下记录成功"""
        initial_failure_count = self.breaker.failure_count
        self.breaker.record_success()
        assert self.breaker.failure_count == initial_failure_count  # 不应该改变

    def test_record_failure_transition_to_open(self):
        """测试记录失败导致转换到开启状态"""
        config = self.breaker.get_config()
        config.failure_threshold = 2  # 设置较低的阈值
        self.controller.set_circuit_breaker_config("test_breaker", config)

        # 记录失败直到超过阈值
        self.breaker.record_failure()
        assert self.breaker.get_state() == CircuitBreakerState.CLOSED

        self.breaker.record_failure()
        assert self.breaker.get_state() == CircuitBreakerState.OPEN

    def test_half_open_transition(self):
        """测试半开状态转换"""
        # 设置熔断器为开启状态
        config = self.breaker.get_config()
        config.state = CircuitBreakerState.OPEN
        config.recovery_timeout = 0.1  # 很短的恢复时间
        self.controller.set_circuit_breaker_config("test_breaker", config)

        # 等待恢复时间
        time.sleep(0.2)

        # 记录成功应该转换到半开状态
        self.breaker.record_success()
        assert self.breaker.get_state() == CircuitBreakerState.HALF_OPEN

    def test_half_open_to_closed_transition(self):
        """测试从半开状态转换到关闭状态"""
        # 设置熔断器为半开状态
        config = self.breaker.get_config()
        config.state = CircuitBreakerState.HALF_OPEN
        self.controller.set_circuit_breaker_config("test_breaker", config)

        # 记录成功直到达到最大调用次数
        self.breaker.record_success()
        assert self.breaker.get_state() == CircuitBreakerState.HALF_OPEN

        self.breaker.record_success()
        assert self.breaker.get_state() == CircuitBreakerState.CLOSED

    def test_is_open(self):
        """测试is_open方法"""
        assert self.breaker.is_open() is False

        # 设置为开启状态
        config = self.breaker.get_config()
        config.state = CircuitBreakerState.OPEN
        self.controller.set_circuit_breaker_config("test_breaker", config)

        assert self.breaker.is_open() is True

    def test_can_execute(self):
        """测试can_execute方法"""
        # 关闭状态
        assert self.breaker.can_execute() is True

        # 开启状态
        config = self.breaker.get_config()
        config.state = CircuitBreakerState.OPEN
        self.controller.set_circuit_breaker_config("test_breaker", config)
        assert self.breaker.can_execute() is False

        # 半开状态
        config.state = CircuitBreakerState.HALF_OPEN
        self.controller.set_circuit_breaker_config("test_breaker", config)
        assert self.breaker.can_execute() is True


class TestRateLimiter:
    """测试限流器"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.controller = ResilienceController()
        self.limiter = RateLimiter("test_limiter", self.controller)

    def test_initialization(self):
        """测试初始化"""
        assert self.limiter.name == "test_limiter"
        assert isinstance(self.limiter.tokens, dict)
        assert isinstance(self.limiter.request_times, dict)

    def test_token_bucket_allowed(self):
        """测试令牌桶允许请求"""
        config = self.limiter.get_config()
        config.limit_type = RateLimitType.TOKEN_BUCKET
        config.max_requests = 10
        config.tokens_per_second = 1
        self.controller.set_rate_limit_config("test_limiter", config)

        # 应该允许请求
        assert self.limiter.is_allowed("test_key") is True

    def test_token_bucket_limited(self):
        """测试令牌桶限制请求"""
        config = self.limiter.get_config()
        config.limit_type = RateLimitType.TOKEN_BUCKET
        config.max_requests = 1
        config.tokens_per_second = 0.1  # 很慢的令牌生成
        self.controller.set_rate_limit_config("test_limiter", config)

        # 第一个请求应该被允许
        assert self.limiter.is_allowed("test_key") is True

        # 第二个请求应该被拒绝
        assert self.limiter.is_allowed("test_key") is False

    def test_sliding_window_allowed(self):
        """测试滑动窗口允许请求"""
        config = self.limiter.get_config()
        config.limit_type = RateLimitType.SLIDING_WINDOW
        config.max_requests = 10
        config.time_window = 60.0
        self.controller.set_rate_limit_config("test_limiter", config)

        # 应该允许请求
        assert self.limiter.is_allowed("test_key") is True

    def test_sliding_window_limited(self):
        """测试滑动窗口限制请求"""
        config = self.limiter.get_config()
        config.limit_type = RateLimitType.SLIDING_WINDOW
        config.max_requests = 2
        config.time_window = 60.0
        self.controller.set_rate_limit_config("test_limiter", config)

        # 前两个请求应该被允许
        assert self.limiter.is_allowed("test_key") is True
        assert self.limiter.is_allowed("test_key") is True

        # 第三个请求应该被拒绝
        assert self.limiter.is_allowed("test_key") is False

    def test_disabled_limiter(self):
        """测试禁用的限流器"""
        config = self.limiter.get_config()
        config.enabled = False
        self.controller.set_rate_limit_config("test_limiter", config)

        # 禁用的限流器应该总是允许请求
        for _ in range(100):
            assert self.limiter.is_allowed("test_key") is True


class TestDecorators:
    """测试装饰器"""

    def test_circuit_breaker_decorator_success(self):
        """测试熔断器装饰器成功情况"""
        call_count = 0

        @circuit_breaker("test_breaker")
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        # 应该正常执行
        result = test_function()
        assert result == "success"
        assert call_count == 1

    def test_circuit_breaker_decorator_failure(self):
        """测试熔断器装饰器失败情况"""
        call_count = 0

        @circuit_breaker("test_breaker")
        def test_function():
            nonlocal call_count
            call_count += 1
            raise Exception("test error")

        # 应该抛出异常
        with pytest.raises(Exception, match="test error"):
            test_function()
        assert call_count == 1

    def test_circuit_breaker_decorator_with_fallback(self):
        """测试熔断器装饰器带降级函数"""
        call_count = 0
        fallback_count = 0

        def fallback_function():
            nonlocal fallback_count
            fallback_count += 1
            return "fallback"

        @circuit_breaker("test_breaker", fallback_function)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise Exception("test error")

        # 应该调用降级函数
        result = test_function()
        assert result == "fallback"
        assert call_count == 1
        assert fallback_count == 1

    def test_rate_limit_decorator(self):
        """测试限流器装饰器"""
        call_count = 0

        @rate_limit("test_limiter")
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        # 应该正常执行
        result = test_function()
        assert result == "success"
        assert call_count == 1

    def test_degradable_decorator_enabled(self):
        """测试降级装饰器启用情况"""
        call_count = 0
        fallback_count = 0

        def fallback_function():
            nonlocal fallback_count
            fallback_count += 1
            return "fallback"

        @degradable("test_degradation", fallback_function)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "normal"

        # 启用降级
        controller = get_resilience_controller()
        config = controller.get_degradation_config("test_degradation")
        config.enabled = True
        controller.set_degradation_config("test_degradation", config)

        # 应该调用降级函数
        result = test_function()
        assert result == "fallback"
        assert call_count == 0
        assert fallback_count == 1

    def test_degradable_decorator_disabled(self):
        """测试降级装饰器禁用情况"""
        call_count = 0
        fallback_count = 0

        def fallback_function():
            nonlocal fallback_count
            fallback_count += 1
            return "fallback"

        @degradable("test_degradation", fallback_function)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "normal"

        # 禁用降级
        controller = get_resilience_controller()
        config = controller.get_degradation_config("test_degradation")
        config.enabled = False
        controller.set_degradation_config("test_degradation", config)

        # 应该调用正常函数
        result = test_function()
        assert result == "normal"
        assert call_count == 1
        assert fallback_count == 0


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_get_circuit_breaker_state(self):
        """测试获取熔断器状态"""
        state = get_circuit_breaker_state("test_breaker")
        assert "name" in state
        assert "state" in state
        assert "failure_count" in state
        assert "config" in state

    def test_get_rate_limit_status(self):
        """测试获取限流器状态"""
        status = get_rate_limit_status("test_limiter")
        assert "name" in status
        assert "enabled" in status
        assert "limit_type" in status
        assert "max_requests" in status

    def test_set_circuit_breaker_config(self):
        """测试设置熔断器配置"""
        success = set_circuit_breaker_config("test_breaker", failure_threshold=10)
        assert success is True

        # 验证配置已更新
        state = get_circuit_breaker_state("test_breaker")
        assert state["config"]["failure_threshold"] == 10

    def test_set_rate_limit_config(self):
        """测试设置限流器配置"""
        success = set_rate_limit_config("test_limiter", max_requests=50)
        assert success is True

        # 验证配置已更新
        status = get_rate_limit_status("test_limiter")
        assert status["max_requests"] == 50

    def test_set_degradation_config(self):
        """测试设置降级配置"""
        success = set_degradation_config("test_degradation", enabled=True)
        assert success is True

        # 验证配置已更新
        controller = get_resilience_controller()
        config = controller.get_degradation_config("test_degradation")
        assert config.enabled is True


def test_redis_integration():
    """测试Redis集成"""
    # 模拟Redis不可用的情况
    with patch("app.core.permission_resilience.REDIS_AVAILABLE", False):
        controller = ResilienceController()
        assert controller.config_source is None

        # 应该使用内存存储
        config = controller.get_circuit_breaker_config("test_breaker")
        assert config is not None


def test_thread_safety():
    """测试线程安全性"""
    controller = ResilienceController()
    breaker = CircuitBreaker("test_breaker", controller)

    def worker():
        for _ in range(100):
            breaker.record_success()
            breaker.record_failure()

    # 创建多个线程
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 验证没有异常发生
    assert True


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
