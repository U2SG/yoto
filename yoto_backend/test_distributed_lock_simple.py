"""
简单的分布式锁模块测试脚本
直接在yoto_backend目录下运行
"""

import sys
import os
import unittest
from unittest.mock import Mock

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def test_distributed_lock_import():
    """测试分布式锁模块导入"""
    try:
        from app.core.common.distributed_lock import (
            OptimizedDistributedLock,
            create_optimized_distributed_lock,
        )

        print("✅ 通用分布式锁模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ 通用分布式锁模块导入失败: {e}")
        return False


def test_optimized_distributed_lock_creation():
    """测试OptimizedDistributedLock创建"""
    try:
        from app.core.common.distributed_lock import OptimizedDistributedLock

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test_value"
        mock_redis.eval.return_value = 1
        mock_redis.ping.return_value = True
        mock_redis.expire.return_value = True

        # 创建分布式锁
        lock = OptimizedDistributedLock(
            redis_client=mock_redis,
            lock_key="test_lock",
            timeout=2.0,
            retry_interval=0.02,
            retry_count=3,
        )

        print("✅ OptimizedDistributedLock创建成功")
        print(f"   锁键: {lock.lock_key}")
        print(f"   超时: {lock.timeout}")
        return True
    except Exception as e:
        print(f"❌ OptimizedDistributedLock创建失败: {e}")
        return False


def test_factory_function():
    """测试工厂函数"""
    try:
        from app.core.common.distributed_lock import create_optimized_distributed_lock

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test_value"
        mock_redis.eval.return_value = 1
        mock_redis.ping.return_value = True
        mock_redis.expire.return_value = True

        # 使用工厂函数创建锁
        lock = create_optimized_distributed_lock(
            redis_client=mock_redis, lock_key="test_factory_lock", timeout=1.0
        )

        print("✅ 工厂函数创建分布式锁成功")
        print(f"   锁键: {lock.lock_key}")
        return True
    except Exception as e:
        print(f"❌ 工厂函数创建分布式锁失败: {e}")
        return False


def test_context_manager():
    """测试上下文管理器"""
    try:
        from app.core.common.distributed_lock import OptimizedDistributedLock

        # 创建模拟的Redis客户端
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test_value"
        mock_redis.eval.return_value = 1
        mock_redis.ping.return_value = True
        mock_redis.expire.return_value = True

        # 测试上下文管理器
        lock = OptimizedDistributedLock(
            redis_client=mock_redis, lock_key="test_context_lock"
        )

        with lock:
            print("✅ 分布式锁上下文管理器工作正常")
            print(f"   锁值: {lock.lock_value}")

        return True
    except Exception as e:
        print(f"❌ 分布式锁上下文管理器失败: {e}")
        return False


def test_advanced_optimization_functions():
    """测试高级优化模块的函数"""
    try:
        import importlib

        advanced_opt_module = importlib.import_module(
            "app.core.permission.advanced_optimization"
        )

        # 检查函数是否存在
        functions_to_check = [
            "advanced_get_permissions_from_cache",
            "advanced_set_permissions_to_cache",
            "advanced_batch_get_permissions",
            "get_advanced_optimizer",
        ]

        for func_name in functions_to_check:
            if hasattr(advanced_opt_module, func_name):
                print(f"✅ 函数 {func_name} 存在")
            else:
                print(f"❌ 函数 {func_name} 不存在")
                return False

        print("✅ 高级优化模块函数检查通过")
        return True
    except Exception as e:
        print(f"❌ 高级优化模块函数检查失败: {e}")
        return False


def test_no_circular_dependencies():
    """测试没有循环依赖"""
    try:
        import importlib

        # 按依赖顺序导入
        modules_to_import = [
            "app.core.common.distributed_lock",
            "app.core.permission.advanced_optimization",
            "app.core.permission.permission_resilience",
            "app.core.permission.hybrid_permission_cache",
        ]

        for module_name in modules_to_import:
            try:
                importlib.import_module(module_name)
                print(f"✅ 模块 {module_name} 导入成功")
            except ImportError as e:
                print(f"❌ 模块 {module_name} 导入失败: {e}")
                return False

        print("✅ 没有循环依赖问题")
        return True
    except Exception as e:
        print(f"❌ 循环依赖检查失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始测试分布式锁模块提取和功能恢复...")
    print("=" * 60)

    tests = [
        ("分布式锁模块导入", test_distributed_lock_import),
        ("OptimizedDistributedLock创建", test_optimized_distributed_lock_creation),
        ("工厂函数", test_factory_function),
        ("上下文管理器", test_context_manager),
        ("高级优化模块函数", test_advanced_optimization_functions),
        ("循环依赖检查", test_no_circular_dependencies),
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
        print("🎉 所有测试通过！分布式锁模块提取和功能恢复成功。")
        return True
    else:
        print("❌ 部分测试失败，请检查相关功能。")
        return False


if __name__ == "__main__":
    run_all_tests()
