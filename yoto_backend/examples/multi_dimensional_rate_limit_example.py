"""
多维限流使用示例

展示如何使用基于user_id、server_id、ip_address的多维限流
"""

import time
from typing import Optional
from app.core.permission_resilience import (
    MultiDimensionalKey,
    set_rate_limit_config,
    get_rate_limit_status,
    rate_limit,
    get_resilience_controller,
)


def create_multi_key_from_request(
    user_id: str, server_id: str, ip_address: str
) -> MultiDimensionalKey:
    """从请求参数创建多维限流键"""
    return MultiDimensionalKey(
        user_id=user_id, server_id=server_id, ip_address=ip_address
    )


def create_multi_key_from_context(*args, **kwargs) -> MultiDimensionalKey:
    """从函数参数创建多维限流键"""
    # 从kwargs中提取参数
    user_id = kwargs.get("user_id", "anonymous")
    server_id = kwargs.get("server_id", "default")
    ip_address = kwargs.get("ip_address", "127.0.0.1")

    return MultiDimensionalKey(
        user_id=user_id, server_id=server_id, ip_address=ip_address
    )


# ==================== 示例1: 用户权限检查 ====================


@rate_limit("permission_check", multi_key_func=create_multi_key_from_context)
def check_user_permission(
    user_id: str,
    permission: str,
    server_id: str = "default",
    ip_address: str = "127.0.0.1",
) -> bool:
    """检查用户权限（带多维限流）"""
    print(f"检查用户 {user_id} 的权限: {permission}")
    # 模拟权限检查逻辑
    time.sleep(0.1)  # 模拟处理时间
    return True


def example_permission_check():
    """权限检查示例"""
    print("=== 权限检查多维限流示例 ===")

    # 设置多维限流配置
    set_rate_limit_config(
        "permission_check",
        multi_dimensional=True,
        user_id_limit=5,  # 每个用户最多5次权限检查
        server_id_limit=20,  # 每个服务器最多20次权限检查
        ip_limit=10,  # 每个IP最多10次权限检查
        combined_limit=30,  # 组合维度最多30次权限检查
    )

    # 模拟多个用户的权限检查
    users = ["user1", "user2", "user3"]
    servers = ["server1", "server2"]
    ips = ["192.168.1.100", "192.168.1.101"]

    for i in range(10):
        user = users[i % len(users)]
        server = servers[i % len(servers)]
        ip = ips[i % len(ips)]

        try:
            result = check_user_permission(
                user_id=user, permission="read", server_id=server, ip_address=ip
            )
            print(f"✓ 用户 {user} 权限检查成功")
        except Exception as e:
            print(f"✗ 用户 {user} 权限检查被限流: {e}")


# ==================== 示例2: API接口限流 ====================


@rate_limit("api_endpoint", multi_key_func=create_multi_key_from_context)
def api_get_user_data(
    user_id: str, server_id: str = "default", ip_address: str = "127.0.0.1"
) -> dict:
    """获取用户数据API（带多维限流）"""
    print(f"获取用户 {user_id} 的数据")
    # 模拟API调用
    time.sleep(0.05)  # 模拟处理时间
    return {"user_id": user_id, "data": "user_data"}


def example_api_rate_limit():
    """API限流示例"""
    print("\n=== API接口多维限流示例 ===")

    # 设置API限流配置
    set_rate_limit_config(
        "api_endpoint",
        multi_dimensional=True,
        user_id_limit=3,  # 每个用户最多3次API调用
        server_id_limit=15,  # 每个服务器最多15次API调用
        ip_limit=8,  # 每个IP最多8次API调用
        combined_limit=25,  # 组合维度最多25次API调用
    )

    # 模拟API调用
    for i in range(15):
        user = f"user{i % 5}"  # 5个不同用户
        server = f"server{i % 3}"  # 3个不同服务器
        ip = f"192.168.1.{100 + i % 4}"  # 4个不同IP

        try:
            result = api_get_user_data(user_id=user, server_id=server, ip_address=ip)
            print(f"✓ API调用成功: {user} -> {result['user_id']}")
        except Exception as e:
            print(f"✗ API调用被限流: {user} -> {e}")


# ==================== 示例3: 缓存访问限流 ====================


@rate_limit("cache_access", multi_key_func=create_multi_key_from_context)
def get_cached_data(
    key: str, user_id: str, server_id: str = "default", ip_address: str = "127.0.0.1"
) -> Optional[str]:
    """获取缓存数据（带多维限流）"""
    print(f"用户 {user_id} 访问缓存: {key}")
    # 模拟缓存访问
    time.sleep(0.02)  # 模拟处理时间
    return f"cached_data_for_{key}"


