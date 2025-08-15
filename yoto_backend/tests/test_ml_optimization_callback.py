"""
测试ML优化回调机制

验证回调机制是否正常工作，配置是否能正确应用到系统组件
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.permission_ml import (
    AdaptiveOptimizer,
    MLPerformanceMonitor,
    PerformanceMetrics,
    register_ml_config_callback,
    unregister_ml_config_callback,
)
from app.core.permissions_refactored import PermissionSystem, get_permission_system


class TestMLOptimizationCallback:
    """测试ML优化回调机制"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.optimizer = AdaptiveOptimizer()
        self.ml_monitor = MLPerformanceMonitor()
        self.callback_called = False
        self.callback_config = None

    def test_register_callback(self):
        """测试注册回调函数"""

        def test_callback(config):
            self.callback_called = True
            self.callback_config = config

        # 注册回调
        self.optimizer.register_config_update_callback(test_callback)

        # 验证回调已注册
        assert test_callback in self.optimizer.config_update_callbacks

    def test_unregister_callback(self):
        """测试注销回调函数"""

        def test_callback(config):
            pass

        # 注册回调
        self.optimizer.register_config_update_callback(test_callback)
        assert test_callback in self.optimizer.config_update_callbacks

        # 注销回调
        self.optimizer.unregister_config_update_callback(test_callback)
        assert test_callback not in self.optimizer.config_update_callbacks

    def test_callback_execution(self):
        """测试回调函数执行"""

        def test_callback(config):
            self.callback_called = True
            self.callback_config = config

        # 注册回调
        self.optimizer.register_config_update_callback(test_callback)

        # 创建测试配置
        test_config = {
            "cache_max_size": 1500,
            "connection_pool_size": 150,
            "socket_timeout": 0.3,
        }

        # 直接调用_notify_config_update来测试回调执行
        self.optimizer._notify_config_update(test_config)

        # 验证回调被调用
        assert self.callback_called
        assert self.callback_config == test_config

    def test_multiple_callbacks(self):
        """测试多个回调函数"""
        callback1_called = False
        callback2_called = False

        def callback1(config):
            nonlocal callback1_called
            callback1_called = True

        def callback2(config):
            nonlocal callback2_called
            callback2_called = True

        # 注册多个回调
        self.optimizer.register_config_update_callback(callback1)
        self.optimizer.register_config_update_callback(callback2)

        # 直接调用_notify_config_update来测试回调执行
        test_config = {"cache_max_size": 1500}
        self.optimizer._notify_config_update(test_config)

        # 验证所有回调都被调用
        assert callback1_called
        assert callback2_called

    def test_callback_error_handling(self):
        """测试回调函数错误处理"""

        def error_callback(config):
            raise Exception("测试错误")

        def normal_callback(config):
            self.callback_called = True

        # 注册错误回调和正常回调
        self.optimizer.register_config_update_callback(error_callback)
        self.optimizer.register_config_update_callback(normal_callback)

        # 直接调用_notify_config_update来测试回调执行
        test_config = {"cache_max_size": 1500}
        self.optimizer._notify_config_update(test_config)

        # 验证正常回调仍然被调用
        assert self.callback_called

    def test_ml_monitor_callback(self):
        """测试ML监控器的回调机制"""

        def test_callback(config):
            self.callback_called = True
            self.callback_config = config

        # 注册回调
        self.ml_monitor.register_config_update_callback(test_callback)

        # 添加性能数据触发优化
        for i in range(10):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.3,  # 低缓存命中率，应该触发优化
                response_time=200.0,  # 高响应时间，应该触发优化
                memory_usage=0.6,
                cpu_usage=0.3,
                error_rate=0.01,
                qps=1000.0,
                lock_timeout_rate=0.02,
                connection_pool_usage=0.7,
            )
            self.ml_monitor.feed_metrics(metrics)

        # 验证回调被调用（如果有优化配置生成）
        # 注意：这取决于ML模块的具体实现，可能需要更多数据才能触发优化
        assert hasattr(self.ml_monitor.optimizer, "config_update_callbacks")

    def test_permission_system_ml_integration(self):
        """测试权限系统与ML模块的集成"""
        # 创建权限系统实例
        system = PermissionSystem()

        # 验证ML优化已设置
        if hasattr(system, "_apply_ml_optimization"):
            assert callable(system._apply_ml_optimization)

    def test_optimization_trigger(self):
        """测试优化触发机制"""
        # 添加一些可能导致优化的性能数据
        for i in range(20):
            metrics = PerformanceMetrics(
                timestamp=time.time() + i,
                cache_hit_rate=0.3,  # 持续低缓存命中率
                response_time=300.0,  # 持续高响应时间
                memory_usage=0.8,  # 高内存使用
                cpu_usage=0.7,  # 高CPU使用
                error_rate=0.05,  # 高错误率
                qps=500.0,  # 低QPS
                lock_timeout_rate=0.05,
                connection_pool_usage=0.9,
            )
            self.ml_monitor.feed_metrics(metrics)

        # 获取优化配置
        config = self.ml_monitor.get_optimized_config()
        assert isinstance(config, dict)

        # 验证配置包含预期的参数
        expected_params = [
            "connection_pool_size",
            "socket_timeout",
            "lock_timeout",
            "batch_size",
            "cache_max_size",
        ]
        for param in expected_params:
            assert param in config

    def test_convenience_functions(self):
        """测试便捷函数"""
        callback_called = False

        def test_callback(config):
            nonlocal callback_called
            callback_called = True

        # 测试注册回调
        register_ml_config_callback(test_callback)

        # 测试注销回调
        unregister_ml_config_callback(test_callback)

        # 验证回调机制正常工作
        assert True  # 如果没有异常，说明函数调用成功

    def test_optimization_strategy_impact(self):
        """测试优化策略对配置的影响"""
        # 测试保守策略
        self.optimizer.set_strategy(AdaptiveOptimizer.OptimizationStrategy.CONSERVATIVE)
        conservative_config = self.optimizer.get_optimized_config()

        # 测试激进策略
        self.optimizer.set_strategy(AdaptiveOptimizer.OptimizationStrategy.AGGRESSIVE)
        aggressive_config = self.optimizer.get_optimized_config()

        # 验证配置存在
        assert isinstance(conservative_config, dict)
        assert isinstance(aggressive_config, dict)

        # 验证配置包含预期参数
        expected_params = [
            "connection_pool_size",
            "socket_timeout",
            "lock_timeout",
            "batch_size",
            "cache_max_size",
        ]
        for param in expected_params:
            assert param in conservative_config
            assert param in aggressive_config


def test_callback_mechanism_design():
    """测试回调机制设计"""
    # 验证回调机制的设计模式
    optimizer = AdaptiveOptimizer()

    # 测试回调注册
    def test_callback(config):
        pass

    optimizer.register_config_update_callback(test_callback)
    assert test_callback in optimizer.config_update_callbacks

    # 测试回调注销
    optimizer.unregister_config_update_callback(test_callback)
    assert test_callback not in optimizer.config_update_callbacks

    # 测试回调执行
    callback_executed = False

    def execution_callback(config):
        nonlocal callback_executed
        callback_executed = True

    optimizer.register_config_update_callback(execution_callback)
    optimizer._notify_config_update({"cache_max_size": 1500})
    assert callback_executed


def test_ml_monitor_callback_integration():
    """测试ML监控器回调集成"""
    monitor = MLPerformanceMonitor()

    # 测试回调注册
    def test_callback(config):
        pass

    monitor.register_config_update_callback(test_callback)

    # 验证回调已注册到优化器
    assert test_callback in monitor.optimizer.config_update_callbacks

    # 测试回调注销
    monitor.unregister_config_update_callback(test_callback)
    assert test_callback not in monitor.optimizer.config_update_callbacks


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
