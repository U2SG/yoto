#!/usr/bin/env python3
"""
Redis优化测试脚本
验证Redis优化策略的效果
"""
import time
import statistics
import threading
import concurrent.futures
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import (
    _get_redis_client,
    _get_redis_pipeline,
    _redis_batch_get,
    _redis_batch_set,
    _redis_batch_delete,
    _redis_scan_keys,
    _set_permissions_to_cache,
    _get_permissions_from_cache,
)
from sqlalchemy import text


class RedisOptimizationTester:
    """Redis优化测试器"""

    def __init__(self):
        self.app = create_app("mysql_testing")
        self.setup_database()

    def setup_database(self):
        """设置数据库"""
        with self.app.app_context():
            try:
                # 创建表
                db.create_all()

                # 创建测试数据
                self.create_test_data()

            except Exception as e:
                print(f"数据库设置失败: {e}")

    def create_test_data(self):
        """创建测试数据"""
        print("创建测试数据...")

        import time

        unique_id = int(time.time() * 1000) % 100000

        # 创建50个用户
        users = []
        for i in range(50):
            user = User(
                username=f"redis_test_user_{unique_id}_{i}", password_hash="test_hash"
            )
            users.append(user)
        db.session.add_all(users)
        db.session.commit()

        # 创建10个角色
        roles = []
        for i in range(10):
            role = Role(name=f"redis_test_role_{unique_id}_{i}", server_id=1)
            roles.append(role)
        db.session.add_all(roles)
        db.session.commit()

        # 创建200个权限
        permissions = []
        for i in range(200):
            perm = Permission(
                name=f"redis_test_perm_{unique_id}_{i}",
                group="redis_test",
                description=f"Redis optimization permission {i}",
            )
            permissions.append(perm)
        db.session.add_all(permissions)
        db.session.commit()

        # 分配用户角色
        user_roles = []
        for i, user in enumerate(users):
            role = roles[i % len(roles)]
            user_role = UserRole(user_id=user.id, role_id=role.id)
            user_roles.append(user_role)
        db.session.add_all(user_roles)
        db.session.commit()

        # 分配角色权限
        role_permissions = []
        for i, role in enumerate(roles):
            for j in range(20):  # 每个角色20个权限
                perm = permissions[i * 20 + j]
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                role_permissions.append(rp)
        db.session.add_all(role_permissions)
        db.session.commit()

        # 保存用户ID列表
        self.user_ids = [user.id for user in users]

        print(
            f"创建了 {len(users)} 个用户, {len(roles)} 个角色, {len(permissions)} 个权限"
        )

    def test_redis_connection_pool(self):
        """测试Redis连接池性能"""
        print("\n=== Redis连接池性能测试 ===")

        # 测试连接池性能
        connection_times = []
        with self.app.app_context():
            for i in range(100):
                start_time = time.time()
                redis_client = _get_redis_client()
                connection_time = time.time() - start_time
                connection_times.append(connection_time)

        avg_connection_time = statistics.mean(connection_times)
        print(f"- 平均连接时间: {avg_connection_time:.6f}秒")
        print(
            f"- 连接池性能: {'✅ 优秀' if avg_connection_time < 0.001 else '⚠️ 需要优化'}"
        )

        return avg_connection_time

    def test_redis_pipeline_performance(self):
        """测试Redis管道性能"""
        print("\n=== Redis管道性能测试 ===")

        with self.app.app_context():
            # 准备测试数据
            test_data = {
                f"test_key_{i}": f"test_value_{i}".encode() for i in range(100)
            }

            # 测试批量设置性能
            start_time = time.time()
            batch_set_success = _redis_batch_set(test_data, ttl=60)
            batch_set_time = time.time() - start_time

            # 测试批量获取性能
            start_time = time.time()
            batch_get_result = _redis_batch_get(list(test_data.keys()))
            batch_get_time = time.time() - start_time

            # 测试批量删除性能
            start_time = time.time()
            batch_delete_success = _redis_batch_delete(list(test_data.keys()))
            batch_delete_time = time.time() - start_time

            print(
                f"- 批量设置性能: {batch_set_time:.6f}秒 ({'✅ 成功' if batch_set_success else '❌ 失败'})"
            )
            print(
                f"- 批量获取性能: {batch_get_time:.6f}秒 (获取到 {len(batch_get_result)} 个键)"
            )
            print(
                f"- 批量删除性能: {batch_delete_time:.6f}秒 ({'✅ 成功' if batch_delete_success else '❌ 失败'})"
            )

            return batch_set_time, batch_get_time, batch_delete_time

    def test_redis_scan_performance(self):
        """测试Redis SCAN性能"""
        print("\n=== Redis SCAN性能测试 ===")

        with self.app.app_context():
            # 创建测试键
            test_keys = [f"scan_test_key_{i}" for i in range(1000)]
            test_data = {key: f"value_{i}".encode() for i, key in enumerate(test_keys)}

            # 批量设置测试数据
            _redis_batch_set(test_data, ttl=60)

            # 测试SCAN性能
            start_time = time.time()
            scanned_keys = _redis_scan_keys("scan_test_key_*")
            scan_time = time.time() - start_time

            # 清理测试数据
            _redis_batch_delete(test_keys)

            print(f"- SCAN查询时间: {scan_time:.6f}秒")
            print(f"- 扫描到键数量: {len(scanned_keys)}")
            print(f"- SCAN性能: {'✅ 优秀' if scan_time < 0.1 else '⚠️ 需要优化'}")

            return scan_time, len(scanned_keys)

    def test_cache_performance(self):
        """测试缓存性能"""
        print("\n=== 缓存性能测试 ===")

        with self.app.app_context():
            # 测试缓存设置性能
            cache_set_times = []
            for i in range(50):
                cache_key = f"cache_test_{i}"
                permissions = {f"perm_{j}" for j in range(10)}

                start_time = time.time()
                _set_permissions_to_cache(cache_key, permissions)
                set_time = time.time() - start_time
                cache_set_times.append(set_time)

            # 测试缓存获取性能
            cache_get_times = []
            for i in range(50):
                cache_key = f"cache_test_{i}"

                start_time = time.time()
                result = _get_permissions_from_cache(cache_key)
                get_time = time.time() - start_time
                cache_get_times.append(get_time)

            avg_set_time = statistics.mean(cache_set_times)
            avg_get_time = statistics.mean(cache_get_times)

            print(f"- 平均缓存设置时间: {avg_set_time:.6f}秒")
            print(f"- 平均缓存获取时间: {avg_get_time:.6f}秒")
            print(f"- 缓存性能: {'✅ 优秀' if avg_get_time < 0.001 else '⚠️ 需要优化'}")

            return avg_set_time, avg_get_time

    def test_concurrent_redis_operations(self):
        """测试并发Redis操作"""
        print("\n=== 并发Redis操作测试 ===")

        def concurrent_worker(worker_id, operations):
            """并发工作线程"""
            results = []
            for i in range(operations):
                cache_key = f"concurrent_test_{worker_id}_{i}"
                permissions = {f"perm_{j}" for j in range(5)}

                start_time = time.time()
                _set_permissions_to_cache(cache_key, permissions)
                set_time = time.time() - start_time

                start_time = time.time()
                result = _get_permissions_from_cache(cache_key)
                get_time = time.time() - start_time

                results.append((set_time, get_time))
            return results

        # 测试不同并发级别
        concurrency_levels = [1, 5, 10]
        concurrent_results = {}

        for concurrency in concurrency_levels:
            print(f"测试并发级别: {concurrency}")

            operations_per_worker = 20
            start_time = time.time()

            with self.app.app_context():
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=concurrency
                ) as executor:
                    futures = [
                        executor.submit(concurrent_worker, i, operations_per_worker)
                        for i in range(concurrency)
                    ]
                    all_results = [future.result() for future in futures]

            total_time = time.time() - start_time
            total_operations = sum(len(results) for results in all_results)
            total_qps = (
                total_operations / total_time if total_time > 0 else float("inf")
            )

            print(f"- 总操作数: {total_operations}")
            print(f"- 总时间: {total_time:.3f}秒")
            print(f"- 并发QPS: {total_qps:.0f} ops/s")

            concurrent_results[concurrency] = total_qps

        return concurrent_results

    def cleanup(self):
        """清理测试数据"""
        with self.app.app_context():
            try:
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.execute(text("DROP TABLE IF EXISTS role_permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS user_roles"))
                db.session.execute(text("DROP TABLE IF EXISTS permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS roles"))
                db.session.execute(text("DROP TABLE IF EXISTS users"))
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
                print("测试数据清理完成")
            except Exception as e:
                print(f"清理失败: {e}")


