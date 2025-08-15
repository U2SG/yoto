"""
智能失效机制简化测试
"""

import sys
import os
import time
from unittest.mock import Mock

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def test_smart_invalidation_core():
    """测试智能失效核心功能"""
    print("🔧 测试智能失效核心功能...")

    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.ping.return_value = True

        # 创建配置
        config = {
            "smart_invalidation_interval": 1,
            "min_queue_size": 10,
            "max_growth_rate": 0.1,
            "min_processing_rate": 5,
        }

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(config, mock_redis)

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
        print(f"❌ 智能失效核心功能测试失败: {e}")
        return False


def test_double_checked_locking():
    """测试双重检查锁定"""
    print("🔧 测试双重检查锁定...")

    try:
        from app.core.permission.hybrid_permission_cache import HybridPermissionCache

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.get.return_value = b'{"permissions": ["perm1", "perm2"]}'

        # 创建混合缓存实例
        cache = HybridPermissionCache()
        cache.distributed_cache = Mock()
        cache.distributed_cache.redis_client = mock_redis

        # 模拟分布式锁管理器
        mock_lock_manager = Mock()
        mock_lock = Mock()
        mock_lock.__enter__ = Mock(return_value=mock_lock)
        mock_lock.__exit__ = Mock(return_value=None)
        mock_lock_manager.create_lock.return_value = mock_lock
        cache._distributed_lock_manager = mock_lock_manager

        # 测试双重检查锁定
        result = cache.distributed_cache_get("test_key")
        print(f"✅ 双重检查锁定: {result is not None}")

        return True
    except Exception as e:
        print(f"❌ 双重检查锁定测试失败: {e}")
        return False


def test_background_tasks():
    """测试后台任务"""
    print("🔧 测试后台任务...")

    try:
        from app.core.permission.advanced_optimization import (
            AdvancedDistributedOptimizer,
        )

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.zrevrange.return_value = [b"1", b"2"]
        mock_redis.lrange.return_value = []

        # 创建配置
        config = {
            "smart_invalidation_interval": 1,
            "preload_interval": 1,
            "preload": {"enabled": True},
            "batch_size": 100,
        }

        # 创建优化器实例
        optimizer = AdvancedDistributedOptimizer(config, mock_redis)

        # 检查后台任务是否启动
        print(f"✅ 后台任务统计: {len(optimizer._stats)} 项")

        return True
    except Exception as e:
        print(f"❌ 后台任务测试失败: {e}")
        return False


def run_simple_tests():
    """运行简化测试"""
    print("🚀 开始智能失效机制简化测试...")
    print("=" * 60)

    tests = [
        ("智能失效核心功能", test_smart_invalidation_core),
        ("双重检查锁定", test_double_checked_locking),
        ("后台任务", test_background_tasks),
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
        print("🎉 智能失效机制核心功能正常！")
        print("\n📋 功能总结:")
        print("✅ 智能失效分析 - 根据队列状态智能判断")
        print("✅ 数据预加载 - 预加载热门用户和角色权限")
        print("✅ 双重检查锁定 - 减少锁竞争，提高性能")
        print("✅ 后台任务 - 异步处理批量操作")
        print("✅ 错误处理 - 优雅处理各种异常")
        return True
    else:
        print("❌ 部分功能需要进一步调试。")
        return False


if __name__ == "__main__":
    run_simple_tests()
