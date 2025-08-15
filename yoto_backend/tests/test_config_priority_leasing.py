#!/usr/bin/env python3
"""
测试配置优先级与租期机制

验证运维人员手动配置不会被ML模块自动优化覆盖的功能
"""

import sys
import os
import time
import json
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.permission.permission_resilience import (
    get_resilience_controller,
    set_circuit_breaker_config,
    set_rate_limit_config,
    set_degradation_config,
    CircuitBreakerConfig,
    RateLimitConfig,
    DegradationConfig,
)
from app.core.permission.permission_ml import (
    get_ml_performance_monitor,
    PerformanceMetrics,
    OptimizationStrategy,
)


class TestConfigPriorityLeasing(unittest.TestCase):
    """测试配置优先级与租期机制"""

    def setUp(self):
        """测试前准备"""
        # 获取韧性控制器
        self.controller = get_resilience_controller()

        # 清除所有配置覆盖
        self.controller.clear_expired_overrides()

        # 获取ML监控器
        self.ml_monitor = get_ml_performance_monitor()

        # 设置测试配置
        self.test_configs = {
            "circuit_breaker": {
                "name": "test_breaker",
                "failure_threshold": 3,
                "recovery_timeout": 30.0,
            },
            "rate_limiter": {
                "name": "test_limiter",
                "max_requests": 50,
                "time_window": 30.0,
            },
            "degradation": {
                "name": "test_degradation",
                "enabled": True,
                "timeout": 10.0,
            },
        }

    def tearDown(self):
        """测试后清理"""
        # 清除所有配置覆盖
        self.controller.clear_expired_overrides()

    def test_manual_override_priority(self):
        """测试手动配置覆盖优先级"""
        print("\n=== 测试手动配置覆盖优先级 ===")

        # 1. 设置手动配置覆盖（运维人员操作）
        print("1. 设置手动配置覆盖...")
        success = set_circuit_breaker_config(
            name="test_breaker",
            use_override=True,  # 使用覆盖层
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        self.assertTrue(success)
        print("✓ 手动配置覆盖设置成功")

        # 2. 验证覆盖配置存在
        print("2. 验证覆盖配置存在...")
        overrides = self.controller.get_config_overrides()
        self.assertIn("circuit_breaker:test_breaker", overrides)
        print(f"✓ 覆盖配置存在: {list(overrides.keys())}")

        # 3. 获取配置，应该优先使用覆盖配置
        print("3. 验证配置优先级...")
        config = self.controller.get_circuit_breaker_config("test_breaker")
        self.assertEqual(config.failure_threshold, 5)  # 应该使用覆盖值
        self.assertEqual(config.recovery_timeout, 60.0)  # 应该使用覆盖值
        print(
            f"✓ 配置优先级正确: failure_threshold={config.failure_threshold}, recovery_timeout={config.recovery_timeout}"
        )

        # 4. 模拟ML模块尝试优化配置
        print("4. 模拟ML模块优化...")
        ml_config = CircuitBreakerConfig(
            name="test_breaker",
            failure_threshold=2,  # ML建议更激进的设置
            recovery_timeout=15.0,
        )

        # ML模块使用use_override=False，直接修改主配置
        success = self.controller.set_circuit_breaker_config(
            "test_breaker", ml_config, use_override=False
        )
        self.assertTrue(success)
        print("✓ ML模块配置设置成功")

        # 5. 验证手动覆盖仍然有效
        print("5. 验证手动覆盖仍然有效...")
        config = self.controller.get_circuit_breaker_config("test_breaker")
        self.assertEqual(config.failure_threshold, 5)  # 仍然使用覆盖值
        self.assertEqual(config.recovery_timeout, 60.0)  # 仍然使用覆盖值
        print(
            f"✓ 手动覆盖仍然有效: failure_threshold={config.failure_threshold}, recovery_timeout={config.recovery_timeout}"
        )

    def test_override_ttl_expiration(self):
        """测试配置覆盖的TTL过期机制"""
        print("\n=== 测试配置覆盖TTL过期机制 ===")

        # 1. 设置短期覆盖（1秒TTL）
        print("1. 设置短期覆盖...")
        success = self.controller._set_config_override(
            "circuit_breaker",
            "test_breaker",
            {"failure_threshold": 10, "recovery_timeout": 120.0},
            ttl_seconds=1,  # 1秒后过期
        )
        self.assertTrue(success)
        print("✓ 短期覆盖设置成功")

        # 2. 验证覆盖立即生效
        print("2. 验证覆盖立即生效...")
        config = self.controller.get_circuit_breaker_config("test_breaker")
        self.assertEqual(config.failure_threshold, 10)
        print(f"✓ 覆盖立即生效: failure_threshold={config.failure_threshold}")

        # 3. 等待过期
        print("3. 等待覆盖过期...")
        time.sleep(2)  # 等待超过TTL时间

        # 4. 验证过期后自动清除
        print("4. 验证过期后自动清除...")
        config = self.controller.get_circuit_breaker_config("test_breaker")
        self.assertEqual(config.failure_threshold, 5)  # 回到默认值
        print(f"✓ 过期后自动清除: failure_threshold={config.failure_threshold}")

        # 5. 验证覆盖列表为空
        overrides = self.controller.get_config_overrides()
        self.assertEqual(len(overrides), 0)
        print("✓ 覆盖列表已清空")

    def test_ml_optimization_respects_overrides(self):
        """测试ML优化尊重配置覆盖"""
        print("\n=== 测试ML优化尊重配置覆盖 ===")

        # 1. 设置手动配置覆盖
        print("1. 设置手动配置覆盖...")
        success = set_rate_limit_config(
            name="test_limiter", use_override=True, max_requests=100, time_window=60.0
        )
        self.assertTrue(success)
        print("✓ 手动配置覆盖设置成功")

        # 2. 模拟ML模块优化
        print("2. 模拟ML模块优化...")
        # 创建性能指标
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            cache_hit_rate=0.8,
            response_time=50.0,
            memory_usage=0.6,
            cpu_usage=0.7,
            error_rate=0.02,
            qps=100.0,
            lock_timeout_rate=0.01,
            connection_pool_usage=0.5,
        )

        # 设置ML优化策略
        self.ml_monitor.set_optimization_strategy(OptimizationStrategy.AGGRESSIVE)

        # 3. 注册配置更新回调
        print("3. 注册配置更新回调...")
        applied_configs = []

        def config_callback(plan):
            applied_configs.append(plan)
            print(f"ML优化配置应用: {plan}")

        self.ml_monitor.register_config_update_callback(config_callback)

        # 4. 触发ML优化
        print("4. 触发ML优化...")
        self.ml_monitor.feed_metrics(metrics)

        # 5. 验证ML优化被限制
        print("5. 验证ML优化被限制...")
        # 等待一下让ML处理
        time.sleep(1)

        # 检查是否有配置被应用
        if applied_configs:
            print(f"应用的ML配置: {applied_configs}")
            # 验证应用的配置不包含被覆盖的参数
            for config in applied_configs:
                self.assertNotIn("max_requests", config)
                self.assertNotIn("time_window", config)
        else:
            print("✓ ML优化被完全阻止")

        # 6. 验证手动覆盖仍然有效
        print("6. 验证手动覆盖仍然有效...")
        config = self.controller.get_rate_limit_config("test_limiter")
        self.assertEqual(config.max_requests, 100)  # 仍然使用覆盖值
        self.assertEqual(config.time_window, 60.0)  # 仍然使用覆盖值
        print(
            f"✓ 手动覆盖仍然有效: max_requests={config.max_requests}, time_window={config.time_window}"
        )

    def test_clear_override_functionality(self):
        """测试清除配置覆盖功能"""
        print("\n=== 测试清除配置覆盖功能 ===")

        # 1. 设置配置覆盖
        print("1. 设置配置覆盖...")
        success = set_degradation_config(
            name="test_degradation", use_override=True, enabled=True, timeout=15.0
        )
        self.assertTrue(success)
        print("✓ 配置覆盖设置成功")

        # 2. 验证覆盖存在
        print("2. 验证覆盖存在...")
        overrides = self.controller.get_config_overrides()
        self.assertIn("degradation:test_degradation", overrides)
        print(f"✓ 覆盖存在: {list(overrides.keys())}")

        # 3. 清除特定覆盖
        print("3. 清除特定覆盖...")
        success = self.controller._clear_config_override(
            "degradation", "test_degradation"
        )
        self.assertTrue(success)
        print("✓ 特定覆盖清除成功")

        # 4. 验证覆盖已清除
        print("4. 验证覆盖已清除...")
        overrides = self.controller.get_config_overrides()
        self.assertNotIn("degradation:test_degradation", overrides)
        print("✓ 覆盖已清除")

        # 5. 验证配置回到默认值
        print("5. 验证配置回到默认值...")
        config = self.controller.get_degradation_config("test_degradation")
        self.assertFalse(config.enabled)  # 回到默认值
        self.assertEqual(config.timeout, 5.0)  # 回到默认值
        print(f"✓ 配置回到默认值: enabled={config.enabled}, timeout={config.timeout}")

    def test_multiple_config_types(self):
        """测试多种配置类型的覆盖机制"""
        print("\n=== 测试多种配置类型的覆盖机制 ===")

        # 1. 设置多种配置覆盖
        print("1. 设置多种配置覆盖...")

        # 熔断器覆盖
        set_circuit_breaker_config("breaker1", use_override=True, failure_threshold=8)
        # 限流器覆盖
        set_rate_limit_config("limiter1", use_override=True, max_requests=200)
        # 降级覆盖
        set_degradation_config("degradation1", use_override=True, enabled=True)
        # 舱壁隔离覆盖
        success = self.controller.set_bulkhead_config(
            "bulkhead1",
            self.controller.get_bulkhead_config("bulkhead1"),
            use_override=True,
        )

        print("✓ 多种配置覆盖设置成功")

        # 2. 验证所有覆盖都存在
        print("2. 验证所有覆盖都存在...")
        overrides = self.controller.get_config_overrides()
        expected_keys = [
            "circuit_breaker:breaker1",
            "rate_limiter:limiter1",
            "degradation:degradation1",
            "bulkhead:bulkhead1",
        ]

        for key in expected_keys:
            self.assertIn(key, overrides)
        print(f"✓ 所有覆盖都存在: {list(overrides.keys())}")

        # 3. 验证配置优先级
        print("3. 验证配置优先级...")

        # 熔断器配置
        cb_config = self.controller.get_circuit_breaker_config("breaker1")
        self.assertEqual(cb_config.failure_threshold, 8)

        # 限流器配置
        rl_config = self.controller.get_rate_limit_config("limiter1")
        self.assertEqual(rl_config.max_requests, 200)

        # 降级配置
        dg_config = self.controller.get_degradation_config("degradation1")
        self.assertTrue(dg_config.enabled)

        print("✓ 所有配置优先级正确")

        # 4. 清除过期覆盖
        print("4. 清除过期覆盖...")
        expired_count = self.controller.clear_expired_overrides()
        print(f"✓ 清除过期覆盖: {expired_count} 个")


def run_manual_tests():
    """运行手动测试"""
    print("=" * 60)
    print("配置优先级与租期机制 - 手动测试")
    print("=" * 60)

    # 创建测试实例
    test = TestConfigPriorityLeasing()

    try:
        # 运行所有测试
        test.setUp()

        test.test_manual_override_priority()
        test.test_override_ttl_expiration()
        test.test_ml_optimization_respects_overrides()
        test.test_clear_override_functionality()
        test.test_multiple_config_types()

        test.tearDown()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！配置优先级与租期机制工作正常")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 运行单元测试
    unittest.main(argv=[""], exit=False, verbosity=2)

    # 运行手动测试
    run_manual_tests()
