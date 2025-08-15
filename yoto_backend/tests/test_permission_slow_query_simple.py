"""
权限系统简化测试
快速验证权限系统的基本功能，避免长时间运行
"""

import pytest
import time
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "yoto_backend"))

# 使用相对导入
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission

# 检查权限模块是否存在
try:
    from app.core.permissions import _permission_cache, get_cache_performance_stats

    PERMISSIONS_AVAILABLE = True
except ImportError:
    PERMISSIONS_AVAILABLE = False


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.mark.skipif(not PERMISSIONS_AVAILABLE, reason="权限模块不可用")
class TestPermissionBasic:
    """权限系统基础功能测试"""

    def setup_method(self):
        """测试前准备"""
        if PERMISSIONS_AVAILABLE:
            _permission_cache.clear()

    def test_basic_permission_cache(self, app):
        """测试基础权限缓存功能"""
        with app.app_context():
            # 创建测试用户
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            # 创建少量权限
            permissions = []
            for i in range(10):
                perm = Permission(
                    name=f"test_perm_{i}",
                    description=f"Test permission {i}",
                    permission_type="read",
                    level=1,
                    version="1.0",
                    is_deprecated=False,
                    group="test",
                    category="system",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                permissions.append(perm)

            db.session.add_all(permissions)
            db.session.commit()

            # 测试缓存设置和获取 - 直接使用本地缓存
            cache_key = f"perm:{user.id}:global:none"
            test_permissions = {f"test_perm_{i}" for i in range(5)}

            # 直接设置到本地缓存
            _permission_cache.set(cache_key, test_permissions)

            # 从本地缓存获取
            result = _permission_cache.get(cache_key)

            # 验证结果
            assert result is not None
            assert result == test_permissions

            print(f"基础权限缓存测试通过")
            print(f"  缓存键: {cache_key}")
            print(f"  权限数量: {len(result)}")

    def test_cache_performance_basic(self, app):
        """测试基础缓存性能 - 只测试本地缓存"""
        with app.app_context():
            # 测试本地缓存性能
            start_time = time.time()

            for i in range(10):
                cache_key = f"test_key_{i}"
                permissions = {f"perm_{j}" for j in range(10)}

                # 直接使用本地缓存，避免Redis连接
                _permission_cache.set(cache_key, permissions)
                result = _permission_cache.get(cache_key)
                assert result is not None

            total_time = time.time() - start_time
            avg_time = total_time / 10

            print(f"基础缓存性能测试:")
            print(f"  总时间: {total_time:.4f}秒")
            print(f"  平均时间: {avg_time*1000:.2f}毫秒")
            if total_time > 0:
                print(f"  QPS: {10/total_time:.0f}")
            else:
                print(f"  QPS: 无限 (总时间为0)")

            # 验证性能 - 本地缓存应该很快
            assert avg_time < 0.01, f"平均查询时间({avg_time*1000:.2f}ms)应该小于10ms"

    def test_cache_stats(self, app):
        """测试缓存统计功能"""
        with app.app_context():
            # 执行一些缓存操作
            for i in range(5):
                cache_key = f"stats_test_key_{i}"
                permissions = {f"perm_{j}" for j in range(5)}
                _permission_cache.set(cache_key, permissions)
                _permission_cache.get(cache_key)

            # 获取缓存统计
            stats = get_cache_performance_stats()

            print(f"缓存统计测试:")
            print(f"  L1缓存大小: {stats['l1_cache']['size']}")
            print(f"  L1缓存命中率: {stats['l1_cache']['hit_rate']:.2%}")

            # 验证统计信息
            assert "l1_cache" in stats
            assert "size" in stats["l1_cache"]
            assert "hit_rate" in stats["l1_cache"]

    def test_memory_usage_basic(self, app):
        """测试基础内存使用情况"""
        with app.app_context():
            # 获取初始内存使用
            initial_memory = sys.getsizeof(_permission_cache.cache)

            # 添加一些缓存数据
            for i in range(10):
                cache_key = f"memory_test_key_{i}"
                permissions = {f"perm_{j}" for j in range(10)}
                _permission_cache.set(cache_key, permissions)

            # 获取添加后的内存使用
            after_memory = sys.getsizeof(_permission_cache.cache)

            print(f"基础内存使用测试:")
            print(f"  初始内存: {initial_memory} 字节")
            print(f"  添加数据后: {after_memory} 字节")
            print(f"  内存增长: {after_memory - initial_memory} 字节")

            # 验证内存使用
            assert after_memory >= initial_memory, "内存使用应该增加或保持不变"

    def test_error_handling(self, app):
        """测试错误处理"""
        with app.app_context():
            # 测试获取不存在的缓存
            non_existent_key = "non_existent_key"
            result = _permission_cache.get(non_existent_key)

            # 应该返回None而不是抛出异常
            assert result is None

            print(f"错误处理测试通过")
            print(f"  测试键: {non_existent_key}")
            print(f"  返回结果: {result}")

    def test_concurrent_basic(self, app):
        """测试基础并发功能"""
        with app.app_context():
            import threading

            def worker(worker_id):
                """工作线程函数"""
                for i in range(3):
                    cache_key = f"concurrent_test_key_{worker_id}_{i}"
                    permissions = {f"perm_{j}" for j in range(5)}
                    _permission_cache.set(cache_key, permissions)

                    result = _permission_cache.get(cache_key)
                    assert result is not None

            # 创建3个线程
            threads = []
            for i in range(3):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()

            # 等待所有线程完成
            for thread in threads:
                thread.join()

            print(f"基础并发测试通过")
            print(f"  线程数: 3")
            print(f"  每线程操作数: 3")
            print(f"  总操作数: 9")

    def test_lru_eviction(self, app):
        """测试LRU淘汰机制"""
        with app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 添加超过最大容量的数据
            max_size = _permission_cache.maxsize
            for i in range(max_size + 10):
                cache_key = f"lru_test_key_{i}"
                permissions = {f"perm_{j}" for j in range(5)}
                _permission_cache.set(cache_key, permissions)

            # 验证缓存大小不超过最大容量
            assert len(_permission_cache.cache) <= max_size

            print(f"LRU淘汰测试通过")
            print(f"  最大容量: {max_size}")
            print(f"  当前大小: {len(_permission_cache.cache)}")

    def test_cache_hit_rate(self, app):
        """测试缓存命中率"""
        with app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 设置一些测试数据
            test_keys = [f"hit_rate_test_{i}" for i in range(5)]
            for key in test_keys:
                permissions = {f"perm_{j}" for j in range(5)}
                _permission_cache.set(key, permissions)

            # 重复访问某些键（模拟热点数据）
            for i in range(10):
                key = test_keys[i % len(test_keys)]
                _permission_cache.get(key)

            # 访问不存在的键（模拟冷数据）
            for i in range(5):
                _permission_cache.get(f"miss_key_{i}")

            # 获取统计信息
            stats = _permission_cache.get_stats()

            print(f"缓存命中率测试:")
            print(f"  命中次数: {stats['hit_count']}")
            print(f"  未命中次数: {stats['miss_count']}")
            print(f"  命中率: {stats['hit_rate']:.2%}")

            # 验证命中率
            assert stats["hit_count"] > 0, "应该有命中"
            assert stats["miss_count"] > 0, "应该有未命中"
            assert 0 <= stats["hit_rate"] <= 1, "命中率应该在0-1之间"
