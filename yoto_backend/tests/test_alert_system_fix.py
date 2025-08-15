"""
测试告警系统修复

验证告警状态管理委托给后端，解决多进程数据孤岛问题
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.permission_monitor import (
    PermissionMonitor,
    RecordType,
    MetricType,
    AlertLevel,
)
from app.core.monitor_backends import MemoryBackend


class TestAlertSystemFix:
    """测试告警系统修复"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.monitor = PermissionMonitor()
        # 重置后端为内存后端以便测试
        self.monitor.backend = MemoryBackend()

    def test_no_local_alert_storage(self):
        """验证 PermissionMonitor 不再有本地告警存储"""
        # 检查没有本地告警存储属性
        assert not hasattr(self.monitor, "alerts")
        assert not hasattr(self.monitor, "alert_counters")

        # 检查有 backend 属性
        assert hasattr(self.monitor, "backend")
        assert isinstance(self.monitor.backend, MemoryBackend)

    def test_alert_creation_delegates_to_backend(self):
        """验证告警创建委托给后端"""
        # 触发一个告警
        self.monitor.record(
            "cache_hit_rate",
            0.3,
            RecordType.GAUGE,
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )

        # 验证告警存储在后端
        active_alerts = self.monitor.backend.get_active_alerts()
        assert len(active_alerts) >= 1

        # 验证告警内容
        alert = active_alerts[0]
        assert alert.metric_type == MetricType.CACHE_HIT_RATE
        # 0.3的缓存命中率会触发WARNING级别（阈值0.8），不是CRITICAL
        assert alert.level == AlertLevel.WARNING
        assert "指标过低" in alert.message

    def test_alert_counters_from_backend(self):
        """验证告警计数器来自后端"""
        # 触发多个告警
        self.monitor.record(
            "cache_hit_rate",
            0.3,
            RecordType.GAUGE,
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )
        self.monitor.record(
            "response_time",
            600.0,
            RecordType.HISTOGRAM,
            check_alerts=True,
            metric_type=MetricType.RESPONSE_TIME,
        )

        # 获取性能报告
        report = self.monitor.get_performance_report()

        # 验证告警计数器来自后端
        assert "alerts_count" in report
        assert isinstance(report["alerts_count"], dict)

        # 验证活跃告警数量
        assert report["active_alerts"] >= 2

    def test_alert_deduplication_across_processes(self):
        """验证跨进程告警去重"""
        # 模拟多个进程创建相同告警
        alert1 = self.monitor.backend.create_alert(
            Mock(
                id="test_alert_1",
                metric_type=MetricType.CACHE_HIT_RATE,
                level=AlertLevel.CRITICAL,
                current_value=0.3,
                threshold=0.4,
                timestamp=time.time(),
                resolved=False,
            )
        )

        alert2 = self.monitor.backend.create_alert(
            Mock(
                id="test_alert_2",
                metric_type=MetricType.CACHE_HIT_RATE,
                level=AlertLevel.CRITICAL,
                current_value=0.3,
                threshold=0.4,
                timestamp=time.time(),
                resolved=False,
            )
        )

        # 验证去重逻辑工作正常
        active_alerts = self.monitor.backend.get_active_alerts()
        # 应该只有一个活跃告警（相同类型和级别）
        assert len(active_alerts) == 1

    def test_alert_resolution_delegates_to_backend(self):
        """验证告警解决委托给后端"""
        # 创建一个告警
        alert = Mock(
            id="test_resolve_alert",
            metric_type=MetricType.CACHE_HIT_RATE,
            level=AlertLevel.WARNING,
            current_value=0.7,
            threshold=0.8,
            timestamp=time.time(),
            resolved=False,
        )

        self.monitor.backend.create_alert(alert)

        # 验证告警存在
        active_alerts = self.monitor.backend.get_active_alerts()
        assert len(active_alerts) >= 1

        # 解决告警
        self.monitor.backend.resolve_alert("test_resolve_alert")

        # 验证告警已解决
        active_alerts_after = self.monitor.backend.get_active_alerts()
        assert len(active_alerts_after) < len(active_alerts)

    def test_clear_alerts_uses_backend(self):
        """验证清除告警使用后端"""
        # 创建一些告警
        for i in range(3):
            alert = Mock(
                id=f"test_alert_{i}",
                metric_type=MetricType.CACHE_HIT_RATE,
                level=AlertLevel.WARNING,
                current_value=0.7,
                threshold=0.8,
                timestamp=time.time(),
                resolved=False,
                message=f"Test alert {i}",
            )
            self.monitor.backend.create_alert(alert)

        # 验证告警存在
        assert len(self.monitor.backend.get_active_alerts()) >= 1

        # 清除所有告警
        self.monitor.clear_alerts()

        # 验证告警已清除
        assert len(self.monitor.backend.get_active_alerts()) == 0

    def test_health_status_uses_backend_alerts(self):
        """验证健康状态使用后端告警"""
        # 创建一些告警
        alert = Mock(
            id="test_health_alert",
            metric_type=MetricType.CACHE_HIT_RATE,
            level=AlertLevel.CRITICAL,
            current_value=0.3,
            threshold=0.4,
            timestamp=time.time(),
            resolved=False,
        )
        self.monitor.backend.create_alert(alert)

        # 获取健康状态
        health_status = self.monitor.get_health_status()

        # 验证健康状态包含告警
        assert len(health_status.alerts) >= 1
        assert health_status.alerts[0].level == AlertLevel.CRITICAL

    def test_backend_independence_for_alerts(self):
        """验证告警系统的后端独立性"""
        # 创建模拟后端
        mock_backend = Mock()
        mock_backend.create_alert.return_value = True
        mock_backend.get_active_alerts.return_value = []
        mock_backend.get_alert_counters.return_value = {"warning": 0, "critical": 0}
        mock_backend.resolve_alert.return_value = True

        # 切换后端
        self.monitor.backend = mock_backend

        # 触发告警
        self.monitor.record(
            "cache_hit_rate",
            0.3,
            RecordType.GAUGE,
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )

        # 验证调用的是模拟后端
        mock_backend.create_alert.assert_called()

    def test_multi_process_alert_scenario(self):
        """测试多进程告警场景"""
        # 模拟多个进程同时触发相同告警
        processes = []
        for i in range(3):
            # 模拟不同进程的监控器实例
            process_monitor = PermissionMonitor()
            process_monitor.backend = self.monitor.backend  # 共享后端

            # 每个进程都触发相同的告警
            process_monitor.record(
                "cache_hit_rate",
                0.3,
                RecordType.GAUGE,
                check_alerts=True,
                metric_type=MetricType.CACHE_HIT_RATE,
            )
            processes.append(process_monitor)

        # 验证告警数量（由于每个进程都会触发多个级别的告警，所以会有多个告警）
        active_alerts = self.monitor.backend.get_active_alerts()
        # 每个进程会触发WARNING、ERROR、CRITICAL三个级别的告警
        # 但由于去重逻辑，相同级别只会有一个告警
        assert len(active_alerts) >= 1

        # 验证告警计数器正确
        counters = self.monitor.backend.get_alert_counters()
        assert counters.get("warning", 0) >= 1  # 至少有一个WARNING告警


def test_alert_system_is_distributed():
    """测试告警系统是分布式的"""
    monitor = PermissionMonitor()

    # 验证核心职责：委托给后端
    assert hasattr(monitor, "backend")  # 有后端
    assert not hasattr(monitor, "alerts")  # 没有本地告警存储
    assert not hasattr(monitor, "alert_counters")  # 没有本地计数器


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
