"""
缓存性能测试演示

展示不同级别权限的缓存效果和命中率
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


def demonstrate_cache_performance():
    """演示缓存性能"""
    print_separator("缓存性能测试演示")

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

        # 演示1: 基础权限缓存测试
        demonstrate_basic_cache_test(flow)

        # 演示2: 标准权限缓存测试
        demonstrate_standard_cache_test(flow)

        # 演示3: 混合权限缓存测试
        demonstrate_mixed_cache_test(flow)

        # 演示4: 缓存统计报告
        demonstrate_cache_statistics(flow)


def demonstrate_basic_cache_test(flow: PermissionBusinessFlow):
    """演示基础权限缓存测试"""
    print_section("1. 基础权限缓存测试")

    # 基础权限测试用例
    basic_permissions = [
        ("alice", "read", ResourceType.SERVER, "server_001"),
        ("bob", "read", ResourceType.CHANNEL, "channel_001"),
        ("charlie", "read", ResourceType.SERVER, "server_002"),
    ]

    print("基础权限特点：可以完全在客户端验证和缓存")
    print("测试策略：重复访问相同权限，观察缓存命中")
    print()

    # 第一轮：初始访问
    print("第一轮访问（缓存未命中）：")
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        basic_permissions
    ):
        request = PermissionRequest(
            request_id=f"basic_first_{i}",
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

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 第二轮：重复访问（应该命中缓存）
    print("\n第二轮访问（应该命中缓存）：")
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        basic_permissions
    ):
        request = PermissionRequest(
            request_id=f"basic_second_{i}",
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

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )


def demonstrate_standard_cache_test(flow: PermissionBusinessFlow):
    """演示标准权限缓存测试"""
    print_section("2. 标准权限缓存测试")

    # 标准权限测试用例
    standard_permissions = [
        ("alice", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("bob", "edit_message", ResourceType.CHANNEL, "channel_002"),
        ("charlie", "react_message", ResourceType.CHANNEL, "channel_001"),
    ]

    print("标准权限特点：首次服务器验证，后续可缓存")
    print("测试策略：重复访问相同权限，观察缓存效果")
    print()

    # 第一轮：初始访问（服务器验证）
    print("第一轮访问（服务器验证）：")
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        standard_permissions
    ):
        request = PermissionRequest(
            request_id=f"standard_first_{i}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            permission_level=PermissionLevel.WRITE,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 第二轮：重复访问（应该命中缓存）
    print("\n第二轮访问（应该命中缓存）：")
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        standard_permissions
    ):
        request = PermissionRequest(
            request_id=f"standard_second_{i}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            permission_level=PermissionLevel.WRITE,
            timestamp=time.time(),
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )


def demonstrate_mixed_cache_test(flow: PermissionBusinessFlow):
    """演示混合权限缓存测试"""
    print_section("3. 混合权限缓存测试")

    # 混合权限测试用例
    mixed_permissions = [
        # 基础权限
        ("alice", "read", ResourceType.SERVER, "server_001"),
        ("bob", "read", ResourceType.CHANNEL, "channel_001"),
        # 标准权限
        ("alice", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("bob", "edit_message", ResourceType.CHANNEL, "channel_002"),
        # 高级权限
        ("admin", "manage_channel", ResourceType.CHANNEL, "channel_001"),
        ("admin", "manage_role", ResourceType.SERVER, "server_001"),
        # 关键权限
        ("superadmin", "manage_server", ResourceType.SERVER, "server_001"),
        ("superadmin", "delete_server", ResourceType.SERVER, "server_001"),
    ]

    print("混合权限测试：不同级别权限的缓存效果对比")
    print()

    # 第一轮：初始访问
    print("第一轮访问（初始验证）：")
    first_round_times = []
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        mixed_permissions
    ):
        request = PermissionRequest(
            request_id=f"mixed_first_{i}",
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
        first_round_times.append(response_time)

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 第二轮：重复访问
    print("\n第二轮访问（缓存测试）：")
    second_round_times = []
    cache_hits = 0
    for i, (user_id, action, resource_type, resource_id) in enumerate(
        mixed_permissions
    ):
        request = PermissionRequest(
            request_id=f"mixed_second_{i}",
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
        second_round_times.append(response_time)

        if result.cached:
            cache_hits += 1

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 性能对比
    print("\n性能对比：")
    avg_first = sum(first_round_times) / len(first_round_times)
    avg_second = sum(second_round_times) / len(second_round_times)
    improvement = (avg_first - avg_second) / avg_first * 100

    print(f"  第一轮平均响应时间: {avg_first:.4f}s")
    print(f"  第二轮平均响应时间: {avg_second:.4f}s")
    print(f"  性能提升: {improvement:.1f}%")
    print(
        f"  缓存命中率: {cache_hits}/{len(mixed_permissions)} ({cache_hits/len(mixed_permissions)*100:.1f}%)"
    )


def demonstrate_cache_statistics(flow: PermissionBusinessFlow):
    """演示缓存统计报告"""
    print_section("4. 缓存统计报告")

    # 获取分级验证统计
    tier_stats = flow.get_tiered_validation_stats()

    print("验证统计:")
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

    # 获取缓存统计
    cache_stats = flow.tiered_validator.get_cache_stats()
    print(f"\n缓存统计:")
    print(f"  总缓存条目: {cache_stats['total_cache']}")
    print(f"  有效缓存: {cache_stats['valid_cache']}")
    print(f"  过期缓存: {cache_stats['expired_cache']}")
    print(f"  缓存命中率: {cache_stats['cache_hit_rate']*100:.1f}%")

    print("\n权限级别缓存策略:")
    tier_definitions = tier_stats["tier_definitions"]
    for tier_name, tier_info in tier_definitions.items():
        config = tier_info["config"]
        print(f"  {tier_name}:")
        print(f"    客户端缓存: {'启用' if config['client_cache_enabled'] else '禁用'}")
        print(
            f"    服务器验证: {'必需' if config['server_validation_required'] else '可选'}"
        )
        print(f"    缓存TTL: {config['cache_ttl']}秒")


if __name__ == "__main__":
    print("🚀 缓存性能测试演示")
    print("本演示展示不同级别权限的缓存效果和性能提升")

    try:
        demonstrate_cache_performance()

        print("\n✅ 缓存性能测试完成！")
        print("\n缓存优化的效果:")
        print("1. 基础权限：完全客户端缓存，极速响应")
        print("2. 标准权限：首次服务器验证，后续缓存")
        print("3. 高级权限：每次服务器验证，保证安全")
        print("4. 关键权限：强制服务器验证，最高安全")
        print("\n通过分层缓存策略，既保证了性能，又确保了安全性！")

    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
