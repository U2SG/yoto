"""
权限系统性能测试 - Task 114优化效果验证
测试优化后的权限缓存系统性能，包括并发支持
"""

import pytest
import time
import threading
import concurrent.futures
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import (
    _permission_cache,
    _make_perm_cache_key,
    _compress_permissions,
    _decompress_permissions,
    get_cache_performance_stats,
    _warm_up_cache,
    _get_permissions_from_cache,
    _set_permissions_to_cache,
)
import statistics


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


class TestPermissionPerformance:
    """测试权限系统性能优化效果"""

    def test_cache_performance_improvement(self, app):
        """测试缓存性能提升"""
        # 清空缓存
        _permission_cache.clear()

        # 测试大量权限的缓存性能
        test_permissions = {f"permission_{i}" for i in range(10000)}
        cache_key = "performance_test_key"

        # 测试设置性能
        start_time = time.time()
        _permission_cache.set(cache_key, test_permissions)
        set_time = time.time() - start_time

        # 测试获取性能
        start_time = time.time()
        result = _permission_cache.get(cache_key)
        get_time = time.time() - start_time

        assert result == test_permissions
        assert set_time < 0.001  # 设置时间应该很快
        assert get_time < 0.001  # 获取时间应该很快

        print(f"缓存设置时间: {set_time:.6f}秒")
        print(f"缓存获取时间: {get_time:.6f}秒")

    def test_compression_performance(self, app):
        """测试压缩性能"""
        # 创建大量权限数据
        large_permissions = {
            f"very_long_permission_name_with_many_characters_{i}" for i in range(1000)
        }

        # 测试压缩性能
        start_time = time.time()
        compressed_data = _compress_permissions(large_permissions)
        compress_time = time.time() - start_time

        # 测试解压缩性能
        start_time = time.time()
        decompressed_permissions = _decompress_permissions(compressed_data)
        decompress_time = time.time() - start_time

        assert decompressed_permissions == large_permissions

        # 计算压缩比
        original_size = len(str(large_permissions).encode())
        compressed_size = len(compressed_data)
        compression_ratio = compressed_size / original_size

        print(f"压缩时间: {compress_time:.6f}秒")
        print(f"解压缩时间: {decompress_time:.6f}秒")
        print(f"压缩比: {compression_ratio:.2%}")
        print(f"原始大小: {original_size}字节")
        print(f"压缩后大小: {compressed_size}字节")

        assert compression_ratio < 0.8  # 应该有明显的压缩效果
        assert compress_time < 0.01  # 压缩应该很快
        assert decompress_time < 0.01  # 解压缩应该很快

    def test_concurrent_cache_access(self, app):
        """测试并发缓存访问"""
        # 清空缓存
        _permission_cache.clear()

        results = []
        errors = []

        def worker(thread_id):
            """工作线程函数"""
            try:
                for i in range(50):  # 每个线程50次操作
                    key = f"concurrent_key_{thread_id}_{i}"
                    permissions = {f"perm_{thread_id}_{i}"}

                    # 设置缓存
                    _permission_cache.set(key, permissions)

                    # 获取缓存
                    result = _permission_cache.get(key)

                    if result == permissions:
                        results.append(True)
                    else:
                        results.append(False)

            except Exception as e:
                errors.append(str(e))

        # 创建多个线程并发访问
        threads = []
        start_time = time.time()

        for i in range(10):  # 10个并发线程
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # 验证结果
        assert len(errors) == 0, f"并发访问出现错误: {errors}"
        assert len(results) == 500, f"期望500次操作，实际{len(results)}次"
        assert all(results), "所有缓存操作都应该成功"

        print(f"并发测试完成，总时间: {total_time:.3f}秒")
        print(f"总操作数: {len(results)}")
        print(f"平均每次操作时间: {total_time/len(results):.6f}秒")

    def test_cache_hit_rate_optimization(self, app):
        """测试缓存命中率优化"""
        # 清空缓存
        _permission_cache.clear()

        # 模拟重复访问模式
        test_keys = [f"frequent_key_{i}" for i in range(20)]
        test_permissions = [{f"perm_{i}_{j}" for j in range(10)} for i in range(20)]

        # 第一轮：设置缓存
        for i, (key, perms) in enumerate(zip(test_keys, test_permissions)):
            _permission_cache.set(key, perms)

        # 第二轮：重复访问（应该命中）
        hit_count = 0
        miss_count = 0

        for i in range(100):  # 100次访问
            key = test_keys[i % len(test_keys)]  # 循环访问
            result = _permission_cache.get(key)
            if result is not None:
                hit_count += 1
            else:
                miss_count += 1

        # 获取统计信息
        stats = _permission_cache.get_stats()

        print(f"命中次数: {hit_count}")
        print(f"未命中次数: {miss_count}")
        print(f"命中率: {stats['hit_rate']:.2%}")

        # 验证命中率应该很高（因为重复访问）
        assert stats["hit_rate"] > 0.8  # 命中率应该超过80%

    def test_memory_efficiency(self, app):
        """测试内存效率"""
        # 清空缓存
        _permission_cache.clear()

        # 测试大量数据的内存使用
        large_permissions = {f"permission_with_very_long_name_{i}" for i in range(500)}

        # 测试压缩效果
        original_size = len(str(large_permissions).encode())
        compressed_data = _compress_permissions(large_permissions)
        compressed_size = len(compressed_data)

        # 计算内存节省
        memory_saved = original_size - compressed_size
        memory_saved_percent = (memory_saved / original_size) * 100

        print(f"原始大小: {original_size}字节")
        print(f"压缩后大小: {compressed_size}字节")
        print(f"节省内存: {memory_saved}字节 ({memory_saved_percent:.1f}%)")

        assert memory_saved > 0  # 应该有内存节省
        assert memory_saved_percent > 10  # 至少节省10%内存

    def test_cache_eviction_performance(self, app):
        """测试缓存淘汰性能"""
        # 清空缓存
        _permission_cache.clear()

        # 填充缓存到接近最大容量
        start_time = time.time()
        for i in range(1000):  # 接近maxsize=1000
            key = f"eviction_test_{i}"
            permissions = {f"perm_{i}"}
            _permission_cache.set(key, permissions)

        fill_time = time.time() - start_time

        # 继续添加，触发淘汰
        start_time = time.time()
        for i in range(1000, 1100):  # 继续添加100个
            key = f"eviction_test_{i}"
            permissions = {f"perm_{i}"}
            _permission_cache.set(key, permissions)

        eviction_time = time.time() - start_time

        # 验证缓存大小不超过限制
        stats = _permission_cache.get_stats()
        assert stats["size"] <= 1000

        print(f"填充缓存时间: {fill_time:.3f}秒")
        print(f"淘汰操作时间: {eviction_time:.3f}秒")
        print(f"最终缓存大小: {stats['size']}")

        # 淘汰操作应该很快
        assert eviction_time < 0.1

    def test_performance_monitoring(self, app):
        """测试性能监控功能"""
        # 执行一些操作
        for i in range(100):
            key = f"monitor_test_{i}"
            permissions = {f"perm_{i}"}
            _permission_cache.set(key, permissions)
            _permission_cache.get(key)

        # 获取性能统计
        stats = get_cache_performance_stats()

        # 验证统计信息完整性
        assert "l1_cache" in stats
        assert "l2_cache" in stats
        assert "performance" in stats

        l1_stats = stats["l1_cache"]
        assert "size" in l1_stats
        assert "hit_count" in l1_stats
        assert "miss_count" in l1_stats
        assert "hit_rate" in l1_stats
        assert "uptime" in l1_stats

        print(f"L1缓存统计: {l1_stats}")
        print(f"L2缓存统计: {stats['l2_cache']}")
        print(f"性能统计: {stats['performance']}")

        # 验证统计数据的合理性
        assert l1_stats["size"] >= 0
        assert l1_stats["hit_count"] >= 0
        assert l1_stats["miss_count"] >= 0
        assert 0 <= l1_stats["hit_rate"] <= 1

    def test_stress_test(self, app):
        """压力测试"""
        # 清空缓存
        _permission_cache.clear()

        # 模拟高并发场景
        def stress_worker(worker_id):
            """压力测试工作线程"""
            results = []
            for i in range(100):  # 每个线程100次操作
                key = f"stress_{worker_id}_{i}"
                permissions = {f"perm_{worker_id}_{i}"}

                # 随机操作：设置或获取
                if i % 3 == 0:  # 33%概率设置
                    _permission_cache.set(key, permissions)
                    results.append(True)
                else:  # 67%概率获取
                    result = _permission_cache.get(key)
                    results.append(result is not None)

            return results

        # 使用线程池执行压力测试
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(stress_worker, i) for i in range(20)]
            all_results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        total_time = time.time() - start_time

        # 统计结果
        total_operations = sum(len(results) for results in all_results)
        successful_operations = sum(sum(results) for results in all_results)

        print(f"压力测试完成")
        print(f"总操作数: {total_operations}")
        print(f"成功操作数: {successful_operations}")
        print(f"成功率: {successful_operations/total_operations:.2%}")
        print(f"总时间: {total_time:.3f}秒")
        print(f"平均每秒操作数: {total_operations/total_time:.0f}")

        # 验证压力测试结果
        assert total_operations == 2000  # 20线程 * 100操作
        assert successful_operations > 0  # 至少有一些成功操作
        assert total_time < 10  # 压力测试应该在10秒内完成
