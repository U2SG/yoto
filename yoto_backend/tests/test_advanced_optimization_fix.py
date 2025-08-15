"""
测试高级优化模块的依赖注入修复

验证修复后的高级优化模块是否能够正常工作，不再有启动时错误
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# 导入需要测试的模块
from app.core.permission.advanced_optimization import (
    AdvancedOptimization,
    AdvancedDistributedOptimizer,
    OptimizedDistributedLock,
    get_advanced_optimizer,
)


class TestAdvancedOptimizationFix(unittest.TestCase):
    """测试高级优化模块修复"""

    def setUp(self):
        """设置测试环境"""
        # 创建Flask应用
        self.app = Flask(__name__)

        # 配置高级优化
        self.app.config["ADVANCED_OPTIMIZATION_CONFIG"] = {
            "connection_pool_size": 10,
            "lock_timeout": 2.0,
            "lock_retry_interval": 0.02,
            "lock_retry_count": 3,
            "batch_size": 100,
            "max_concurrent_batches": 5,
            "distributed_cache_ttl": 3600,
            "preload_enabled": False,
            "delayed_invalidation_delay": 300,
        }

        # 模拟Redis客户端
        self.mock_redis_client = Mock()
        self.mock_redis_client.ping.return_value = True

        # 模拟韧性扩展
        self.app.extensions["redis_client"] = self.mock_redis_client

    def test_advanced_optimization_initialization(self):
        """测试高级优化模块初始化"""
        # 创建高级优化扩展
        advanced_opt = AdvancedOptimization()

        # 初始化应用
        advanced_opt.init_app(self.app)

        # 验证扩展已正确初始化
        self.assertIn("advanced_optimization", self.app.extensions)
        self.assertIsNotNone(advanced_opt.optimizer)
        self.assertEqual(advanced_opt.optimizer.redis_client, self.mock_redis_client)

    def test_optimizer_dependency_injection(self):
        """测试优化器的依赖注入"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 验证依赖注入
        self.assertEqual(optimizer.redis_client, self.mock_redis_client)
        self.assertEqual(optimizer.config, config)
        self.assertIsNotNone(optimizer._stats)

    def test_lock_factory_method(self):
        """测试锁的工厂方法"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 使用工厂方法创建锁
        lock = optimizer.create_lock("test_lock", timeout=1.0)

        # 验证锁的依赖注入
        self.assertEqual(lock.optimizer, optimizer)
        self.assertEqual(lock.redis_client, self.mock_redis_client)
        self.assertEqual(lock.config, config)
        self.assertEqual(lock.lock_key, "lock:opt:test_lock")

    def test_lock_dependency_injection(self):
        """测试锁的依赖注入"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 直接创建锁（通过工厂方法）
        lock = OptimizedDistributedLock(optimizer, "test_lock", timeout=1.0)

        # 验证依赖注入
        self.assertEqual(lock.optimizer, optimizer)
        self.assertEqual(lock.redis_client, self.mock_redis_client)
        self.assertEqual(lock.config, config)

    def test_config_access_with_defaults(self):
        """测试配置访问的默认值处理"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 验证配置访问使用默认值
        self.assertEqual(optimizer.config.get("preload_enabled", False), False)
        self.assertEqual(optimizer.config.get("delayed_invalidation_delay", 300), 300)
        self.assertEqual(optimizer.config.get("batch_size", 100), 100)

    def test_get_advanced_optimizer(self):
        """测试获取高级优化器"""
        # 创建并初始化高级优化扩展
        advanced_opt = AdvancedOptimization()
        advanced_opt.init_app(self.app)

        # 在应用上下文中获取优化器
        with self.app.app_context():
            optimizer = get_advanced_optimizer()

            # 验证优化器
            self.assertIsNotNone(optimizer)
            self.assertIsInstance(optimizer, AdvancedDistributedOptimizer)
            self.assertEqual(optimizer.redis_client, self.mock_redis_client)

    def test_advanced_optimization_without_global_config(self):
        """测试没有全局配置的高级优化模块"""
        # 验证模块导入不会失败
        try:
            from app.core.permission.advanced_optimization import (
                AdvancedOptimization,
                AdvancedDistributedOptimizer,
                OptimizedDistributedLock,
            )

            # 如果没有抛出异常，说明修复成功
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"模块导入失败: {e}")

    def test_config_access_safety(self):
        """测试配置访问的安全性"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 测试安全的配置访问
        self.assertEqual(optimizer.config.get("non_existent_key", "default"), "default")
        self.assertEqual(optimizer.config.get("lock_timeout", 5.0), 2.0)

    def test_background_tasks_initialization(self):
        """测试后台任务初始化"""
        # 创建优化器实例
        config = self.app.config["ADVANCED_OPTIMIZATION_CONFIG"]
        optimizer = AdvancedDistributedOptimizer(config, self.mock_redis_client)

        # 验证后台任务相关属性
        self.assertIsNotNone(optimizer.batch_queue)
        self.assertIsNotNone(optimizer.permission_update_queue)
        self.assertIsNotNone(optimizer.stop_event)
        self.assertIsNotNone(optimizer.background_tasks)


class TestAdvancedOptimizationIntegration(unittest.TestCase):
    """测试高级优化模块集成"""

    def setUp(self):
        """设置测试环境"""
        self.app = Flask(__name__)
        self.app.config["ADVANCED_OPTIMIZATION_CONFIG"] = {
            "connection_pool_size": 10,
            "lock_timeout": 2.0,
            "lock_retry_interval": 0.02,
            "lock_retry_count": 3,
            "batch_size": 100,
            "max_concurrent_batches": 5,
            "distributed_cache_ttl": 3600,
            "preload_enabled": False,
            "delayed_invalidation_delay": 300,
        }

        # 模拟Redis客户端
        self.mock_redis_client = Mock()
        self.mock_redis_client.ping.return_value = True
        self.app.extensions["redis_client"] = self.mock_redis_client

    def test_full_integration(self):
        """测试完整集成"""
        # 创建并初始化高级优化扩展
        advanced_opt = AdvancedOptimization()
        advanced_opt.init_app(self.app)

        # 在应用上下文中获取优化器
        with self.app.app_context():
            optimizer = get_advanced_optimizer()

            # 创建锁
            lock = optimizer.create_lock("test_integration_lock")

            # 验证整个链条正常工作
            self.assertIsNotNone(optimizer)
            self.assertIsNotNone(lock)
            self.assertEqual(lock.optimizer, optimizer)
            self.assertEqual(lock.redis_client, self.mock_redis_client)


if __name__ == "__main__":
    unittest.main()
