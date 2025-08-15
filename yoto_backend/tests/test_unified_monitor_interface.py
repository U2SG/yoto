"""
测试统一监控接口
"""

import pytest
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.permission_monitor import (
    PermissionMonitor,
    RecordType,
    MetricType,
    record,
    record_gauge,
    record_counter,
    record_histogram,
    record_event,
    get_permission_monitor,
    demo_unified_interface,
)


class TestUnifiedMonitorInterface:
    """测试统一监控接口"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 获取监控器实例并重置
        self.monitor = get_permission_monitor()
        self.monitor.clear_alerts()
        # 清空记录
        self.monitor.records.clear()
        self.monitor.record_stats.clear()
        self.monitor.record_counters.clear()

    def test_record_gauge(self):
        """测试记录仪表盘指标"""
        # 记录缓存命中率
        record_gauge(
            "cache_hit_rate",
            0.85,
            {"cache_level": "l1"},
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )

        # 验证记录
        assert "cache_hit_rate" in self.monitor.records
        assert len(self.monitor.records["cache_hit_rate"]) == 1

        record_point = self.monitor.records["cache_hit_rate"][0]
        assert record_point.name == "cache_hit_rate"
        assert record_point.value == 0.85
        assert record_point.record_type == RecordType.GAUGE
        assert record_point.tags == {"cache_level": "l1"}

        # 验证统计信息
        stats = self.monitor.record_stats["cache_hit_rate"]
        assert stats["count"] == 1
        assert stats["sum"] == 0.85
        assert stats["min"] == 0.85
        assert stats["max"] == 0.85

    def test_record_counter(self):
        """测试记录计数器"""
        # 记录权限检查次数
        record_counter("permission_checks", 1, {"operation": "user_permission"})
        record_counter("permission_checks", 1, {"operation": "user_permission"})

        # 验证记录
        assert "permission_checks" in self.monitor.records
        assert len(self.monitor.records["permission_checks"]) == 2

        # 验证统计信息
        stats = self.monitor.record_stats["permission_checks"]
        assert stats["count"] == 2
        assert stats["sum"] == 2.0

    def test_record_histogram(self):
        """测试记录直方图"""
        # 记录响应时间
        record_histogram("response_time", 100.0, {"endpoint": "/api/permissions"})
        record_histogram("response_time", 150.0, {"endpoint": "/api/permissions"})
        record_histogram("response_time", 200.0, {"endpoint": "/api/permissions"})

        # 验证统计信息
        stats = self.monitor.record_stats["response_time"]
        assert stats["count"] == 3
        assert stats["sum"] == 450.0
        assert stats["min"] == 100.0
        assert stats["max"] == 200.0
        # 计算平均值
        assert stats["sum"] / stats["count"] == 150.0

    def test_record_event(self):
        """测试记录事件"""
        # 记录缓存失效事件
        event_data = {
            "entity_type": "user",
            "entity_id": "12345",
            "reason": "permission_change",
        }
        record_event("cache_invalidation", event_data, {"cache_level": "l1"})

        # 验证记录
        assert "cache_invalidation" in self.monitor.records
        record_point = self.monitor.records["cache_invalidation"][0]
        assert record_point.record_type == RecordType.EVENT
        assert record_point.value == 1.0
        assert record_point.metadata == event_data
        assert record_point.tags == {"cache_level": "l1"}

    def test_unified_interface_usage(self):
        """测试统一接口的使用场景"""

        # 模拟权限系统运行
        # 1. 记录缓存命中率
        record_gauge(
            "cache_hit_rate",
            0.92,
            {"cache_level": "l1"},
            check_alerts=True,
            metric_type=MetricType.CACHE_HIT_RATE,
        )

        # 2. 记录响应时间
        record_histogram(
            "response_time",
            85.5,
            {"operation": "permission_check"},
            check_alerts=True,
            metric_type=MetricType.RESPONSE_TIME,
        )

        # 3. 记录QPS
        record_counter(
            "qps",
            1,
            {"endpoint": "/api/permissions"},
            check_alerts=True,
            metric_type=MetricType.QPS,
        )

        # 4. 记录缓存失效事件
        record_event(
            "cache_invalidation",
            {"entity_type": "user", "entity_id": "67890", "reason": "role_change"},
        )

        # 5. 记录维护完成事件
        record_event(
            "maintenance_completed",
            {"duration": 15.2, "type": "cache_cleanup", "items_processed": 1500},
        )

        # 验证所有记录
        expected_records = [
            "cache_hit_rate",
            "response_time",
            "qps",
            "cache_invalidation",
            "maintenance_completed",
        ]

        for record_name in expected_records:
            assert record_name in self.monitor.records
            assert len(self.monitor.records[record_name]) == 1

        # 验证统计信息
        assert self.monitor.record_stats["cache_hit_rate"]["count"] == 1
        assert self.monitor.record_stats["response_time"]["count"] == 1
        assert self.monitor.record_stats["qps"]["count"] == 1

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 测试旧的接口仍然可用
        self.monitor.record_cache_hit_rate(0.88, "l2")
        self.monitor.record_response_time(120.0, "permission_check")
        self.monitor.record_event("test_event", {"test": "data"})
        self.monitor.record_value("test_value", 42.0, {"tag": "test"})

        # 验证记录存在
        assert len(self.monitor.records["cache_hit_rate"]) == 1
        assert len(self.monitor.records["response_time"]) == 1
        assert len(self.monitor.records["test_event"]) == 1
        assert len(self.monitor.records["test_value"]) == 1

    def test_record_without_value(self):
        """测试无值的记录（事件类型）"""
        # 事件类型可以不提供value
        record("test_event", record_type=RecordType.EVENT, metadata={"test": True})

        record_point = self.monitor.records["test_event"][0]
        assert record_point.value == 0.0  # 默认值
        assert record_point.record_type == RecordType.EVENT
        assert record_point.metadata == {"test": True}

    def test_record_with_tags_and_metadata(self):
        """测试带标签和元数据的记录"""
        tags = {"service": "permission", "version": "1.0"}
        metadata = {"user_id": "123", "action": "check_permission"}

        record("permission_check", 1.0, RecordType.COUNTER, tags, metadata)

        record_point = self.monitor.records["permission_check"][0]
        assert record_point.tags == tags
        assert record_point.metadata == metadata
        assert record_point.record_type == RecordType.COUNTER


def test_demo_unified_interface():
    """演示统一接口的使用"""
    # 运行演示
    demo_unified_interface()

    # 验证演示产生了记录
    monitor = get_permission_monitor()
    expected_records = [
        "cache_hit_rate",
        "permission_checks",
        "response_time",
        "cache_invalidation",
        "maintenance_completed",
    ]

    for record_name in expected_records:
        assert record_name in monitor.records
        assert len(monitor.records[record_name]) >= 1


if __name__ == "__main__":
    # 运行演示
    demo_unified_interface()

    # 打印统计信息
    monitor = get_permission_monitor()
    print("\n=== 记录统计 ===")
    for name, stats in monitor.record_stats.items():
        if stats["count"] > 0:
            print(f"{name}: {stats}")

    print("\n=== 事件摘要 ===")
    events_summary = monitor.get_events_summary()
    print(f"总事件数: {events_summary['total_events']}")
    print(f"事件类型: {events_summary['event_types']}")
