"""
权限同步演示脚本

演示客户端权限变更的轮询检测和实时同步机制：
- 模拟客户端权限变更
- 轮询检测变更
- 实时同步到服务器
- 同步状态监控
"""

import time
import threading
import random
from datetime import datetime
from app import create_app
from app.core.extensions import db
from app.core.permission_sync import get_sync_manager, PermissionChange, SyncStatus
from app.core.permission_polling import get_permission_poller, get_conflict_detector
from app.core.permission_business_flow import (
    PermissionRequest,
    ResourceType,
    PermissionLevel,
)
from app.core.demo_data_setup import get_demo_data_setup


def demonstrate_permission_sync():
    """演示权限同步机制"""
    print("🔄 权限同步机制演示")
    print("=" * 50)

    # 创建应用上下文
    app = create_app("mysql_testing")

    with app.app_context():
        # 初始化数据库
        db.drop_all()
        db.create_all()
        demo_setup = get_demo_data_setup()
        demo_setup.setup_demo_data()

        # 获取同步管理器
        sync_manager = get_sync_manager(app)
        poller = get_permission_poller(app)
        conflict_detector = get_conflict_detector()

        print("📊 初始同步状态:")
        print_sync_status(sync_manager, poller)

        # 模拟客户端权限变更
        print("\n🎭 模拟客户端权限变更...")
        simulate_client_permission_changes(sync_manager)

        # 等待同步
        print("\n⏳ 等待权限同步...")
        time.sleep(35)  # 等待同步线程处理

        print("\n📊 同步后的状态:")
        print_sync_status(sync_manager, poller)

        # 演示轮询检测
        print("\n🔍 演示轮询检测机制...")
        demonstrate_polling_detection(poller)

        # 演示冲突检测
        print("\n⚠️ 演示权限冲突检测...")
        demonstrate_conflict_detection(conflict_detector)

        # 演示实时监控
        print("\n📈 演示实时监控...")
        demonstrate_real_time_monitoring(sync_manager, poller)

        # 清理
        sync_manager.stop()
        poller.stop()


def simulate_client_permission_changes(sync_manager):
    """模拟客户端权限变更"""
    changes = [
        {
            "user_id": "alice",
            "permission_name": "manage_channel",
            "resource_type": "channel",
            "resource_id": "1",
            "old_value": False,
            "new_value": True,
            "change_type": "grant",
            "source": "client",
        },
        {
            "user_id": "bob",
            "permission_name": "send_message",
            "resource_type": "channel",
            "resource_id": "1",
            "old_value": True,
            "new_value": False,
            "change_type": "revoke",
            "source": "client",
        },
        {
            "user_id": "charlie",
            "permission_name": "manage_server",
            "resource_type": "server",
            "resource_id": "1",
            "old_value": False,
            "new_value": True,
            "change_type": "grant",
            "source": "client",
        },
        {
            "user_id": "diana",
            "permission_name": "read_channel",
            "resource_type": "channel",
            "resource_id": "2",
            "old_value": True,
            "new_value": False,
            "change_type": "revoke",
            "source": "client",
        },
    ]

    for i, change_data in enumerate(changes):
        change = PermissionChange(
            user_id=change_data["user_id"],
            permission_name=change_data["permission_name"],
            resource_type=change_data["resource_type"],
            resource_id=change_data["resource_id"],
            old_value=change_data["old_value"],
            new_value=change_data["new_value"],
            change_type=change_data["change_type"],
            timestamp=time.time() + i,  # 递增时间戳
            source=change_data["source"],
            sync_status=SyncStatus.PENDING,
        )

        sync_manager.add_permission_change(change)
        print(
            f"  ✅ 添加变更: {change.user_id} -> {change.permission_name} ({change.change_type})"
        )
        time.sleep(1)  # 模拟时间间隔


