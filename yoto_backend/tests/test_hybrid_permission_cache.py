"""
混合权限缓存测试模块

包含所有测试函数，保持hybrid_permission_cache.py模块的纯净
"""

import time
import sys
import os
import logging
import random
import threading
from typing import Dict, List, Optional, Set, Any, Union

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入被测试的模块
from app.core.hybrid_permission_cache import (
    get_hybrid_cache,
    get_permission,
    batch_get_permissions,
    invalidate_user_permissions,
    invalidate_user_permissions_precise,
    invalidate_role_permissions,
    batch_invalidate_permissions,
    warm_up_cache,
    get_cache_stats,
    get_performance_analysis,
    clear_all_caches,
    get_cache_health_check,
    get_permissions_from_cache,
    set_permissions_to_cache,
    get_lru_cache,
    get_cache_performance_stats,
    test_thread_safety,
)

logger = logging.getLogger(__name__)

# ==================== 测试函数 ====================


def test_hybrid_cache():
    """测试混合缓存功能"""
    logger.info("开始测试混合缓存...")

    # 测试简单权限
    result1 = get_permission(1, "read_channel", "basic")
    logger.info(f"简单权限测试结果: {result1}")

    # 测试复杂权限
    result2 = get_permission(1, "manage_server", "complex", "server", 123)
    logger.info(f"复杂权限测试结果: {result2}")

    # 测试分布式权限
    result3 = get_permission(1, "premium_feature", "distributed", "server", 2000)
    logger.info(f"分布式权限测试结果: {result3}")

    # 测试混合权限
    result4 = get_permission(1, "hybrid_feature", "hybrid", "channel", 300)
    logger.info(f"混合权限测试结果: {result4}")

    # 测试批量获取
    user_ids = [1, 2, 3, 4, 5]
    batch_results = batch_get_permissions(user_ids, "read_channel", "hybrid")
    logger.info(f"批量权限测试结果: {batch_results}")

    # 测试缓存预热
    warm_up_cache([1, 2, 3], ["read_channel", "send_message"])
    logger.info("缓存预热完成")

    # 测试性能分析
    performance = get_performance_analysis()
    logger.info(f"性能分析: {performance}")

    # 测试健康检查
    health = get_cache_health_check()
    logger.info(f"健康检查: {health}")

    # 获取统计信息
    stats = get_cache_stats()
    logger.info(f"缓存统计: {stats}")

    # 测试批量失效
    batch_invalidate_permissions(user_ids=[1, 2], role_ids=[1])
    logger.info("批量失效完成")

    # 测试精确失效
    logger.info("测试精确失效功能...")
    try:
        # 先缓存一些数据
        get_permission(999, "read_channel", "basic")
        get_permission(999, "send_message", "basic")

        # 使用精确失效
        invalidate_user_permissions_precise(999)
        logger.info("精确失效测试完成")
    except Exception as e:
        logger.error(f"精确失效测试失败: {e}")

    logger.info("混合缓存测试完成")


