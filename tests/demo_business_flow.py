#!/usr/bin/env python3
"""
权限系统完整业务流程演示

展示所有模块如何协同工作，形成完整的业务逻辑
"""

import time
import random
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.core.permission_business_flow import (
        PermissionBusinessFlow,
        PermissionRequest,
        PermissionLevel,
        ResourceType,
        require_permission,
        get_server_info,
        send_message,
        manage_user,
    )
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在正确的目录下运行演示脚本")
    sys.exit(1)


def print_separator(title: str):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_request_info(request: PermissionRequest):
    """打印请求信息"""
    print(f"用户ID: {request.user_id}")
    print(f"资源类型: {request.resource_type.value}")
    print(f"资源ID: {request.resource_id}")
    print(f"操作: {request.action}")
    print(f"权限级别: {request.permission_level.name}")
    print(f"请求时间: {datetime.fromtimestamp(request.timestamp)}")


def print_result_info(result):
    """打印结果信息"""
    print(f"权限验证: {'✅ 通过' if result.allowed else '❌ 拒绝'}")
    print(f"缓存命中: {'✅ 是' if result.cached else '❌ 否'}")
    print(f"响应时间: {result.response_time:.3f}秒")
    print(f"优化应用: {'✅ 是' if result.optimization_applied else '❌ 否'}")
    if not result.allowed:
        print(f"拒绝原因: {result.reason}")


def simulate_user_requests(flow: PermissionBusinessFlow, duration: int = 60):
    """模拟用户请求"""
    print_separator("模拟用户请求")
    print(f"模拟时长: {duration}秒")

    # 预定义一些用户和资源
    users = ["user_001", "user_002", "user_003", "admin_001", "super_admin"]
    servers = ["server_001", "server_002", "server_003"]
    channels = ["channel_001", "channel_002", "channel_003"]

    start_time = time.time()
    request_count = 0

    try:
        while time.time() - start_time < duration:
            # 随机选择用户和资源
            user_id = random.choice(users)
            resource_type = random.choice([ResourceType.SERVER, ResourceType.CHANNEL])
            resource_id = random.choice(
                servers if resource_type == ResourceType.SERVER else channels
            )
            action = random.choice(["read", "write", "delete", "admin"])

            # 根据用户类型设置权限级别
            if "super_admin" in user_id:
                permission_level = PermissionLevel.SUPER_ADMIN
            elif "admin" in user_id:
                permission_level = PermissionLevel.ADMIN
            else:
                permission_level = random.choice(
                    [PermissionLevel.READ, PermissionLevel.WRITE]
                )

            # 创建权限请求
            request = PermissionRequest(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                permission_level=permission_level,
                timestamp=time.time(),
                request_id=f"req_{int(time.time() * 1000)}",
            )

            # 检查权限
            result = flow.check_permission(request)
            request_count += 1

            # 每10个请求显示一次统计
            if request_count % 10 == 0:
                print(f"\n请求统计: {request_count} 次")
                print(f"缓存命中率: {flow.cache_hit_count / request_count:.2%}")
                print(f"优化次数: {flow.optimization_count}")

            # 随机延迟
            time.sleep(random.uniform(0.1, 0.5))

    except KeyboardInterrupt:
        print("\n\n模拟被用户中断")

    print(f"\n模拟完成，共处理 {request_count} 个请求")


def demonstrate_permission_levels(flow: PermissionBusinessFlow):
    """演示不同权限级别"""
    print_separator("权限级别演示")

    # 测试不同权限级别
    test_cases = [
        ("user_001", PermissionLevel.READ, "应该通过"),
        ("user_002", PermissionLevel.WRITE, "应该通过"),
        ("admin_001", PermissionLevel.ADMIN, "应该通过"),
        ("super_admin", PermissionLevel.SUPER_ADMIN, "应该通过"),
    ]

    for user_id, level, expected in test_cases:
        print(f"\n测试用户: {user_id}, 权限级别: {level.name}")

        request = PermissionRequest(
            user_id=user_id,
            resource_type=ResourceType.SERVER,
            resource_id="server_001",
            action="read",
            permission_level=level,
            timestamp=time.time(),
            request_id=f"req_{int(time.time() * 1000)}",
        )

        result = flow.check_permission(request)
        print_result_info(result)
        print(f"预期结果: {expected}")


def demonstrate_resource_types(flow: PermissionBusinessFlow):
    """演示不同资源类型"""
    print_separator("资源类型演示")

    resource_types = [
        (ResourceType.SERVER, "服务器"),
        (ResourceType.CHANNEL, "频道"),
        (ResourceType.USER, "用户"),
        (ResourceType.MESSAGE, "消息"),
        (ResourceType.ROLE, "角色"),
    ]

    for resource_type, name in resource_types:
        print(f"\n测试资源类型: {name}")

        request = PermissionRequest(
            user_id="admin_001",
            resource_type=resource_type,
            resource_id=f"{resource_type.value}_001",
            action="read",
            permission_level=PermissionLevel.READ,
            timestamp=time.time(),
            request_id=f"req_{int(time.time() * 1000)}",
        )

        result = flow.check_permission(request)
        print_result_info(result)


