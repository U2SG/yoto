"""
监控模块修复测试

验证AlertLevel枚举问题是否已修复
"""

import pytest
from app.core.permission_monitor import (
    PermissionMonitor,
    AlertLevel,
    MetricType,
    get_permission_monitor,
)


class TestMonitorFix:
    """监控模块修复测试"""

    def test_alert_level_enum(self):
        """测试AlertLevel枚举"""
        # 测试所有枚举值
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"

        # 测试从字符串创建枚举
        assert AlertLevel("info") == AlertLevel.INFO
        assert AlertLevel("warning") == AlertLevel.WARNING
        assert AlertLevel("error") == AlertLevel.ERROR
        assert AlertLevel("critical") == AlertLevel.CRITICAL

    def test_monitor_initialization(self):
        """测试监控器初始化"""
        monitor = PermissionMonitor()
        assert monitor is not None
        assert hasattr(monitor, "thresholds")
        assert MetricType.CACHE_HIT_RATE in monitor.thresholds

    def test_record_metric_without_alert(self):
        """测试记录指标（不触发告警）"""
        monitor = PermissionMonitor()

        # 记录一个正常的缓存命中率（不会触发告警）
        monitor.record_cache_hit_rate(0.9, "l1")

        # 验证指标被记录
        assert len(monitor.metrics[MetricType.CACHE_HIT_RATE]) == 1

        # 验证没有告警（因为0.9 > 0.8，不会触发warning告警）
        active_alerts = [alert for alert in monitor.alerts if not alert.resolved]
        assert len(active_alerts) == 0

    def test_record_metric_with_alert(self):
        """测试记录指标（触发告警）"""
        monitor = PermissionMonitor()

        # 记录一个低的缓存命中率（会触发告警）
        monitor.record_cache_hit_rate(0.5, "l1")

        # 验证指标被记录
        assert len(monitor.metrics[MetricType.CACHE_HIT_RATE]) == 1

        # 验证有告警（因为0.5 < 0.8，会触发warning告警）
        active_alerts = [alert for alert in monitor.alerts if not alert.resolved]
        assert len(active_alerts) > 0

        # 验证告警级别
        alert = active_alerts[0]
        assert alert.level in [
            AlertLevel.WARNING,
            AlertLevel.ERROR,
            AlertLevel.CRITICAL,
        ]
        assert alert.metric_type == MetricType.CACHE_HIT_RATE

    def test_health_status(self):
        """测试健康状态"""
        monitor = PermissionMonitor()

        # 记录一些指标
        monitor.record_cache_hit_rate(0.9, "l1")
        monitor.record_response_time(50, "permission_check")
        monitor.record_error_rate(0.01, "permission_error")

        # 获取健康状态
        health = monitor.get_health_status()

        # 验证健康状态包含必要信息
        assert hasattr(health, "overall_status")
        assert hasattr(health, "cache_status")
        assert hasattr(health, "performance_status")
        assert hasattr(health, "error_status")
        assert hasattr(health, "alerts")
        assert hasattr(health, "metrics")

        # 验证状态值
        assert health.overall_status in ["healthy", "warning", "error"]
        assert health.cache_status in [
            "excellent",
            "good",
            "warning",
            "error",
            "unknown",
        ]
        assert health.performance_status in [
            "excellent",
            "good",
            "warning",
            "error",
            "unknown",
        ]
        assert health.error_status in [
            "excellent",
            "good",
            "warning",
            "error",
            "unknown",
        ]

    def test_global_monitor(self):
        """测试全局监控器"""
        monitor = get_permission_monitor()
        assert monitor is not None
        assert isinstance(monitor, PermissionMonitor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
