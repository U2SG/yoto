import pytest
import time
from unittest.mock import patch, MagicMock
from app.core.distributed_cache import (
    ClusterNode,
    ConsistentHashRing,
    ClusterHealthMonitor,
    DistributedCacheCluster,
    get_distributed_cache,
    get_cluster_stats,
    distributed_get,
    distributed_set,
    distributed_delete,
)
from app.core.permissions import (
    get_distributed_cache_stats,
    distributed_cache_get,
    distributed_cache_set,
    distributed_cache_delete,
)


class TestClusterNode:
    """测试集群节点功能"""

    def setup_method(self):
        """设置测试环境"""
        self.node = ClusterNode("localhost", 6379, password=None, db=0)

    def test_node_initialization(self):
        """测试节点初始化"""
        assert self.node.host == "localhost"
        assert self.node.port == 6379
        assert self.node.is_healthy is True
        assert self.node.fail_count == 0
        assert self.node.success_count == 0

    def test_node_ping_success(self):
        """测试节点ping成功"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.ping.return_value = True

            result = self.node.ping()

            assert result is True
            assert self.node.is_healthy is True
            assert self.node.success_count == 1

    def test_node_ping_failure(self):
        """测试节点ping失败"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.ping.side_effect = Exception("Connection failed")

            result = self.node.ping()

            assert result is False
            assert self.node.is_healthy is False
            assert self.node.fail_count == 1

    def test_node_close(self):
        """测试节点连接关闭"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn

            # 获取连接
            self.node.get_connection()
            assert self.node.connection is not None

            # 关闭连接
            self.node.close()
            assert self.node.connection is None


class TestConsistentHashRing:
    """测试一致性哈希环"""

    def setup_method(self):
        """设置测试环境"""
        self.hash_ring = ConsistentHashRing(virtual_nodes=10)
        self.node1 = ClusterNode("localhost", 6379)
        self.node2 = ClusterNode("localhost", 6380)

    def test_add_node(self):
        """测试添加节点"""
        self.hash_ring.add_node(self.node1)

        assert len(self.hash_ring.nodes) == 1
        assert len(self.hash_ring.ring) == 10  # 虚拟节点数量
        assert len(self.hash_ring.sorted_keys) == 10

    def test_remove_node(self):
        """测试移除节点"""
        self.hash_ring.add_node(self.node1)
        self.hash_ring.add_node(self.node2)

        initial_ring_size = len(self.hash_ring.ring)
        initial_keys_size = len(self.hash_ring.sorted_keys)

        self.hash_ring.remove_node(self.node1)

        assert len(self.hash_ring.nodes) == 1
        assert len(self.hash_ring.ring) == initial_ring_size - 10
        assert len(self.hash_ring.sorted_keys) == initial_keys_size - 10

    def test_get_node(self):
        """测试获取节点"""
        self.hash_ring.add_node(self.node1)
        self.hash_ring.add_node(self.node2)

        # 测试不同键的节点分配
        node1 = self.hash_ring.get_node("key1")
        node2 = self.hash_ring.get_node("key2")

        assert node1 is not None
        assert node2 is not None
        assert isinstance(node1, ClusterNode)
        assert isinstance(node2, ClusterNode)

    def test_get_node_empty_ring(self):
        """测试空环获取节点"""
        node = self.hash_ring.get_node("key1")
        assert node is None

    def test_hash_consistency(self):
        """测试哈希一致性"""
        key = "test_key"
        hash1 = self.hash_ring._hash(key)
        hash2 = self.hash_ring._hash(key)

        assert hash1 == hash2
        assert isinstance(hash1, int)


class TestClusterHealthMonitor:
    """测试集群健康监控"""

    def setup_method(self):
        """设置测试环境"""
        self.monitor = ClusterHealthMonitor(check_interval=0.1)

    def test_monitor_initialization(self):
        """测试监控器初始化"""
        assert self.monitor.check_interval == 0.1
        assert self.monitor.monitoring is False
        assert self.monitor.cluster is None

    def test_start_stop_monitoring(self):
        """测试开始和停止监控"""
        mock_cluster = MagicMock()

        self.monitor.start_monitoring(mock_cluster)
        assert self.monitor.monitoring is True
        assert self.monitor.cluster == mock_cluster
        assert self.monitor.monitor_thread is not None

        self.monitor.stop_monitoring()
        assert self.monitor.monitoring is False


class TestDistributedCacheCluster:
    """测试分布式缓存集群"""

    def setup_method(self):
        """设置测试环境"""
        self.nodes = [
            {"host": "localhost", "port": 6379, "password": None, "db": 0},
            {"host": "localhost", "port": 6380, "password": None, "db": 0},
        ]
        self.cluster = DistributedCacheCluster(self.nodes)

    def test_cluster_initialization(self):
        """测试集群初始化"""
        assert len(self.cluster.nodes) == 2
        assert self.cluster.hash_ring is not None
        assert self.cluster.health_monitor is not None
        assert self.cluster.stats["total_operations"] == 0

    def test_add_remove_node(self):
        """测试添加和移除节点"""
        initial_count = len(self.cluster.nodes)

        # 添加节点
        new_node = {"host": "localhost", "port": 6381, "password": None, "db": 0}
        self.cluster.add_node(new_node)
        assert len(self.cluster.nodes) == initial_count + 1

        # 移除节点
        self.cluster.remove_node("localhost")
        assert len(self.cluster.nodes) == initial_count

    def test_get_operation_success(self):
        """测试获取操作成功"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.get.return_value = b"test_value"

            result = self.cluster.get("test_key")

            assert result == b"test_value"
            assert self.cluster.stats["total_operations"] == 1
            assert self.cluster.stats["successful_operations"] == 1

    def test_get_operation_failure(self):
        """测试获取操作失败"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.get.side_effect = Exception("Connection failed")

            result = self.cluster.get("test_key")

            assert result is None
            assert self.cluster.stats["total_operations"] == 1
            assert self.cluster.stats["failed_operations"] == 1

    def test_set_operation_success(self):
        """测试设置操作成功"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.setex.return_value = True

            result = self.cluster.set("test_key", b"test_value", 300)

            assert result is True
            assert self.cluster.stats["total_operations"] == 1
            assert self.cluster.stats["successful_operations"] == 1

    def test_delete_operation_success(self):
        """测试删除操作成功"""
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.delete.return_value = 1

            result = self.cluster.delete("test_key")

            assert result is True
            assert self.cluster.stats["total_operations"] == 1
            assert self.cluster.stats["successful_operations"] == 1

    def test_get_cluster_stats(self):
        """测试获取集群统计"""
        stats = self.cluster.get_cluster_stats()

        assert "total_nodes" in stats
        assert "healthy_nodes" in stats
        assert "unhealthy_nodes" in stats
        assert "health_rate" in stats
        assert "operation_stats" in stats
        assert "node_details" in stats
        assert isinstance(stats["node_details"], list)

    def test_close(self):
        """测试关闭集群"""
        self.cluster.close()
        # 验证所有节点连接都已关闭
        for node in self.cluster.hash_ring.get_nodes():
            assert node.connection is None


