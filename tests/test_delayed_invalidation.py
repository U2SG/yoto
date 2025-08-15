import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from app.core.cache_monitor import (
    CacheMonitor,
    add_delayed_invalidation,
    get_delayed_invalidation_stats,
)
from app.core.permissions import (
    add_delayed_invalidation as add_delayed_from_permissions,
    get_delayed_invalidation_stats as get_stats_from_permissions,
)


class TestDelayedInvalidation:
    """测试延迟失效机制功能"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = CacheMonitor()
        self.monitor.reset()

    def test_add_delayed_invalidation(self):
        """测试添加延迟失效操作"""
        # 添加延迟失效操作
        self.monitor.add_delayed_invalidation("test_key_1", "l1", "test_reason")
        self.monitor.add_delayed_invalidation("test_key_2", "l2", "update_reason")

        # 检查队列大小
        with self.monitor.invalidation_lock:
            assert len(self.monitor.delayed_invalidation_queue) == 2

        # 检查统计信息
        stats = self.monitor.get_delayed_invalidation_stats()
        assert stats["queue_size"] == 2
        assert stats["total_delayed"] == 2

    def test_delayed_invalidation_queue_operations(self):
        """测试延迟失效队列操作"""
        # 添加多个失效操作
        for i in range(5):
            self.monitor.add_delayed_invalidation(f"key_{i}", "l1", f"reason_{i}")

        # 检查队列内容
        with self.monitor.invalidation_lock:
            queue = list(self.monitor.delayed_invalidation_queue)
            assert len(queue) == 5

            # 检查第一个操作
            first_op = queue[0]
            assert first_op["cache_key"] == "key_0"
            assert first_op["cache_level"] == "l1"
            assert first_op["reason"] == "reason_0"
            assert "timestamp" in first_op

    def test_batch_size_limit(self):
        """测试批量大小限制"""
        # 添加超过批量大小的操作
        for i in range(15):  # 超过默认批量大小10
            self.monitor.add_delayed_invalidation(f"key_{i}", "l1")

        # 检查队列大小不超过限制
        with self.monitor.invalidation_lock:
            assert len(self.monitor.delayed_invalidation_queue) <= 1000  # maxlen

    def test_get_delayed_invalidation_stats(self):
        """测试获取延迟失效统计"""
        # 添加一些操作
        for i in range(3):
            self.monitor.add_delayed_invalidation(f"key_{i}", "l1")

        stats = self.monitor.get_delayed_invalidation_stats()

        assert "queue_size" in stats
        assert "batch_size" in stats
        assert "delay_seconds" in stats
        assert "total_delayed" in stats
        assert "total_batches" in stats
        assert "total_batch_operations" in stats
        assert "avg_batch_size" in stats

        assert stats["queue_size"] == 3
        assert stats["batch_size"] == 10
        assert stats["delay_seconds"] == 5.0
        assert stats["total_delayed"] == 3

    def test_public_functions(self):
        """测试公共接口函数"""
        # 测试add_delayed_invalidation函数
        add_delayed_invalidation("public_key", "l2", "public_reason")

        # 测试get_delayed_invalidation_stats函数
        stats = get_delayed_invalidation_stats()
        assert isinstance(stats, dict)
        assert "queue_size" in stats

    def test_permissions_module_functions(self):
        """测试从permissions模块调用函数"""
        # 测试从permissions模块添加延迟失效
        add_delayed_from_permissions("perm_key", "l1", "perm_reason")

        # 测试从permissions模块获取统计
        stats = get_stats_from_permissions()
        assert isinstance(stats, dict)
        assert "queue_size" in stats

    def test_thread_safety(self):
        """测试线程安全性"""
        results = []

        def add_operations():
            for i in range(10):
                self.monitor.add_delayed_invalidation(f"thread_key_{i}", "l1")
                time.sleep(0.01)

        # 启动多个线程同时添加操作
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_operations)
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 检查统计信息
        stats = self.monitor.get_delayed_invalidation_stats()
        assert stats["total_delayed"] == 30  # 3个线程 * 10个操作

    def test_reset_functionality(self):
        """测试重置功能"""
        # 添加一些操作
        for i in range(5):
            self.monitor.add_delayed_invalidation(f"reset_key_{i}", "l1")

        # 重置监控器
        self.monitor.reset()

        # 检查队列是否清空
        with self.monitor.invalidation_lock:
            assert len(self.monitor.delayed_invalidation_queue) == 0

        # 检查统计是否重置
        stats = self.monitor.get_delayed_invalidation_stats()
        assert stats["queue_size"] == 0
        assert stats["total_delayed"] == 0


class TestDelayedInvalidationIntegration:
    """测试延迟失效机制集成功能"""

    def test_delayed_invalidation_with_monitoring(self):
        """测试延迟失效与监控的集成"""
        monitor = CacheMonitor()
        monitor.reset()

        # 添加延迟失效操作
        for i in range(8):
            monitor.add_delayed_invalidation(f"int_key_{i}", "l1", f"int_reason_{i}")

        # 获取统计信息
        delayed_stats = monitor.get_delayed_invalidation_stats()
        invalidation_analysis = monitor.get_invalidation_strategy_analysis()

        # 验证统计信息
        assert delayed_stats["queue_size"] == 8
        assert delayed_stats["total_delayed"] == 8

        # 验证失效策略分析
        assert invalidation_analysis["current_strategy"] == "standard"

    def test_delayed_invalidation_edge_cases(self):
        """测试延迟失效的边界情况"""
        monitor = CacheMonitor()
        monitor.reset()

        # 测试空队列
        stats = monitor.get_delayed_invalidation_stats()
        assert stats["queue_size"] == 0
        assert stats["total_delayed"] == 0

        # 测试大量操作
        for i in range(100):
            monitor.add_delayed_invalidation(f"edge_key_{i}", "l1")

        stats = monitor.get_delayed_invalidation_stats()
        assert stats["queue_size"] <= 1000  # 不超过maxlen
        assert stats["total_delayed"] == 100

    def test_delayed_invalidation_parameters(self):
        """测试延迟失效参数"""
        monitor = CacheMonitor()
        monitor.reset()

        # 测试不同缓存级别
        monitor.add_delayed_invalidation("l1_key", "l1", "l1_reason")
        monitor.add_delayed_invalidation("l2_key", "l2", "l2_reason")

        with monitor.invalidation_lock:
            queue = list(monitor.delayed_invalidation_queue)
            assert len(queue) == 2

            l1_op = queue[0]
            l2_op = queue[1]

            assert l1_op["cache_level"] == "l1"
            assert l2_op["cache_level"] == "l2"
            assert l1_op["reason"] == "l1_reason"
            assert l2_op["reason"] == "l2_reason"
