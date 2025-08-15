import pytest
import time
from unittest.mock import patch, MagicMock
from app.core.cache_monitor import CacheMonitor
from app.core.permissions import (
    get_smart_batch_invalidation_analysis,
    execute_smart_batch_invalidation,
)


class TestSmartBatchInvalidation:
    """测试智能批量失效功能"""

    def setup_method(self):
        """设置测试环境"""
        self.monitor = CacheMonitor()
        self.monitor.reset()

    def test_get_smart_batch_invalidation_analysis_empty(self):
        """测试空操作时的批量失效分析"""
        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        assert analysis["batch_strategy"] == "none"
        assert analysis["optimal_batch_size"] == 10
        assert analysis["batch_interval"] == 5.0
        assert analysis["key_grouping"] == "none"
        assert analysis["priority_keys"] == []
        assert analysis["batch_efficiency_score"] == 0.0
        assert "暂无失效操作" in analysis["optimization_suggestions"][0]

    def test_get_smart_batch_invalidation_analysis_with_operations(self):
        """测试有操作时的批量失效分析"""
        # 添加一些失效操作
        for i in range(20):
            self.monitor.record_operation(
                "invalidate", "l1", True, cache_key=f"key_{i % 5}"
            )

        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        assert analysis["batch_strategy"] in [
            "time_based",
            "key_based",
            "frequency_based",
        ]
        assert analysis["optimal_batch_size"] > 0
        assert analysis["batch_interval"] > 0
        assert analysis["batch_efficiency_score"] >= 0.0
        assert isinstance(analysis["optimization_suggestions"], list)

    def test_get_smart_batch_invalidation_analysis_high_frequency(self):
        """测试高频失效模式"""
        # 添加高频失效操作，让某些键更频繁
        for i in range(50):
            if i % 2 == 0:  # 50% 的操作使用 key_0
                self.monitor.record_operation(
                    "invalidate", "l1", True, cache_key="key_0"
                )
            else:  # 50% 的操作使用其他键
                self.monitor.record_operation(
                    "invalidate", "l1", True, cache_key=f"key_{i % 3 + 1}"
                )

        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        assert analysis["optimal_batch_size"] >= 15
        assert len(analysis["priority_keys"]) > 0
        assert analysis["batch_efficiency_score"] < 1.0

    def test_execute_smart_batch_invalidation_empty(self):
        """测试空键列表的批量失效"""
        result = self.monitor.execute_smart_batch_invalidation([])

        assert result["success"] is True
        assert result["processed_keys"] == 0
        assert result["batch_count"] == 0
        assert result["execution_time"] == 0.0
        assert result["efficiency_score"] == 1.0

    def test_execute_smart_batch_invalidation_small(self):
        """测试小批量失效"""
        keys = [f"key_{i}" for i in range(15)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "small")

        assert result["success"] is True
        assert result["processed_keys"] == 15
        assert result["batch_count"] == 3  # 15 / 5 = 3
        assert result["execution_time"] > 0.0
        assert result["efficiency_score"] > 0.0

    def test_execute_smart_batch_invalidation_medium(self):
        """测试中等批量失效"""
        keys = [f"key_{i}" for i in range(25)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "medium")

        assert result["success"] is True
        assert result["processed_keys"] == 25
        assert result["batch_count"] == 3  # 25 / 10 = 3 (向上取整)
        assert result["avg_batch_size"] > 0.0

    def test_execute_smart_batch_invalidation_large(self):
        """测试大批量失效"""
        keys = [f"key_{i}" for i in range(50)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "large")

        assert result["success"] is True
        assert result["processed_keys"] == 50
        assert result["batch_count"] == 3  # 50 / 20 = 3 (向上取整)
        assert result["efficiency_score"] > 0.0

    def test_execute_smart_batch_invalidation_auto(self):
        """测试自动策略批量失效"""
        # 先添加一些操作来影响自动分析
        for i in range(10):
            self.monitor.record_operation(
                "invalidate", "l1", True, cache_key=f"key_{i % 3}"
            )

        keys = [f"key_{i}" for i in range(20)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "auto")

        assert result["success"] is True
        assert result["processed_keys"] == 20
        assert result["batch_count"] > 0
        assert result["efficiency_score"] > 0.0

    def test_batch_efficiency_calculation(self):
        """测试批量效率计算"""
        # 添加一些操作
        for i in range(30):
            self.monitor.record_operation(
                "invalidate", "l1", True, cache_key=f"key_{i % 5}"
            )

        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        assert 0.0 <= analysis["batch_efficiency_score"] <= 1.0
        assert analysis["optimal_batch_size"] > 0

    def test_priority_keys_identification(self):
        """测试优先级键识别"""
        # 添加一些高频键
        for i in range(20):
            self.monitor.record_operation("invalidate", "l1", True, cache_key="hot_key")
        for i in range(5):
            self.monitor.record_operation(
                "invalidate", "l1", True, cache_key=f"cold_key_{i}"
            )

        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        assert "hot_key" in analysis["priority_keys"]
        assert len(analysis["priority_keys"]) > 0

    def test_public_functions(self):
        """测试公共函数"""
        # 测试分析函数
        analysis = get_smart_batch_invalidation_analysis()
        assert isinstance(analysis, dict)
        assert "batch_strategy" in analysis

        # 测试执行函数
        keys = ["key1", "key2", "key3"]
        result = execute_smart_batch_invalidation(keys, "small")
        assert isinstance(result, dict)
        assert result["success"] is True


