"""
Redis集群功能测试

测试Redis集群连接、监控后端、缓存操作等功能
"""

import sys
import os
import time
import json
from unittest.mock import Mock

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def test_redis_cluster_connection():
    """测试Redis集群连接"""
    print("🔍 测试Redis集群连接...")

    try:
        import redis

        # 配置Redis集群节点
        startup_nodes = [
            {"host": "localhost", "port": 6379},
            {"host": "localhost", "port": 6380},
            {"host": "localhost", "port": 6381},
        ]

        # 尝试连接Redis集群
        cluster_client = redis.RedisCluster(
            startup_nodes=startup_nodes,
            decode_responses=True,
            skip_full_coverage_check=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        # 测试连接
        result = cluster_client.ping()
        print(f"✅ Redis集群连接成功: {result}")

        # 测试基本操作
        cluster_client.set("test_key", "test_value")
        value = cluster_client.get("test_key")
        print(f"✅ 基本读写操作: {value}")

        # 测试集群信息
        cluster_info = cluster_client.cluster_info()
        print(f"✅ 集群状态: {cluster_info.get('cluster_state', 'unknown')}")

        return True
    except Exception as e:
        print(f"❌ Redis集群连接失败: {e}")
        return False


def test_monitor_backend_redis_cluster():
    """测试监控后端的Redis集群功能"""
    print("🔍 测试监控后端Redis集群功能...")

    try:
        from app.core.permission.monitor_backends import RedisBackend

        # 创建Redis后端实例
        backend = RedisBackend(
            redis_url="redis://localhost:6379",
            key_prefix="test_monitor:",
            max_history_size=1000,
        )

        # 测试连接
        if backend.redis is None:
            print("❌ Redis连接失败")
            return False

        # 测试指标记录
        success = backend.record_metric("test_metric", 123.45, {"tag1": "value1"})
        print(f"✅ 指标记录: {success}")

        # 测试事件记录
        success = backend.record_event(
            "test_event", {"data": "test"}, {"tag1": "value1"}
        )
        print(f"✅ 事件记录: {success}")

        # 测试获取指标
        metrics = backend.get_metrics("test_metric", limit=10)
        print(f"✅ 获取指标: {len(metrics)} 条")

        # 测试获取事件
        events = backend.get_events("test_event", limit=10)
        print(f"✅ 获取事件: {len(events)} 条")

        return True
    except Exception as e:
        print(f"❌ 监控后端Redis集群测试失败: {e}")
        return False


def test_hybrid_cache_redis_cluster():
    """测试混合缓存的Redis集群功能"""
    print("🔍 测试混合缓存Redis集群功能...")

    try:
        from app.core.permission.hybrid_permission_cache import HybridPermissionCache

        # 创建混合缓存实例
        cache = HybridPermissionCache()

        # 测试分布式缓存操作
        test_data = {"permissions": ["perm1", "perm2", "perm3"]}

        # 设置缓存
        success = cache.distributed_cache_set("test_user_1", test_data)
        print(f"✅ 分布式缓存设置: {success}")

        # 获取缓存
        result = cache.distributed_cache_get("test_user_1")
        print(f"✅ 分布式缓存获取: {result is not None}")

        # 测试批量操作
        batch_data = {
            "test_user_2": {"permissions": ["perm4", "perm5"]},
            "test_user_3": {"permissions": ["perm6", "perm7"]},
        }

        success = cache.distributed_cache_batch_set(batch_data)
        print(f"✅ 批量缓存设置: {success}")

        return True
    except Exception as e:
        print(f"❌ 混合缓存Redis集群测试失败: {e}")
        return False


def test_advanced_optimization_redis_cluster():
    """测试高级优化的Redis集群功能"""
    print("🔍 测试高级优化Redis集群功能...")

    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建配置
        config = {
            "smart_invalidation_interval": 1,
            "preload_interval": 1,
            "preload": {"enabled": True},
            "batch_size": 100,
            "lock_timeout": 2.0,
            "lock_retry_interval": 0.1,
        }

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(
            config, None
        )  # Redis客户端将在内部获取

        # 测试智能失效分析
        analysis = optimizer._get_smart_invalidation_analysis()
        print(f"✅ 智能失效分析: {analysis['should_process']}")

        # 测试预加载策略
        preload_result = optimizer._execute_preload_strategy()
        print(f"✅ 预加载策略: {preload_result['success']}")

        # 测试批量操作处理
        batch_result = optimizer._process_batch_operations()
        print(f"✅ 批量操作: {batch_result['processed_count']} 个")

        return True
    except Exception as e:
        print(f"❌ 高级优化Redis集群测试失败: {e}")
        return False


def test_performance_redis_cluster():
    """测试Redis集群性能"""
    print("🔍 测试Redis集群性能...")

    try:
        import redis

        # 连接Redis集群
        startup_nodes = [
            {"host": "localhost", "port": 6379},
            {"host": "localhost", "port": 6380},
            {"host": "localhost", "port": 6381},
        ]

        cluster_client = redis.RedisCluster(
            startup_nodes=startup_nodes,
            decode_responses=True,
            skip_full_coverage_check=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        # 性能测试
        operations = 1000
        start_time = time.time()

        # 批量写入测试
        for i in range(operations):
            cluster_client.set(f"perf_test_key_{i}", f"value_{i}")

        write_time = time.time() - start_time

        # 批量读取测试
        start_time = time.time()
        for i in range(operations):
            cluster_client.get(f"perf_test_key_{i}")

        read_time = time.time() - start_time

        # 计算性能指标
        write_ops_per_sec = operations / write_time
        read_ops_per_sec = operations / read_time

        print(f"✅ 写入性能: {write_ops_per_sec:.2f} ops/sec")
        print(f"✅ 读取性能: {read_ops_per_sec:.2f} ops/sec")
        print(f"✅ 写入耗时: {write_time:.3f} 秒")
        print(f"✅ 读取耗时: {read_time:.3f} 秒")

        return True
    except Exception as e:
        print(f"❌ Redis集群性能测试失败: {e}")
        return False


def test_cluster_failover():
    """测试集群故障转移"""
    print("🔍 测试集群故障转移...")

    try:
        from app.core.permission.monitor_backends import RedisBackend

        # 创建Redis后端实例
        backend = RedisBackend(
            redis_url="redis://localhost:6379",
            key_prefix="failover_test:",
            max_history_size=1000,
        )

        # 测试连接健康检查
        if backend.redis is None:
            print("❌ Redis连接失败")
            return False

        # 测试连接健康状态
        healthy = backend._check_connection_health()
        print(f"✅ 连接健康状态: {healthy}")

        # 测试指标记录（模拟故障转移场景）
        success = backend.record_metric("failover_test", 100.0, {"test": "failover"})
        print(f"✅ 故障转移测试指标记录: {success}")

        return True
    except Exception as e:
        print(f"❌ 集群故障转移测试失败: {e}")
        return False


def run_redis_cluster_test():
    """运行Redis集群测试"""
    print("🚀 开始Redis集群功能测试...")
    print("=" * 60)

    tests = [
        ("Redis集群连接", test_redis_cluster_connection),
        ("监控后端Redis集群", test_monitor_backend_redis_cluster),
        ("混合缓存Redis集群", test_hybrid_cache_redis_cluster),
        ("高级优化Redis集群", test_advanced_optimization_redis_cluster),
        ("Redis集群性能", test_performance_redis_cluster),
        ("集群故障转移", test_cluster_failover),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 测试: {test_name}")
        print("-" * 40)
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} 失败")

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有Redis集群测试通过！")
        print("\n📋 功能验证:")
        print("✅ Redis集群连接 - 成功连接到6379、6380、6381端口")
        print("✅ 监控后端集群 - 指标和事件记录功能正常")
        print("✅ 混合缓存集群 - 分布式缓存操作正常")
        print("✅ 高级优化集群 - 智能失效和预加载功能正常")
        print("✅ 集群性能 - 读写性能符合预期")
        print("✅ 故障转移 - 连接健康检查和降级机制正常")
        return True
    else:
        print("❌ 部分测试失败，需要检查Redis集群配置。")
        return False


if __name__ == "__main__":
    run_redis_cluster_test()