def main():
    """主函数"""
    print("Redis优化测试")
    print("=" * 50)

    # 创建测试器
    tester = RedisOptimizationTester()

    try:
        # 1. Redis连接池性能测试
        connection_time = tester.test_redis_connection_pool()

        # 2. Redis管道性能测试
        set_time, get_time, delete_time = tester.test_redis_pipeline_performance()

        # 3. Redis SCAN性能测试
        scan_time, scanned_count = tester.test_redis_scan_performance()

        # 4. 缓存性能测试
        cache_set_time, cache_get_time = tester.test_cache_performance()

        # 5. 并发Redis操作测试
        concurrent_results = tester.test_concurrent_redis_operations()

        # 总结报告
        print("\n" + "=" * 50)
        print("Redis优化效果总结")
        print("=" * 50)

        print(f"\n1. 连接池性能:")
        print(f"   - 平均连接时间: {connection_time:.6f}秒")

        print(f"\n2. 管道性能:")
        print(f"   - 批量设置: {set_time:.6f}秒")
        print(f"   - 批量获取: {get_time:.6f}秒")
        print(f"   - 批量删除: {delete_time:.6f}秒")

        print(f"\n3. SCAN性能:")
        print(f"   - SCAN查询时间: {scan_time:.6f}秒")
        print(f"   - 扫描键数量: {scanned_count}")

        print(f"\n4. 缓存性能:")
        print(f"   - 缓存设置: {cache_set_time:.6f}秒")
        print(f"   - 缓存获取: {cache_get_time:.6f}秒")

        print(f"\n5. 并发性能:")
        for concurrency, qps in concurrent_results.items():
            print(f"   - 并发级别 {concurrency}: {qps:.0f} ops/s")

        # 性能评估
        print(f"\n6. 性能评估:")
        if connection_time < 0.001:
            print("   ✅ 连接池性能优秀")
        else:
            print("   ⚠️  连接池性能需要优化")

        if cache_get_time < 0.001:
            print("   ✅ 缓存性能优秀")
        else:
            print("   ⚠️  缓存性能需要优化")

        if scan_time < 0.1:
            print("   ✅ SCAN性能优秀")
        else:
            print("   ⚠️  SCAN性能需要优化")

    finally:
        # 清理测试数据
        tester.cleanup()


if __name__ == "__main__":
    main()