class TestDistributedCacheIntegration:
    """测试分布式缓存集成场景"""

    def setup_method(self):
        """设置测试环境"""
        self.nodes = [
            {"host": "localhost", "port": 6379, "password": None, "db": 0},
            {"host": "localhost", "port": 6380, "password": None, "db": 0},
        ]

    def test_public_functions(self):
        """测试公共函数"""
        # 测试获取集群统计
        stats = get_cluster_stats()
        assert isinstance(stats, dict)
        assert "total_nodes" in stats

        # 测试分布式缓存操作
        with patch("app.core.distributed_cache.distributed_get") as mock_get:
            mock_get.return_value = b"test_value"
            result = distributed_get("test_key")
            assert result == b"test_value"

        with patch("app.core.distributed_cache.distributed_set") as mock_set:
            mock_set.return_value = True
            result = distributed_set("test_key", b"test_value", 300)
            assert result is True

        with patch("app.core.distributed_cache.distributed_delete") as mock_delete:
            mock_delete.return_value = True
            result = distributed_delete("test_key")
            assert result is True

    def test_permissions_module_functions(self):
        """测试permissions模块函数"""
        # 测试获取分布式缓存统计
        stats = get_distributed_cache_stats()
        assert isinstance(stats, dict)
        assert "total_nodes" in stats

        # 测试分布式缓存操作
        with patch("app.core.permissions.distributed_get") as mock_get:
            mock_get.return_value = b"test_value"
            result = distributed_cache_get("test_key")
            assert result == b"test_value"

        with patch("app.core.permissions.distributed_set") as mock_set:
            mock_set.return_value = True
            result = distributed_cache_set("test_key", b"test_value", 300)
            assert result is True

        with patch("app.core.permissions.distributed_delete") as mock_delete:
            mock_delete.return_value = True
            result = distributed_cache_delete("test_key")
            assert result is True

    def test_fault_tolerance(self):
        """测试故障容错"""
        cluster = DistributedCacheCluster(self.nodes)

        # 模拟节点故障
        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.get.side_effect = Exception("Connection failed")

            # 应该尝试其他节点
            result = cluster.get("test_key")
            # 由于所有节点都失败，应该返回None
            assert result is None
            assert cluster.stats["failed_operations"] == 1

    def test_health_monitoring(self):
        """测试健康监控"""
        cluster = DistributedCacheCluster(self.nodes)

        # 检查健康状态
        cluster.check_health()

        # 验证统计信息
        stats = cluster.get_cluster_stats()
        assert "healthy_nodes" in stats
        assert "unhealthy_nodes" in stats

    def test_node_management(self):
        """测试节点管理"""
        cluster = DistributedCacheCluster()

        # 添加节点
        node_config = {"host": "localhost", "port": 6379, "password": None, "db": 0}
        cluster.add_node(node_config)
        assert len(cluster.nodes) == 1

        # 移除节点
        cluster.remove_node("localhost")
        assert len(cluster.nodes) == 0

    def test_comprehensive_scenario(self):
        """测试综合场景"""
        cluster = DistributedCacheCluster(self.nodes)

        with patch("redis.Redis") as mock_redis:
            mock_conn = MagicMock()
            mock_redis.return_value = mock_conn
            mock_conn.setex.return_value = True
            mock_conn.get.return_value = b"test_value"
            mock_conn.delete.return_value = 1

            # 设置数据
            result = cluster.set("test_key", b"test_value", 300)
            assert result is True

            # 获取数据
            result = cluster.get("test_key")
            assert result == b"test_value"

            # 删除数据
            result = cluster.delete("test_key")
            assert result is True

            # 检查统计
            stats = cluster.get_cluster_stats()
            assert stats["operation_stats"]["total_operations"] == 3
            assert stats["operation_stats"]["successful_operations"] == 3
