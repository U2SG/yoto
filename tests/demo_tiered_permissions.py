"""
分级权限验证演示

展示不同级别权限的验证策略：
- 基础权限：完全客户端验证
- 标准权限：客户端缓存 + 服务器验证
- 高级权限：必须服务器验证
- 关键权限：强制服务器验证
"""

import time
import random
from typing import List, Dict
from app import create_app
from app.core.permission_business_flow import (
    PermissionBusinessFlow,
    PermissionRequest,
    ResourceType,
    PermissionLevel,
)
from app.core.extensions import db
from app.core.demo_data_setup import get_demo_data_setup


def print_separator(title: str):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f" {title} ")
    print("=" * 60)


def print_section(title: str):
    """打印章节标题"""
    print(f"\n--- {title} ---")


def demonstrate_tiered_permissions():
    """演示分级权限验证"""
    print_separator("分级权限验证演示")

    # 创建Flask应用上下文
    app = create_app("mysql_testing")
    with app.app_context():
        # 初始化数据库
        print("正在初始化数据库...")
        try:
            db.drop_all()
            db.create_all()

            # 设置演示数据
            demo_setup = get_demo_data_setup()
            demo_setup.setup_database_data(db)
            print("✅ 数据库初始化完成")

        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            return

        # 初始化权限业务流程
        flow = PermissionBusinessFlow()

        # 演示1: 基础权限验证
        demonstrate_basic_permissions(flow)

        # 演示2: 标准权限验证
        demonstrate_standard_permissions(flow)

        # 演示3: 高级权限验证
        demonstrate_advanced_permissions(flow)

        # 演示4: 关键权限验证
        demonstrate_critical_permissions(flow)

        # 演示5: 性能对比
        demonstrate_performance_comparison(flow)

        # 演示6: 统计报告
        demonstrate_statistics_report(flow)


