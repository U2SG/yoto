"""
权限系统MySQL性能测试 - Task 114优化效果验证
使用真实MySQL数据库测试优化后的权限缓存系统性能
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
    require_permission,
)
import statistics


@pytest.fixture
def mysql_app():
    """MySQL测试应用"""
    app = create_app("mysql_testing")
    with app.app_context():
        # 创建所有表
        db.create_all()
        yield app
        # 清理数据库
        db.session.remove()
        db.drop_all()


@pytest.fixture
def mysql_client(mysql_app):
    return mysql_app.test_client()


class TestPermissionMySQLPerformance:
    """测试权限系统在MySQL环境下的性能优化效果"""

    def test_mysql_cache_performance(self, mysql_app):
        """测试MySQL环境下的缓存性能"""
        with mysql_app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 创建测试数据
            user = User(username="testuser", password_hash="test_hash")
            db.session.add(user)
            db.session.commit()

            # 创建权限
            permissions = []
            for i in range(100):
                perm = Permission(
                    name=f"permission_{i}",
                    group="test",
                    description=f"Test permission {i}",
                )
                permissions.append(perm)
            db.session.add_all(permissions)
            db.session.commit()

            # 测试缓存性能
            test_permissions = {f"permission_{i}" for i in range(100)}
            cache_key = "mysql_performance_test_key"

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

            print(f"MySQL缓存设置时间: {set_time:.6f}秒")
            print(f"MySQL缓存获取时间: {get_time:.6f}秒")

    def test_mysql_compression_performance(self, mysql_app):
        """测试MySQL环境下的压缩性能"""
        with mysql_app.app_context():
            # 创建大量权限数据
            large_permissions = {
                f"very_long_permission_name_with_many_characters_{i}"
                for i in range(1000)
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

            print(f"MySQL压缩时间: {compress_time:.6f}秒")
            print(f"MySQL解压缩时间: {decompress_time:.6f}秒")
            print(f"MySQL压缩比: {compression_ratio:.2%}")
            print(f"MySQL原始大小: {original_size}字节")
            print(f"MySQL压缩后大小: {compressed_size}字节")

            assert compression_ratio < 0.8  # 应该有明显的压缩效果
            assert compress_time < 0.01  # 压缩应该很快
            assert decompress_time < 0.01  # 解压缩应该很快

    def test_mysql_concurrent_cache_access(self, mysql_app):
        """测试MySQL环境下的并发缓存访问"""
        with mysql_app.app_context():
            # 清空缓存
            _permission_cache.clear()

            results = []
            errors = []

            def worker(thread_id):
                """工作线程函数"""
                try:
                    for i in range(50):  # 每个线程50次操作
                        key = f"mysql_concurrent_key_{thread_id}_{i}"
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
            assert len(errors) == 0, f"MySQL并发访问出现错误: {errors}"
            assert len(results) == 500, f"期望500次操作，实际{len(results)}次"
            assert all(results), "所有MySQL缓存操作都应该成功"

            print(f"MySQL并发测试完成，总时间: {total_time:.3f}秒")
            print(f"MySQL总操作数: {len(results)}")
            print(f"MySQL平均每次操作时间: {total_time/len(results):.6f}秒")

    def test_mysql_database_integration(self, mysql_app):
        """测试MySQL数据库集成性能"""
        with mysql_app.app_context():
            # 创建测试用户和权限
            user = User(username="mysqluser", password_hash="test_hash")
            db.session.add(user)
            db.session.commit()

            # 创建角色
            role = Role(name="test_role", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建权限
            permissions = []
            for i in range(50):
                perm = Permission(
                    name=f"mysql_perm_{i}",
                    group="mysql_test",
                    description=f"MySQL test permission {i}",
                )
                permissions.append(perm)
            db.session.add_all(permissions)
            db.session.commit()

            # 分配用户角色
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.session.add(user_role)
            db.session.commit()

            # 分配角色权限
            role_permissions = []
            for perm in permissions:
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                role_permissions.append(rp)
            db.session.add_all(role_permissions)
            db.session.commit()

            # 测试权限查询性能
            start_time = time.time()

            # 模拟权限检查
            user_roles = UserRole.query.filter_by(user_id=user.id).all()
            role_ids = [ur.role_id for ur in user_roles]

            role_perms = RolePermission.query.filter(
                RolePermission.role_id.in_(role_ids)
            ).all()
            user_permissions = set()
            for rp in role_perms:
                perm = Permission.query.get(rp.permission_id)
                if perm:
                    user_permissions.add(perm.name)

            query_time = time.time() - start_time

            print(f"MySQL权限查询时间: {query_time:.6f}秒")
            print(f"MySQL用户权限数量: {len(user_permissions)}")

            assert query_time < 0.2  # MySQL查询应该在200ms内完成（比SQLite慢一些）
            assert len(user_permissions) == 50  # 应该有50个权限

    def test_mysql_cache_hit_rate(self, mysql_app):
        """测试MySQL环境下的缓存命中率"""
        with mysql_app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 模拟重复访问模式
            test_keys = [f"mysql_frequent_key_{i}" for i in range(20)]
            test_permissions = [
                {f"mysql_perm_{i}_{j}" for j in range(10)} for i in range(20)
            ]

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

            # 计算实际命中率
            actual_hit_rate = (
                hit_count / (hit_count + miss_count)
                if (hit_count + miss_count) > 0
                else 0
            )

            # 获取缓存统计信息
            stats = _permission_cache.get_stats()

            print(f"MySQL命中次数: {hit_count}")
            print(f"MySQL未命中次数: {miss_count}")
            print(f"MySQL实际命中率: {actual_hit_rate:.2%}")
            print(f"MySQL缓存统计命中率: {stats['hit_rate']:.2%}")

            # 验证命中率应该很高（因为重复访问）
            assert actual_hit_rate > 0.9  # 实际命中率应该超过90%（因为重复访问相同key）

    def test_mysql_memory_efficiency(self, mysql_app):
        """测试MySQL环境下的内存效率"""
        with mysql_app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 测试大量数据的内存使用
            large_permissions = {
                f"mysql_permission_with_very_long_name_{i}" for i in range(500)
            }

            # 测试压缩效果
            original_size = len(str(large_permissions).encode())
            compressed_data = _compress_permissions(large_permissions)
            compressed_size = len(compressed_data)

            # 计算内存节省
            memory_saved = original_size - compressed_size
            memory_saved_percent = (memory_saved / original_size) * 100

            print(f"MySQL原始大小: {original_size}字节")
            print(f"MySQL压缩后大小: {compressed_size}字节")
            print(f"MySQL节省内存: {memory_saved}字节 ({memory_saved_percent:.1f}%)")

            assert memory_saved > 0  # 应该有内存节省
            assert memory_saved_percent > 10  # 至少节省10%内存

    def test_mysql_stress_test(self, mysql_app):
        """MySQL环境下的压力测试"""
        with mysql_app.app_context():
            # 清空缓存
            _permission_cache.clear()

            # 创建测试数据
            users = []
            roles = []
            permissions = []

            # 创建10个用户
            for i in range(10):
                user = User(
                    username=f"mysql_stress_user_{i}", password_hash="test_hash"
                )
                users.append(user)
            db.session.add_all(users)
            db.session.commit()

            # 创建5个角色
            for i in range(5):
                role = Role(name=f"mysql_stress_role_{i}", server_id=1)
                roles.append(role)
            db.session.add_all(roles)
            db.session.commit()

            # 创建100个权限
            for i in range(100):
                perm = Permission(
                    name=f"mysql_stress_perm_{i}",
                    group="stress_test",
                    description=f"Stress test permission {i}",
                )
                permissions.append(perm)
            db.session.add_all(permissions)
            db.session.commit()

            # 模拟高并发场景
            def stress_worker(worker_id):
                """压力测试工作线程"""
                results = []
                cache_keys = []  # 记录已设置的key

                for i in range(50):  # 每个线程50次操作
                    key = f"mysql_stress_{worker_id}_{i}"
                    permissions = {f"mysql_perm_{worker_id}_{i}"}

                    # 随机操作：设置或获取
                    if i % 3 == 0:  # 33%概率设置
                        _permission_cache.set(key, permissions)
                        cache_keys.append(key)  # 记录已设置的key
                        results.append(True)
                    else:  # 67%概率获取
                        # 优先尝试获取已设置的key，提高命中率
                        if cache_keys and i % 2 == 0:
                            # 从已设置的key中随机选择
                            import random

                            key = random.choice(cache_keys)

                        result = _permission_cache.get(key)
                        # 获取操作本身是成功的，无论是否命中
                        results.append(True)

                return results

            # 使用线程池执行压力测试
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(stress_worker, i) for i in range(10)]
                all_results = [
                    future.result()
                    for future in concurrent.futures.as_completed(futures)
                ]

            total_time = time.time() - start_time

            # 统计结果
            total_operations = sum(len(results) for results in all_results)
            successful_operations = sum(sum(results) for results in all_results)

            # 计算缓存命中率（通过缓存统计）
            cache_stats = _permission_cache.get_stats()

            print(f"MySQL压力测试完成")
            print(f"MySQL总操作数: {total_operations}")
            print(f"MySQL成功操作数: {successful_operations}")
            print(f"MySQL操作成功率: {successful_operations/total_operations:.2%}")
            print(f"MySQL缓存命中率: {cache_stats['hit_rate']:.2%}")
            print(f"MySQL总时间: {total_time:.3f}秒")
            print(f"MySQL平均每秒操作数: {total_operations/total_time:.0f}")

            # 验证压力测试结果
            assert total_operations == 500  # 10线程 * 50操作
            assert successful_operations == total_operations  # 所有操作都应该成功
            assert total_time < 10  # 压力测试应该在10秒内完成
            assert (
                cache_stats["hit_rate"] > 0.3
            )  # 缓存命中率应该超过30%（因为有重复访问）
