"""
装饰器工厂测试

验证修复后的装饰器工厂使用全局注册表
"""

import pytest
import time
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.permission_resilience import (
    circuit_breaker,
    rate_limit,
    bulkhead,
    get_or_create_circuit_breaker,
    get_or_create_rate_limiter,
    get_or_create_bulkhead,
    clear_resilience_instances,
    get_resilience_instances_info,
    CircuitBreaker,
    RateLimiter,
    Bulkhead,
)


class TestDecoratorFactory:
    """装饰器工厂测试"""

    def setup_method(self):
        """测试前准备"""
        # 清空注册表，确保测试独立性
        clear_resilience_instances()

    def teardown_method(self):
        """测试后清理"""
        clear_resilience_instances()

    def test_circuit_breaker_singleton_behavior(self):
        """测试熔断器装饰器的单例行为"""

        # 定义两个使用相同名称的装饰器函数
        @circuit_breaker("test_breaker")
        def function1():
            return "function1"

        @circuit_breaker("test_breaker")
        def function2():
            return "function2"

        # 验证两个函数使用同一个熔断器实例
        breaker1 = get_or_create_circuit_breaker("test_breaker")
        breaker2 = get_or_create_circuit_breaker("test_breaker")

        assert breaker1 is breaker2
        assert id(breaker1) == id(breaker2)

        # 验证注册表信息
        instances_info = get_resilience_instances_info()
        assert "test_breaker" in instances_info
        assert instances_info["test_breaker"] == "CircuitBreaker"

    def test_rate_limiter_singleton_behavior(self):
        """测试限流器装饰器的单例行为"""

        # 定义两个使用相同名称的装饰器函数
        @rate_limit("test_limiter")
        def function1():
            return "function1"

        @rate_limit("test_limiter")
        def function2():
            return "function2"

        # 验证两个函数使用同一个限流器实例
        limiter1 = get_or_create_rate_limiter("test_limiter")
        limiter2 = get_or_create_rate_limiter("test_limiter")

        assert limiter1 is limiter2
        assert id(limiter1) == id(limiter2)

        # 验证注册表信息
        instances_info = get_resilience_instances_info()
        assert "test_limiter" in instances_info
        assert instances_info["test_limiter"] == "RateLimiter"

    def test_bulkhead_singleton_behavior(self):
        """测试舱壁隔离器装饰器的单例行为"""

        # 定义两个使用相同名称的装饰器函数
        @bulkhead("test_bulkhead")
        def function1():
            return "function1"

        @bulkhead("test_bulkhead")
        def function2():
            return "function2"

        # 验证两个函数使用同一个舱壁隔离器实例
        bulkhead1 = get_or_create_bulkhead("test_bulkhead")
        bulkhead2 = get_or_create_bulkhead("test_bulkhead")

        assert bulkhead1 is bulkhead2
        assert id(bulkhead1) == id(bulkhead2)

        # 验证注册表信息
        instances_info = get_resilience_instances_info()
        assert "test_bulkhead" in instances_info
        assert instances_info["test_bulkhead"] == "Bulkhead"

    def test_multiple_resilience_components(self):
        """测试多个韧性组件的独立注册"""
        # 创建不同类型的韧性组件
        breaker = get_or_create_circuit_breaker("breaker1")
        limiter = get_or_create_rate_limiter("limiter1")
        bulkhead_instance = get_or_create_bulkhead("bulkhead1")

        # 验证它们是不同的实例
        assert breaker is not limiter
        assert breaker is not bulkhead_instance
        assert limiter is not bulkhead_instance

        # 验证注册表包含所有实例
        instances_info = get_resilience_instances_info()
        assert len(instances_info) == 3
        assert "breaker1" in instances_info
        assert "limiter1" in instances_info
        assert "bulkhead1" in instances_info

    def test_bulkhead_state_persistence(self):
        """测试舱壁隔离器状态持久性"""

        @bulkhead("test_bulkhead_persistence")
        def test_function():
            return "success"

        # 获取舱壁隔离器实例
        bulkhead_instance = get_or_create_bulkhead("test_bulkhead_persistence")

        # 记录初始状态
        initial_total_calls = bulkhead_instance.total_calls
        initial_active_calls = bulkhead_instance.active_calls

        # 调用函数
        result = test_function()
        assert result == "success"

        # 验证状态已更新
        assert bulkhead_instance.total_calls == initial_total_calls + 1
        assert bulkhead_instance.active_calls == initial_active_calls  # 应该回到初始值

        # 再次调用，验证状态继续累积
        result = test_function()
        assert result == "success"
        assert bulkhead_instance.total_calls == initial_total_calls + 2

    def test_clear_resilience_instances(self):
        """测试清空韧性组件注册表"""
        # 创建一些实例
        get_or_create_circuit_breaker("test1")
        get_or_create_rate_limiter("test2")
        get_or_create_bulkhead("test3")

        # 验证注册表不为空
        instances_info = get_resilience_instances_info()
        assert len(instances_info) == 3

        # 清空注册表
        clear_resilience_instances()

        # 验证注册表已清空
        instances_info = get_resilience_instances_info()
        assert len(instances_info) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