def demonstrate_business_functions():
    """演示业务函数"""
    print_separator("业务函数演示")

    # 模拟权限检查成功
    from unittest.mock import patch, MagicMock

    with patch(
        "app.core.permission_business_flow.get_permission_business_flow"
    ) as mock_get_flow:
        mock_flow = MagicMock()
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_result.reason = "权限验证通过"
        mock_result.response_time = 0.1
        mock_flow.check_permission.return_value = mock_result
        mock_get_flow.return_value = mock_flow

        print("\n1. 获取服务器信息")
        try:
            result = get_server_info(user_id="user_001", server_id="server_001")
            print(f"✅ 成功: {result}")
        except Exception as e:
            print(f"❌ 失败: {e}")

        print("\n2. 发送消息")
        try:
            result = send_message(
                user_id="user_001", channel_id="channel_001", message="Hello World"
            )
            print(f"✅ 成功: {result}")
        except Exception as e:
            print(f"❌ 失败: {e}")

        print("\n3. 管理用户")
        try:
            result = manage_user(
                user_id="admin_001", target_user_id="user_001", action="ban"
            )
            print(f"✅ 成功: {result}")
        except Exception as e:
            print(f"❌ 失败: {e}")


def demonstrate_performance_monitoring(flow: PermissionBusinessFlow):
    """演示性能监控"""
    print_separator("性能监控演示")

    # 获取性能报告
    report = flow.get_performance_report()

    print("📊 性能报告:")
    print(f"  总请求数: {report['requests']['total']}")
    print(f"  缓存命中数: {report['requests']['cache_hits']}")
    print(f"  缓存命中率: {report['requests']['cache_hit_rate']:.2%}")
    print(f"  优化次数: {report['optimizations']}")

    # 显示ML预测
    if "ml_predictions" in report and report["ml_predictions"]:
        print("\n🤖 ML预测:")
        for pred in report["ml_predictions"][:3]:  # 显示前3个预测
            print(f"  {pred['metric_name']}: {pred['trend']} ({pred['urgency_level']})")

    # 显示缓存统计
    if "cache_stats" in report:
        cache_stats = report["cache_stats"]
        print("\n💾 缓存统计:")
        if "l1_cache" in cache_stats:
            l1 = cache_stats["l1_cache"]
            print(f"  L1缓存大小: {l1.get('size', 'N/A')}")
            print(f"  L1命中率: {l1.get('hit_rate', 'N/A')}")


def demonstrate_optimization_status(flow: PermissionBusinessFlow):
    """演示优化状态"""
    print_separator("优化状态演示")

    status = flow.get_optimization_status()

    print("⚡ 优化状态:")
    print(f"  优化次数: {status['optimization_count']}")

    if "current_config" in status:
        config = status["current_config"]
        print(f"  连接池大小: {config.get('connection_pool_size', 'N/A')}")
        print(f"  Socket超时: {config.get('socket_timeout', 'N/A')}s")
        print(f"  锁超时: {config.get('lock_timeout', 'N/A')}s")
        print(f"  批处理大小: {config.get('batch_size', 'N/A')}")
        print(f"  缓存大小: {config.get('cache_max_size', 'N/A')}")

    if "optimization_history" in status and status["optimization_history"]:
        print(f"\n📈 优化历史 (最近{len(status['optimization_history'])}次):")
        for i, record in enumerate(status["optimization_history"][-3:], 1):
            print(f"  {i}. 时间: {datetime.fromtimestamp(record['timestamp'])}")
            print(f"     策略: {record['strategy']}")


def main():
    """主函数"""
    print("🏗️ 权限系统完整业务流程演示")
    print("=" * 60)

    try:
        # 创建Flask应用上下文
        from app import create_app

        app = create_app("testing")

        with app.app_context():
            # 1. 初始化业务流程
            print("正在初始化业务流程...")
            flow = PermissionBusinessFlow()
            print("✅ 业务流程初始化完成")

            # 2. 演示权限级别
            demonstrate_permission_levels(flow)

            # 3. 演示资源类型
            demonstrate_resource_types(flow)

            # 4. 演示业务函数
            demonstrate_business_functions()

            # 5. 模拟用户请求
            simulate_user_requests(flow, duration=30)

            # 6. 演示性能监控
            demonstrate_performance_monitoring(flow)

            # 7. 演示优化状态
            demonstrate_optimization_status(flow)

            print_separator("演示完成")
            print("✅ 权限系统完整业务流程演示完成")
            print("📊 系统已自动收集性能数据并进行优化")
            print("🔍 可通过日志查看详细的业务处理过程")

    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
