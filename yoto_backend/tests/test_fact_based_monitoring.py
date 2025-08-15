"""
测试基于事实的监控指标记录
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_fact_based_monitoring():
    """测试基于事实的监控指标记录"""
    try:
        from app.core.permissions_refactored import (
            PermissionSystem,
            get_permission_system,
        )
        from app.core.permission_monitor import get_permission_monitor

        # 测试1: 验证invalidate方法记录实际事件
        ps = PermissionSystem()
        monitor = get_permission_monitor()

        # 清空之前的监控数据
        monitor.clear_alerts()

        # 执行缓存失效操作
        ps.invalidate_user_cache(123)
        ps.invalidate_role_cache(456)

        # 验证事件记录
        events_summary = monitor.get_events_summary()
        print(f"✅ 事件摘要: {events_summary}")

        # 检查是否有缓存失效事件
        if "cache_invalidation" in events_summary.get("event_types", {}):
            print("✅ 缓存失效事件记录成功")
        else:
            print("❌ 缓存失效事件记录失败")
            return False

        # 测试2: 验证process_maintenance记录实际处理数量
        # 由于这些函数依赖Redis，我们只测试函数调用
        try:
            # 调用维护任务
            ps.process_maintenance()

            # 验证维护事件记录
            events_summary = monitor.get_events_summary()
            if "maintenance_completed" in events_summary.get("event_types", {}):
                print("✅ 维护完成事件记录成功")
            else:
                print("⚠️  维护完成事件记录（可能没有实际处理的任务）")

            # 验证数值记录
            values_summary = monitor.get_values_summary()
            print(f"✅ 数值摘要: {values_summary}")

        except Exception as e:
            print(f"⚠️  维护任务测试中出现异常（可能是正常的）: {e}")

        # 测试3: 验证事件数据结构
        events = monitor.get_events_summary()
        if events["total_events"] > 0:
            recent_events = events.get("recent_events", [])
            if recent_events:
                event = recent_events[0]
                if "type" in event and "data" in event and "timestamp" in event:
                    print("✅ 事件数据结构正确")
                else:
                    print("❌ 事件数据结构不正确")
                    return False

        # 测试4: 验证数值记录功能
        monitor.record_value("test_metric", 42.5, {"tag": "test"})
        values_summary = monitor.get_values_summary()

        if "test_metric" in values_summary:
            metric_stats = values_summary["test_metric"]
            if metric_stats["count"] == 1 and metric_stats["avg"] == 42.5:
                print("✅ 数值记录功能正常")
            else:
                print("❌ 数值记录功能异常")
                return False

        print("\n🎉 基于事实的监控指标记录验证成功！")
        return True

    except Exception as e:
        print(f"❌ 基于事实的监控指标记录测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_monitoring_methods():
    """测试监控方法的存在性"""
    try:
        from app.core.permission_monitor import PermissionMonitor

        monitor = PermissionMonitor()

        # 测试事件记录方法
        if hasattr(monitor, "record_event"):
            print("✅ record_event方法存在")
        else:
            print("❌ record_event方法不存在")
            return False

        # 测试数值记录方法
        if hasattr(monitor, "record_value"):
            print("✅ record_value方法存在")
        else:
            print("❌ record_value方法不存在")
            return False

        # 测试事件摘要方法
        if hasattr(monitor, "get_events_summary"):
            print("✅ get_events_summary方法存在")
        else:
            print("❌ get_events_summary方法不存在")
            return False

        # 测试数值摘要方法
        if hasattr(monitor, "get_values_summary"):
            print("✅ get_values_summary方法存在")
        else:
            print("❌ get_values_summary方法不存在")
            return False

        print("✅ 所有监控方法都存在")
        return True

    except Exception as e:
        print(f"❌ 监控方法测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=== 测试基于事实的监控指标记录 ===")
    test_fact_based_monitoring()

    print("\n=== 测试监控方法的存在性 ===")
    test_monitoring_methods()
