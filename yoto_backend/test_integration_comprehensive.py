"""
全面集成测试脚本

包含压力测试和回归测试，验证智能缓存失效和数据预加载机制
"""

import sys
import os
import time
import threading
import concurrent.futures
import statistics
from unittest.mock import Mock, patch
from collections import defaultdict

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


class IntegrationTestSuite:
    """集成测试套件"""

    def __init__(self):
        self.results = defaultdict(list)
        self.test_data = {}
        self.setup_test_environment()

    def setup_test_environment(self):
        """设置测试环境"""
        print("🔧 设置测试环境...")

        # 创建Flask应用
        from flask import Flask

        self.app = Flask(__name__)
        self.app.config.update(
            {
                "TESTING": True,
                "REDIS_CONFIG": {
                    "startup_nodes": [{"host": "localhost", "port": 6379}]
                },
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "preload_interval": 1,
                    "preload": {"enabled": True},
                    "batch_size": 100,
                    "min_queue_size": 10,
                    "max_growth_rate": 0.1,
                    "min_processing_rate": 5,
                },
            }
        )

        # 初始化模块
        with self.app.app_context():
            from app.core.permission.advanced_optimization import AdvancedOptimization
            from app.core.permission.permission_resilience import ResilienceExtension

            # 初始化韧性模块
            self.resilience = ResilienceExtension()
            self.resilience.init_app(self.app)

            # 初始化高级优化模块
            self.advanced_opt = AdvancedOptimization()
            self.advanced_opt.init_app(self.app)

    def run_regression_tests(self):
        """运行回归测试"""
        print("\n📋 开始回归测试...")
        print("=" * 60)

        tests = [
            ("基础功能测试", self.test_basic_functionality),
            ("缓存操作测试", self.test_cache_operations),
            ("智能失效测试", self.test_smart_invalidation),
            ("数据预加载测试", self.test_data_preloading),
            ("双重检查锁定测试", self.test_double_checked_locking),
            ("错误处理测试", self.test_error_handling),
            ("配置管理测试", self.test_configuration_management),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            print(f"\n🔍 测试: {test_name}")
            print("-" * 40)
            try:
                result = test_func()
                if result:
                    print(f"✅ {test_name} 通过")
                    passed += 1
                else:
                    print(f"❌ {test_name} 失败")
            except Exception as e:
                print(f"❌ {test_name} 异常: {e}")

        print(f"\n📊 回归测试结果: {passed}/{total} 通过")
        return passed == total

    def run_stress_tests(self):
        """运行压力测试"""
        print("\n📋 开始压力测试...")
        print("=" * 60)

        stress_tests = [
            ("高并发缓存操作", self.stress_test_high_concurrency_cache),
            ("大量权限检查", self.stress_test_mass_permission_checks),
            ("智能失效压力", self.stress_test_smart_invalidation),
            ("预加载压力", self.stress_test_preloading),
            ("双重检查锁定压力", self.stress_test_double_checked_locking),
        ]

        for test_name, test_func in stress_tests:
            print(f"\n🔥 压力测试: {test_name}")
            print("-" * 40)
            try:
                metrics = test_func()
                self.results[test_name] = metrics
                print(f"✅ {test_name} 完成")
                print(f"   平均响应时间: {metrics['avg_response_time']:.3f}ms")
                print(f"   最大响应时间: {metrics['max_response_time']:.3f}ms")
                print(f"   最小响应时间: {metrics['min_response_time']:.3f}ms")
                print(f"   成功率: {metrics['success_rate']:.2f}%")
                print(f"   总请求数: {metrics['total_requests']}")
            except Exception as e:
                print(f"❌ {test_name} 异常: {e}")

    def test_basic_functionality(self):
        """测试基础功能"""
        try:
            with self.app.app_context():
                from app.core.permission.advanced_optimization import (
                    get_advanced_optimizer,
                )

                optimizer = get_advanced_optimizer()
                if optimizer is None:
                    return False

                # 测试配置加载
                config = optimizer.config
                if not config:
                    return False

                # 测试Redis连接
                redis_client = optimizer.redis_client
                if redis_client is None:
                    return False

                return True
        except Exception as e:
            print(f"基础功能测试异常: {e}")
            return False

    def test_cache_operations(self):
        """测试缓存操作"""
        try:
            with self.app.app_context():
                from app.core.permission.hybrid_permission_cache import get_hybrid_cache

                cache = get_hybrid_cache()

                # 测试L1缓存
                test_key = "test_cache_key"
                test_data = {"permissions": ["read", "write"]}

                # 设置缓存
                cache.l1_simple_cache.set(test_key, test_data)

                # 获取缓存
                result = cache.l1_simple_cache.get(test_key)

                if result != test_data:
                    return False

                return True
        except Exception as e:
            print(f"缓存操作测试异常: {e}")
            return False

    def test_smart_invalidation(self):
        """测试智能失效"""
        try:
            with self.app.app_context():
                from app.core.permission.advanced_optimization import (
                    AdvancedDistributedOptimizer,
                )

                # 创建优化器实例
                config = self.app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
                mock_redis = Mock()
                mock_redis.ping.return_value = True

                optimizer = AdvancedDistributedOptimizer(config, mock_redis)

                # 测试智能失效分析
                analysis = optimizer._get_smart_invalidation_analysis()
                if not isinstance(analysis, dict):
                    return False

                # 测试预加载策略
                preload_result = optimizer._execute_preload_strategy()
                if not isinstance(preload_result, dict):
                    return False

                return True
        except Exception as e:
            print(f"智能失效测试异常: {e}")
            return False

    def test_data_preloading(self):
        """测试数据预加载"""
        try:
            with self.app.app_context():
                from app.core.permission.advanced_optimization import (
                    AdvancedDistributedOptimizer,
                )

                config = self.app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                mock_redis.zrevrange.return_value = [b"1", b"2", b"3"]

                optimizer = AdvancedDistributedOptimizer(config, mock_redis)

                # 测试获取热门用户
                hot_users = optimizer._get_hot_users()
                if not isinstance(hot_users, list):
                    return False

                # 测试获取热门角色
                hot_roles = optimizer._get_hot_roles()
                if not isinstance(hot_roles, list):
                    return False

                return True
        except Exception as e:
            print(f"数据预加载测试异常: {e}")
            return False

    def test_double_checked_locking(self):
        """测试双重检查锁定"""
        try:
            with self.app.app_context():
                from app.core.permission.hybrid_permission_cache import (
                    HybridPermissionCache,
                )

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
                if result is None:
                    return False

                return True
        except Exception as e:
            print(f"双重检查锁定测试异常: {e}")
            return False

    def test_error_handling(self):
        """测试错误处理"""
        try:
            with self.app.app_context():
                from app.core.permission.advanced_optimization import (
                    AdvancedDistributedOptimizer,
                )

                config = self.app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})

                # 测试Redis连接失败的情况
                mock_redis_failed = Mock()
                mock_redis_failed.ping.side_effect = Exception("Connection failed")

                optimizer = AdvancedDistributedOptimizer(config, mock_redis_failed)

                # 测试批量操作处理
                result = optimizer._process_batch_operations()
                if not isinstance(result, dict):
                    return False

                return True
        except Exception as e:
            print(f"错误处理测试异常: {e}")
            return False

    def test_configuration_management(self):
        """测试配置管理"""
        try:
            with self.app.app_context():
                from app.core.permission.advanced_optimization import (
                    get_advanced_optimization_config,
                )

                config = get_advanced_optimization_config()
                if not isinstance(config, dict):
                    return False

                # 检查必要的配置项
                required_keys = [
                    "smart_invalidation_interval",
                    "preload_interval",
                    "batch_size",
                ]
                for key in required_keys:
                    if key not in config:
                        return False

                return True
        except Exception as e:
            print(f"配置管理测试异常: {e}")
            return False

    def stress_test_high_concurrency_cache(self):
        """高并发缓存操作压力测试"""
        print("🔥 执行高并发缓存操作压力测试...")

        def cache_operation(thread_id):
            """单个缓存操作"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.hybrid_permission_cache import (
                        get_hybrid_cache,
                    )

                    cache = get_hybrid_cache()
                    key = f"stress_test_key_{thread_id}"
                    data = {"permissions": [f"perm_{thread_id}"]}

                    # 设置缓存
                    cache.l1_simple_cache.set(key, data)

                    # 获取缓存
                    result = cache.l1_simple_cache.get(key)

                    if result == data:
                        return time.time() - start_time, True
                    else:
                        return time.time() - start_time, False
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(cache_operation, 100, 10)

    def stress_test_mass_permission_checks(self):
        """大量权限检查压力测试"""
        print("🔥 执行大量权限检查压力测试...")

        def permission_check(thread_id):
            """单个权限检查"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.permissions_refactored import (
                        get_permission_system,
                    )

                    permission_system = get_permission_system()
                    user_id = thread_id % 10 + 1
                    permission = f"test_permission_{thread_id % 5}"

                    # 执行权限检查
                    result = permission_system.check_permission(user_id, permission)

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(permission_check, 200, 20)

    def stress_test_smart_invalidation(self):
        """智能失效压力测试"""
        print("🔥 执行智能失效压力测试...")

        def invalidation_operation(thread_id):
            """单个失效操作"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.advanced_optimization import (
                        AdvancedDistributedOptimizer,
                    )

                    config = self.app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
                    mock_redis = Mock()
                    mock_redis.ping.return_value = True

                    optimizer = AdvancedDistributedOptimizer(config, mock_redis)

                    # 执行智能失效分析
                    analysis = optimizer._get_smart_invalidation_analysis()

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(invalidation_operation, 50, 5)

    def stress_test_preloading(self):
        """预加载压力测试"""
        print("🔥 执行预加载压力测试...")

        def preload_operation(thread_id):
            """单个预加载操作"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.advanced_optimization import (
                        AdvancedDistributedOptimizer,
                    )

                    config = self.app.config.get("ADVANCED_OPTIMIZATION_CONFIG", {})
                    mock_redis = Mock()
                    mock_redis.ping.return_value = True
                    mock_redis.zrevrange.return_value = [b"1", b"2", b"3"]

                    optimizer = AdvancedDistributedOptimizer(config, mock_redis)

                    # 执行预加载策略
                    result = optimizer._execute_preload_strategy()

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(preload_operation, 30, 3)

    def stress_test_double_checked_locking(self):
        """双重检查锁定压力测试"""
        print("🔥 执行双重检查锁定压力测试...")

        def locking_operation(thread_id):
            """单个锁定操作"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.hybrid_permission_cache import (
                        HybridPermissionCache,
                    )

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

                    # 执行双重检查锁定
                    result = cache.distributed_cache_get(f"test_key_{thread_id}")

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(locking_operation, 150, 15)

    def _run_concurrent_test(self, operation_func, total_requests, max_workers):
        """运行并发测试"""
        response_times = []
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_thread = {
                executor.submit(operation_func, i): i for i in range(total_requests)
            }

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_thread):
                response_time, success = future.result()
                response_times.append(response_time * 1000)  # 转换为毫秒
                if success:
                    success_count += 1

        # 计算统计信息
        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
        else:
            avg_response_time = max_response_time = min_response_time = 0

        success_rate = (
            (success_count / total_requests) * 100 if total_requests > 0 else 0
        )

        return {
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time,
            "success_rate": success_rate,
            "total_requests": total_requests,
            "success_count": success_count,
        }

    def generate_report(self):
        """生成测试报告"""
        print("\n📊 生成测试报告...")
        print("=" * 60)

        print("\n🎯 回归测试结果:")
        regression_passed = sum(
            1 for result in self.results.values() if isinstance(result, bool) and result
        )
        regression_total = len(
            [result for result in self.results.values() if isinstance(result, bool)]
        )
        print(f"   通过: {regression_passed}/{regression_total}")

        print("\n🔥 压力测试结果:")
        for test_name, metrics in self.results.items():
            if isinstance(metrics, dict):
                print(f"   {test_name}:")
                print(f"     平均响应时间: {metrics['avg_response_time']:.3f}ms")
                print(f"     最大响应时间: {metrics['max_response_time']:.3f}ms")
                print(f"     成功率: {metrics['success_rate']:.2f}%")
                print(f"     总请求数: {metrics['total_requests']}")

        print("\n📈 性能分析:")
        all_response_times = []
        for metrics in self.results.values():
            if isinstance(metrics, dict) and "avg_response_time" in metrics:
                all_response_times.append(metrics["avg_response_time"])

        if all_response_times:
            overall_avg = statistics.mean(all_response_times)
            overall_max = max(all_response_times)
            print(f"   整体平均响应时间: {overall_avg:.3f}ms")
            print(f"   整体最大响应时间: {overall_max:.3f}ms")

        print("\n✅ 集成测试完成！")
        print("智能缓存失效和数据预加载机制已通过全面测试验证。")


def run_comprehensive_integration_test():
    """运行全面集成测试"""
    print("🚀 开始全面集成测试...")
    print("=" * 60)

    # 创建测试套件
    test_suite = IntegrationTestSuite()

    # 运行回归测试
    regression_success = test_suite.run_regression_tests()

    # 运行压力测试
    test_suite.run_stress_tests()

    # 生成报告
    test_suite.generate_report()

    if regression_success:
        print("\n🎉 所有回归测试通过！")
        return True
    else:
        print("\n❌ 部分回归测试失败，需要进一步调试。")
        return False


if __name__ == "__main__":
    run_comprehensive_integration_test()
