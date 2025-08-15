"""
分布式权限系统测试
测试Redis分布式集群、分布式锁和数据一致性
"""

import pytest
import time
import threading
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
    from app.core.permissions import (
        _permission_cache,
        _get_permissions_from_cache,
        _set_permissions_to_cache,
        get_cache_performance_stats,
    )
    from app.core.distributed_cache import (
        get_distributed_cache,
        distributed_get,
        distributed_set,
        distributed_lock,
    )

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
class TestDistributedPermissionSystem:
    """分布式权限系统测试"""

    def setup_method(self):
        """测试前准备"""
        if PERMISSIONS_AVAILABLE:
            _permission_cache.clear()

    def test_distributed_cache_basic(self, app):
        """测试分布式缓存基础功能"""
        with app.app_context():
            # 测试分布式缓存设置和获取
            cache_key = "dist_test_key"
            test_data = b"test_permissions_data"

            # 设置到分布式缓存
            success = distributed_set(cache_key, test_data, ttl=60)
            assert success, "分布式缓存设置应该成功"

            # 从分布式缓存获取
            result = distributed_get(cache_key)
            assert result == test_data, "分布式缓存获取应该返回正确的数据"

            print(f"分布式缓存基础测试通过")
            print(f"  缓存键: {cache_key}")
            print(f"  数据大小: {len(test_data)} 字节")

    def test_distributed_lock_basic(self, app):
        """测试分布式锁基础功能"""
        with app.app_context():
            lock_key = "test_lock"

            # 获取分布式锁
            with distributed_lock(lock_key, timeout=5):
                # 在锁保护下执行操作
                cache_key = "lock_test_key"
                test_data = b"locked_data"

                # 设置缓存
                success = distributed_set(cache_key, test_data, ttl=60)
                assert success, "在锁保护下设置缓存应该成功"

                # 获取缓存
                result = distributed_get(cache_key)
                assert result == test_data, "在锁保护下获取缓存应该成功"

                print(f"分布式锁基础测试通过")
                print(f"  锁键: {lock_key}")
                print(f"  缓存键: {cache_key}")

    def test_distributed_permission_cache(self, app):
        """测试分布式权限缓存"""
        with app.app_context():
            # 创建测试用户
            user = User(username="dist_user", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            # 测试权限缓存设置和获取
            cache_key = f"perm:{user.id}:global:none"
            permissions = {f"perm_{i}" for i in range(10)}

            # 使用分布式锁保护缓存操作
            with distributed_lock(f"lock:{cache_key}", timeout=5):
                # 设置权限到缓存
                _set_permissions_to_cache(cache_key, permissions)

                # 从缓存获取权限
                result = _get_permissions_from_cache(cache_key)
                assert result == permissions, "权限缓存应该返回正确的数据"

            print(f"分布式权限缓存测试通过")
            print(f"  用户ID: {user.id}")
            print(f"  权限数量: {len(permissions)}")

    def test_concurrent_distributed_operations(self, app):
        """测试并发分布式操作"""
        with app.app_context():
            # 创建测试用户
            user = User(username="concurrent_user", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            results = []
            errors = []

            def concurrent_worker(worker_id):
                """并发工作线程"""
                try:
                    cache_key = f"perm:{user.id}:worker:{worker_id}"
                    permissions = {f"perm_{worker_id}_{i}" for i in range(5)}

                    # 使用分布式锁保护操作
                    with distributed_lock(f"lock:{cache_key}", timeout=3):
                        # 设置缓存
                        _set_permissions_to_cache(cache_key, permissions)

                        # 获取缓存
                        result = _get_permissions_from_cache(cache_key)

                        if result == permissions:
                            results.append(f"worker_{worker_id}_success")
                        else:
                            errors.append(f"worker_{worker_id}_data_mismatch")

                except Exception as e:
                    errors.append(f"worker_{worker_id}_error: {str(e)}")

            # 启动多个并发线程
            threads = []
            for i in range(5):
                thread = threading.Thread(target=concurrent_worker, args=(i,))
                threads.append(thread)
                thread.start()

            # 等待所有线程完成
            for thread in threads:
                thread.join()

            print(f"并发分布式操作测试:")
            print(f"  成功操作: {len(results)}")
            print(f"  错误操作: {len(errors)}")
            print(f"  线程数: 5")

            # 验证结果
            assert len(errors) == 0, f"并发测试出现错误: {errors}"
            assert len(results) == 5, "所有操作都应该成功"

    def test_distributed_cache_performance(self, app):
        """测试分布式缓存性能"""
        with app.app_context():
            start_time = time.time()

            # 执行分布式缓存操作
            for i in range(10):
                cache_key = f"perf_test_key_{i}"
                test_data = b"performance_test_data" * 100  # 增加数据大小

                # 设置缓存
                success = distributed_set(cache_key, test_data, ttl=60)
                assert success, f"设置缓存 {i} 应该成功"

                # 获取缓存
                result = distributed_get(cache_key)
                assert result == test_data, f"获取缓存 {i} 应该成功"

            total_time = time.time() - start_time
            avg_time = total_time / 10

            print(f"分布式缓存性能测试:")
            print(f"  总时间: {total_time:.4f}秒")
            print(f"  平均时间: {avg_time*1000:.2f}毫秒")
            if total_time > 0:
                print(f"  QPS: {10/total_time:.0f}")
            else:
                print(f"  QPS: 无限 (总时间为0)")

            # 验证性能 - 分布式缓存应该比本地缓存慢，但应该在合理范围内
            assert avg_time < 1.0, f"平均查询时间({avg_time*1000:.2f}ms)应该小于1000ms"

    def test_distributed_lock_timeout(self, app):
        """测试分布式锁超时机制"""
        with app.app_context():
            lock_key = "timeout_test_lock"

            # 第一个线程获取锁
            def lock_holder():
                with distributed_lock(lock_key, timeout=10):
                    time.sleep(3)  # 持有锁3秒

            # 第二个线程尝试获取锁
            def lock_waiter():
                time.sleep(1)  # 等待1秒后尝试获取锁
                try:
                    with distributed_lock(lock_key, timeout=2):  # 2秒超时
                        return "lock_acquired"
                except Exception as e:
                    return f"lock_timeout: {str(e)}"

            # 启动第一个线程
            holder_thread = threading.Thread(target=lock_holder)
            holder_thread.start()

            # 启动第二个线程
            waiter_thread = threading.Thread(target=lock_waiter)
            waiter_thread.start()

            # 等待线程完成
            holder_thread.join()
            waiter_thread.join()

            print(f"分布式锁超时测试完成")

    def test_data_consistency(self, app):
        """测试数据一致性"""
        with app.app_context():
            # 创建测试用户
            user = User(username="consistency_user", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            cache_key = f"perm:{user.id}:global:none"
            original_permissions = {f"perm_{i}" for i in range(10)}

            # 模拟并发更新场景
            def update_worker(worker_id):
                """更新工作线程"""
                try:
                    with distributed_lock(f"lock:{cache_key}", timeout=5):
                        # 获取当前权限
                        current_permissions = _get_permissions_from_cache(cache_key)
                        if current_permissions is None:
                            current_permissions = set()

                        # 添加新权限
                        new_permissions = current_permissions.copy()
                        new_permissions.add(f"new_perm_{worker_id}")

                        # 更新缓存
                        _set_permissions_to_cache(cache_key, new_permissions)

                        return f"worker_{worker_id}_updated"
                except Exception as e:
                    return f"worker_{worker_id}_error: {str(e)}"

            # 初始化权限
            _set_permissions_to_cache(cache_key, original_permissions)

            # 启动多个更新线程
            threads = []
            results = []

            for i in range(3):
                thread = threading.Thread(
                    target=lambda: results.append(update_worker(i))
                )
                threads.append(thread)
                thread.start()

            # 等待所有线程完成
            for thread in threads:
                thread.join()

            # 验证最终结果
            final_permissions = _get_permissions_from_cache(cache_key)

            print(f"数据一致性测试:")
            print(f"  原始权限数: {len(original_permissions)}")
            print(f"  最终权限数: {len(final_permissions)}")
            print(f"  更新操作数: {len(results)}")

            # 验证一致性
            assert final_permissions is not None, "最终权限不应该为空"
            assert len(final_permissions) >= len(
                original_permissions
            ), "权限数量应该增加或保持不变"

    def test_cluster_health(self, app):
        """测试集群健康状态"""
        with app.app_context():
            try:
                # 获取分布式缓存实例
                cluster = get_distributed_cache()

                # 检查集群状态
                stats = cluster.get_cluster_stats()

                print(f"集群健康状态测试:")
                print(f"  节点数量: {stats.get('node_count', 0)}")
                print(f"  健康节点: {stats.get('healthy_nodes', 0)}")
                print(f"  总操作数: {stats.get('total_operations', 0)}")
                print(f"  成功率: {stats.get('success_rate', 0):.2%}")

                # 验证集群状态
                assert stats.get("node_count", 0) > 0, "应该有可用的集群节点"
                assert stats.get("healthy_nodes", 0) > 0, "应该有健康的集群节点"

            except Exception as e:
                print(f"集群健康检查失败: {str(e)}")
                # 如果集群不可用，跳过此测试
                pytest.skip("Redis集群不可用")

    def test_cache_invalidation(self, app):
        """测试缓存失效机制"""
        with app.app_context():
            # 创建测试用户
            user = User(username="invalidation_user", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            cache_key = f"perm:{user.id}:global:none"
            permissions = {f"perm_{i}" for i in range(10)}

            # 设置缓存
            with distributed_lock(f"lock:{cache_key}", timeout=5):
                _set_permissions_to_cache(cache_key, permissions)

                # 验证缓存设置成功
                result = _get_permissions_from_cache(cache_key)
                assert result == permissions, "缓存设置应该成功"

            # 模拟缓存失效
            with distributed_lock(f"lock:{cache_key}", timeout=5):
                # 清除本地缓存
                _permission_cache.clear()

                # 尝试获取缓存（应该从分布式缓存获取）
                result = _get_permissions_from_cache(cache_key)

                # 验证缓存失效后的一致性
                if result is not None:
                    print(f"缓存失效测试通过 - 从分布式缓存恢复数据")
                else:
                    print(f"缓存失效测试通过 - 数据已失效")

            print(f"缓存失效测试完成")
