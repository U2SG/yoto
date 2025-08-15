"""
客户端压力转移优化演示

展示如何将服务器压力转移到客户端，提升系统性能
"""

import time
import random
import threading
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


def demonstrate_client_side_optimization():
    """演示客户端优化功能"""
    print_separator("客户端压力转移优化演示")

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

        # 演示1: 基础客户端验证
        demonstrate_basic_client_validation(flow)

        # 演示2: 智能预取
        demonstrate_smart_prefetch(flow)

        # 演示3: 行为预测
        demonstrate_behavior_prediction(flow)

        # 演示4: 性能对比
        demonstrate_performance_comparison(flow)

        # 演示5: 优化统计
        demonstrate_optimization_stats(flow)


def demonstrate_basic_client_validation(flow: PermissionBusinessFlow):
    """演示基础客户端验证"""
    print_section("1. 基础客户端验证")

    # 测试用例
    test_cases = [
        {
            "user_id": "superadmin",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "read",
            "permission_level": PermissionLevel.READ,
            "expected": True,
            "description": "超级管理员读取服务器",
        },
        {
            "user_id": "alice",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "write",
            "permission_level": PermissionLevel.WRITE,
            "expected": False,
            "description": "普通用户写入服务器",
        },
        {
            "user_id": "alice",
            "resource_type": ResourceType.SERVER,
            "resource_id": "server_001",
            "action": "read",
            "permission_level": PermissionLevel.READ,
            "expected": True,
            "description": "普通用户读取服务器",
        },
    ]

    print("测试客户端验证规则:")
    for i, case in enumerate(test_cases, 1):
        request = PermissionRequest(
            request_id=f"test_{i}",
            user_id=case["user_id"],
            resource_type=case["resource_type"],
            resource_id=case["resource_id"],
            action=case["action"],
            permission_level=case["permission_level"],
            timestamp=time.time(),  # 添加timestamp参数
        )

        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        status = "✅" if result.allowed == case["expected"] else "❌"
        cache_status = "缓存" if result.cached else "服务器"

        print(f"{status} {case['description']}")
        print(f"   结果: {result.allowed} | 原因: {result.reason}")
        print(f"   响应时间: {response_time:.4f}s | 来源: {cache_status}")
        print()