class TestSmartBatchInvalidationIntegration:
    """测试智能批量失效集成场景"""

    def setup_method(self):
        """设置测试环境"""
        self.monitor = CacheMonitor()
        self.monitor.reset()

    def test_smart_batch_invalidation_with_delayed_invalidation(self):
        """测试智能批量失效与延迟失效的集成"""
        # 添加延迟失效操作
        for i in range(10):
            self.monitor.add_delayed_invalidation(f"key_{i}", "l1", "test")

        # 获取延迟失效统计
        delayed_stats = self.monitor.get_delayed_invalidation_stats()
        assert delayed_stats["queue_size"] == 10

        # 获取批量失效分析
        batch_analysis = self.monitor.get_smart_batch_invalidation_analysis()
        assert isinstance(batch_analysis, dict)

    def test_smart_batch_invalidation_with_performance_analysis(self):
        """测试智能批量失效与性能分析的集成"""
        # 添加一些操作
        for i in range(15):
            self.monitor.record_operation(
                "invalidate", "l1", True, cache_key=f"key_{i % 3}"
            )

        # 获取性能分析
        perf_analysis = self.monitor.get_performance_analysis()
        assert isinstance(perf_analysis, dict)

        # 获取批量失效分析
        batch_analysis = self.monitor.get_smart_batch_invalidation_analysis()
        assert isinstance(batch_analysis, dict)

        # 执行批量失效
        keys = [f"key_{i}" for i in range(10)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "auto")
        assert result["success"] is True

    def test_smart_batch_invalidation_comprehensive(self):
        """测试智能批量失效的综合场景"""
        # 模拟复杂的失效模式
        for i in range(50):
            if i % 3 == 0:
                self.monitor.record_operation(
                    "invalidate", "l1", True, cache_key="hot_key"
                )
            else:
                self.monitor.record_operation(
                    "invalidate", "l1", True, cache_key=f"key_{i}"
                )

        # 获取分析结果
        analysis = self.monitor.get_smart_batch_invalidation_analysis()

        # 验证分析结果
        assert analysis["batch_strategy"] in [
            "time_based",
            "key_based",
            "frequency_based",
        ]
        assert analysis["optimal_batch_size"] > 0
        assert "hot_key" in analysis["priority_keys"]

        # 执行批量失效
        keys = ["hot_key"] + [f"key_{i}" for i in range(20)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "auto")

        assert result["success"] is True
        assert result["processed_keys"] == 21
        assert result["batch_count"] > 0
        assert result["efficiency_score"] > 0.0

    def test_smart_batch_invalidation_edge_cases(self):
        """测试智能批量失效的边界情况"""
        # 测试单个键
        result = self.monitor.execute_smart_batch_invalidation(["single_key"], "small")
        assert result["success"] is True
        assert result["processed_keys"] == 1
        assert result["batch_count"] == 1

        # 测试大量键
        keys = [f"key_{i}" for i in range(100)]
        result = self.monitor.execute_smart_batch_invalidation(keys, "large")
        assert result["success"] is True
        assert result["processed_keys"] == 100
        assert result["batch_count"] == 5  # 100 / 20 = 5

        # 测试无效策略
        result = self.monitor.execute_smart_batch_invalidation(
            ["key1", "key2"], "invalid_strategy"
        )
        assert result["success"] is True
        assert result["processed_keys"] == 2
