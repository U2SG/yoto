"""
测试Prometheus后端

验证Prometheus指标记录和端点功能
"""

import pytest
import os
import time
from unittest.mock import Mock, patch
from app.core.monitor_backends import (
    PROMETHEUS_AVAILABLE,
    PrometheusBackend,
    BackendType,
)
from app.core.permission_monitor import MetricType, AlertLevel


class TestPrometheusBackend:
    """测试Prometheus后端"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 为每个测试创建独立的注册表，避免重复注册问题
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import CollectorRegistry

            self.registry = CollectorRegistry()
            self.backend = PrometheusBackend(prefix="test_", registry=self.registry)
        else:
            self.backend = PrometheusBackend(prefix="test_")

    def test_prometheus_initialization(self):
        """测试Prometheus后端初始化"""
        assert self.backend.prefix == "test_"
        assert hasattr(self.backend, "_metrics")

    def test_record_metric_cache_hit_rate(self):
        """测试记录缓存命中率指标"""
        result = self.backend.record_metric(
            "cache_hit_rate", 0.85, tags={"cache_level": "l1"}
        )
        assert result is True

    def test_record_metric_response_time(self):
        """测试记录响应时间指标"""
        result = self.backend.record_metric(
            "response_time", 150.0, tags={"operation": "permission_check"}
        )
        assert result is True

    def test_record_metric_error_rate(self):
        """测试记录错误率指标"""
        result = self.backend.record_metric(
            "error_rate", 0.02, tags={"error_type": "permission_error"}
        )
        assert result is True

    def test_record_metric_qps(self):
        """测试记录QPS指标"""
        result = self.backend.record_metric(
            "qps", 1000.0, tags={"endpoint": "permissions"}
        )
        assert result is True

    def test_record_metric_memory_usage(self):
        """测试记录内存使用指标"""
        result = self.backend.record_metric("memory_usage", 1024.0)
        assert result is True

    def test_record_metric_connection_pool(self):
        """测试记录连接池指标"""
        result = self.backend.record_metric(
            "connection_pool", 10.0, tags={"pool_type": "default"}
        )
        assert result is True

    def test_record_event(self):
        """测试记录事件"""
        result = self.backend.record_event(
            "cache_invalidation",
            metadata={"cache_level": "l1"},
            tags={"entity": "user"},
        )
        assert result is True

    def test_create_alert(self):
        """测试创建告警"""
        alert = Mock(
            level=AlertLevel.WARNING,
            metric_type=MetricType.CACHE_HIT_RATE,
            current_value=0.7,
            threshold=0.8,
        )
        result = self.backend.create_alert(alert)
        assert result is True

    def test_get_metrics_endpoint(self):
        """测试获取指标端点"""
        metrics = self.backend.get_metrics_endpoint()
        assert isinstance(metrics, str)
        assert len(metrics) > 0

    def test_get_metrics_returns_empty(self):
        """测试获取指标历史返回空列表"""
        metrics = self.backend.get_metrics("cache_hit_rate", 10)
        assert metrics == []

    def test_get_events_returns_empty(self):
        """测试获取事件历史返回空列表"""
        events = self.backend.get_events("cache_invalidation", 10)
        assert events == []

    def test_get_stats_returns_empty(self):
        """测试获取统计返回空统计"""
        stats = self.backend.get_stats("cache_hit_rate")
        assert stats == {
            "count": 0,
            "sum": 0,
            "min": float("inf"),
            "max": float("-inf"),
        }

    def test_get_active_alerts_returns_empty(self):
        """测试获取活跃告警返回空列表"""
        alerts = self.backend.get_active_alerts()
        assert alerts == []

    def test_resolve_alert_returns_false(self):
        """测试解决告警返回False"""
        result = self.backend.resolve_alert("test_alert_id")
        assert result is False

    def test_get_alert_counters_returns_empty(self):
        """测试获取告警计数器返回空字典"""
        counters = self.backend.get_alert_counters()
        assert counters == {}


class TestPrometheusBackendWithoutClient:
    """测试没有prometheus_client的情况"""

    @patch("app.core.monitor_backends.PROMETHEUS_AVAILABLE", False)
    def test_backend_without_prometheus_client(self):
        """测试没有prometheus_client时的行为"""
        backend = PrometheusBackend(prefix="test_")

        # 所有操作都应该成功（模拟模式）
        assert backend.record_metric("cache_hit_rate", 0.85) is True
        assert backend.record_event("test_event") is True
        assert backend.create_alert(Mock()) is True

        # 端点应该返回提示信息
        metrics = backend.get_metrics_endpoint()
        assert "prometheus_client not available" in metrics


class TestPrometheusBackendFactory:
    """测试Prometheus后端工厂"""

    def test_create_prometheus_backend(self):
        """测试创建Prometheus后端"""
        from app.core.monitor_backends import MonitorBackendFactory

        # 为测试创建独立的注册表
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import CollectorRegistry

            registry = CollectorRegistry()
            backend = MonitorBackendFactory.create_backend(
                BackendType.PROMETHEUS, prefix="test_", registry=registry
            )
        else:
            backend = MonitorBackendFactory.create_backend(
                BackendType.PROMETHEUS, prefix="test_"
            )
        assert isinstance(backend, PrometheusBackend)
        assert backend.prefix == "test_"


class TestPrometheusEnvironmentConfig:
    """测试Prometheus环境配置"""

    def test_prometheus_environment_variables(self):
        """测试Prometheus环境变量配置"""
        # 设置环境变量
        os.environ["MONITOR_BACKEND"] = "prometheus"
        os.environ["PROMETHEUS_PREFIX"] = "test_system_"

        try:
            from app.core.monitor_backends import get_monitor_backend

            backend = get_monitor_backend()
            assert isinstance(backend, PrometheusBackend)
            assert backend.prefix == "test_system_"
        finally:
            # 清理环境变量
            if "MONITOR_BACKEND" in os.environ:
                del os.environ["MONITOR_BACKEND"]
            if "PROMETHEUS_PREFIX" in os.environ:
                del os.environ["PROMETHEUS_PREFIX"]


def test_prometheus_metrics_structure():
    """测试Prometheus指标结构"""
    # 为测试创建独立的注册表
    if PROMETHEUS_AVAILABLE:
        from prometheus_client import CollectorRegistry

        registry = CollectorRegistry()
        backend = PrometheusBackend(prefix="test_", registry=registry)
    else:
        backend = PrometheusBackend(prefix="test_")

    # 验证指标类型映射
    assert "cache_hit_rate" in backend._metrics
    assert "response_time" in backend._metrics
    assert "error_rate" in backend._metrics
    assert "qps" in backend._metrics
    assert "memory_usage" in backend._metrics
    assert "connection_pool" in backend._metrics
    assert "alerts" in backend._metrics


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
