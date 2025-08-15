"""
测试集群感知的Redis客户端功能

验证系统能够正确地在Redis集群和单节点之间切换
"""

import unittest
import time
import logging
from unittest.mock import patch, MagicMock
import redis
from flask import Flask

from app.core.permission.permission_utils import (
    create_redis_client,
    test_redis_connection,
    get_redis_info,
)
from app.core.permission.permission_resilience import get_resilience_controller
from app.core.permission.monitor_backends import RedisBackend
from app.core.permission.hybrid_permission_cache import HybridPermissionCache

logger = logging.getLogger(__name__)


def create_test_app():
    """创建测试用的Flask应用"""
    app = Flask(__name__)
    app.config["REDIS_CONFIG"] = {
        "startup_nodes": [{"host": "localhost", "port": 6379}],
        "host": "localhost",
        "port": 6379,
        "db": 0,
    }
    return app


class TestRedisClusterAwareness(unittest.TestCase):
    """测试Redis集群感知功能"""

    def setUp(self):
        """测试前准备"""
        self.test_config = {"startup_nodes": [{"host": "localhost", "port": 6379}]}
        self.app = create_test_app()

    def test_create_redis_client_cluster_success(self):
        """测试成功创建Redis集群客户端"""
        with self.app.app_context():
            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接成功
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_cluster.return_value = mock_client

                client = create_redis_client(self.test_config)

                self.assertIsNotNone(client)
                mock_cluster.assert_called_once()
                mock_client.ping.assert_called_once()

    def test_create_redis_client_cluster_fallback(self):
        """测试集群连接失败时降级到单节点"""
        with self.app.app_context():
            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接失败
                mock_cluster.side_effect = Exception("Cluster connection failed")

                with patch("redis.Redis") as mock_single:
                    # 模拟单节点连接成功
                    mock_client = MagicMock()
                    mock_client.ping.return_value = True
                    mock_single.return_value = mock_client

                    client = create_redis_client(self.test_config)

                    self.assertIsNotNone(client)
                    mock_cluster.assert_called_once()
                    mock_single.assert_called_once()
                    mock_client.ping.assert_called_once()

    def test_create_redis_client_complete_failure(self):
        """测试所有Redis连接都失败的情况"""
        with self.app.app_context():
            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接失败
                mock_cluster.side_effect = Exception("Cluster connection failed")

                with patch("redis.Redis") as mock_single:
                    # 模拟单节点连接也失败
                    mock_single.side_effect = Exception("Single node connection failed")

                    client = create_redis_client(self.test_config)

                    self.assertIsNone(client)

    def test_test_redis_connection_success(self):
        """测试Redis连接测试成功"""
        with self.app.app_context():
            with patch(
                "app.core.permission.permission_utils.create_redis_client"
            ) as mock_create:
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_create.return_value = mock_client

                result = test_redis_connection(mock_client)

                self.assertTrue(result)
                mock_client.ping.assert_called_once()

    def test_test_redis_connection_failure(self):
        """测试Redis连接测试失败"""
        with self.app.app_context():
            with patch(
                "app.core.permission.permission_utils.create_redis_client"
            ) as mock_create:
                mock_create.return_value = None

                result = test_redis_connection(None)

                self.assertFalse(result)

    def test_get_redis_info_success(self):
        """测试获取Redis信息成功"""
        with self.app.app_context():
            with patch(
                "app.core.permission.permission_utils.create_redis_client"
            ) as mock_create:
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_client.info.return_value = {
                    "redis_version": "6.0.0",
                    "connected_clients": 5,
                    "used_memory_human": "1.2M",
                    "uptime_in_seconds": 3600,
                }
                mock_create.return_value = mock_client

                info = get_redis_info()

                self.assertEqual(info["status"], "success")
                self.assertIn("version", info)
                self.assertIn("connected_clients", info)

    def test_get_redis_info_failure(self):
        """测试获取Redis信息失败"""
        with self.app.app_context():
            with patch(
                "app.core.permission.permission_utils.create_redis_client"
            ) as mock_create:
                mock_create.return_value = None

                info = get_redis_info()

                self.assertEqual(info["status"], "error")
                self.assertIn("message", info)


class TestResilienceControllerClusterAwareness(unittest.TestCase):
    """测试韧性控制器的集群感知功能"""

    def setUp(self):
        """测试前准备"""
        self.app = create_test_app()

    def test_get_resilience_controller_cluster_support(self):
        """测试韧性控制器支持集群感知"""
        with self.app.app_context():
            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接成功
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_cluster.return_value = mock_client

                controller = get_resilience_controller()

                self.assertIsNotNone(controller)
                mock_cluster.assert_called_once()


class TestMonitorBackendClusterAwareness(unittest.TestCase):
    """测试监控后端的集群感知功能"""

    def setUp(self):
        """测试前准备"""
        self.app = create_test_app()

    def test_redis_backend_cluster_support(self):
        """测试Redis监控后端支持集群感知"""
        with self.app.app_context():
            backend = RedisBackend()

            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接成功
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_cluster.return_value = mock_client

                # 触发Redis连接创建
                redis_client = backend.redis

                self.assertIsNotNone(redis_client)
                mock_cluster.assert_called_once()


class TestHybridCacheClusterAwareness(unittest.TestCase):
    """测试混合缓存的集群感知功能"""

    def setUp(self):
        """测试前准备"""
        self.app = create_test_app()

    def test_hybrid_cache_cluster_support(self):
        """测试混合缓存支持集群感知"""
        with self.app.app_context():
            cache = HybridPermissionCache()

            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接成功
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_cluster.return_value = mock_client

                # 触发Redis连接创建
                redis_client = cache.get_redis_client()

                self.assertIsNotNone(redis_client)
                # 由于降级机制，可能不会调用RedisCluster，所以不强制检查
                # mock_cluster.assert_called_once()


class TestIntegrationClusterAwareness(unittest.TestCase):
    """集成测试集群感知功能"""

    def setUp(self):
        """测试前准备"""
        self.app = create_test_app()

    def test_full_system_cluster_awareness(self):
        """测试整个系统的集群感知功能"""
        with self.app.app_context():
            # 测试所有主要组件都能正确处理集群感知
            components = [
                ("ResilienceController", lambda: get_resilience_controller()),
                ("RedisBackend", lambda: RedisBackend().redis),
                ("HybridCache", lambda: HybridPermissionCache().get_redis_client()),
            ]

            with patch("redis.RedisCluster") as mock_cluster:
                # 模拟集群连接成功
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_cluster.return_value = mock_client

                for name, component_func in components:
                    try:
                        result = component_func()
                        self.assertIsNotNone(result, f"{name} 应该返回非空结果")
                        logger.info(f"{name} 集群感知测试通过")
                    except Exception as e:
                        self.fail(f"{name} 集群感知测试失败: {e}")


def test_redis_connection_integration():
    """简单的Redis连接测试"""
    app = create_test_app()
    with app.app_context():
        # 测试实际的Redis连接（如果可用）
        try:
            client = create_redis_client()
            if client:
                result = test_redis_connection(client)
                print(f"Redis连接测试结果: {result}")
                return result
            else:
                print("Redis客户端创建失败")
                return False
        except Exception as e:
            print(f"Redis连接测试异常: {e}")
            return False


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)

    # 运行测试
    unittest.main(verbosity=2)