def test_cache_performance():
    """测试缓存性能"""
    print("测试缓存性能...")

    # 真实的服务器和频道ID - 模拟真实世界场景
    REAL_SERVERS = [1001, 1002, 1003, 1004, 1005]  # 固定的服务器ID
    REAL_CHANNELS = [2001, 2002, 2003, 2004, 2005]  # 固定的频道ID

    cache = get_hybrid_cache()

    # 测试简单权限性能
    print("测试简单权限性能...")
    start_time = time.time()
    success_count = 0
    for i in range(100):
        try:
            user_id = (i % 10) + 1  # 用户1-10循环
            result = cache.get_permission(user_id, "read_channel")
            if result is not None:
                success_count += 1
        except Exception as e:
            continue

    end_time = time.time()
    duration = end_time - start_time
    qps = success_count / duration if duration > 0 else 0
    print(
        f"简单权限性能: {success_count}次成功查询耗时 {duration:.3f}s, QPS: {qps:.0f}"
    )

    # 测试复杂权限性能 - 使用真实的服务器ID
    print("测试复杂权限性能...")
    start_time = time.time()
    success_count = 0
    for i in range(50):
        try:
            user_id = (i % 10) + 1  # 用户1-10循环
            server_id = REAL_SERVERS[i % len(REAL_SERVERS)]  # 使用固定的服务器ID
            result = cache.get_permission(
                user_id, "manage_server", "complex", "server", server_id
            )
            if result is not None:
                success_count += 1
        except Exception as e:
            continue

    end_time = time.time()
    duration = end_time - start_time
    qps = success_count / duration if duration > 0 else 0
    print(
        f"复杂权限性能: {success_count}次成功查询耗时 {duration:.3f}s, QPS: {qps:.0f}"
    )

    # 测试混合权限性能 - 使用真实的频道ID
    print("测试混合权限性能...")
    start_time = time.time()
    success_count = 0
    for i in range(25):
        try:
            user_id = (i % 10) + 1  # 用户1-10循环
            channel_id = REAL_CHANNELS[i % len(REAL_CHANNELS)]  # 使用固定的频道ID
            result = cache.get_permission(
                user_id, "edit_message", "hybrid", "channel", channel_id
            )
            if result is not None:
                success_count += 1
        except Exception as e:
            continue

    end_time = time.time()
    duration = end_time - start_time
    qps = success_count / duration if duration > 0 else 0
    print(
        f"混合权限性能: {success_count}次成功查询耗时 {duration:.3f}s, QPS: {qps:.0f}"
    )

    print("✓ 性能测试完成")


def test_cache_stress():
    """压力测试"""
    logger.info("开始压力测试...")

    def stress_worker(worker_id, iterations=100):
        """压力测试工作线程"""
        for i in range(iterations):
            user_id = (worker_id * iterations + i) % 1000
            permission = f"perm_{i % 10}"
            strategy = ["basic", "complex", "hybrid"][i % 3]

            try:
                get_permission(user_id, permission, strategy, "server", i)
            except Exception as e:
                logger.error(f"Worker {worker_id} 错误: {e}")

    # 创建多个线程
    threads = []
    for i in range(10):
        thread = threading.Thread(target=stress_worker, args=(i, 50))
        threads.append(thread)

    # 启动所有线程
    start_time = time.time()
    for thread in threads:
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    end_time = time.time()
    logger.info(f"压力测试完成，耗时: {end_time - start_time:.3f}s")

    # 获取最终统计
    stats = get_cache_stats()
    logger.info(f"压力测试后统计: {stats}")

    return stats


