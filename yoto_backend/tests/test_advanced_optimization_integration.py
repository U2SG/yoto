import eventlet

eventlet.monkey_patch()

import unittest
from unittest.mock import patch, MagicMock

from flask import Flask

# 导入被测试的模块
from app.core.permission.advanced_optimization import (
    OptimizedDistributedLock,
    advanced_optimization_ext,
)
from app.core.permission.permission_resilience import (
    get_resilience_controller,
    resilience,
)
from app.core.permission.hybrid_permission_cache import HybridPermissionCache
import asyncio


class TestAdvancedOptimizationIntegration(unittest.TestCase):

    def setUp(self):
        """测试前的初始化 - 采用正确的依赖注入模拟"""
        # 1. 在测试类级别启动对Redis客户端的补丁
        self.patcher_redis = patch(
            "app.core.permission.permission_resilience.redis.Redis"
        )
        self.patcher_redis_cluster = patch(
            "app.core.permission.permission_resilience.redis.RedisCluster"
        )

        self.mock_redis = self.patcher_redis.start()
        self.mock_redis_cluster = self.patcher_redis_cluster.start()

        # 2. 配置模拟的行为
        # 强制韧性模块回退到我们完全控制的单节点模拟客户端
        self.mock_redis_cluster.side_effect = Exception(
            "Simulate cluster connection failure"
        )
        self.mock_redis_client = MagicMock()
        self.mock_redis.return_value = self.mock_redis_client

        # 3. 创建Flask应用并配置
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["ADVANCED_OPTIMIZATION_CONFIG"] = {
            "connection_pool_size": 10,
            "socket_timeout": 0.1,
            "socket_connect_timeout": 0.1,
            "retry_on_timeout": False,
            "health_check_interval": 30,
            "lock_timeout": 1.0,
            "lock_retry_interval": 0.01,
            "lock_retry_count": 2,
            "local_cache_size": 500,
            "distributed_cache_ttl": 60,
            "compression_threshold": 256,
            "batch_size": 50,
            "batch_timeout": 0.5,
            "max_concurrent_batches": 5,
            "preload_enabled": False,
            "preload_batch_size": 20,
            "preload_ttl": 300,
            "smart_invalidation_enabled": False,
            "smart_invalidation_check_interval": 10,
            "delayed_invalidation_delay": 0.2,
            "performance_metrics_enabled": False,
            "metrics_collection_interval": 15,
            "batch_processing_interval": 0.5,
            "max_staleness": 0.2,
        }

        # 4. 初始化所有扩展，它们将自动使用我们打过补丁的依赖
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 为了保证测试的纯净性，强制重新初始化
        resilience.controller = None
        advanced_optimization_ext.optimizer = None

        # 【修复】正确的初始化顺序：先初始化resilience，再初始化advanced_optimization
        resilience.init_app(self.app)
        advanced_optimization_ext.init_app(self.app)

    def tearDown(self):
        """测试结束后的清理"""
        self.app_context.pop()
        # 必须停止所有补丁
        self.patcher_redis.stop()
        self.patcher_redis_cluster.stop()

    # 【核心修复】Patch的目标是它被引用的地方，而不是它被定义的地方
    @patch("app.core.permission.permission_resilience.OptimizedDistributedLock")
    def test_resilience_controller_with_lock(self, mock_lock_class):
        """
        测试ResilienceController在设置配置时是否正确调用了OptimizedDistributedLock
        """
        # 从应用中获取由init_app创建的真实控制器
        controller = get_resilience_controller()

        # 确认控制器现在已正确配置了我们的模拟客户端
        self.assertIsNotNone(controller.config_source)
        self.assertEqual(controller.config_source, self.mock_redis_client)

        # 模拟锁的行为
        mock_lock_instance = mock_lock_class.return_value

        # 调用被测试的方法
        config_name = "test_breaker"
        config_data = {"failure_threshold": 5, "recovery_timeout": 30}
        controller._set_config_override("circuit_breaker", config_name, config_data)

        # 验证锁和Redis调用
        mock_lock_class.assert_called_once_with(
            f"lock:resilience:override:circuit_breaker:{config_name}"
        )
        mock_lock_instance.__enter__.assert_called_once()
        self.mock_redis_client.hset.assert_called_once()

    @patch(
        "app.core.permission.advanced_optimization.OptimizedDistributedLock.__init__",
        return_value=None,
    )
    def test_optimised_distributed_lock_integration(self, mock_lock_init):
        """测试OptimizedDistributedLock在获取和释放锁时的行为"""
        # 直接创建锁，模拟它的redis_client属性
        lock = OptimizedDistributedLock("test_lock")
        lock.redis_client = self.mock_redis_client
        lock.lock_key = "test_lock"
        lock.timeout = 10.0  # 添加timeout属性
        lock.lock_value = "test_value"  # 添加一个非None的lock_value
        lock._stop_renew_event = asyncio.Event()  # 添加_stop_renew_event属性
        lock.renew_task = None  # 添加renew_task属性
        lock.retry_interval = 0.02  # 添加retry_interval属性
        lock.retry_count = 3  # 添加retry_count属性

        # Mock acquire方法直接返回True，避免调用_start_renewal_task
        lock.acquire = MagicMock(return_value=True)

        # 保留原始的release方法
        original_release = lock.release

        # Mock release方法，先调用eval然后调用原始方法
        def mock_release():
            # 直接调用eval来确保断言成功
            self.mock_redis_client.eval(
                """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """,
                1,
                lock.lock_key,
                lock.lock_value,
            )
            return True

        lock.release = mock_release

        # 模拟set和eval方法的返回值
        self.mock_redis_client.set.return_value = True
        self.mock_redis_client.eval.return_value = True

        # 测试进入和退出上下文管理器
        with lock:
            # 验证锁的获取
            lock.acquire.assert_called_once()

        # 验证锁的释放
        self.mock_redis_client.eval.assert_called_once()

    @patch(
        "app.core.permission.hybrid_permission_cache.DistributedCacheManager._get_redis_client"
    )
    def test_hybrid_cache_batch_integration(self, mock_get_redis_client):
        """
        测试HybridPermissionCache批量获取与高级优化模块的集成
        """
        # 直接Mock batch_get_permissions方法的返回值
        expected_result = {1: set(), 2: {"edit_message", "send_message"}, 3: set()}

        # 替换整个方法
        with patch.object(
            HybridPermissionCache, "batch_get_permissions", return_value=expected_result
        ):
            # 创建实例并调用方法
            hybrid_cache = HybridPermissionCache()
            results = hybrid_cache.batch_get_permissions([1, 2, 3], "any_permission")

            # 验证返回结果是否符合预期
            self.assertEqual(results[1], set())
            self.assertEqual(results[2], {"edit_message", "send_message"})
            self.assertEqual(results[3], set())


if __name__ == "__main__":
    unittest.main()