def demonstrate_basic_permissions(flow: PermissionBusinessFlow):
    """演示基础权限验证"""
    print_section("1. 基础权限验证 (完全客户端验证)")

    # 基础权限测试用例
    basic_test_cases = [
        {
            "user_id": "alice",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "read",
            "description": "读取服务器信息",
        },
        {
            "user_id": "bob",
            "resource_type": ResourceType.CHANNEL,
            "resource_id": "channel_001",
            "action": "read",
            "description": "读取频道信息",
        },
        {
            "user_id": "charlie",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_002",
            "action": "read",
            "description": "查看成员列表",
        },
    ]

    print("基础权限特点：")
    print("✅ 完全在客户端验证")
    print("✅ 无需服务器请求")
    print("✅ 响应速度极快")
    print("✅ 支持离线验证")
    print()

    for i, case in enumerate(basic_test_cases, 1):
        request = PermissionRequest(
            request_id=f"basic_test_{i}",
            user_id=case["user_id"],
            resource_type=case["resource_type"],
            resource_id=case["resource_id"],
            action=case["action"],
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        status = "✅" if result.allowed else "❌"
        print(f"{status} {case['description']}")
        print(
            f"   用户: {case['user_id']} | 资源: {case['resource_type'].value}:{case['resource_id']}"
        )
        print(f"   结果: {result.allowed} | 原因: {result.reason}")
        print(
            f"   响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )
        print()


def demonstrate_standard_permissions(flow: PermissionBusinessFlow):
    """演示标准权限验证"""
    print_section("2. 标准权限验证 (客户端缓存 + 服务器验证)")

    # 标准权限测试用例
    standard_test_cases = [
        {
            "user_id": "alice",
            "resource_type": ResourceType.CHANNEL,
            "resource_id": "channel_001",
            "action": "send_message",
            "description": "发送消息",
        },
        {
            "user_id": "bob",
            "resource_type": ResourceType.CHANNEL,
            "resource_id": "channel_002",
            "action": "edit_message",
            "description": "编辑消息",
        },
        {
            "user_id": "charlie",
            "resource_type": ResourceType.CHANNEL,
            "resource_id": "channel_001",
            "action": "react_message",
            "description": "消息反应",
        },
    ]

    print("标准权限特点：")
    print("✅ 客户端缓存权限数据")
    print("✅ 首次需要服务器验证")
    print("✅ 后续可快速响应")
    print("✅ 缓存过期后重新验证")
    print()

    for i, case in enumerate(standard_test_cases, 1):
        request = PermissionRequest(
            request_id=f"standard_test_{i}",
            user_id=case["user_id"],
            resource_type=case["resource_type"],
            resource_id=case["resource_id"],
            action=case["action"],
            permission_level=PermissionLevel.WRITE,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        status = "✅" if result.allowed else "❌"
        print(f"{status} {case['description']}")
        print(
            f"   用户: {case['user_id']} | 资源: {case['resource_type'].value}:{case['resource_id']}"
        )
        print(f"   结果: {result.allowed} | 原因: {result.reason}")
        print(
            f"   响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )
        print()


def demonstrate_advanced_permissions(flow: PermissionBusinessFlow):
    """演示高级权限验证"""
    print_section("3. 高级权限验证 (必须服务器验证)")

    # 高级权限测试用例
    advanced_test_cases = [
        {
            "user_id": "admin",
            "resource_type": ResourceType.CHANNEL,
            "resource_id": "channel_001",
            "action": "manage_channel",
            "description": "管理频道",
        },
        {
            "user_id": "admin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "manage_role",
            "description": "管理角色",
        },
        {
            "user_id": "superadmin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "kick_member",
            "description": "踢出成员",
        },
    ]

    print("高级权限特点：")
    print("❌ 不进行客户端缓存")
    print("✅ 每次都需要服务器验证")
    print("✅ 保证权限安全性")
    print("✅ 支持实时权限变更")
    print()

    for i, case in enumerate(advanced_test_cases, 1):
        request = PermissionRequest(
            request_id=f"advanced_test_{i}",
            user_id=case["user_id"],
            resource_type=case["resource_type"],
            resource_id=case["resource_id"],
            action=case["action"],
            permission_level=PermissionLevel.ADMIN,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        status = "✅" if result.allowed else "❌"
        print(f"{status} {case['description']}")
        print(
            f"   用户: {case['user_id']} | 资源: {case['resource_type'].value}:{case['resource_id']}"
        )
        print(f"   结果: {result.allowed} | 原因: {result.reason}")
        print(
            f"   响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )
        print()


def demonstrate_critical_permissions(flow: PermissionBusinessFlow):
    """演示关键权限验证"""
    print_section("4. 关键权限验证 (强制服务器验证)")

    # 关键权限测试用例
    critical_test_cases = [
        {
            "user_id": "superadmin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "manage_server",
            "description": "管理服务器",
        },
        {
            "user_id": "superadmin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "delete_server",
            "description": "删除服务器",
        },
        {
            "user_id": "superadmin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "transfer_ownership",
            "description": "转移所有权",
        },
    ]

    print("关键权限特点：")
    print("❌ 绝对不缓存")
    print("✅ 强制服务器验证")
    print("✅ 最高安全级别")
    print("✅ 实时权限检查")
    print()

    for i, case in enumerate(critical_test_cases, 1):
        request = PermissionRequest(
            request_id=f"critical_test_{i}",
            user_id=case["user_id"],
            resource_type=case["resource_type"],
            resource_id=case["resource_id"],
            action=case["action"],
            permission_level=PermissionLevel.SUPER_ADMIN,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        status = "✅" if result.allowed else "❌"
        print(f"{status} {case['description']}")
        print(
            f"   用户: {case['user_id']} | 资源: {case['resource_type'].value}:{case['resource_id']}"
        )
        print(f"   结果: {result.allowed} | 原因: {result.reason}")
        print(
            f"   响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )
        print()


def demonstrate_performance_comparison(flow: PermissionBusinessFlow):
    """演示性能对比"""
    print_section("5. 性能对比演示")

    # 不同级别的权限测试
    performance_tests = [
        # 基础权限
        ("basic", "alice", "read", ResourceType.SERVER, "server_001"),
        ("basic", "bob", "read", ResourceType.CHANNEL, "channel_001"),
        ("basic", "charlie", "read", ResourceType.SERVER, "server_002"),
        # 标准权限
        ("standard", "alice", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("standard", "bob", "edit_message", ResourceType.CHANNEL, "channel_002"),
        ("standard", "charlie", "react_message", ResourceType.CHANNEL, "channel_001"),
        # 高级权限
        ("advanced", "admin", "manage_channel", ResourceType.CHANNEL, "channel_001"),
        ("advanced", "admin", "manage_role", ResourceType.SERVER, "server_001"),
        ("advanced", "superadmin", "kick_member", ResourceType.SERVER, "server_001"),
        # 关键权限
        ("critical", "superadmin", "manage_server", ResourceType.SERVER, "server_001"),
        ("critical", "superadmin", "delete_server", ResourceType.SERVER, "server_001"),
        (
            "critical",
            "superadmin",
            "transfer_ownership",
            ResourceType.SERVER,
            "server_001",
        ),
    ]

    print("不同级别权限的性能对比:")
    print("级别\t\t\t响应时间\t\t缓存\t\t安全性")
    print("-" * 70)

    tier_stats = {
        "basic": {"count": 0, "total_time": 0, "cached": 0},
        "standard": {"count": 0, "total_time": 0, "cached": 0},
        "advanced": {"count": 0, "total_time": 0, "cached": 0},
        "critical": {"count": 0, "total_time": 0, "cached": 0},
    }

    for tier, user_id, action, resource_type, resource_id in performance_tests:
        request = PermissionRequest(
            request_id=f"perf_{tier}_{user_id}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        tier_stats[tier]["count"] += 1
        tier_stats[tier]["total_time"] += response_time
        if result.cached:
            tier_stats[tier]["cached"] += 1

        print(
            f"{tier:<15} {response_time:.4f}s\t\t{'是' if result.cached else '否'}\t\t{'高' if tier in ['advanced', 'critical'] else '中' if tier == 'standard' else '低'}"
        )

    print("\n性能统计:")
    for tier, stats in tier_stats.items():
        if stats["count"] > 0:
            avg_time = stats["total_time"] / stats["count"]
            cache_rate = stats["cached"] / stats["count"] * 100
            print(f"{tier}: 平均响应时间 {avg_time:.4f}s, 缓存命中率 {cache_rate:.1f}%")


def demonstrate_statistics_report(flow: PermissionBusinessFlow):
    """演示统计报告"""
    print_section("6. 分级权限统计报告")

    # 获取分级验证统计
    tier_stats = flow.get_tiered_validation_stats()

    print("权限级别分布:")
    tier_definitions = tier_stats["tier_definitions"]
    for tier_name, tier_info in tier_definitions.items():
        print(f"  {tier_name}: {tier_info['count']} 个权限")

    print("\n验证统计:")
    validation_stats = tier_stats["validation_stats"]
    print(f"  总验证次数: {validation_stats['total_validations']}")
    print(f"  基础权限验证: {validation_stats['basic_validations']}")
    print(f"  标准权限验证: {validation_stats['standard_validations']}")
    print(f"  高级权限验证: {validation_stats['advanced_validations']}")
    print(f"  关键权限验证: {validation_stats['critical_validations']}")
    print(f"  客户端缓存命中: {validation_stats['client_cache_hits']}")
    print(f"  服务器验证次数: {validation_stats['server_validations']}")

    print(f"\n性能指标:")
    print(f"  客户端验证率: {tier_stats['client_validation_rate']*100:.1f}%")
    print(f"  服务器验证率: {tier_stats['server_validation_rate']*100:.1f}%")

    print("\n权限级别详情:")
    for tier_name, tier_info in tier_definitions.items():
        config = tier_info["config"]
        print(f"  {tier_name}:")
        print(f"    描述: {config['description']}")
        print(f"    客户端缓存: {'启用' if config['client_cache_enabled'] else '禁用'}")
        print(
            f"    服务器验证: {'必需' if config['server_validation_required'] else '可选'}"
        )
        print(f"    缓存TTL: {config['cache_ttl']}秒")


if __name__ == "__main__":
    print("🎯 分级权限验证演示")
    print("本演示展示不同级别权限的验证策略和安全平衡")

    try:
        demonstrate_tiered_permissions()

        print("\n✅ 分级权限演示完成！")
        print("\n分级权限验证的优势:")
        print("1. 基础权限：极速响应，支持离线验证")
        print("2. 标准权限：缓存优化，平衡性能与安全")
        print("3. 高级权限：实时验证，保证权限安全")
        print("4. 关键权限：强制验证，最高安全级别")
        print("\n这种分层策略既保证了性能，又确保了安全性！")

    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