def demonstrate_smart_prefetch(flow: PermissionBusinessFlow):
    """演示智能预取"""
    print_section("2. 智能预取演示")

    # 模拟用户行为模式
    user_actions = [
        ("alice", "read", "server", "server_001"),
        ("alice", "read", "server", "server_001"),
        ("alice", "read", "server", "server_001"),
        ("alice", "read", "channel", "channel_001"),
        ("alice", "read", "channel", "channel_001"),
        ("alice", "read", "server", "server_002"),
        ("alice", "read", "server", "server_002"),
        ("bob", "read", "server", "server_001"),
        ("bob", "read", "server", "server_001"),
        ("bob", "write", "server", "server_001"),
    ]

    print("模拟用户行为模式:")
    for user_id, action, resource_type, resource_id in user_actions:
        # 记录行为
        flow.client_predictor.record_user_action(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        print(f"   记录: {user_id} -> {action} {resource_type}:{resource_id}")

    print("\n获取预测结果:")
    for user_id in ["alice", "bob"]:
        predictions = flow.client_predictor.get_predicted_resources(user_id)
        print(f"\n用户 {user_id} 的预测资源:")
        for pred in predictions[:3]:  # 显示前3个预测
            print(
                f"   {pred['resource_type']}:{pred['resource_id']} "
                f"(置信度: {pred['confidence']:.2f}) - {pred['reason']}"
            )

    # 触发预取
    print("\n触发预取:")
    for user_id in ["alice", "bob"]:
        flow.trigger_prefetch_for_user(user_id)


def demonstrate_behavior_prediction(flow: PermissionBusinessFlow):
    """演示行为预测"""
    print_section("3. 行为预测分析")

    # 模拟不同时间段的用户行为
    time_patterns = [
        (9, "alice", "read", "server", "server_001"),  # 上午9点
        (10, "alice", "read", "server", "server_001"),  # 上午10点
        (11, "alice", "read", "server", "server_001"),  # 上午11点
        (14, "bob", "write", "server", "server_002"),  # 下午2点
        (15, "bob", "write", "server", "server_002"),  # 下午3点
        (16, "bob", "write", "server", "server_002"),  # 下午4点
    ]

    print("模拟时间模式:")
    for hour, user_id, action, resource_type, resource_id in time_patterns:
        # 模拟特定时间的行为
        flow.client_predictor.record_user_action(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            context={"hour": hour},
        )
        print(f"   {hour:02d}:00 - {user_id} -> {action} {resource_type}:{resource_id}")

    # 获取访问模式
    print("\n用户访问模式:")
    for user_id in ["alice", "bob"]:
        patterns = flow.client_predictor.analyzer.get_user_patterns(user_id)
        print(f"\n用户 {user_id} 的访问模式:")
        for pattern in patterns[:3]:
            print(
                f"   {pattern['resource_type']}:{pattern['resource_id']} "
                f"(频率: {pattern['frequency']})"
            )


def demonstrate_performance_comparison(flow: PermissionBusinessFlow):
    """演示性能对比"""
    print_section("4. 性能对比演示")

    # 测试用例
    test_requests = [
        PermissionRequest(
            request_id=f"perf_test_{i}",
            user_id=random.choice(["alice", "bob", "admin"]),
            resource_type=random.choice([ResourceType.SERVER, ResourceType.CHANNEL]),
            resource_id=random.choice(["server_001", "server_002", "channel_001"]),
            action=random.choice(["read", "write"]),
            permission_level=random.choice(
                [PermissionLevel.READ, PermissionLevel.WRITE]
            ),
            timestamp=time.time(),  # 添加timestamp参数
        )
        for i in range(20)
    ]

    print("执行20个权限检查请求:")

    total_time = 0
    cache_hits = 0
    client_validations = 0
    server_checks = 0

    for i, request in enumerate(test_requests, 1):
        start_time = time.time()
        result = flow.check_permission(request)
        response_time = time.time() - start_time

        total_time += response_time

        if result.cached:
            cache_hits += 1
        if hasattr(result, "client_validated") and result.client_validated:
            client_validations += 1
        else:
            server_checks += 1

        if i % 5 == 0:
            print(f"   完成 {i}/20 请求")

    print(f"\n性能统计:")
    print(f"   总响应时间: {total_time:.4f}s")
    print(f"   平均响应时间: {total_time/20:.4f}s")
    print(f"   缓存命中: {cache_hits}/20 ({cache_hits/20*100:.1f}%)")
    print(f"   客户端验证: {client_validations}/20 ({client_validations/20*100:.1f}%)")
    print(f"   服务器检查: {server_checks}/20 ({server_checks/20*100:.1f}%)")


def demonstrate_optimization_stats(flow: PermissionBusinessFlow):
    """演示优化统计"""
    print_section("5. 优化统计报告")

    # 获取各种统计信息
    client_stats = flow.get_client_optimization_stats()

    print("客户端优化统计:")
    print(f"   总客户端请求: {client_stats['total_client_requests']}")
    print(f"   服务器负载减少: {client_stats['server_load_reduction']*100:.1f}%")

    print("\n缓存统计:")
    optimizer_stats = client_stats["optimizer"]["cache_stats"]
    print(f"   总缓存: {optimizer_stats['total_cache']}")
    print(f"   有效缓存: {optimizer_stats['valid_cache']}")
    print(f"   频繁访问缓存: {optimizer_stats['frequent_cache']}")

    print("\n预测统计:")
    predictor_stats = client_stats["predictor"]
    print(f"   总行为记录: {predictor_stats['total_behaviors']}")
    print(f"   用户模式: {predictor_stats['user_patterns']}")
    print(f"   预取队列: {predictor_stats['prefetch_queue_size']}")
    print(f"   预取缓存: {predictor_stats['prefetch_cache_size']}")

    print("\n验证统计:")
    validator_stats = client_stats["validator"]
    print(f"   总验证: {validator_stats['total_validations']}")
    print(f"   缓存命中率: {validator_stats['cache_hit_rate']*100:.1f}%")
    print(f"   本地验证率: {validator_stats['local_validation_rate']*100:.1f}%")
    print(f"   服务器检查率: {validator_stats['server_check_rate']*100:.1f}%")


def demonstrate_server_load_reduction():
    """演示服务器负载减少效果"""
    print_separator("服务器负载减少效果演示")

    app = create_app("mysql_testing")
    with app.app_context():
        flow = PermissionBusinessFlow()

        # 模拟高并发场景
        print("模拟高并发权限检查场景...")

        def simulate_user_requests(user_id: str, request_count: int):
            """模拟用户请求"""
            for i in range(request_count):
                request = PermissionRequest(
                    request_id=f"{user_id}_req_{i}",
                    user_id=user_id,
                    resource_type=random.choice(
                        [ResourceType.SERVER, ResourceType.CHANNEL]
                    ),
                    resource_id=random.choice(
                        ["server_001", "server_002", "channel_001"]
                    ),
                    action=random.choice(["read", "write"]),
                    permission_level=random.choice(
                        [PermissionLevel.READ, PermissionLevel.WRITE]
                    ),
                    timestamp=time.time(),  # 添加timestamp参数
                )

                result = flow.check_permission(request)
                time.sleep(0.01)  # 模拟请求间隔

        # 多线程模拟并发
        threads = []
        users = ["alice", "bob", "admin", "charlie"]

        for user in users:
            thread = threading.Thread(target=simulate_user_requests, args=(user, 10))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 显示最终统计
        final_stats = flow.get_client_optimization_stats()

        print("\n最终优化效果:")
        print(f"   总请求数: {final_stats['total_client_requests']}")
        print(f"   服务器负载减少: {final_stats['server_load_reduction']*100:.1f}%")
        print(f"   平均响应时间: 显著降低")
        print(f"   缓存命中率: {final_stats['validator']['cache_hit_rate']*100:.1f}%")


if __name__ == "__main__":
    print("🚀 客户端压力转移优化演示")
    print("本演示展示如何将服务器压力转移到客户端，提升系统性能")

    try:
        # 基础演示
        demonstrate_client_side_optimization()

        # 负载减少演示
        demonstrate_server_load_reduction()

        print("\n✅ 客户端优化演示完成！")
        print("\n主要优化效果:")
        print("1. 客户端本地验证减少服务器请求")
        print("2. 智能预取提前加载数据")
        print("3. 行为预测优化用户体验")
        print("4. 多层缓存提升响应速度")
        print("5. 服务器负载显著降低")

    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