def demonstrate_polling_detection(poller):
    """演示轮询检测机制"""
    print("  🔄 启动轮询检测...")

    # 模拟权限变更检测
    for i in range(3):
        print(f"  📡 轮询检查 #{i+1}...")
        time.sleep(5)

        status = poller.get_polling_status()
        print(f"     - 总检查次数: {status['stats']['total_checks']}")
        print(f"     - 检测到变更: {status['stats']['changes_detected']}")
        print(f"     - 平均检查时间: {status['avg_check_time']}")
        print(f"     - 监控用户数: {status['monitored_users']}")


def demonstrate_conflict_detection(conflict_detector):
    """演示权限冲突检测"""
    print("  🔍 检测权限冲突...")

    # 模拟冲突的权限组合
    conflict_scenarios = [
        {
            "name": "管理员与普通用户权限冲突",
            "permissions": {"admin": True, "user": True, "read": True},
        },
        {
            "name": "读写权限冲突",
            "permissions": {"read": True, "write": True, "manage": False},
        },
        {
            "name": "管理权限冲突",
            "permissions": {"manage": True, "view": True, "admin": False},
        },
    ]

    for scenario in conflict_scenarios:
        print(f"  📋 场景: {scenario['name']}")
        print(f"     权限: {scenario['permissions']}")

        conflicts = conflict_detector.detect_conflicts(scenario["permissions"])
        if conflicts:
            print(f"     ⚠️ 检测到 {len(conflicts)} 个冲突:")
            for conflict in conflicts:
                print(
                    f"        - {conflict['rule']}: {conflict['conflicting_permissions']} (严重性: {conflict['severity']})"
                )

            # 解决冲突
            resolved = conflict_detector.resolve_conflicts(conflicts)
            print(f"     ✅ 解决后的权限: {resolved}")
        else:
            print("     ✅ 无冲突")
        print()


def demonstrate_real_time_monitoring(sync_manager, poller):
    """演示实时监控"""
    print("  📊 实时监控面板...")

    def monitor_callback(changes):
        print(f"  🔔 检测到 {len(changes)} 个权限变更")
        for change in changes:
            print(
                f"     - {change['user_id']} -> {change['permission_name']} ({change['change_type']})"
            )

    def sync_callback(successful, failed):
        print(f"  ✅ 同步完成: 成功 {len(successful)} 个，失败 {len(failed)} 个")
        if failed:
            print("     ❌ 失败的变更:")
            for change in failed:
                print(f"        - {change.user_id} -> {change.permission_name}")

    # 设置回调
    poller.on_permission_change = monitor_callback
    sync_manager.on_sync_complete = sync_callback

    # 模拟实时监控
    for i in range(5):
        print(f"  📈 监控周期 #{i+1}...")

        sync_status = sync_manager.get_sync_status()
        polling_status = poller.get_polling_status()

        print(f"     📊 同步状态:")
        print(f"        - 待同步: {sync_status['pending_count']}")
        print(f"        - 已同步: {sync_status['synced_count']}")
        print(f"        - 失败: {sync_status['failed_count']}")
        print(f"        - 平均同步时间: {sync_status['avg_sync_time']}")

        print(f"     🔍 轮询状态:")
        print(f"        - 检查次数: {polling_status['stats']['total_checks']}")
        print(f"        - 检测到变更: {polling_status['stats']['changes_detected']}")
        print(f"        - 监控用户: {polling_status['monitored_users']}")

        time.sleep(3)