def example_cache_rate_limit():
    """缓存访问限流示例"""
    print("\n=== 缓存访问多维限流示例 ===")

    # 设置缓存访问限流配置
    set_rate_limit_config(
        "cache_access",
        multi_dimensional=True,
        user_id_limit=10,  # 每个用户最多10次缓存访问
        server_id_limit=50,  # 每个服务器最多50次缓存访问
        ip_limit=25,  # 每个IP最多25次缓存访问
        combined_limit=80,  # 组合维度最多80次缓存访问
    )

    # 模拟缓存访问
    cache_keys = ["user_profile", "user_permissions", "user_settings"]

    for i in range(20):
        user = f"user{i % 8}"  # 8个不同用户
        server = f"server{i % 4}"  # 4个不同服务器
        ip = f"192.168.1.{100 + i % 6}"  # 6个不同IP
        key = cache_keys[i % len(cache_keys)]

        try:
            result = get_cached_data(
                key=key, user_id=user, server_id=server, ip_address=ip
            )
            print(f"✓ 缓存访问成功: {user} -> {key}")
        except Exception as e:
            print(f"✗ 缓存访问被限流: {user} -> {e}")


# ==================== 示例4: 动态配置调整 ====================


def example_dynamic_configuration():
    """动态配置调整示例"""
    print("\n=== 动态配置调整示例 ===")

    # 初始配置
    set_rate_limit_config(
        "dynamic_test",
        multi_dimensional=True,
        user_id_limit=5,
        server_id_limit=10,
        ip_limit=8,
        combined_limit=20,
    )

    # 查看初始状态
    status = get_rate_limit_status("dynamic_test")
    print(
        f"初始配置: 用户限制={status['user_id_limit']}, 服务器限制={status['server_id_limit']}"
    )

    # 动态调整配置（模拟高负载情况）
    print("检测到高负载，调整限流配置...")
    set_rate_limit_config(
        "dynamic_test",
        user_id_limit=2,  # 降低用户限制
        server_id_limit=5,  # 降低服务器限制
        ip_limit=4,  # 降低IP限制
        combined_limit=10,  # 降低组合限制
    )

    # 查看调整后的状态
    status = get_rate_limit_status("dynamic_test")
    print(
        f"调整后配置: 用户限制={status['user_id_limit']}, 服务器限制={status['server_id_limit']}"
    )

    # 模拟负载降低，恢复正常配置
    print("负载降低，恢复正常配置...")
    set_rate_limit_config(
        "dynamic_test",
        user_id_limit=5,
        server_id_limit=10,
        ip_limit=8,
        combined_limit=20,
    )

    status = get_rate_limit_status("dynamic_test")
    print(
        f"恢复正常: 用户限制={status['user_id_limit']}, 服务器限制={status['server_id_limit']}"
    )


# ==================== 示例5: 监控和统计 ====================


def example_monitoring():
    """监控和统计示例"""
    print("\n=== 监控和统计示例 ===")

    # 设置监控配置
    set_rate_limit_config(
        "monitor_test",
        multi_dimensional=True,
        user_id_limit=3,
        server_id_limit=6,
        ip_limit=4,
        combined_limit=8,
    )

    # 模拟一些请求
    for i in range(5):
        try:
            check_user_permission(
                user_id=f"monitor_user{i}",
                permission="read",
                server_id="monitor_server",
                ip_address=f"192.168.1.{100 + i}",
            )
        except Exception as e:
            pass

    # 获取监控状态
    status = get_rate_limit_status("monitor_test")
    print("监控状态:")
    print(f"  - 多维限流启用: {status['multi_dimensional']}")
    print(f"  - 用户限制: {status['user_id_limit']}")
    print(f"  - 服务器限制: {status['server_id_limit']}")
    print(f"  - IP限制: {status['ip_limit']}")
    print(f"  - 组合限制: {status['combined_limit']}")


# ==================== 主函数 ====================


def main():
    """运行所有示例"""
    print("多维限流功能演示")
    print("=" * 50)

    try:
        # 运行各个示例
        example_permission_check()
        example_api_rate_limit()
        example_cache_rate_limit()
        example_dynamic_configuration()
        example_monitoring()

        print("\n" + "=" * 50)
        print("所有示例运行完成！")

    except Exception as e:
        print(f"示例运行出错: {e}")


if __name__ == "__main__":
    main()
