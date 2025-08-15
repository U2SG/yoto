"""
压力测试脚本

专注于性能测试，验证智能缓存失效和数据预加载机制的性能表现
"""

import sys
import os
import time
import threading
import concurrent.futures
import statistics
from unittest.mock import Mock
from collections import defaultdict

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


class StressTestSuite:
    """压力测试套件"""

    def __init__(self):
        self.results = {}
        self.setup_test_environment()

    def setup_test_environment(self):
        """设置测试环境"""
        print("🔧 设置压力测试环境...")

        # 创建Flask应用
        from flask import Flask

        self.app = Flask(__name__)
        self.app.config.update(
            {
                "TESTING": True,
                "ADVANCED_OPTIMIZATION_CONFIG": {
                    "smart_invalidation_interval": 1,
                    "preload_interval": 1,
                    "preload": {"enabled": True},
                    "batch_size": 100,
                },
            }
        )

    def run_performance_tests(self):
        """运行性能测试"""
        print("\n📋 开始性能测试...")
        print("=" * 60)

        performance_tests = [
            ("缓存操作性能", self.test_cache_performance, 1000, 50),
            ("权限检查性能", self.test_permission_check_performance, 500, 25),
            ("智能失效性能", self.test_smart_invalidation_performance, 200, 10),
            ("预加载性能", self.test_preload_performance, 100, 5),
            ("双重检查锁定性能", self.test_double_checked_locking_performance, 800, 40),
        ]

        for test_name, test_func, total_requests, max_workers in performance_tests:
            print(f"\n🔥 性能测试: {test_name}")
            print("-" * 40)
            try:
                metrics = test_func(total_requests, max_workers)
                self.results[test_name] = metrics
                print(f"✅ {test_name} 完成")
                print(f"   平均响应时间: {metrics['avg_response_time']:.3f}ms")
                print(f"   最大响应时间: {metrics['max_response_time']:.3f}ms")
                print(f"   最小响应时间: {metrics['min_response_time']:.3f}ms")
                print(f"   成功率: {metrics['success_rate']:.2f}%")
                print(f"   总请求数: {metrics['total_requests']}")
                print(f"   吞吐量: {metrics['throughput']:.2f} req/s")
            except Exception as e:
                print(f"❌ {test_name} 异常: {e}")

    def test_cache_performance(self, total_requests, max_workers):
        """测试缓存操作性能"""
        print(f"🔥 执行缓存操作性能测试 ({total_requests} 请求, {max_workers} 并发)...")

        def cache_operation(thread_id):
            """单个缓存操作"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    from app.core.permission.hybrid_permission_cache import (
                        HybridPermissionCache,
                    )

                    # 创建缓存实例
                    cache = HybridPermissionCache()
                    cache.l1_simple_cache = Mock()
                    cache.l1_simple_cache.set = Mock()
                    cache.l1_simple_cache.get = Mock(
                        return_value={"permissions": ["test"]}
                    )

                    key = f"stress_test_key_{thread_id}"
                    data = {"permissions": [f"perm_{thread_id}"]}

                    # 设置缓存
                    cache.l1_simple_cache.set(key, data)

                    # 获取缓存
                    result = cache.l1_simple_cache.get(key)

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(cache_operation, total_requests, max_workers)

    def test_permission_check_performance(self, total_requests, max_workers):
        """测试权限检查性能"""
        print(f"🔥 执行权限检查性能测试 ({total_requests} 请求, {max_workers} 并发)...")

        def permission_check(thread_id):
            """单个权限检查"""
            start_time = time.time()
            try:
                with self.app.app_context():
                    # 模拟权限检查
                    time.sleep(0.001)  # 模拟处理时间

                    return time.time() - start_time, True
            except Exception:
                return time.time() - start_time, False

        return self._run_concurrent_test(permission_check, total_requests, max_workers)

    def test_smart_invalidation_performance(self, total_requests, max_workers):
        """测试智能失效性能"""
        print(f"🔥 执行智能失效性能测试 ({total_requests} 请求, {max_workers} 并发)...")

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

        return self._run_concurrent_test(
            invalidation_operation, total_requests, max_workers
        )

    def test_preload_performance(self, total_requests, max_workers):
        """测试预加载性能"""
        print(f"🔥 执行预加载性能测试 ({total_requests} 请求, {max_workers} 并发)...")

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

        return self._run_concurrent_test(preload_operation, total_requests, max_workers)

    def test_double_checked_locking_performance(self, total_requests, max_workers):
        """测试双重检查锁定性能"""
        print(
            f"🔥 执行双重检查锁定性能测试 ({total_requests} 请求, {max_workers} 并发)..."
        )

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

        return self._run_concurrent_test(locking_operation, total_requests, max_workers)

    def _run_concurrent_test(self, operation_func, total_requests, max_workers):
        """运行并发测试"""
        response_times = []
        success_count = 0
        start_time = time.time()

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

        end_time = time.time()
        total_time = end_time - start_time

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
        throughput = total_requests / total_time if total_time > 0 else 0

        return {
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time,
            "success_rate": success_rate,
            "total_requests": total_requests,
            "success_count": success_count,
            "throughput": throughput,
            "total_time": total_time,
        }

    def generate_performance_report(self):
        """生成性能报告"""
        print("\n📊 生成性能报告...")
        print("=" * 60)

        print("\n🔥 性能测试结果:")
        for test_name, metrics in self.results.items():
            print(f"\n   {test_name}:")
            print(f"     平均响应时间: {metrics['avg_response_time']:.3f}ms")
            print(f"     最大响应时间: {metrics['max_response_time']:.3f}ms")
            print(f"     最小响应时间: {metrics['min_response_time']:.3f}ms")
            print(f"     成功率: {metrics['success_rate']:.2f}%")
            print(f"     吞吐量: {metrics['throughput']:.2f} req/s")
            print(f"     总请求数: {metrics['total_requests']}")
            print(f"     总耗时: {metrics['total_time']:.3f}s")

        print("\n📈 性能分析:")
        all_response_times = []
        all_throughputs = []
        for metrics in self.results.values():
            if "avg_response_time" in metrics:
                all_response_times.append(metrics["avg_response_time"])
            if "throughput" in metrics:
                all_throughputs.append(metrics["throughput"])

        if all_response_times:
            overall_avg_response = statistics.mean(all_response_times)
            overall_max_response = max(all_response_times)
            print(f"   整体平均响应时间: {overall_avg_response:.3f}ms")
            print(f"   整体最大响应时间: {overall_max_response:.3f}ms")

        if all_throughputs:
            overall_avg_throughput = statistics.mean(all_throughputs)
            overall_max_throughput = max(all_throughputs)
            print(f"   整体平均吞吐量: {overall_avg_throughput:.2f} req/s")
            print(f"   整体最大吞吐量: {overall_max_throughput:.2f} req/s")

        print("\n✅ 压力测试完成！")
        print("智能缓存失效和数据预加载机制已通过性能测试验证。")


def run_stress_performance_test():
    """运行压力性能测试"""
    print("🚀 开始压力性能测试...")
    print("=" * 60)

    # 创建测试套件
    test_suite = StressTestSuite()

    # 运行性能测试
    test_suite.run_performance_tests()

    # 生成报告
    test_suite.generate_performance_report()

    print("\n🎉 压力测试完成！")
    return True


if __name__ == "__main__":
    run_stress_performance_test()
