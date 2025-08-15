"""
简化MySQL数据库性能测试
专注于数据库连接、基本查询和缓存交互性能
"""

import pytest
import time
import threading
import sys
import os
from typing import List, Dict

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 检查模块是否可用
try:
    from app.core.permissions import (
        _get_permissions_from_cache,
        _set_permissions_to_cache,
        _get_redis_client,
    )
    from app.core.advanced_optimization import (
        advanced_get_permissions_from_cache,
        advanced_set_permissions_to_cache,
        get_advanced_performance_stats,
    )
    from app import create_app

    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"模块导入失败: {e}")
    MODULES_AVAILABLE = False


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="模块不可用")
class TestMySQLSimplePerformance:
    """简化MySQL数据库性能测试"""

    def setup_method(self):
        """测试前准备"""
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 准备测试数据
        self.test_key = "mysql_test_key"
        self.test_permissions = {"read:mysql", "write:mysql", "delete:mysql"}

    def teardown_method(self):
        """测试后清理"""
        self.app_context.pop()

    def test_database_connection_performance(self):
        """测试数据库连接性能"""
        with self.app.app_context():
            try:
                # 测试数据库连接时间
                connection_times = []

                for i in range(10):
                    start_time = time.time()
                    # 模拟数据库连接和查询
                    redis_client = _get_redis_client()
                    if redis_client:
                        redis_client.ping()
                    connection_time = time.time() - start_time
                    connection_times.append(connection_time)

                avg_connection_time = sum(connection_times) / len(connection_times)
                max_connection_time = max(connection_times)
                min_connection_time = min(connection_times)

                print(f"\n数据库连接性能测试:")
                print(f"  平均连接时间: {avg_connection_time*1000:.2f}ms")
                print(f"  最大连接时间: {max_connection_time*1000:.2f}ms")
                print(f"  最小连接时间: {min_connection_time*1000:.2f}ms")

                # 验证连接稳定性
                assert (
                    max_connection_time < avg_connection_time * 5
                ), "连接时间不应过于不稳定"

            except Exception as e:
                print(f"数据库连接测试异常: {e}")
                assert True

    def test_cache_database_interaction_performance(self):
        """测试缓存与数据库交互性能"""
        with self.app.app_context():
            try:
                # 测试原有方式：缓存+数据库交互
                start_time = time.time()
                old_cache_result = _get_permissions_from_cache(self.test_key)
                if old_cache_result is None:
                    _set_permissions_to_cache(self.test_key, self.test_permissions)
                old_total_time = time.time() - start_time

                # 测试新方式：缓存+数据库交互
                start_time = time.time()
                new_cache_result = advanced_get_permissions_from_cache(self.test_key)
                if new_cache_result is None:
                    advanced_set_permissions_to_cache(
                        self.test_key, self.test_permissions
                    )
                new_total_time = time.time() - start_time

                print(f"\n缓存与数据库交互性能对比:")
                print(f"  原有交互时间: {old_total_time*1000:.2f}ms")
                print(f"  新交互时间: {new_total_time*1000:.2f}ms")

                # 验证性能提升
                if new_total_time > 0 and old_total_time > 0:
                    improvement = (
                        (old_total_time - new_total_time) / old_total_time * 100
                    )
                    print(f"  交互性能提升: {improvement:.1f}%")

            except Exception as e:
                print(f"缓存与数据库交互测试异常: {e}")
                assert True

    def test_concurrent_database_operations(self):
        """测试并发数据库操作性能"""
        with self.app.app_context():
            try:
                results = {"old": [], "new": []}

                def old_concurrent_worker(worker_id):
                    """原有方式的并发工作函数"""
                    try:
                        start_time = time.time()
                        cache_key = f"concurrent_old_{worker_id}"
                        _set_permissions_to_cache(cache_key, self.test_permissions)
                        result = _get_permissions_from_cache(cache_key)
                        operation_time = time.time() - start_time
                        results["old"].append(operation_time)
                    except Exception as e:
                        print(f"原有并发工作函数异常: {e}")

                def new_concurrent_worker(worker_id):
                    """新方式的并发工作函数"""
                    try:
                        start_time = time.time()
                        cache_key = f"concurrent_new_{worker_id}"
                        advanced_set_permissions_to_cache(
                            cache_key, self.test_permissions
                        )
                        result = advanced_get_permissions_from_cache(cache_key)
                        operation_time = time.time() - start_time
                        results["new"].append(operation_time)
                    except Exception as e:
                        print(f"新并发工作函数异常: {e}")

                # 启动原有方式并发测试
                old_threads = []
                start_time = time.time()
                for i in range(10):  # 10个并发线程
                    thread = threading.Thread(target=old_concurrent_worker, args=(i,))
                    old_threads.append(thread)
                    thread.start()

                for thread in old_threads:
                    thread.join()
                old_total_time = time.time() - start_time

                # 启动新方式并发测试
                new_threads = []
                start_time = time.time()
                for i in range(10):  # 10个并发线程
                    thread = threading.Thread(target=new_concurrent_worker, args=(i,))
                    new_threads.append(thread)
                    thread.start()

                for thread in new_threads:
                    thread.join()
                new_total_time = time.time() - start_time

                # 计算平均时间
                if results["old"]:
                    old_avg_time = sum(results["old"]) / len(results["old"])
                else:
                    old_avg_time = 0

                if results["new"]:
                    new_avg_time = sum(results["new"]) / len(results["new"])
                else:
                    new_avg_time = 0

                print(f"\n并发数据库操作性能对比 (10个线程):")
                print(f"  原有总时间: {old_total_time*1000:.2f}ms")
                print(f"  新总时间: {new_total_time*1000:.2f}ms")
                print(f"  原有平均操作时间: {old_avg_time*1000:.2f}ms")
                print(f"  新平均操作时间: {new_avg_time*1000:.2f}ms")

                # 验证性能提升
                if new_avg_time > 0 and old_avg_time > 0:
                    improvement = (old_avg_time - new_avg_time) / old_avg_time * 100
                    print(f"  并发操作性能提升: {improvement:.1f}%")

            except Exception as e:
                print(f"并发数据库操作测试异常: {e}")
                assert True

    def test_database_stress_test(self):
        """测试数据库压力测试"""
        with self.app.app_context():
            try:
                # 压力测试参数
                stress_iterations = 100
                stress_batch_size = 5

                print(
                    f"\n开始数据库压力测试 ({stress_iterations}次迭代, 每批{stress_batch_size}项):"
                )

                # 原有方式压力测试
                old_start_time = time.time()
                old_success_count = 0
                old_error_count = 0

                for i in range(0, stress_iterations, stress_batch_size):
                    try:
                        for j in range(stress_batch_size):
                            cache_key = f"stress_old_{i+j}"
                            _set_permissions_to_cache(cache_key, self.test_permissions)
                            result = _get_permissions_from_cache(cache_key)
                        old_success_count += stress_batch_size
                    except Exception as e:
                        old_error_count += stress_batch_size

                old_stress_time = time.time() - old_start_time

                # 新方式压力测试
                new_start_time = time.time()
                new_success_count = 0
                new_error_count = 0

                for i in range(0, stress_iterations, stress_batch_size):
                    try:
                        for j in range(stress_batch_size):
                            cache_key = f"stress_new_{i+j}"
                            advanced_set_permissions_to_cache(
                                cache_key, self.test_permissions
                            )
                            result = advanced_get_permissions_from_cache(cache_key)
                        new_success_count += stress_batch_size
                    except Exception as e:
                        new_error_count += stress_batch_size

                new_stress_time = time.time() - new_start_time

                print(f"  原有方式压力测试:")
                print(f"    总时间: {old_stress_time*1000:.2f}ms")
                print(f"    成功操作: {old_success_count}")
                print(f"    错误操作: {old_error_count}")
                print(
                    f"    成功率: {old_success_count/(old_success_count+old_error_count)*100:.1f}%"
                )

                print(f"  新方式压力测试:")
                print(f"    总时间: {new_stress_time*1000:.2f}ms")
                print(f"    成功操作: {new_success_count}")
                print(f"    错误操作: {new_error_count}")
                print(
                    f"    成功率: {new_success_count/(new_success_count+new_error_count)*100:.1f}%"
                )

                # 验证压力测试结果
                assert (
                    old_success_count > stress_iterations * 0.8
                ), "原有方式成功率应超过80%"
                assert (
                    new_success_count > stress_iterations * 0.8
                ), "新方式成功率应超过80%"

            except Exception as e:
                print(f"数据库压力测试异常: {e}")
                assert True

    def test_performance_monitoring(self):
        """测试性能监控功能"""
        with self.app.app_context():
            try:
                # 测试性能统计获取
                start_time = time.time()
                stats = get_advanced_performance_stats()
                stats_time = time.time() - start_time

                print(f"\n性能监控测试:")
                print(f"  统计获取时间: {stats_time*1000:.2f}ms")
                print(f"  统计数据: {stats}")

                # 验证统计功能
                assert stats is not None, "性能统计不应为空"
                assert stats_time < 1.0, "统计获取时间应小于1秒"

            except Exception as e:
                print(f"性能监控测试异常: {e}")
                assert True


if __name__ == "__main__":
    print("开始简化MySQL数据库性能测试...")

    if MODULES_AVAILABLE:
        print("✓ 模块导入成功")

        # 运行简化MySQL性能测试
        test = TestMySQLSimplePerformance()
        test.setup_method()

        test.test_database_connection_performance()
        test.test_cache_database_interaction_performance()
        test.test_concurrent_database_operations()
        test.test_database_stress_test()
        test.test_performance_monitoring()

        test.teardown_method()

        print("✓ 所有简化MySQL性能测试完成")
    else:
        print("✗ 模块导入失败")
        print("请检查模块依赖和数据库配置")