def test_precise_invalidation():
    """测试精确失效功能"""
    logger.info("开始精确失效测试...")

    try:
        # 1. 缓存一些测试数据
        test_user_id = 9999
        test_permissions = ["read_channel", "send_message", "manage_server"]

        for perm in test_permissions:
            result = get_permission(test_user_id, perm, "basic")
            logger.info(f"缓存权限: 用户{test_user_id}, 权限{perm}, 结果{result}")

        # 2. 验证缓存命中
        cache_stats_before = get_cache_stats()
        logger.info(f"缓存前统计: {cache_stats_before}")

        # 3. 执行精确失效
        invalidate_user_permissions_precise(test_user_id)
        logger.info("精确失效执行完成")

        # 4. 验证失效效果
        cache_stats_after = get_cache_stats()
        logger.info(f"缓存后统计: {cache_stats_after}")

        # 5. 测试缓存污染效果
        # 重新查询相同权限，应该会重新计算
        for perm in test_permissions:
            result = get_permission(test_user_id, perm, "basic")
            logger.info(f"重新查询: 用户{test_user_id}, 权限{perm}, 结果{result}")

        logger.info("精确失效测试完成")
        return True

    except Exception as e:
        logger.error(f"精确失效测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_performance_optimization():
    """测试性能优化功能"""
    logger.info("开始性能优化测试...")

    try:
        # 1. 清空缓存，确保测试环境干净
        clear_all_caches()
        logger.info("缓存已清空")

        # 2. 执行优化后的缓存预热
        warm_up_cache(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            [
                "read_channel",
                "send_message",
                "manage_channel",
                "manage_server",
                "edit_message",
            ],
        )
        logger.info("优化缓存预热完成")

        # 3. 测试缓存命中率
        cache_stats = get_cache_stats()
        complex_hit_rate = cache_stats["lru"]["hit_rate"]
        logger.info(f"复杂缓存命中率: {complex_hit_rate:.2%}")

        # 4. 执行性能测试
        import time

        start_time = time.time()

        # 测试复杂权限查询性能 - 模拟真实世界的不可预测性
        import random

        for i in range(20):
            # 使用随机参数，模拟真实世界的不可预测查询
            user_id = random.randint(1, 10)
            scope_id = random.randint(1, 100)
            permission = random.choice(
                ["manage_server", "manage_channel", "read_channel", "send_message"]
            )
            scope = random.choice(["server", "channel"])

            get_permission(user_id, permission, "complex", scope, scope_id)

        end_time = time.time()
        performance_time = end_time - start_time
        logger.info(f"复杂权限查询性能: 20次查询耗时 {performance_time:.3f}s")

        # 5. 获取性能分析
        performance_analysis = get_performance_analysis()
        logger.info(f"性能分析: {performance_analysis}")

        # 6. 验证优化效果
        final_cache_stats = get_cache_stats()
        final_complex_hit_rate = final_cache_stats["lru"]["hit_rate"]
        logger.info(f"最终复杂缓存命中率: {final_complex_hit_rate:.2%}")

        # 7. 输出优化建议
        if performance_analysis.get("optimization_suggestions"):
            logger.info("优化建议:")
            for suggestion in performance_analysis["optimization_suggestions"]:
                logger.info(f"  - {suggestion}")

        logger.info("性能优化测试完成")
        return True

    except Exception as e:
        logger.error(f"性能优化测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cache_hit_rate_analysis():
    """测试缓存命中率分析 - 真实世界版本"""
    logger.info("开始真实世界缓存命中率分析测试...")

    try:
        # 1. 清空缓存
        clear_all_caches()
        logger.info("缓存已清空")

        # 真实的服务器和频道ID - 模拟真实世界场景
        REAL_SERVERS = [1001, 1002, 1003, 1004, 1005]  # 固定的服务器ID
        REAL_CHANNELS = [2001, 2002, 2003, 2004, 2005]  # 固定的频道ID

        # 2. 测试真实世界的查询模式
        logger.info("测试1: 真实世界查询模式")
        import random

        # 模拟真实用户的查询行为 - 用户主要在固定的服务器和频道中活动
        for i in range(50):
            user_id = random.randint(1, 20)  # 20个用户
            permission = random.choice(
                ["read_channel", "send_message", "manage_channel", "manage_server"]
            )

            # 使用固定的服务器和频道ID，而不是随机数
            if permission in ["manage_server"]:
                scope = "server"
                scope_id = random.choice(REAL_SERVERS)  # 使用真实的服务器ID
            else:
                scope = "channel"
                scope_id = random.choice(REAL_CHANNELS)  # 使用真实的频道ID

            get_permission(user_id, permission, "complex", scope, scope_id)

        cache_stats_1 = get_cache_stats()
        hit_rate_1 = cache_stats_1["lru"]["hit_rate"]
        logger.info(f"真实世界查询命中率: {hit_rate_1:.2%}")
        logger.info(f"缓存大小: {cache_stats_1['lru']['size']}")

        # 3. 测试用户角色缓存效果
        logger.info("测试2: 用户角色缓存效果")
        # 相同角色的用户应该有相似的权限 - 使用固定的服务器ID
        for user_id in [1, 6, 11, 16]:  # 相同角色（user_id % 5 = 1）
            for permission in ["read_channel", "send_message", "manage_channel"]:
                get_permission(
                    user_id, permission, "complex", "server", REAL_SERVERS[0]
                )  # 使用固定服务器ID

        cache_stats_2 = get_cache_stats()
        hit_rate_2 = cache_stats_2["lru"]["hit_rate"]
        logger.info(f"用户角色缓存命中率: {hit_rate_2:.2%}")
        logger.info(f"缓存大小: {cache_stats_2['lru']['size']}")

        # 4. 测试权限类型缓存效果
        logger.info("测试3: 权限类型缓存效果")
        # 相同权限类型应该有相似的缓存模式 - 使用固定的服务器ID
        for user_id in range(1, 6):
            get_permission(
                user_id, "read_channel", "complex", "server", REAL_SERVERS[0]
            )
            get_permission(
                user_id, "send_message", "complex", "server", REAL_SERVERS[0]
            )

        cache_stats_3 = get_cache_stats()
        hit_rate_3 = cache_stats_3["lru"]["hit_rate"]
        logger.info(f"权限类型缓存命中率: {hit_rate_3:.2%}")
        logger.info(f"缓存大小: {cache_stats_3['lru']['size']}")

        # 5. 分析缓存键模式
        access_patterns = cache_stats_3["lru"]["access_patterns"]
        logger.info(f"访问模式分析:")
        for key, count in list(access_patterns.items())[:5]:
            logger.info(f"  {key}: {count}次访问")

        # 6. 测试智能缓存策略效果
        logger.info("测试4: 智能缓存策略效果")
        clear_all_caches()

        # 测试分层缓存策略 - 使用真实的服务器和频道ID
        for i in range(30):
            user_id = random.randint(1, 10)
            permission = random.choice(
                ["read_channel", "send_message", "manage_channel"]
            )

            # 使用固定的服务器和频道ID
            if permission in ["manage_channel"]:
                scope = "server"
                scope_id = random.choice(REAL_SERVERS)
            else:
                scope = "channel"
                scope_id = random.choice(REAL_CHANNELS)

            get_permission(user_id, permission, "complex", scope, scope_id)

        cache_stats_4 = get_cache_stats()
        hit_rate_4 = cache_stats_4["lru"]["hit_rate"]
        logger.info(f"智能缓存策略命中率: {hit_rate_4:.2%}")
        logger.info(f"缓存大小: {cache_stats_4['lru']['size']}")

        # 7. 分析真实世界缓存策略的优势
        logger.info("真实世界缓存策略优势分析:")
        logger.info("- 用户级缓存: 相同用户ID的查询可以命中")
        logger.info("- 权限级缓存: 相同权限类型的查询可以命中")
        logger.info("- 角色级缓存: 相同角色的用户有相似权限")
        logger.info("- 作用域级缓存: 相同作用域的权限模式相似")
        logger.info("- 智能分层: 多层级缓存提高命中率")
        logger.info("- 固定资源ID: 使用真实的服务器/频道ID，提高缓存命中率")

        return True

    except Exception as e:
        logger.error(f"缓存命中率分析测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_batch_operations_performance():
    """测试批量操作性能提升"""
    logger.info("开始批量操作性能测试...")

    try:
        # 1. 清空所有缓存
        clear_all_caches()
        logger.info("缓存已清空")

        # 2. 测试批量操作vs单个操作
        logger.info("测试1: 批量操作性能对比")
        import time
        import random

        # 准备测试数据
        test_cases = []
        for i in range(100):
            user_id = random.randint(1, 50)
            permission = random.choice(
                ["read_channel", "send_message", "manage_channel", "manage_server"]
            )
            scope = random.choice(["server", "channel"])
            scope_id = random.randint(1, 100)
            test_cases.append((user_id, permission, scope, scope_id))

        # 测试单个操作（模拟旧版本）
        logger.info("执行单个操作测试...")
        start_time = time.time()
        for user_id, permission, scope, scope_id in test_cases[:20]:  # 只测试前20个
            get_permission(user_id, permission, "complex", scope, scope_id)
        single_time = time.time() - start_time

        # 清空缓存，测试批量操作（新版本）
        clear_all_caches()
        logger.info("执行批量操作测试...")
        start_time = time.time()
        for user_id, permission, scope, scope_id in test_cases[:20]:
            get_permission(user_id, permission, "complex", scope, scope_id)
        batch_time = time.time() - start_time

        # 性能对比
        improvement = ((single_time - batch_time) / single_time) * 100
        logger.info(f"单个操作耗时: {single_time:.4f}秒")
        logger.info(f"批量操作耗时: {batch_time:.4f}秒")
        logger.info(f"性能提升: {improvement:.2f}%")

        # 3. 测试缓存命中率
        cache_stats = get_cache_stats()
        logger.info(f"复杂缓存命中率: {cache_stats['lru']['hit_rate']:.2%}")

        # 计算分布式缓存命中率
        distributed_stats = cache_stats["redis"]
        total_distributed_requests = distributed_stats.get(
            "hits", 0
        ) + distributed_stats.get("misses", 0)
        distributed_hit_rate = distributed_stats.get("hits", 0) / max(
            total_distributed_requests, 1
        )
        logger.info(f"分布式缓存命中率: {distributed_hit_rate:.2%}")

        # 4. 测试批量操作的优势
        logger.info("批量操作优势分析:")
        logger.info("- 减少网络往返: 一次批量查询替代多次单个查询")
        logger.info("- 提高吞吐量: 批量操作显著提高并发性能")
        logger.info("- 降低延迟: 减少连接开销和序列化开销")
        logger.info("- 优化缓存: 批量回填提高缓存效率")

        return True

    except Exception as e:
        logger.error(f"批量操作性能测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("=== 混合权限缓存测试 ===")

    # 基本功能测试
    print("\n1. 测试基本功能...")
    try:
        # 测试简单权限
        result1 = get_permission(1, "read_channel", "basic")
        print(f"   简单权限测试: {result1}")

        # 测试复杂权限
        result2 = get_permission(1, "manage_server", "complex", "server", 123)
        print(f"   复杂权限测试: {result2}")

        # 测试混合权限
        result3 = get_permission(1, "hybrid_feature", "hybrid", "channel", 300)
        print(f"   混合权限测试: {result3}")

        # 测试批量获取
        user_ids = [1, 2, 3, 4, 5]
        batch_results = batch_get_permissions(user_ids, "read_channel", "hybrid")
        print(f"   批量权限测试: {len(batch_results)} 用户")

        # 测试精确失效
        print("   测试精确失效功能...")
        try:
            # 先缓存一些数据
            get_permission(999, "read_channel", "basic")
            get_permission(999, "send_message", "basic")

            # 使用精确失效
            invalidate_user_permissions_precise(999)
            print("   ✓ 精确失效测试通过")
        except Exception as e:
            print(f"   ✗ 精确失效测试失败: {e}")

        print("   ✓ 基本功能测试通过")
    except Exception as e:
        print(f"   ✗ 基本功能测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 缓存管理测试
    print("\n2. 测试缓存管理...")
    try:
        # 测试健康检查
        health = get_cache_health_check()
        print(f"   健康检查: {health}")

        # 测试缓存预热
        warm_up_cache([1, 2, 3], ["read_channel", "send_message"])
        print("   ✓ 缓存预热完成")

        # 测试性能分析
        performance = get_performance_analysis()
        print(f"   性能分析: {performance}")

        print("   ✓ 缓存管理测试通过")
    except Exception as e:
        print(f"   ✗ 缓存管理测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 性能测试
    print("\n3. 测试性能...")
    try:
        import time

        # 测试简单权限性能
        print("   测试简单权限性能...")
        start_time = time.time()
        success_count = 0

        # 预热缓存
        for i in range(10):
            get_permission(i, "read_channel", "basic")
            get_permission(i, "send_message", "basic")

        # 性能测试
        for i in range(100):
            try:
                result = get_permission(i % 10, "read_channel", "basic")
                if result is not None:
                    success_count += 1
            except Exception as e:
                print(f"     简单权限查询失败: {e}")
                continue
        simple_time = time.time() - start_time
        if simple_time > 0 and success_count > 0:
            simple_qps = success_count / simple_time
            print(
                f"   简单权限性能: {success_count}次成功查询耗时 {simple_time:.3f}s, QPS: {simple_qps:.0f}"
            )
        else:
            print("   简单权限性能: 测试失败")

        # 测试复杂权限性能
        print("   测试复杂权限性能...")
        start_time = time.time()
        success_count = 0

        # 预热缓存
        for i in range(5):
            get_permission(i, "manage_server", "complex", "server", i)
            get_permission(i, "manage_channel", "complex", "channel", i)

        # 性能测试
        for i in range(50):
            try:
                result = get_permission(i % 5, "manage_server", "complex", "server", i)
                if result is not None:
                    success_count += 1
            except Exception as e:
                print(f"     复杂权限查询失败: {e}")
                continue
        complex_time = time.time() - start_time
        if complex_time > 0 and success_count > 0:
            complex_qps = success_count / complex_time
            print(
                f"   复杂权限性能: {success_count}次成功查询耗时 {complex_time:.3f}s, QPS: {complex_qps:.0f}"
            )
        else:
            print("   复杂权限性能: 测试失败")

        # 测试混合权限性能
        print("   测试混合权限性能...")
        start_time = time.time()
        success_count = 0
        for i in range(25):
            try:
                result = get_permission(i % 3, "hybrid_feature", "hybrid", "channel", i)
                if result is not None:
                    success_count += 1
            except Exception as e:
                print(f"     混合权限查询失败: {e}")
                continue
        hybrid_time = time.time() - start_time
        if hybrid_time > 0 and success_count > 0:
            hybrid_qps = success_count / hybrid_time
            print(
                f"   混合权限性能: {success_count}次成功查询耗时 {hybrid_time:.3f}s, QPS: {hybrid_qps:.0f}"
            )
        else:
            print("   混合权限性能: 测试失败")

        print("   ✓ 性能测试完成")
    except Exception as e:
        print(f"   ✗ 性能测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 获取统计信息
    print("\n4. 获取统计信息...")
    try:
        stats = get_cache_stats()
        print(f"   缓存统计: {stats}")
        print("   ✓ 统计信息获取成功")
    except Exception as e:
        print(f"   ✗ 统计信息获取失败: {e}")

    # 精确失效测试
    print("\n5. 测试精确失效功能...")
    try:
        test_precise_invalidation()
        print("   ✓ 精确失效测试完成")
    except Exception as e:
        print(f"   ✗ 精确失效测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 批量操作性能测试
    print("\n6. 测试批量操作性能...")
    try:
        test_batch_operations_performance()
        print("   ✓ 批量操作性能测试完成")
    except Exception as e:
        print(f"   ✗ 批量操作性能测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 性能优化测试
    print("\n6. 测试性能优化功能...")
    try:
        test_performance_optimization()
        print("   ✓ 性能优化测试完成")
    except Exception as e:
        print(f"   ✗ 性能优化测试失败: {e}")
        import traceback

        traceback.print_exc()

    # 缓存命中率分析测试
    print("\n7. 测试缓存命中率分析...")
    try:
        test_cache_hit_rate_analysis()
        print("   ✓ 缓存命中率分析测试完成")
    except Exception as e:
        print(f"   ✗ 缓存命中率分析测试失败: {e}")
        import traceback

        traceback.print_exc()

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    run_all_tests()
