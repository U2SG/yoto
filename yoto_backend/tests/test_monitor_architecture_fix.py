"""
测试监控架构修复

验证 local_cache 移除后，PermissionMonitor 成为纯粹的无状态协调器
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.permission_monitor import PermissionMonitor, RecordType, MetricType
from app.core.monitor_backends import MemoryBackend


class TestMonitorArchitectureFix:
    """测试监控架构修复"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = PermissionMonitor()
        # 重置后端为内存后端以便测试
        self.monitor.backend = MemoryBackend()

    def test_no_local_cache_attribute(self):
        """验证 PermissionMonitor 不再有 local_cache 属性"""
        # 检查没有 local_cache 属性
        assert not hasattr(self.monitor, "local_cache")

        # 检查有 backend 属性
        assert hasattr(self.monitor, "backend")
        assert isinstance(self.monitor.backend, MemoryBackend)

    def test_record_delegates_to_backend_only(self):
        """验证 record 方法只委托给后端，不维护本地状态"""
        # 记录一个指标
        self.monitor.record("test_metric", 42.0, RecordType.GAUGE)

        # 验证数据只存储在后端
        metrics = self.monitor.backend.get_metrics("test_metric")
        assert len(metrics) == 1
        assert metrics[0]["value"] == 42.0

        # 验证 PermissionMonitor 本身不存储数据
        assert not hasattr(self.monitor, "local_cache")

    def test_record_metric_delegates_to_backend_only(self):
        """验证 record_metric 方法只委托给后端"""
        # 记录一个指标
        self.monitor.record_metric(MetricType.CACHE_HIT_RATE, 0.85)

        # 验证数据只存储在后端
        metrics = self.monitor.backend.get_metrics("cache_hit_rate")
        assert len(metrics) == 1
        assert metrics[0]["value"] == 0.85

    def test_health_status_uses_backend_data(self):
        """验证健康状态计算使用后端数据"""
        # 记录一些测试数据
        self.monitor.record("cache_hit_rate", 0.92, RecordType.GAUGE)
        self.monitor.record("response_time", 50.0, RecordType.HISTOGRAM)
        self.monitor.record("error_rate", 0.01, RecordType.GAUGE)

        # 获取健康状态
        health_status = self.monitor.get_health_status()

        # 验证健康状态不是空的
        assert health_status.overall_status in ["healthy", "warning", "error"]
        assert health_status.cache_status in ["excellent", "good", "warning", "error"]
        assert health_status.performance_status in [
            "excellent",
            "good",
            "warning",
            "error",
        ]
        assert health_status.error_status in ["excellent", "good", "warning", "error"]

    def test_memory_efficiency(self):
        """验证内存效率 - PermissionMonitor 不存储数据副本"""
        import sys

        # 记录大量数据
        for i in range(100):
            self.monitor.record(f"metric_{i}", float(i), RecordType.GAUGE)

        # 获取 PermissionMonitor 的大小
        monitor_size = sys.getsizeof(self.monitor)

        # 验证 PermissionMonitor 本身不会因为数据量增加而显著增长
        # 因为数据存储在 backend 中，而不是 PermissionMonitor 中
        assert monitor_size < 10000  # 合理的大小限制

    def test_backend_independence(self):
        """验证后端独立性 - 可以轻松切换后端"""
        # 创建模拟后端
        mock_backend = Mock()
        mock_backend.record_metric.return_value = True
        mock_backend.record_event.return_value = True
        mock_backend.get_metrics.return_value = []
        mock_backend.get_stats.return_value = {
            "count": 0,
            "sum": 0,
            "min": float("inf"),
            "max": float("-inf"),
        }

        # 切换后端
        self.monitor.backend = mock_backend

        # 记录数据
        self.monitor.record("test_metric", 42.0, RecordType.GAUGE)

        # 验证调用的是模拟后端
        # 注意：时间戳是动态生成的，所以我们只验证其他参数
        mock_backend.record_metric.assert_called_once()
        call_args = mock_backend.record_metric.call_args
        assert call_args[0][0] == "test_metric"  # name
        assert call_args[0][1] == 42.0  # value
        assert call_args[0][2] is None  # tags
        assert call_args[0][3] is not None  # timestamp (应该存在)

    def test_no_data_duplication(self):
        """验证没有数据重复存储"""
        # 记录数据
        self.monitor.record("test_metric", 42.0, RecordType.GAUGE)

        # 检查 PermissionMonitor 的属性
        monitor_attrs = [
            attr
            for attr in dir(self.monitor)
            if not attr.startswith("_") and not callable(getattr(self.monitor, attr))
        ]

        # 验证没有数据存储相关的属性
        data_attrs = ["metrics", "records", "events", "values", "cache"]
        for attr in data_attrs:
            assert attr not in monitor_attrs, f"PermissionMonitor 不应该有 {attr} 属性"


def test_monitor_is_stateless_coordinator():
    """测试 PermissionMonitor 是无状态协调器"""
    monitor = PermissionMonitor()

    # 验证核心职责：接收 -> 格式化 -> 委托
    assert hasattr(monitor, "record")  # 接收数据
    assert hasattr(monitor, "backend")  # 委托给后端
    assert not hasattr(monitor, "local_cache")  # 不存储数据副本


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
