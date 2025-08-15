"""
缓存监控功能测试脚本
测试CacheMonitor类、装饰器、统计功能等。
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from app.core.cache_monitor import (
    CacheMonitor,
    monitored_cache,
    get_cache_hit_rate_stats,
    get_cache_performance_analysis,
    get_cache_recent_operations,
    reset_cache_monitoring,
    _cache_monitor,
)


class TestCacheMonitor:
    """测试CacheMonitor类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = CacheMonitor()

    def test_init(self):
        """测试初始化"""
        assert self.monitor.start_time > 0
        assert len(self.monitor.stats) == 0
        assert len(self.monitor.operation_history) == 0
        assert self.monitor.max_history == 1000

    def test_record_operation(self):
        """测试记录操作"""
        self.monitor.record_operation("get", "l1", True, 0.001)
        self.monitor.record_operation("get", "l1", False, 0.002)
        self.monitor.record_operation("set", "l2", True, 0.003)

        assert self.monitor.stats["get_l1_hit"] == 1
        assert self.monitor.stats["get_l1_miss"] == 1
        assert self.monitor.stats["set_l2_hit"] == 1
        assert len(self.monitor.operation_history) == 3

    def test_get_hit_rate_stats(self):
        """测试命中率统计"""
        # 记录一些操作
        self.monitor.record_operation("get", "l1", True, 0.001)  # L1命中
        self.monitor.record_operation("get", "l1", True, 0.002)  # L1命中
        self.monitor.record_operation("get", "l1", False, 0.003)  # L1未命中
        self.monitor.record_operation("get", "l2", True, 0.004)  # L2命中
        self.monitor.record_operation("get", "l2", False, 0.005)  # L2未命中
        self.monitor.record_operation("set", "l1", True, 0.006)  # 设置操作

        stats = self.monitor.get_hit_rate_stats()

        # 验证L1缓存统计
        assert stats["l1_cache"]["hits"] == 2
        assert stats["l1_cache"]["misses"] == 1
        assert stats["l1_cache"]["total"] == 3
        assert stats["l1_cache"]["hit_rate"] == 2 / 3
        assert stats["l1_cache"]["hit_rate_percentage"] == "66.67%"

        # 验证L2缓存统计
        assert stats["l2_cache"]["hits"] == 1
        assert stats["l2_cache"]["misses"] == 1
        assert stats["l2_cache"]["total"] == 2
        assert stats["l2_cache"]["hit_rate"] == 0.5
        assert stats["l2_cache"]["hit_rate_percentage"] == "50.00%"

        # 验证总体统计
        assert stats["overall"]["hits"] == 3
        assert stats["overall"]["total_requests"] == 5
        assert stats["overall"]["hit_rate"] == 0.6
        assert stats["overall"]["hit_rate_percentage"] == "60.00%"

        # 验证操作统计
        assert stats["operations"]["cache_writes"] == 1
        assert stats["operations"]["cache_invalidations"] == 0
        assert stats["operations"]["db_queries"] == 0

    def test_get_performance_analysis(self):
        """测试性能分析"""
        # 模拟低命中率情况
        self.monitor.record_operation("get", "l1", True, 0.001)  # 1次命中
        for _ in range(9):
            self.monitor.record_operation("get", "l1", False, 0.003)  # 9次未命中

        analysis = self.monitor.get_performance_analysis()

        assert analysis["performance_level"] == "poor"
        assert "L1缓存命中率过低" in analysis["bottlenecks"]
        assert "增加L1缓存大小或优化缓存策略" in analysis["recommendations"]

    def test_get_recent_operations(self):
        """测试获取最近操作"""
        # 记录多个操作
        for i in range(10):
            self.monitor.record_operation("get", "l1", True, 0.001)

        # 获取最近5个操作
        recent = self.monitor.get_recent_operations(5)
        assert len(recent) == 5

        # 验证操作格式
        for op in recent:
            assert "timestamp" in op
            assert "type" in op
            assert "level" in op
            assert "success" in op
            assert "duration" in op

    def test_reset(self):
        """测试重置功能"""
        # 记录一些操作
        self.monitor.record_operation("get", "l1", True, 0.001)
        self.monitor.record_operation("set", "l2", True, 0.002)

        # 验证有数据
        assert len(self.monitor.stats) > 0
        assert len(self.monitor.operation_history) > 0

        # 重置
        self.monitor.reset()

        # 验证已清空
        assert len(self.monitor.stats) == 0
        assert len(self.monitor.operation_history) == 0


