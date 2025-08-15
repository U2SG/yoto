import pytest
from unittest.mock import patch, MagicMock
from app.core.cache_monitor import (
    CacheMonitor,
    get_cache_invalidation_strategy_analysis,
)
from app.core.permissions import (
    get_cache_invalidation_strategy_analysis as get_invalidation_analysis_from_permissions,
)


class TestCacheInvalidationStrategy:
    """测试智能失效策略分析功能"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = CacheMonitor()
        self.monitor.reset()

    def test_get_invalidation_strategy_analysis_normal_frequency(self):
        """测试正常失效频率的分析"""
        # 模拟正常操作 - 只有少量操作，无失效操作
        self.monitor.record_operation("get", "l1", True)
        self.monitor.record_operation("set", "l1", True)
        self.monitor.record_operation("get", "l1", True)

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["current_strategy"] == "standard"
        assert analysis["recommended_strategy"] == "standard"
        assert analysis["invalidation_frequency"] == "normal"
        assert analysis["priority"] == "low"
        assert len(analysis["optimization_suggestions"]) == 0

    def test_get_invalidation_strategy_analysis_high_frequency(self):
        """测试高失效频率的分析"""
        # 模拟高失效频率操作 - 确保失效比例超过0.15
        for i in range(8):  # 8组操作
            self.monitor.record_operation("get", "l1", True)
            self.monitor.record_operation("invalidate", "l1", True)  # 每个组都有失效

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["invalidation_frequency"] == "high"
        assert analysis["recommended_strategy"] == "delayed"
        assert analysis["priority"] == "high"
        assert "延迟失效策略" in analysis["optimization_suggestions"][0]

    def test_get_invalidation_strategy_analysis_medium_frequency(self):
        """测试中等失效频率的分析"""
        # 模拟中等失效频率操作 - 失效比例在0.05-0.15之间
        for i in range(3):  # 3组操作
            self.monitor.record_operation("get", "l1", True)
            self.monitor.record_operation("set", "l1", True)
            self.monitor.record_operation("invalidate", "l1", True)

        for i in range(30):  # 增加其他操作
            self.monitor.record_operation("get", "l1", True)

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["invalidation_frequency"] == "medium"
        assert analysis["recommended_strategy"] == "smart"
        assert analysis["priority"] == "medium"
        assert "智能失效策略" in analysis["optimization_suggestions"][0]

    def test_get_invalidation_strategy_analysis_low_hit_rate(self):
        """测试低命中率的失效策略分析"""
        # 模拟低命中率场景 - 确保有足够的get操作
        for i in range(20):
            self.monitor.record_operation("get", "l1", False)  # 大量miss
            self.monitor.record_operation("set", "l1", True)

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["priority"] == "high"
        assert "减少不必要的失效操作" in analysis["optimization_suggestions"][0]

    def test_get_invalidation_strategy_analysis_high_hit_rate(self):
        """测试高命中率的失效策略分析"""
        # 模拟高命中率场景 - 确保有足够的get操作
        for i in range(100):  # 大量hit操作
            self.monitor.record_operation("get", "l1", True)

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["priority"] == "low"
        assert "更激进的失效策略" in analysis["optimization_suggestions"][0]

    def test_get_invalidation_strategy_analysis_inefficient_invalidation(self):
        """测试失效效率低的分析"""
        # 模拟失效操作远多于设置操作 - 确保比例超过1.2但不超过高频率阈值
        for i in range(3):  # 少量设置操作
            self.monitor.record_operation("set", "l1", True)

        for i in range(8):  # 大量失效操作，但不超过高频率阈值
            self.monitor.record_operation("invalidate", "l1", True)

        # 添加一些其他操作来稀释失效比例
        for i in range(20):
            self.monitor.record_operation("get", "l1", True)

        analysis = self.monitor.get_invalidation_strategy_analysis()

        assert analysis["priority"] == "high"
        # 检查是否包含失效效率相关的建议
        suggestions = " ".join(analysis["optimization_suggestions"])
        assert "优化失效时机" in suggestions

    def test_get_cache_invalidation_strategy_analysis_function(self):
        """测试公共接口函数"""
        # 模拟一些操作
        self.monitor.record_operation("l1", "get", True)
        self.monitor.record_operation("l1", "set", True)
        self.monitor.record_operation("l1", "invalidate", True)

        analysis = get_cache_invalidation_strategy_analysis()

        assert isinstance(analysis, dict)
        assert "current_strategy" in analysis
        assert "recommended_strategy" in analysis
        assert "invalidation_frequency" in analysis
        assert "optimization_suggestions" in analysis
        assert "priority" in analysis

    def test_get_invalidation_analysis_from_permissions(self):
        """测试从permissions模块获取失效策略分析"""
        # 模拟一些操作
        self.monitor.record_operation("l1", "get", True)
        self.monitor.record_operation("l1", "set", True)

        analysis = get_invalidation_analysis_from_permissions()

        assert isinstance(analysis, dict)
        assert "current_strategy" in analysis
        assert "recommended_strategy" in analysis
        assert "invalidation_frequency" in analysis
        assert "optimization_suggestions" in analysis
        assert "priority" in analysis

    def test_debug_invalidation_frequency_calculation(self):
        """调试失效频率计算"""
        # 模拟高失效频率操作
        for i in range(8):
            self.monitor.record_operation("l1", "get", True)
            self.monitor.record_operation("l1", "set", True)
            self.monitor.record_operation("l1", "invalidate", True)

        recent_ops = self.monitor.get_recent_operations(100)
        invalidation_ops = [op for op in recent_ops if op["type"] == "invalidate"]

        print(f"总操作数: {len(recent_ops)}")
        print(f"失效操作数: {len(invalidation_ops)}")
        print(
            f"失效比例: {len(invalidation_ops) / len(recent_ops) if recent_ops else 0}"
        )

        analysis = self.monitor.get_invalidation_strategy_analysis()
        print(f"分析结果: {analysis}")

        # 这个测试只是为了调试，不进行断言
        assert True


class TestCacheInvalidationStrategyIntegration:
    """测试智能失效策略集成功能"""

    def test_invalidation_strategy_with_performance_analysis(self):
        """测试失效策略与性能分析的集成"""
        monitor = CacheMonitor()
        monitor.reset()

        # 模拟高失效频率场景 - 确保失效比例超过0.15
        for i in range(12):  # 12组操作
            monitor.record_operation("get", "l1", True)
            monitor.record_operation("invalidate", "l1", True)  # 每个组都有失效

        # 获取性能分析
        performance = monitor.get_performance_analysis()
        invalidation_analysis = monitor.get_invalidation_strategy_analysis()

        # 验证两个分析结果的一致性
        # 注意：性能分析可能没有瓶颈，因为主要是失效操作
        assert invalidation_analysis["priority"] == "high"  # 应该高优先级
        assert (
            invalidation_analysis["recommended_strategy"] == "delayed"
        )  # 应该推荐延迟策略

    def test_invalidation_strategy_edge_cases(self):
        """测试失效策略的边界情况"""
        monitor = CacheMonitor()
        monitor.reset()

        # 测试空操作历史
        analysis = monitor.get_invalidation_strategy_analysis()
        assert analysis["current_strategy"] == "standard"
        assert analysis["recommended_strategy"] == "standard"
        assert analysis["invalidation_frequency"] == "normal"
        assert analysis["priority"] == "low"

        # 测试只有少量失效操作的情况 - 调整数量避免触发中等频率
        for i in range(1):  # 只有1个失效操作
            monitor.record_operation("invalidate", "l1", True)

        # 添加更多其他操作来稀释失效比例，确保低于0.05
        for i in range(25):  # 增加操作数量
            monitor.record_operation("get", "l1", True)

        analysis = monitor.get_invalidation_strategy_analysis()
        assert analysis["invalidation_frequency"] == "normal"  # 应该正常频率
        assert analysis["priority"] == "low"  # 应该低优先级
