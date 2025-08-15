#!/usr/bin/env python3
"""
权限系统完整业务流程演示 - 简化版

不依赖复杂Flask上下文的独立演示
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
    )
    from app import create_app
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


def demonstrate_basic_flow():
    """演示基础业务流程"""
    print_separator("基础业务流程演示")

    # 创建Flask应用上下文 - 使用MySQL测试配置
    app = create_app("mysql_testing")  # 使用MySQL测试配置，确保数据库环境一致
    with app.app_context():
        # 初始化数据库
        print("正在初始化数据库...")
        try:
            from app.core.extensions import db
            from app.core.demo_data_setup import get_demo_data_setup

            # 删除所有表并重新创建
            db.drop_all()
            db.create_all()
            print("✅ 数据库表创建完成")

            # 创建演示数据
            demo_setup = get_demo_data_setup()
            success = demo_setup.setup_database_data(db)
            if success:
                print("✅ 数据库演示数据创建完成")
            else:
                print("❌ 数据库演示数据创建失败")

        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            print("将使用内存数据库进行演示...")

        # 创建业务流程实例
        flow = PermissionBusinessFlow()

        # 初始化演示数据
        print("正在初始化演示数据...")
        try:
            demo_setup = get_demo_data_setup()
            print(f"✅ 演示数据初始化完成")
            print(f"  用户数量: {len(demo_setup.list_users())}")
            print(f"  服务器数量: {len(demo_setup.list_servers())}")
            print(f"  频道数量: {len(demo_setup.list_channels())}")
            print(f"  角色数量: {len(demo_setup.list_roles())}")
        except Exception as e:
            print(f"❌ 演示数据初始化失败: {e}")

        # 设置演示权限数据
        print("正在设置演示权限数据...")
        success_count = flow.setup_demo_permissions()
        print(f"✅ 设置权限数据完成: {success_count} 个权限")

        # 测试用例 - 使用数据库中实际存在的用户名
        test_cases = [
            {
                "user_id": "alice",  # 普通用户
                "resource_type": ResourceType.SERVER,
                "resource_id": "server_001",  # 使用演示数据中的服务器ID
                "action": "read",
                "permission_level": PermissionLevel.READ,
                "expected": "应该通过",
                "description": "普通用户读取服务器",
            },
            {
                "user_id": "bob",  # 版主
                "resource_type": ResourceType.CHANNEL,
                "resource_id": "channel_001",
                "action": "write",
                "permission_level": PermissionLevel.WRITE,
                "expected": "应该通过",
                "description": "版主写入频道",
            },
            {
                "user_id": "admin",  # 管理员
                "resource_type": ResourceType.SERVER,
                "resource_id": "server_001",
                "action": "delete",
                "permission_level": PermissionLevel.ADMIN,
                "expected": "应该通过",
                "description": "管理员删除服务器",
            },
            {
                "user_id": "superadmin",  # 超级管理员
                "resource_type": ResourceType.USER,
                "resource_id": "alice",
                "action": "admin",
                "permission_level": PermissionLevel.SUPER_ADMIN,
                "expected": "应该通过",
                "description": "超级管理员管理用户",
            },
            {
                "user_id": "alice",  # 普通用户
                "resource_type": ResourceType.SERVER,
                "resource_id": "server_001",
                "action": "delete",
                "permission_level": PermissionLevel.ADMIN,
                "expected": "应该拒绝",
                "description": "普通用户尝试删除服务器",
            },
            {
                "user_id": "charlie",  # 用户不在服务器1中
                "resource_type": ResourceType.SERVER,
                "resource_id": "server_001",
                "action": "read",
                "permission_level": PermissionLevel.READ,
                "expected": "应该拒绝",
                "description": "用户访问未授权的服务器",
            },
            {
                "user_id": "charlie",  # 用户在服务器2中
                "resource_type": ResourceType.SERVER,
                "resource_id": "server_002",
                "action": "read",
                "permission_level": PermissionLevel.READ,
                "expected": "应该通过",
                "description": "用户访问授权的服务器",
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- 测试用例 {i}: {test_case['description']} ---")

            # 创建权限请求
            request = PermissionRequest(
                user_id=test_case["user_id"],
                resource_type=test_case["resource_type"],
                resource_id=test_case["resource_id"],
                action=test_case["action"],
                permission_level=test_case["permission_level"],
                timestamp=time.time(),
                request_id=f"req_{int(time.time() * 1000)}",
            )

            print_request_info(request)

            # 检查权限
            result = flow.check_permission(request)

            print_result_info(result)
            print(f"预期结果: {test_case['expected']}")

            # 验证结果是否符合预期
            expected_allowed = "通过" in test_case["expected"]
            actual_allowed = result.allowed
            if expected_allowed == actual_allowed:
                print(f"✅ 结果符合预期")
            else:
                print(f"❌ 结果不符合预期")

            # 短暂延迟
            time.sleep(0.1)


def demonstrate_performance_monitoring():
    """演示性能监控"""
    print_separator("性能监控演示")

    # 创建Flask应用上下文 - 使用MySQL测试配置
    app = create_app("mysql_testing")
    with app.app_context():
        flow = PermissionBusinessFlow()

        # 模拟一些请求
        print("模拟请求处理...")
        # 使用数据库中实际存在的用户名
        test_users = ["alice", "bob", "admin", "superadmin", "charlie"]
        test_servers = ["server_001", "server_002", "server_003"]

        for i in range(10):
            user_id = test_users[i % len(test_users)]
            server_id = test_servers[i % len(test_servers)]

            request = PermissionRequest(
                user_id=user_id,
                resource_type=ResourceType.SERVER,
                resource_id=server_id,
                action="read",
                permission_level=PermissionLevel.READ,
                timestamp=time.time(),
                request_id=f"req_{int(time.time() * 1000)}",
            )

            result = flow.check_permission(request)

            if i % 3 == 0:
                print(
                    f"请求 {i+1}: {'✅' if result.allowed else '❌'} "
                    f"({result.response_time:.3f}s)"
                )

        # 获取性能报告
        print("\n📊 性能报告:")
        report = flow.get_performance_report()

        if "requests" in report:
            requests = report["requests"]
            print(f"  总请求数: {requests.get('total', 0)}")
            print(f"  缓存命中数: {requests.get('cache_hits', 0)}")
            print(f"  缓存命中率: {requests.get('cache_hit_rate', 0):.2%}")
            print(f"  优化次数: {report.get('optimizations', 0)}")
        else:
            print("  无法获取详细性能报告")


def demonstrate_optimization_status():
    """演示优化状态"""
    print_separator("优化状态演示")

    # 创建Flask应用上下文 - 使用MySQL测试配置
    app = create_app("mysql_testing")
    with app.app_context():
        flow = PermissionBusinessFlow()

        status = flow.get_optimization_status()

        print("⚡ 优化状态:")
        print(f"  优化次数: {status.get('optimization_count', 0)}")

        if "current_config" in status:
            config = status["current_config"]
            print(f"  连接池大小: {config.get('connection_pool_size', 'N/A')}")
            print(f"  Socket超时: {config.get('socket_timeout', 'N/A')}s")
            print(f"  锁超时: {config.get('lock_timeout', 'N/A')}s")
            print(f"  批处理大小: {config.get('batch_size', 'N/A')}")
            print(f"  缓存大小: {config.get('cache_max_size', 'N/A')}")
        else:
            print("  当前配置: 使用默认配置")


def simulate_user_requests_simple():
    """简化版用户请求模拟"""
    print_separator("用户请求模拟")

    # 创建Flask应用上下文 - 使用MySQL测试配置
    app = create_app("mysql_testing")
    with app.app_context():
        flow = PermissionBusinessFlow()

        # 预定义用户和资源 - 使用数据库中实际存在的用户名
        users = ["alice", "bob", "charlie", "admin", "superadmin"]
        servers = ["server_001", "server_002", "server_003"]
        channels = ["channel_001", "channel_002", "channel_003"]

        print("开始模拟用户请求...")
        request_count = 0
        start_time = time.time()

        try:
            for i in range(20):  # 减少请求数量
                # 随机选择用户和资源
                user_id = random.choice(users)
                resource_type = random.choice(
                    [ResourceType.SERVER, ResourceType.CHANNEL]
                )
                resource_id = random.choice(
                    servers if resource_type == ResourceType.SERVER else channels
                )
                action = random.choice(["read", "write", "delete"])

                # 根据用户类型设置权限级别
                if "superadmin" in user_id:
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

                # 每5个请求显示一次统计
                if request_count % 5 == 0:
                    elapsed_time = time.time() - start_time
                    qps = request_count / elapsed_time if elapsed_time > 0 else 0
                    print(f"请求统计: {request_count} 次, QPS: {qps:.1f}")
                    print(f"缓存命中率: {flow.cache_hit_count / request_count:.2%}")
                    print(f"优化次数: {flow.optimization_count}")

                # 短暂延迟
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n模拟被用户中断")

        total_time = time.time() - start_time
        final_qps = request_count / total_time if total_time > 0 else 0

        print(f"\n模拟完成，共处理 {request_count} 个请求")
        print(f"总耗时: {total_time:.2f}秒")
        print(f"平均QPS: {final_qps:.1f}")


def demonstrate_business_functions_simple():
    """演示业务函数 - 简化版"""
    print_separator("业务函数演示")

    # 模拟业务函数
    def get_server_info(user_id: str, server_id: str):
        """获取服务器信息"""
        return {"server_id": server_id, "name": "测试服务器", "status": "online"}

    def send_message(user_id: str, channel_id: str, message: str):
        """发送消息"""
        return {"message_id": "msg_123", "content": message, "timestamp": time.time()}

    def manage_user(user_id: str, target_user_id: str, action: str):
        """管理用户"""
        return {"action": action, "target_user": target_user_id, "status": "success"}

    # 演示业务函数
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


def main():
    """主函数"""
    print("🏗️ 权限系统完整业务流程演示 - 简化版")
    print("=" * 60)

    try:
        # 1. 演示基础业务流程
        demonstrate_basic_flow()

        # 2. 演示业务函数
        demonstrate_business_functions_simple()

        # 3. 模拟用户请求
        simulate_user_requests_simple()

        # 4. 演示性能监控
        demonstrate_performance_monitoring()

        # 5. 演示优化状态
        demonstrate_optimization_status()

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
