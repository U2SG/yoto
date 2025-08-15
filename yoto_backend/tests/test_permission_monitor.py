"""
权限系统监控模块测试

测试权限系统监控器的各项功能：
- 指标收集和存储
- 告警检测和触发
- 健康状态计算
- 性能报告生成
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from app.core.permission_monitor import (
    PermissionMonitor,
    MetricType,
    AlertLevel,
    get_permission_monitor,
    record_cache_hit_rate,
    record_response_time,
    record_error_rate,
    get_health_status,
    get_performance_report,
)


class TestPermissionMonitor:
    """权限系统监控器测试"""

    def setup_method(self):
        """测试前准备"""
        self.monitor = PermissionMonitor()

    def test_record_metric(self):
        """测试指标记录"""
        # 记录缓存命中率
        self.monitor.record_cache_hit_rate(0.85, "l1")

        # 验证指标已记录
        assert len(self.monitor.metrics[MetricType.CACHE_HIT_RATE]) == 1
        point = self.monitor.metrics[MetricType.CACHE_HIT_RATE][0]
        assert point.value == 0.85
        assert point.tags["cache_level"] == "l1"

    def test_record_response_time(self):
        """测试响应时间记录"""
        # 记录响应时间
        self.monitor.record_response_time(150.0, "permission_check")

        # 验证指标已记录
        assert len(self.monitor.metrics[MetricType.RESPONSE_TIME]) == 1
        point = self.monitor.metrics[MetricType.RESPONSE_TIME][0]
        assert point.value == 150.0
        assert point.tags["operation"] == "permission_check"

    def test_record_error_rate(self):
        """测试错误率记录"""
        # 记录错误率
        self.monitor.record_error_rate(0.03, "permission_error")

        # 验证指标已记录
        assert len(self.monitor.metrics[MetricType.ERROR_RATE]) == 1
        point = self.monitor.metrics[MetricType.ERROR_RATE][0]
        assert point.value == 0.03
        assert point.tags["error_type"] == "permission_error"

    def test_alert_triggering(self):
        """测试告警触发"""
        # 记录低于阈值的缓存命中率
        self.monitor.record_cache_hit_rate(0.5)  # 低于ERROR阈值0.6

        # 手动触发告警检查
        self.monitor._check_alerts()

        # 验证告警已创建
        assert len(self.monitor.active_alerts) == 1
        alert = self.monitor.active_alerts[0]
        assert alert.level == AlertLevel.ERROR
        assert alert.metric == "cache_hit_rate"
        assert alert.value == 0.5

    def test_alert_suppression(self):
        """测试告警抑制"""
        # 记录低于阈值的缓存命中率
        self.monitor.record_cache_hit_rate(0.5)

        # 触发告警检查
        self.monitor._check_alerts()
        assert len(self.monitor.active_alerts) == 1

        # 再次触发告警检查，应该不会创建重复告警
        self.monitor._check_alerts()
        assert len(self.monitor.active_alerts) == 1

    def test_health_status_calculation(self):
        """测试健康状态计算"""
        # 记录各种指标
        self.monitor.record_cache_hit_rate(0.9)  # 健康
        self.monitor.record_response_time(50.0)  # 健康
        self.monitor.record_error_rate(0.02)  # 健康

        # 获取健康状态
        health_status = self.monitor.get_health_status()

        # 验证状态
        assert health_status.overall_status == "healthy"
        assert health_status.cache_status == "healthy"
        assert health_status.performance_status == "healthy"
        assert health_status.error_status == "healthy"

    def test_health_status_warning(self):
        """测试警告状态"""
        # 记录警告级别的指标
        self.monitor.record_cache_hit_rate(0.75)  # 警告级别
        self.monitor.record_response_time(200.0)  # 警告级别

        # 获取健康状态
        health_status = self.monitor.get_health_status()

        # 验证状态
        assert health_status.overall_status == "warning"
        assert health_status.cache_status == "warning"
        assert health_status.performance_status == "warning"

    def test_health_status_error(self):
        """测试错误状态"""
        # 记录错误级别的指标
        self.monitor.record_cache_hit_rate(0.5)  # 错误级别
        self.monitor.record_response_time(600.0)  # 错误级别
        self.monitor.record_error_rate(0.15)  # 错误级别

        # 获取健康状态
        health_status = self.monitor.get_health_status()

        # 验证状态
        assert health_status.overall_status == "error"
        assert health_status.cache_status == "error"
        assert health_status.performance_status == "error"
        assert health_status.error_status == "error"

    def test_performance_report(self):
        """测试性能报告"""
        # 记录一些指标
        self.monitor.record_cache_hit_rate(0.85)
        self.monitor.record_response_time(100.0)
        self.monitor.record_error_rate(0.03)

        # 获取性能报告
        report = self.monitor.get_performance_report()

        # 验证报告结构
        assert "summary" in report
        assert "metrics" in report
        assert "alerts" in report
        assert "recommendations" in report

        # 验证摘要信息
        assert report["summary"]["total_requests"] > 0
        assert "error_rate" in report["summary"]

    def test_clear_alerts(self):
        """测试清除告警"""
        # 创建一些告警
        self.monitor.record_cache_hit_rate(0.5)
        self.monitor._check_alerts()
        assert len(self.monitor.active_alerts) == 1

        # 清除所有告警
        self.monitor.clear_alerts()
        assert len([a for a in self.monitor.active_alerts if a.is_active]) == 0

    def test_clear_specific_alerts(self):
        """测试清除指定指标告警"""
        # 创建多个告警
        self.monitor.record_cache_hit_rate(0.5)
        self.monitor.record_response_time(600.0)
        self.monitor._check_alerts()
        assert len(self.monitor.active_alerts) == 2

        # 清除指定指标告警
        self.monitor.clear_alerts("cache_hit_rate")
        active_alerts = [a for a in self.monitor.active_alerts if a.is_active]
        assert len(active_alerts) == 1
        assert active_alerts[0].metric == "response_time"

    def test_metrics_history(self):
        """测试指标历史数据"""
        # 记录一些历史数据
        for i in range(10):
            self.monitor.record_cache_hit_rate(0.8 + i * 0.01)
            time.sleep(0.01)

        # 获取历史数据
        history = self.monitor.get_metrics_history(MetricType.CACHE_HIT_RATE, minutes=1)

        # 验证历史数据
        assert len(history) == 10
        assert all(point.value >= 0.8 for point in history)

    def test_recommendations_generation(self):
        """测试优化建议生成"""
        # 记录需要优化的指标
        self.monitor.record_cache_hit_rate(0.7)  # 低于警告阈值
        self.monitor.record_response_time(150.0)  # 高于警告阈值
        self.monitor.record_error_rate(0.08)  # 高于警告阈值

        # 获取性能报告
        report = self.monitor.get_performance_report()

        # 验证建议
        recommendations = report["recommendations"]
        assert len(recommendations) > 0
        assert any("缓存" in rec for rec in recommendations)
        assert any("性能" in rec for rec in recommendations)
        assert any("错误" in rec for rec in recommendations)


class TestPermissionMonitorIntegration:
    """权限系统监控器集成测试"""

    def test_global_monitor_instance(self):
        """测试全局监控实例"""
        monitor = get_permission_monitor()
        assert isinstance(monitor, PermissionMonitor)

    def test_convenience_functions(self):
        """测试便捷函数"""
        # 测试便捷函数
        record_cache_hit_rate(0.85)
        record_response_time(100.0)
        record_error_rate(0.02)

        # 验证函数正常工作
        health_status = get_health_status()
        assert health_status is not None

        report = get_performance_report()
        assert report is not None

    def test_monitor_thread_safety(self):
        """测试监控器线程安全"""
        import threading

        def record_metrics():
            for i in range(100):
                self.monitor.record_cache_hit_rate(0.8 + i * 0.001)
                time.sleep(0.001)

        # 创建多个线程同时记录指标
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_metrics)
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证指标记录正确
        assert len(self.monitor.metrics[MetricType.CACHE_HIT_RATE]) > 0

    def test_monitor_with_real_data(self):
        """测试监控器与真实数据"""
        # 模拟真实的权限检查场景
        for i in range(50):
            # 模拟缓存命中率
            hit_rate = 0.8 + (i % 3) * 0.1
            self.monitor.record_cache_hit_rate(hit_rate)

            # 模拟响应时间
            response_time = 50 + (i % 5) * 20
            self.monitor.record_response_time(response_time)

            # 模拟错误率
            error_rate = 0.01 + (i % 10) * 0.005
            self.monitor.record_error_rate(error_rate)

            time.sleep(0.01)

        # 获取健康状态
        health_status = self.monitor.get_health_status()
        assert health_status.overall_status in ["healthy", "warning", "error"]

        # 获取性能报告
        report = self.monitor.get_performance_report()
        assert report["summary"]["total_requests"] >= 50


class TestPermissionMonitorEdgeCases:
    """权限系统监控器边界情况测试"""

    def test_empty_metrics(self):
        """测试空指标情况"""
        # 不记录任何指标
        health_status = self.monitor.get_health_status()

        # 验证状态为unknown
        assert health_status.cache_status == "unknown"
        assert health_status.performance_status == "unknown"
        assert health_status.error_status == "unknown"
        assert health_status.resource_status == "unknown"

    def test_extreme_values(self):
        """测试极值情况"""
        # 记录极值
        self.monitor.record_cache_hit_rate(0.0)  # 最低值
        self.monitor.record_response_time(10000.0)  # 最高值
        self.monitor.record_error_rate(1.0)  # 最高值

        # 获取健康状态
        health_status = self.monitor.get_health_status()
        assert health_status.overall_status == "error"

    def test_metric_overflow(self):
        """测试指标溢出"""
        # 记录超过最大长度的指标
        for i in range(2000):
            self.monitor.record_cache_hit_rate(0.8)

        # 验证指标长度不超过限制
        assert len(self.monitor.metrics[MetricType.CACHE_HIT_RATE]) <= 1000

    def test_concurrent_alert_checking(self):
        """测试并发告警检查"""
        import threading

        def check_alerts():
            for _ in range(10):
                self.monitor._check_alerts()
                time.sleep(0.001)

        # 创建多个线程同时检查告警
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=check_alerts)
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证没有重复告警
        active_alerts = [a for a in self.monitor.active_alerts if a.is_active]
        assert len(active_alerts) <= len(self.monitor.alert_thresholds)


if __name__ == "__main__":
    pytest.main([__file__])
