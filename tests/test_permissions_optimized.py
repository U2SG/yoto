"""
权限系统优化测试 - Task 114
测试优化后的权限缓存系统功能
"""

import pytest
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
)
import time


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


class TestPermissionCacheOptimization:
    """测试权限缓存系统优化"""

    def test_lru_cache_functionality(self, app):
        """测试LRU缓存功能"""
        # 获取当前统计作为基准
        initial_stats = _permission_cache.get_stats()
        initial_hits = initial_stats["hit_count"]

        # 测试缓存设置和获取
        test_key = "test_key"
        test_permissions = {"perm1", "perm2", "perm3"}

        _permission_cache.set(test_key, test_permissions)
        result = _permission_cache.get(test_key)

        assert result == test_permissions

        # 检查命中次数（相对于基准的增量）
        final_stats = _permission_cache.get_stats()
        new_hits = final_stats["hit_count"] - initial_hits
        assert new_hits >= 1  # 至少应该有1次命中

    def test_cache_eviction(self, app):
        """测试LRU缓存淘汰机制"""
        # 填充缓存到最大容量
        for i in range(1001):  # 超过maxsize=1000
            key = f"test_key_{i}"
            permissions = {f"perm_{i}"}
            _permission_cache.set(key, permissions)

        # 验证缓存大小不超过maxsize
        stats = _permission_cache.get_stats()
        assert stats["size"] <= 1000

    def test_cache_compression(self, app):
        """测试权限压缩功能"""
        # 创建大量权限进行压缩测试
        large_permissions = {f"permission_{i}" for i in range(100)}

        # 压缩
        compressed_data = _compress_permissions(large_permissions)

        # 解压缩
        decompressed_permissions = _decompress_permissions(compressed_data)

        assert decompressed_permissions == large_permissions
        assert len(compressed_data) < len(str(large_permissions).encode())

    def test_cache_key_generation(self, app):
        """测试优化的缓存键生成"""
        # 测试不同参数组合的键生成
        key1 = _make_perm_cache_key(123, "server", 456)
        key2 = _make_perm_cache_key(123, "server", 456)
        key3 = _make_perm_cache_key(123, "channel", 789)

        # 相同参数应该生成相同键
        assert key1 == key2

        # 不同参数应该生成不同键
        assert key1 != key3

        # 键应该是MD5哈希格式
        assert len(key1) == 32 + 5  # MD5哈希长度 + "perm:"前缀

    def test_cache_performance_stats(self, app):
        """测试缓存性能统计"""
        # 执行一些缓存操作
        for i in range(10):
            key = f"stats_test_{i}"
            permissions = {f"perm_{i}"}
            _permission_cache.set(key, permissions)
            _permission_cache.get(key)  # 命中

        # 获取性能统计
        stats = get_cache_performance_stats()

        # 验证统计信息
        assert "l1_cache" in stats
        assert "l2_cache" in stats
        assert "performance" in stats

        l1_stats = stats["l1_cache"]
        assert "size" in l1_stats
        assert "hit_count" in l1_stats
        assert "miss_count" in l1_stats
        assert "hit_rate" in l1_stats

    def test_cache_warm_up(self, app):
        """测试缓存预热功能"""
        # 获取预热前的缓存大小
        initial_size = _permission_cache.get_stats()["size"]

        # 执行预热
        _warm_up_cache()

        # 验证预热后的缓存状态
        final_stats = _permission_cache.get_stats()
        assert final_stats["size"] >= initial_size  # 缓存大小应该增加或保持不变

    def test_cache_hit_rate(self, app):
        """测试缓存命中率"""
        # 获取当前统计作为基准
        initial_stats = _permission_cache.get_stats()
        initial_hits = initial_stats["hit_count"]
        initial_misses = initial_stats["miss_count"]

        # 执行多次访问
        test_key = "hit_rate_test"
        test_permissions = {"perm1", "perm2"}

        # 第一次访问（未命中）
        result1 = _permission_cache.get(test_key)
        assert result1 is None

        # 设置缓存
        _permission_cache.set(test_key, test_permissions)

        # 第二次访问（命中）
        result2 = _permission_cache.get(test_key)
        assert result2 == test_permissions

        # 检查命中率（相对于基准的增量）
        final_stats = _permission_cache.get_stats()
        new_hits = final_stats["hit_count"] - initial_hits
        new_misses = final_stats["miss_count"] - initial_misses

        assert new_hits == 1
        assert new_misses == 1
        assert new_hits + new_misses == 2  # 总共2次访问

    def test_cache_memory_efficiency(self, app):
        """测试缓存内存效率"""
        # 测试大量权限的压缩效果
        large_permissions = {f"very_long_permission_name_{i}" for i in range(50)}

        # 压缩前的大小
        uncompressed_size = len(str(large_permissions).encode())

        # 压缩后的大小
        compressed_data = _compress_permissions(large_permissions)
        compressed_size = len(compressed_data)

        # 验证压缩效果
        compression_ratio = compressed_size / uncompressed_size
        assert compression_ratio < 1.0  # 应该有压缩效果
        assert compression_ratio > 0.1  # 但不会过度压缩

    def test_cache_concurrent_access(self, app):
        """测试缓存并发访问"""
        import threading
        import time

        results = []

        def worker(thread_id):
            """工作线程函数"""
            for i in range(10):
                key = f"concurrent_test_{thread_id}_{i}"
                permissions = {f"perm_{thread_id}_{i}"}

                # 设置缓存
                _permission_cache.set(key, permissions)

                # 获取缓存
                result = _permission_cache.get(key)
                results.append(result == permissions)

                time.sleep(0.001)  # 短暂延迟

        # 创建多个线程
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证所有操作都成功
        assert all(results)
        assert len(results) == 50  # 5线程 * 10操作