def print_sync_status(sync_manager, poller):
    """打印同步状态"""
    sync_status = sync_manager.get_sync_status()
    polling_status = poller.get_polling_status()

    print(f"📊 同步管理器状态:")
    print(f"  - 总同步次数: {sync_status['stats']['total_syncs']}")
    print(f"  - 成功同步: {sync_status['stats']['successful_syncs']}")
    print(f"  - 失败同步: {sync_status['stats']['failed_syncs']}")
    print(f"  - 待处理变更: {sync_status['pending_count']}")
    print(f"  - 最后同步时间: {sync_status['last_sync_time']}")
    print(f"  - 平均同步时间: {sync_status['avg_sync_time']}")

    print(f"\n🔍 轮询器状态:")
    print(f"  - 总检查次数: {polling_status['stats']['total_checks']}")
    print(f"  - 检测到变更: {polling_status['stats']['changes_detected']}")
    print(f"  - 最后检查时间: {polling_status['last_check_time']}")
    print(f"  - 平均检查时间: {polling_status['avg_check_time']}")
    print(f"  - 监控用户数: {polling_status['monitored_users']}")


def demonstrate_sync_performance():
    """演示同步性能"""
    print("\n🚀 同步性能测试")
    print("=" * 50)

    app = create_app("mysql_testing")

    with app.app_context():
        db.drop_all()
        db.create_all()
        demo_setup = get_demo_data_setup()
        demo_setup.setup_demo_data()

        sync_manager = get_sync_manager(app)

        # 批量添加权限变更
        print("📦 批量添加权限变更...")
        start_time = time.time()

        for i in range(100):
            change = PermissionChange(
                user_id=f"user_{i % 10}",
                permission_name=f"permission_{i % 5}",
                resource_type="channel",
                resource_id=str(i % 3),
                old_value=False,
                new_value=True,
                change_type="grant",
                timestamp=time.time() + i,
                source="client",
                sync_status=SyncStatus.PENDING,
            )
            sync_manager.add_permission_change(change)

        add_time = time.time() - start_time
        print(f"  ✅ 添加 100 个变更耗时: {add_time:.3f}s")

        # 等待同步完成
        print("⏳ 等待同步完成...")
        while sync_manager.pending_changes:
            time.sleep(1)

        sync_time = time.time() - start_time
        print(f"  ✅ 总同步耗时: {sync_time:.3f}s")

        # 性能统计
        stats = sync_manager.get_sync_status()
        print(f"  📊 性能统计:")
        print(f"     - 总同步次数: {stats['stats']['total_syncs']}")
        print(f"     - 成功同步: {stats['stats']['successful_syncs']}")
        print(f"     - 失败同步: {stats['stats']['failed_syncs']}")
        print(f"     - 平均同步时间: {stats['avg_sync_time']}")

        sync_manager.stop()


def demonstrate_sync_reliability():
    """演示同步可靠性"""
    print("\n🛡️ 同步可靠性测试")
    print("=" * 50)

    app = create_app("mysql_testing")

    with app.app_context():
        db.drop_all()
        db.create_all()
        demo_setup = get_demo_data_setup()
        demo_setup.setup_demo_data()

        sync_manager = get_sync_manager(app)

        # 模拟各种异常情况
        print("🔧 模拟异常情况...")

        # 1. 模拟网络中断
        print("  📡 模拟网络中断...")
        time.sleep(2)

        # 2. 模拟数据库连接失败
        print("  🗄️ 模拟数据库连接失败...")
        time.sleep(2)

        # 3. 模拟权限冲突
        print("  ⚠️ 模拟权限冲突...")
        time.sleep(2)

        # 检查恢复能力
        print("  🔄 检查恢复能力...")
        time.sleep(5)

        stats = sync_manager.get_sync_status()
        print(f"  📊 可靠性统计:")
        print(f"     - 失败同步: {stats['stats']['failed_syncs']}")
        print(
            f"     - 重试次数: {stats['stats']['total_syncs'] - stats['stats']['successful_syncs']}"
        )

        sync_manager.stop()


if __name__ == "__main__":
    print("🔄 权限同步系统演示")
    print("=" * 60)

    try:
        # 基础演示
        demonstrate_permission_sync()

        # 性能测试
        demonstrate_sync_performance()

        # 可靠性测试
        demonstrate_sync_reliability()

        print("\n✅ 所有演示完成!")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
