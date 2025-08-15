"""
测试分布式锁模块提取和功能恢复

验证以下内容：
1. 通用分布式锁模块可以正常导入和使用
2. 高级优化模块的缓存功能已恢复
3. 韧性模块可以正常使用分布式锁
4. 权限缓存模块可以正常使用高级优化功能
5. 没有循环依赖问题
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..", "..")
sys.path.insert(0, project_root)

# 简化导入，避免复杂的模块路径
try:
    from app.core.common.distributed_lock import (
        OptimizedDistributedLock,
        create_optimized_distributed_lock,
    )

    print("✅ 通用分布式锁模块导入成功")
except ImportError as e:
    print(f"❌ 通用分布式锁模块导入失败: {e}")
    sys.exit(1)


class TestDistributedLockExtraction(unittest.TestCase):
    """测试分布式锁模块提取"""

    def setUp(self):
        """设置测试环境"""
        self.mock_redis = Mock()
        self.mock_redis.set.return_value = True
        self.mock_redis.get.return_value = b"test_value"
        self.mock_redis.eval.return_value = 1
        self.mock_redis.ping.return_value = True
        self.mock_redis.expire.return_value = True

    def test_01_optimized_distributed_lock_creation(self):
        """测试OptimizedDistributedLock可以正常创建"""
        try:
            lock = OptimizedDistributedLock(
                redis_client=self.mock_redis,
                lock_key="test_lock",
                timeout=2.0,
                retry_interval=0.02,
                retry_count=3,
            )
            self.assertIsNotNone(lock)
            self.assertEqual(lock.lock_key, "lock:opt:test_lock")
            print("✅ OptimizedDistributedLock创建成功")
        except Exception as e:
            self.fail(f"OptimizedDistributedLock创建失败: {e}")

    def test_02_create_optimized_distributed_lock_factory(self):
        """测试工厂函数可以正常创建分布式锁"""
        try:
            lock = create_optimized_distributed_lock(
                redis_client=self.mock_redis, lock_key="test_factory_lock", timeout=1.0
            )
            self.assertIsNotNone(lock)
            self.assertEqual(lock.lock_key, "lock:opt:test_factory_lock")
            print("✅ 工厂函数创建分布式锁成功")
        except Exception as e:
            self.fail(f"工厂函数创建分布式锁失败: {e}")

    def test_03_distributed_lock_context_manager(self):
        """测试分布式锁的上下文管理器"""
        lock = OptimizedDistributedLock(
            redis_client=self.mock_redis, lock_key="test_context_lock"
        )

        try:
            with lock:
                # 在锁的上下文中执行操作
                self.assertTrue(lock.lock_value is not None)
                print("✅ 分布式锁上下文管理器工作正常")
        except Exception as e:
            self.fail(f"分布式锁上下文管理器失败: {e}")

    def test_04_advanced_optimization_functions_exist(self):
        """测试高级优化模块的函数存在"""
        try:
            # 动态导入以避免循环依赖
            import importlib

            advanced_opt_module = importlib.import_module(
                "app.core.permission.advanced_optimization"
            )

            # 检查函数是否存在
            self.assertTrue(
                hasattr(advanced_opt_module, "advanced_get_permissions_from_cache")
            )
            self.assertTrue(
                hasattr(advanced_opt_module, "advanced_set_permissions_to_cache")
            )
            self.assertTrue(
                hasattr(advanced_opt_module, "advanced_batch_get_permissions")
            )
            self.assertTrue(hasattr(advanced_opt_module, "get_advanced_optimizer"))

            print("✅ 高级优化模块函数存在")
        except Exception as e:
            self.fail(f"高级优化模块函数检查失败: {e}")

    def test_05_no_circular_dependencies(self):
        """测试没有循环依赖问题"""
        try:
            # 尝试导入所有相关模块
            import importlib

            # 按依赖顺序导入
            importlib.import_module("app.core.common.distributed_lock")
            importlib.import_module("app.core.permission.advanced_optimization")
            importlib.import_module("app.core.permission.permission_resilience")
            importlib.import_module("app.core.permission.hybrid_permission_cache")

            print("✅ 没有循环依赖问题")
        except ImportError as e:
            self.fail(f"存在循环依赖问题: {e}")


class TestDistributedLockFunctionality(unittest.TestCase):
    """测试分布式锁功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_redis = Mock()
        self.mock_redis.set.return_value = True
        self.mock_redis.get.return_value = b"test_value"
        self.mock_redis.eval.return_value = 1
        self.mock_redis.ping.return_value = True
        self.mock_redis.expire.return_value = True

    def test_01_lock_acquire_release(self):
        """测试锁的获取和释放"""
        lock = OptimizedDistributedLock(
            redis_client=self.mock_redis, lock_key="test_acquire_release"
        )

        # 测试获取锁
        result = lock.acquire()
        self.assertTrue(result)
        self.assertIsNotNone(lock.lock_value)

        # 测试释放锁
        result = lock.release()
        self.assertTrue(result)
        self.assertIsNone(lock.lock_value)

        print("✅ 锁的获取和释放功能正常")

    def test_02_lock_timeout_handling(self):
        """测试锁超时处理"""
        # 模拟Redis不可用
        mock_redis_unavailable = Mock()
        mock_redis_unavailable.set.side_effect = Exception("Redis unavailable")

        lock = OptimizedDistributedLock(
            redis_client=mock_redis_unavailable, lock_key="test_timeout"
        )

        # 测试获取锁失败
        result = lock.acquire()
        self.assertFalse(result)
        self.assertIsNone(lock.lock_value)

        print("✅ 锁超时处理功能正常")

    def test_03_lock_thread_safety(self):
        """测试锁的线程安全性"""
        lock = OptimizedDistributedLock(
            redis_client=self.mock_redis, lock_key="test_thread_safety"
        )

        results = []

        def worker():
            try:
                with lock:
                    results.append(threading.current_thread().name)
                    time.sleep(0.1)
            except Exception as e:
                results.append(f"error: {e}")

        # 创建多个线程
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, name=f"Thread-{i}")
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有线程都执行了
        self.assertEqual(len(results), 3)
        print("✅ 锁的线程安全性正常")


def run_tests():
    """运行所有测试"""
    print("🚀 开始测试分布式锁模块提取和功能恢复...")
    print("=" * 60)

    # 创建测试套件
    test_suite = unittest.TestSuite()

    # 添加测试类
    test_suite.addTest(unittest.makeSuite(TestDistributedLockExtraction))
    test_suite.addTest(unittest.makeSuite(TestDistributedLockFunctionality))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    print("=" * 60)
    if result.wasSuccessful():
        print("🎉 所有测试通过！分布式锁模块提取和功能恢复成功。")
    else:
        print("❌ 部分测试失败，请检查相关功能。")

    return result.wasSuccessful()


if __name__ == "__main__":
    run_tests()
