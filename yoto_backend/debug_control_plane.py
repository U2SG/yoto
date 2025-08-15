#!/usr/bin/env python3
"""
控制平面调试脚本

检查各个组件的状态和连接情况
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.core.permission.permissions_refactored import get_permission_system
from app.core.permission.permission_resilience import get_resilience_controller
from app.core.permission.hybrid_permission_cache import get_hybrid_cache
from app.core.permission.permission_monitor import get_permission_monitor
import redis


def debug_components():
    """调试各个组件状态"""
    app = create_app("development")

    with app.app_context():
        print("🔍 调试控制平面组件状态...")
        print("=" * 60)

        # 1. 检查权限系统
        print("\n1. 权限系统状态:")
        try:
            permission_system = get_permission_system()
            print("   ✅ 权限系统初始化成功")
            print(f"   - 类型: {type(permission_system)}")
        except Exception as e:
            print(f"   ❌ 权限系统初始化失败: {e}")
            traceback.print_exc()

        # 2. 检查韧性控制器
        print("\n2. 韧性控制器状态:")
        try:
            controller = get_resilience_controller()
            if controller:
                print("   ✅ 韧性控制器可用")
                print(f"   - 类型: {type(controller)}")
                configs = controller.get_all_configs()
                print(f"   - 配置数量: {len(configs) if configs else 0}")
            else:
                print("   ❌ 韧性控制器不可用")
        except Exception as e:
            print(f"   ❌ 韧性控制器检查失败: {e}")
            traceback.print_exc()

        # 3. 检查混合缓存
        print("\n3. 混合缓存状态:")
        try:
            hybrid_cache = get_hybrid_cache()
            if hybrid_cache:
                print("   ✅ 混合缓存可用")
                print(f"   - 类型: {type(hybrid_cache)}")

                # 尝试获取统计信息
                try:
                    stats = hybrid_cache.get_stats()
                    print("   ✅ 缓存统计获取成功")
                    print(f"   - 统计信息: {stats}")
                except Exception as e:
                    print(f"   ⚠️ 缓存统计获取失败: {e}")
            else:
                print("   ❌ 混合缓存不可用")
        except Exception as e:
            print(f"   ❌ 混合缓存检查失败: {e}")
            traceback.print_exc()

        # 4. 检查监控器
        print("\n4. 权限监控器状态:")
        try:
            monitor = get_permission_monitor()
            if monitor:
                print("   ✅ 权限监控器可用")
                print(f"   - 类型: {type(monitor)}")

                # 尝试获取统计信息
                try:
                    stats = monitor.get_stats()
                    print("   ✅ 监控统计获取成功")
                    print(f"   - 统计信息: {stats}")
                except Exception as e:
                    print(f"   ⚠️ 监控统计获取失败: {e}")
            else:
                print("   ❌ 权限监控器不可用")
        except Exception as e:
            print(f"   ❌ 权限监控器检查失败: {e}")
            traceback.print_exc()

        # 5. 检查Redis连接
        print("\n5. Redis连接状态:")
        try:
            # 尝试创建Redis集群客户端
            startup_nodes = [{"host": "localhost", "port": 6379}]

            try:
                redis_client = redis.RedisCluster(
                    startup_nodes=startup_nodes,
                    decode_responses=True,
                    skip_full_coverage_check=True,  # 开发环境跳过完整覆盖检查
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                redis_client.ping()
                print("   ✅ Redis集群连接正常")

                # 检查一些基本的Redis操作
                redis_client.set("test_key", "test_value")
                value = redis_client.get("test_key")
                redis_client.delete("test_key")
                print("   ✅ Redis集群读写操作正常")
            except Exception as cluster_error:
                print(f"   ⚠️ Redis集群连接失败，尝试单节点模式: {cluster_error}")
                # 降级到单节点Redis
                redis_client = redis.Redis(
                    host="localhost", port=6379, db=0, decode_responses=True
                )
                redis_client.ping()
                print("   ✅ Redis单节点连接正常")

                # 检查一些基本的Redis操作
                redis_client.set("test_key", "test_value")
                value = redis_client.get("test_key")
                redis_client.delete("test_key")
                print("   ✅ Redis单节点读写操作正常")
        except Exception as e:
            print(f"   ❌ Redis连接失败: {e}")

        print("\n" + "=" * 60)
        print("🔍 调试完成")


def main():
    """主函数"""
    debug_components()


if __name__ == "__main__":
    main()