class TestMonitoredCacheDecorator:
    """测试缓存监控装饰器"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 重置全局监控器
        reset_cache_monitoring()

    def test_monitored_cache_success(self):
        """测试装饰器成功情况"""

        @monitored_cache("l1")
        def test_get_function():
            return "test_data"

        result = test_get_function()
        assert result == "test_data"

        # 验证监控记录
        stats = get_cache_hit_rate_stats()
        assert stats["l1_cache"]["hits"] == 1
        assert stats["l1_cache"]["misses"] == 0

    def test_monitored_cache_failure(self):
        """测试装饰器失败情况"""

        @monitored_cache("l2")
        def test_get_function():
            raise Exception("Test error")

        with pytest.raises(Exception):
            test_get_function()

        # 验证监控记录
        stats = get_cache_hit_rate_stats()
        assert stats["l2_cache"]["hits"] == 0
        assert stats["l2_cache"]["misses"] == 1

    def test_monitored_cache_set_operation(self):
        """测试设置操作监控"""

        @monitored_cache("l1")
        def test_set_function():
            return None  # 模拟设置操作返回None

        test_set_function()

        # 验证监控记录 - 返回None被视为未命中，但应该记录为set操作
        stats = get_cache_hit_rate_stats()
        # 注意：set操作不会影响get的命中率统计，但会记录在operations中
        assert stats["l1_cache"]["hits"] == 0
        assert stats["l1_cache"]["misses"] == 0  # 没有get操作
        # 检查是否有set操作记录
        operations = get_cache_recent_operations(1)
        assert len(operations) == 1
        assert operations[0]["type"] == "set"
        assert operations[0]["level"] == "l1"


class TestCacheMonitorFunctions:
    """测试缓存监控函数"""

    def setup_method(self):
        """每个测试方法前的设置"""
        reset_cache_monitoring()

    def test_get_cache_hit_rate_stats(self):
        """测试获取缓存命中率统计"""
        # 记录一些操作
        _cache_monitor.record_operation("get", "l1", True, 0.001)
        _cache_monitor.record_operation("get", "l1", False, 0.002)
        _cache_monitor.record_operation("get", "l2", True, 0.003)

        stats = get_cache_hit_rate_stats()

        assert "l1_cache" in stats
        assert "l2_cache" in stats
        assert "overall" in stats
        assert "operations" in stats
        assert "uptime" in stats

        assert stats["l1_cache"]["hits"] == 1
        assert stats["l1_cache"]["misses"] == 1
        assert stats["l2_cache"]["hits"] == 1
        assert stats["l2_cache"]["misses"] == 0

    def test_get_cache_performance_analysis(self):
        """测试获取性能分析"""
        # 模拟正常性能 - 只记录L1操作，避免L2相关的瓶颈检查
        for i in range(10):
            _cache_monitor.record_operation("get", "l1", True, 0.001)

        analysis = get_cache_performance_analysis()

        assert "performance_level" in analysis
        assert "bottlenecks" in analysis
        assert "recommendations" in analysis

        assert analysis["performance_level"] == "excellent"
        assert len(analysis["bottlenecks"]) == 0

    def test_get_cache_recent_operations(self):
        """测试获取最近操作"""
        # 记录一些操作
        for i in range(5):
            _cache_monitor.record_operation("get", "l1", True, 0.001)

        operations = get_cache_recent_operations(3)

        assert len(operations) == 3
        for op in operations:
            assert "timestamp" in op
            assert "type" in op
            assert "level" in op
            assert "success" in op
            assert "duration" in op

    def test_reset_cache_monitoring(self):
        """测试重置缓存监控"""
        # 记录一些操作
        _cache_monitor.record_operation("get", "l1", True, 0.001)
        _cache_monitor.record_operation("set", "l2", True, 0.002)

        # 验证有数据
        stats = get_cache_hit_rate_stats()
        assert stats["l1_cache"]["hits"] > 0

        # 重置
        reset_cache_monitoring()

        # 验证已清空
        stats = get_cache_hit_rate_stats()
        assert stats["l1_cache"]["hits"] == 0
        assert stats["l1_cache"]["misses"] == 0


class TestCacheMonitorIntegration:
    """测试缓存监控集成"""

    def setup_method(self):
        """每个测试方法前的设置"""
        reset_cache_monitoring()

    def test_cache_monitor_with_permissions(self):
        """测试与权限系统的集成"""
        # 模拟权限缓存操作
        from app.core.cache_monitor import monitored_cache

        @monitored_cache("l1")
        def mock_set_permissions():
            return "success"

        @monitored_cache("l1")
        def mock_get_permissions():
            return "permissions_data"

        # 测试设置权限缓存
        mock_set_permissions()

        # 验证监控记录 - 检查操作历史而不是命中率
        operations = get_cache_recent_operations(1)
        assert len(operations) == 1
        assert operations[0]["type"] == "set"
        assert operations[0]["level"] == "l1"
        assert operations[0]["success"] == True  # 返回非None值被视为成功

        # 测试获取权限缓存
        mock_get_permissions()

        # 验证监控记录
        operations = get_cache_recent_operations(2)
        assert len(operations) == 2
        assert operations[1]["type"] == "get"
        assert operations[1]["level"] == "l1"
        assert operations[1]["success"] == True  # 返回非None值被视为成功

    def test_cache_monitor_performance_scenarios(self):
        """测试不同性能场景"""
        # 场景1：高命中率
        for i in range(100):
            _cache_monitor.record_operation("get", "l1", True, 0.001)

        analysis = get_cache_performance_analysis()
        assert analysis["performance_level"] == "excellent"

        # 重置
        reset_cache_monitoring()

        # 场景2：低命中率
        for i in range(10):
            _cache_monitor.record_operation("get", "l1", True, 0.001)
        for i in range(90):
            _cache_monitor.record_operation("get", "l1", False, 0.002)

        analysis = get_cache_performance_analysis()
        assert analysis["performance_level"] == "poor"
        assert len(analysis["bottlenecks"]) > 0


class TestCacheAutoTuneSuggestions:
    """测试智能缓存调优建议"""

    def setup_method(self):
        """每个测试方法前的设置"""
        reset_cache_monitoring()

    def test_get_cache_auto_tune_suggestions(self):
        """测试获取智能调优建议"""
        from app.core.cache_monitor import get_cache_auto_tune_suggestions

        # 模拟低命中率场景 - 10%命中率
        for i in range(10):
            _cache_monitor.record_operation("get", "l1", True, 0.001)
        for i in range(90):
            _cache_monitor.record_operation("get", "l1", False, 0.002)

        suggestions = get_cache_auto_tune_suggestions()

        assert "l1_cache" in suggestions
        assert "l2_cache" in suggestions
        assert "general" in suggestions
        assert "priority" in suggestions

        # 验证L1缓存建议 - 10%命中率应该触发high优先级
        assert "size_increase" in suggestions["l1_cache"]
        assert "ttl_optimization" in suggestions["l1_cache"]
        assert suggestions["priority"] == "high"

    def test_auto_tune_suggestions_integration(self):
        """测试调优建议与性能分析的集成"""
        # 模拟正常性能场景 - 100%命中率，但总请求数不够触发size_decrease
        for i in range(100):
            _cache_monitor.record_operation("get", "l1", True, 0.001)

        analysis = get_cache_performance_analysis()

        assert "auto_tune_suggestions" in analysis
        # 100%命中率但总请求数<1000，应该保持low优先级
        assert analysis["auto_tune_suggestions"]["priority"] == "low"

    def test_auto_tune_suggestions_from_permissions(self):
        """测试从permissions模块获取调优建议"""
        from app.core.permissions import get_cache_auto_tune_suggestions

        # 模拟中等性能场景 - 70%命中率
        for i in range(70):
            _cache_monitor.record_operation("get", "l1", True, 0.001)
        for i in range(30):
            _cache_monitor.record_operation("get", "l1", False, 0.002)

        suggestions = get_cache_auto_tune_suggestions()

        assert isinstance(suggestions, dict)
        assert "priority" in suggestions
        assert suggestions["priority"] in ["low", "medium", "high"]
        # 70%命中率应该触发medium优先级
        assert suggestions["priority"] == "medium"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
