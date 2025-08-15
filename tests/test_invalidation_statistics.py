import pytest
import time
from unittest.mock import patch, MagicMock
from app.core.cache_monitor import CacheMonitor, get_invalidation_statistics
from app.core.permissions import (
    get_invalidation_statistics as get_stats_from_permissions,
)


class TestInvalidationStatistics:
    """测试失效统计监控功能"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = CacheMonitor()
        self.monitor.reset()

    def test_get_invalidation_statistics_empty(self):
        """测试空操作历史的失效统计"""
        stats = self.monitor.get_invalidation_statistics()

        assert "total_invalidations" in stats
        assert "total_sets" in stats
        assert "total_gets" in stats
        assert "invalidation_ratio" in stats
        assert "set_invalidation_ratio" in stats
        assert "avg_invalidation_delay" in stats
        assert "batch_efficiency" in stats
        assert "invalidation_patterns" in stats
        assert "performance_impact" in stats
        assert "optimization_suggestions" in stats

        assert stats["total_invalidations"] == 0
        assert stats["total_sets"] == 0
        assert stats["total_gets"] == 0
        assert stats["invalidation_ratio"] == 0.0
        assert stats["batch_efficiency"] == 0.0

    def test_get_invalidation_statistics_with_operations(self):
        """测试有操作历史的失效统计"""
        # 添加一些操作
        for i in range(10):
            self.monitor.record_operation("get", "l1", True)
            self.monitor.record_operation("set", "l1", True)
            self.monitor.record_operation("invalidate", "l1", True)

        stats = self.monitor.get_invalidation_statistics()

        assert stats["total_invalidations"] == 10
        assert stats["total_sets"] == 10
        assert stats["total_gets"] == 10
        assert stats["invalidation_ratio"] == 1 / 3  # 10/30
        assert stats["set_invalidation_ratio"] == 1.0  # 10/10

    def test_invalidation_patterns_analysis(self):
        """测试失效模式分析"""
        # 添加一些失效操作
        for i in range(5):
            self.monitor.record_operation("invalidate", "l1", True)

        stats = self.monitor.get_invalidation_statistics()
        patterns = stats["invalidation_patterns"]

        assert "frequency" in patterns
        assert "distribution" in patterns
        assert "hot_keys" in patterns
        assert "cold_keys" in patterns
        assert "avg_frequency" in patterns
        assert "total_unique_keys" in patterns

    def test_performance_impact_analysis(self):
        """测试性能影响分析"""
        # 添加一些操作
        for i in range(20):
            self.monitor.record_operation("get", "l1", True)
            self.monitor.record_operation("invalidate", "l1", True)

        stats = self.monitor.get_invalidation_statistics()
        performance = stats["performance_impact"]

        assert "impact_level" in performance
        assert "hit_rate_impact" in performance
        assert "latency_impact" in performance
        assert "throughput_impact" in performance
        assert "total_impact" in performance

        assert performance["impact_level"] in ["low", "medium", "high"]
        assert performance["total_impact"] >= 0.0

    def test_optimization_suggestions(self):
        """测试优化建议生成"""
        # 添加高失效比例的操作
        for i in range(15):
            self.monitor.record_operation("get", "l1", True)
            self.monitor.record_operation("invalidate", "l1", True)

        stats = self.monitor.get_invalidation_statistics()
        suggestions = stats["optimization_suggestions"]

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

        # 检查是否包含相关建议
        suggestion_text = " ".join(suggestions)
        assert any(keyword in suggestion_text for keyword in ["失效", "优化", "建议"])

    def test_batch_efficiency_calculation(self):
        """测试批量效率计算"""
        # 模拟批量处理
        self.monitor.stats["batch_invalidations"] = 5
        self.monitor.stats["total_batch_operations"] = 25

        stats = self.monitor.get_invalidation_statistics()

        assert stats["batch_efficiency"] == 5.0  # 25/5

    def test_public_functions(self):
        """测试公共接口函数"""
        # 添加一些操作
        for i in range(5):
            self.monitor.record_operation("invalidate", "l1", True)

        # 测试get_invalidation_statistics函数
        stats = get_invalidation_statistics()
        assert isinstance(stats, dict)
        assert "total_invalidations" in stats

    def test_permissions_module_functions(self):
        """测试从permissions模块调用函数"""
        # 添加一些操作
        for i in range(3):
            self.monitor.record_operation("invalidate", "l1", True)

        # 测试从permissions模块获取统计
        stats = get_stats_from_permissions()
        assert isinstance(stats, dict)
        assert "total_invalidations" in stats

    def test_invalidation_statistics_edge_cases(self):
        """测试失效统计的边界情况"""
        # 测试只有失效操作的情况
        for i in range(10):
            self.monitor.record_operation("invalidate", "l1", True)

        stats = self.monitor.get_invalidation_statistics()

        assert stats["total_invalidations"] == 10
        assert stats["total_sets"] == 0
        assert stats["total_gets"] == 0
        assert stats["invalidation_ratio"] == 1.0  # 全部都是失效操作
        assert stats["set_invalidation_ratio"] == float("inf")  # 0个set操作

    def test_invalidation_statistics_with_different_levels(self):
        """测试不同缓存级别的失效统计"""
        # 添加不同级别的操作
        self.monitor.record_operation("invalidate", "l1", True)
        self.monitor.record_operation("invalidate", "l2", True)
        self.monitor.record_operation("set", "l1", True)
        self.monitor.record_operation("get", "l2", True)

        stats = self.monitor.get_invalidation_statistics()

        assert stats["total_invalidations"] == 2
        assert stats["total_sets"] == 1
        assert stats["total_gets"] == 1


class TestInvalidationStatisticsIntegration:
    """测试失效统计监控集成功能"""

    def test_invalidation_statistics_with_delayed_invalidation(self):
        """测试失效统计与延迟失效的集成"""
        monitor = CacheMonitor()
        monitor.reset()

        # 添加延迟失效操作
        for i in range(8):
            monitor.add_delayed_invalidation(f"delayed_key_{i}", "l1", f"reason_{i}")

        # 添加一些普通操作
        for i in range(5):
            monitor.record_operation("invalidate", "l1", True)

        # 获取统计信息
        invalidation_stats = monitor.get_invalidation_statistics()
        delayed_stats = monitor.get_delayed_invalidation_stats()

        # 验证统计信息
        assert invalidation_stats["total_invalidations"] == 5
        assert delayed_stats["queue_size"] == 8
        assert delayed_stats["total_delayed"] == 8

    def test_invalidation_statistics_with_performance_analysis(self):
        """测试失效统计与性能分析的集成"""
        monitor = CacheMonitor()
        monitor.reset()

        # 添加一些操作
        for i in range(10):
            monitor.record_operation("get", "l1", True)
            monitor.record_operation("invalidate", "l1", True)

        # 获取各种分析
        invalidation_stats = monitor.get_invalidation_statistics()
        performance_analysis = monitor.get_performance_analysis()
        invalidation_analysis = monitor.get_invalidation_strategy_analysis()

        # 验证分析结果的一致性
        assert invalidation_stats["total_invalidations"] == 10
        assert invalidation_stats["invalidation_ratio"] == 0.5  # 10/20
        assert invalidation_analysis["invalidation_frequency"] == "high"

    def test_invalidation_statistics_comprehensive(self):
        """测试失效统计的综合分析"""
        monitor = CacheMonitor()
        monitor.reset()

        # 模拟复杂的操作场景
        for i in range(20):
            monitor.record_operation("get", "l1", True)

        for i in range(8):
            monitor.record_operation("set", "l1", True)
            monitor.record_operation("invalidate", "l1", True)

        # 添加延迟失效
        for i in range(5):
            monitor.add_delayed_invalidation(f"comp_key_{i}", "l1")

        # 获取综合统计
        stats = monitor.get_invalidation_statistics()

        # 验证统计结果
        assert stats["total_invalidations"] == 8
        assert stats["total_sets"] == 8
        assert stats["total_gets"] == 20
        assert stats["invalidation_ratio"] == 8 / 36  # 8/(20+8+8)
        assert stats["set_invalidation_ratio"] == 1.0  # 8/8

        # 验证模式分析
        patterns = stats["invalidation_patterns"]
        assert patterns["frequency"] in ["low", "medium", "high"]

        # 验证性能影响
        performance = stats["performance_impact"]
        assert performance["impact_level"] in ["low", "medium", "high"]

        # 验证优化建议
        suggestions = stats["optimization_suggestions"]
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 0
