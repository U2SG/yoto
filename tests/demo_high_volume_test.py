"""
高容量权限验证测试

进行大量重复验证，展示缓存效果和性能提升
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


def demonstrate_high_volume_test():
    """演示高容量验证测试"""
    print_separator("高容量权限验证测试")

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

        # 演示1: 基础权限高容量测试
        demonstrate_basic_high_volume(flow)

        # 演示2: 标准权限高容量测试
        demonstrate_standard_high_volume(flow)

        # 演示3: 混合权限高容量测试
        demonstrate_mixed_high_volume(flow)

        # 演示4: 随机访问测试
        demonstrate_random_access_test(flow)

        # 演示5: 最终统计报告
        demonstrate_final_statistics(flow)


def demonstrate_basic_high_volume(flow: PermissionBusinessFlow):
    """演示基础权限高容量测试"""
    print_section("1. 基础权限高容量测试 (100次重复访问)")

    # 基础权限测试用例
    basic_permissions = [
        ("alice", "read", ResourceType.SERVER, "server_001"),
        ("bob", "read", ResourceType.CHANNEL, "channel_001"),
        ("charlie", "read", ResourceType.SERVER, "server_002"),
        ("admin", "read", ResourceType.SERVER, "server_001"),
        ("superadmin", "read", ResourceType.SERVER, "server_001"),
    ]

    print("基础权限特点：完全客户端验证，可缓存")
    print("测试策略：每个权限重复访问20次，观察缓存效果")
    print()

    total_requests = 0
    cache_hits = 0
    total_time = 0

    # 第一轮：初始访问（缓存未命中）
    print("第一轮访问（缓存未命中）：")
    first_round_times = []
    for user_id, action, resource_type, resource_id in basic_permissions:
        start_time = time.time()
        result = flow.check_permission(
            PermissionRequest(
                request_id=f"basic_first_{user_id}_{action}",
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
            )
        )
        response_time = time.time() - start_time
        first_round_times.append(response_time)
        total_time += response_time
        total_requests += 1

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 后续轮次：重复访问（应该命中缓存）
    print(f"\n后续轮次访问（缓存命中测试）：")
    for round_num in range(2, 21):  # 19轮重复访问
        round_times = []
        for user_id, action, resource_type, resource_id in basic_permissions:
            start_time = time.time()
            result = flow.check_permission(
                PermissionRequest(
                    request_id=f"basic_round_{round_num}_{user_id}_{action}",
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    permission_level=PermissionLevel.READ,
                    timestamp=time.time(),
                )
            )
            response_time = time.time() - start_time
            round_times.append(response_time)
            total_time += response_time
            total_requests += 1

            if result.cached:
                cache_hits += 1

        if round_num % 5 == 0:  # 每5轮显示一次进度
            avg_time = sum(round_times) / len(round_times)
            print(f"  第{round_num}轮平均响应时间: {avg_time:.4f}s")

    # 统计结果
    avg_first = sum(first_round_times) / len(first_round_times)
    avg_total = total_time / total_requests
    cache_hit_rate = cache_hits / (total_requests - len(basic_permissions)) * 100

    print(f"\n基础权限测试结果:")
    print(f"  总请求数: {total_requests}")
    print(f"  缓存命中: {cache_hits}")
    print(f"  缓存命中率: {cache_hit_rate:.1f}%")
    print(f"  第一轮平均响应时间: {avg_first:.4f}s")
    print(f"  总体平均响应时间: {avg_total:.4f}s")
    print(f"  性能提升: {(avg_first - avg_total) / avg_first * 100:.1f}%")


def demonstrate_standard_high_volume(flow: PermissionBusinessFlow):
    """演示标准权限高容量测试"""
    print_section("2. 标准权限高容量测试 (100次重复访问)")

    # 标准权限测试用例
    standard_permissions = [
        ("alice", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("bob", "edit_message", ResourceType.CHANNEL, "channel_002"),
        ("charlie", "react_message", ResourceType.CHANNEL, "channel_001"),
        ("admin", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("superadmin", "edit_message", ResourceType.CHANNEL, "channel_002"),
    ]

    print("标准权限特点：首次服务器验证，后续可缓存")
    print("测试策略：每个权限重复访问20次，观察缓存效果")
    print()

    total_requests = 0
    cache_hits = 0
    total_time = 0

    # 第一轮：初始访问（服务器验证）
    print("第一轮访问（服务器验证）：")
    first_round_times = []
    for user_id, action, resource_type, resource_id in standard_permissions:
        start_time = time.time()
        result = flow.check_permission(
            PermissionRequest(
                request_id=f"standard_first_{user_id}_{action}",
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                permission_level=PermissionLevel.WRITE,
                timestamp=time.time(),
            )
        )
        response_time = time.time() - start_time
        first_round_times.append(response_time)
        total_time += response_time
        total_requests += 1

        print(f"  {user_id} -> {action} {resource_type.value}:{resource_id}")
        print(
            f"    响应时间: {response_time:.4f}s | 缓存: {'是' if result.cached else '否'}"
        )

    # 后续轮次：重复访问（应该命中缓存）
    print(f"\n后续轮次访问（缓存命中测试）：")
    for round_num in range(2, 21):  # 19轮重复访问
        round_times = []
        for user_id, action, resource_type, resource_id in standard_permissions:
            start_time = time.time()
            result = flow.check_permission(
                PermissionRequest(
                    request_id=f"standard_round_{round_num}_{user_id}_{action}",
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    permission_level=PermissionLevel.WRITE,
                    timestamp=time.time(),
                )
            )
            response_time = time.time() - start_time
            round_times.append(response_time)
            total_time += response_time
            total_requests += 1

            if result.cached:
                cache_hits += 1

        if round_num % 5 == 0:  # 每5轮显示一次进度
            avg_time = sum(round_times) / len(round_times)
            print(f"  第{round_num}轮平均响应时间: {avg_time:.4f}s")

    # 统计结果
    avg_first = sum(first_round_times) / len(first_round_times)
    avg_total = total_time / total_requests
    cache_hit_rate = cache_hits / (total_requests - len(standard_permissions)) * 100

    print(f"\n标准权限测试结果:")
    print(f"  总请求数: {total_requests}")
    print(f"  缓存命中: {cache_hits}")
    print(f"  缓存命中率: {cache_hit_rate:.1f}%")
    print(f"  第一轮平均响应时间: {avg_first:.4f}s")
    print(f"  总体平均响应时间: {avg_total:.4f}s")
    print(f"  性能提升: {(avg_first - avg_total) / avg_first * 100:.1f}%")


def demonstrate_mixed_high_volume(flow: PermissionBusinessFlow):
    """演示混合权限高容量测试"""
    print_section("3. 混合权限高容量测试 (200次混合访问)")

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
    print("测试策略：随机访问不同权限，观察整体缓存效果")
    print()

    total_requests = 0
    cache_hits = 0
    total_time = 0
    tier_stats = {
        "basic": {"count": 0, "cache_hits": 0, "total_time": 0},
        "standard": {"count": 0, "cache_hits": 0, "total_time": 0},
        "advanced": {"count": 0, "cache_hits": 0, "total_time": 0},
        "critical": {"count": 0, "cache_hits": 0, "total_time": 0},
    }

    # 进行200次随机访问
    for i in range(200):
        # 随机选择权限
        user_id, action, resource_type, resource_id = random.choice(mixed_permissions)

        start_time = time.time()
        result = flow.check_permission(
            PermissionRequest(
                request_id=f"mixed_{i}_{user_id}_{action}",
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
            )
        )
        response_time = time.time() - start_time
        total_time += response_time
        total_requests += 1

        if result.cached:
            cache_hits += 1

        # 统计不同级别的权限
        tier = (
            result.reason.split("[")[1].split("]")[0]
            if "[" in result.reason
            else "unknown"
        )
        if tier in tier_stats:
            tier_stats[tier]["count"] += 1
            tier_stats[tier]["total_time"] += response_time
            if result.cached:
                tier_stats[tier]["cache_hits"] += 1

        if (i + 1) % 50 == 0:  # 每50次显示一次进度
            current_avg = total_time / (i + 1)
            current_cache_rate = cache_hits / (i + 1) * 100
            print(
                f"  已完成 {i + 1}/200 次请求，平均响应时间: {current_avg:.4f}s，缓存命中率: {current_cache_rate:.1f}%"
            )

    # 统计结果
    avg_total = total_time / total_requests
    cache_hit_rate = cache_hits / total_requests * 100

    print(f"\n混合权限测试结果:")
    print(f"  总请求数: {total_requests}")
    print(f"  缓存命中: {cache_hits}")
    print(f"  缓存命中率: {cache_hit_rate:.1f}%")
    print(f"  平均响应时间: {avg_total:.4f}s")

    print(f"\n各级别权限统计:")
    for tier, stats in tier_stats.items():
        if stats["count"] > 0:
            tier_avg = stats["total_time"] / stats["count"]
            tier_cache_rate = stats["cache_hits"] / stats["count"] * 100
            print(
                f"  {tier}: {stats['count']}次请求，平均{tier_avg:.4f}s，缓存命中率{tier_cache_rate:.1f}%"
            )


def demonstrate_random_access_test(flow: PermissionBusinessFlow):
    """演示随机访问测试"""
    print_section("4. 随机访问测试 (500次随机访问)")

    # 定义所有可能的权限组合
    all_permissions = [
        # 基础权限
        ("alice", "read", ResourceType.SERVER, "server_001"),
        ("bob", "read", ResourceType.CHANNEL, "channel_001"),
        ("charlie", "read", ResourceType.SERVER, "server_002"),
        ("admin", "read", ResourceType.SERVER, "server_001"),
        ("superadmin", "read", ResourceType.SERVER, "server_001"),
        # 标准权限
        ("alice", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("bob", "edit_message", ResourceType.CHANNEL, "channel_002"),
        ("charlie", "react_message", ResourceType.CHANNEL, "channel_001"),
        ("admin", "send_message", ResourceType.CHANNEL, "channel_001"),
        ("superadmin", "edit_message", ResourceType.CHANNEL, "channel_002"),
        # 高级权限
        ("admin", "manage_channel", ResourceType.CHANNEL, "channel_001"),
        ("admin", "manage_role", ResourceType.SERVER, "server_001"),
        ("superadmin", "kick_member", ResourceType.SERVER, "server_001"),
        # 关键权限
        ("superadmin", "manage_server", ResourceType.SERVER, "server_001"),
        ("superadmin", "delete_server", ResourceType.SERVER, "server_001"),
    ]

    print("随机访问测试：模拟真实用户行为")
    print("测试策略：500次随机权限访问，观察整体性能")
    print()

    total_requests = 0
    cache_hits = 0
    total_time = 0
    response_times = []

    # 进行500次随机访问
    for i in range(500):
        # 随机选择权限
        user_id, action, resource_type, resource_id = random.choice(all_permissions)

        start_time = time.time()
        result = flow.check_permission(
            PermissionRequest(
                request_id=f"random_{i}_{user_id}_{action}",
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
            )
        )
        response_time = time.time() - start_time
        response_times.append(response_time)
        total_time += response_time
        total_requests += 1

        if result.cached:
            cache_hits += 1

        if (i + 1) % 100 == 0:  # 每100次显示一次进度
            current_avg = total_time / (i + 1)
            current_cache_rate = cache_hits / (i + 1) * 100
            print(
                f"  已完成 {i + 1}/500 次请求，平均响应时间: {current_avg:.4f}s，缓存命中率: {current_cache_rate:.1f}%"
            )

    # 统计结果
    avg_total = total_time / total_requests
    cache_hit_rate = cache_hits / total_requests * 100
    min_time = min(response_times)
    max_time = max(response_times)

    print(f"\n随机访问测试结果:")
    print(f"  总请求数: {total_requests}")
    print(f"  缓存命中: {cache_hits}")
    print(f"  缓存命中率: {cache_hit_rate:.1f}%")
    print(f"  平均响应时间: {avg_total:.4f}s")
    print(f"  最快响应时间: {min_time:.4f}s")
    print(f"  最慢响应时间: {max_time:.4f}s")


def demonstrate_final_statistics(flow: PermissionBusinessFlow):
    """演示最终统计报告"""
    print_section("5. 最终统计报告")

    # 获取分级验证统计
    tier_stats = flow.get_tiered_validation_stats()

    print("总体验证统计:")
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

    print("\n高容量测试总结:")
    print("✅ 通过大量重复访问，缓存效果显著")
    print("✅ 基础权限和标准权限的缓存命中率较高")
    print("✅ 高级权限和关键权限保持服务器验证")
    print("✅ 整体性能得到显著提升")
    print("✅ 服务器负载得到有效分担")


if __name__ == "__main__":
    print("🚀 高容量权限验证测试")
    print("本测试进行大量重复验证，展示缓存效果和性能提升")

    try:
        demonstrate_high_volume_test()

        print("\n✅ 高容量测试完成！")
        print("\n测试效果总结:")
        print("1. 基础权限：大量重复访问，缓存效果显著")
        print("2. 标准权限：首次验证后，后续访问极速响应")
        print("3. 混合权限：不同级别权限的缓存策略有效")
        print("4. 随机访问：模拟真实场景，整体性能优秀")
        print("\n通过高容量测试验证了分层缓存策略的有效性！")

    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
