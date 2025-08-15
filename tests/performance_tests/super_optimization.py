#!/usr/bin/env python3
"""
权限查询叠加优化测试
将所有优化策略组合在一起，测试最终性能效果
"""
import time
import statistics
import threading
import concurrent.futures
from sqlalchemy import text
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import _permission_cache


class SuperOptimizedPermissionSystem:
    """超级优化的权限系统"""

    def __init__(self):
        self.app = create_app("mysql_testing")
        self.setup_database()

    def setup_database(self):
        """设置数据库和索引"""
        with self.app.app_context():
            try:
                # 创建表
                db.create_all()

                # 创建索引
                print("创建优化索引...")
                try:
                    db.session.execute(
                        text(
                            "CREATE INDEX idx_user_roles_user_id ON user_roles(user_id)"
                        )
                    )
                    db.session.execute(
                        text(
                            "CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id)"
                        )
                    )
                    db.session.execute(
                        text("CREATE INDEX idx_permissions_id ON permissions(id)")
                    )
                    db.session.execute(
                        text("CREATE INDEX idx_permissions_name ON permissions(name)")
                    )
                    db.session.commit()
                    print("索引创建成功")
                except Exception as e:
                    print(f"索引创建失败（可能已存在）: {e}")
                    db.session.rollback()

                # 创建测试数据
                self.create_test_data()

            except Exception as e:
                print(f"数据库设置失败: {e}")

    def create_test_data(self):
        """创建大量测试数据"""
        print("创建测试数据...")

        import time

        unique_id = int(time.time() * 1000) % 100000

        # 创建100个用户
        users = []
        for i in range(1000):
            user = User(
                username=f"super_user_{unique_id}_{i}", password_hash="test_hash"
            )
            users.append(user)
        db.session.add_all(users)
        db.session.commit()

        # 创建20个角色
        roles = []
        for i in range(200):
            role = Role(name=f"super_role_{unique_id}_{i}", server_id=1)
            roles.append(role)
        db.session.add_all(roles)
        db.session.commit()

        # 创建500个权限
        permissions = []
        for i in range(5000):
            perm = Permission(
                name=f"super_perm_{unique_id}_{i}",
                group="super",
                description=f"Super optimization permission {i}",
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
            for j in range(25):  # 每个角色25个权限
                perm = permissions[i * 25 + j]
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                role_permissions.append(rp)
        db.session.add_all(role_permissions)
        db.session.commit()

        # 保存用户ID列表，避免会话问题
        self.user_ids = [user.id for user in users]
        self.role_ids = [role.id for role in roles]
        self.permission_ids = [perm.id for perm in permissions]

        print(
            f"创建了 {len(users)} 个用户, {len(roles)} 个角色, {len(permissions)} 个权限"
        )

    def optimized_query_single_user(self, user_id):
        """优化的单用户权限查询"""
        with self.app.app_context():
            # 1. 先尝试从缓存获取
            cache_key = f"user_permissions_{user_id}"
            cached_permissions = _permission_cache.get(cache_key)

            if cached_permissions is not None:
                return cached_permissions

            # 2. 缓存未命中，使用优化的JOIN查询
            query = (
                db.session.query(Permission.name)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .join(UserRole, RolePermission.role_id == UserRole.role_id)
                .filter(UserRole.user_id == user_id)
            )

            user_permissions = {row[0] for row in query.all()}

            # 3. 缓存结果
            _permission_cache.set(cache_key, user_permissions)

            return user_permissions

    def optimized_batch_query(self, user_ids):
        """优化的批量权限查询"""
        with self.app.app_context():
            # 1. 检查缓存
            cached_results = {}
            uncached_user_ids = []

            for user_id in user_ids:
                cache_key = f"user_permissions_{user_id}"
                cached_permissions = _permission_cache.get(cache_key)
                if cached_permissions is not None:
                    cached_results[user_id] = cached_permissions
                else:
                    uncached_user_ids.append(user_id)

            # 2. 批量查询未缓存的用户
            if uncached_user_ids:
                batch_query = (
                    db.session.query(User.id, Permission.name)
                    .join(UserRole, User.id == UserRole.user_id)
                    .join(RolePermission, UserRole.role_id == RolePermission.role_id)
                    .join(Permission, RolePermission.permission_id == Permission.id)
                    .filter(User.id.in_(uncached_user_ids))
                )

                # 组织结果
                user_permissions_map = {}
                for user_id, perm_name in batch_query.all():
                    if user_id not in user_permissions_map:
                        user_permissions_map[user_id] = set()
                    user_permissions_map[user_id].add(perm_name)

                # 3. 缓存批量查询结果
                for user_id, permissions in user_permissions_map.items():
                    cache_key = f"user_permissions_{user_id}"
                    _permission_cache.set(cache_key, permissions)
                    cached_results[user_id] = permissions

            return cached_results

    def test_single_user_performance(self):
        """测试单用户查询性能"""
        print("\n=== 单用户查询性能测试 ===")

        # 预热缓存
        print("预热缓存...")
        with self.app.app_context():
            # 预热前10个用户
            for user_id in self.user_ids[:10]:
                self.optimized_query_single_user(user_id)

        # 测试缓存命中性能
        print("测试缓存命中性能...")
        cache_hit_times = []

        for i in range(1000):  # 1000次查询
            user_id = self.user_ids[i % len(self.user_ids)]
            start_time = time.time()
            permissions = self.optimized_query_single_user(user_id)
            query_time = time.time() - start_time
            cache_hit_times.append(query_time)

        avg_cache_hit_time = statistics.mean(cache_hit_times)
        cache_hit_qps = (
            1 / avg_cache_hit_time if avg_cache_hit_time > 0.000001 else 1000000
        )

        print(f"- 缓存命中平均时间: {avg_cache_hit_time:.6f}秒")
        print(f"- 缓存命中QPS: {cache_hit_qps:.0f} ops/s")

        return cache_hit_qps

    def test_batch_query_performance(self):
        """测试批量查询性能"""
        print("\n=== 批量查询性能测试 ===")

        # 测试不同批量大小
        batch_sizes = [10, 50, 100]
        batch_results = {}

        for batch_size in batch_sizes:
            print(f"测试批量大小: {batch_size}")

            batch_times = []
            for i in range(10):  # 10次批量查询
                start_idx = (i * batch_size) % len(self.user_ids)
                end_idx = min(start_idx + batch_size, len(self.user_ids))
                user_ids = self.user_ids[start_idx:end_idx]

                # 如果用户不够，从开头补充
                if len(user_ids) < batch_size:
                    additional_needed = batch_size - len(user_ids)
                    user_ids.extend(self.user_ids[:additional_needed])

                start_time = time.time()
                results = self.optimized_batch_query(user_ids)
                batch_time = time.time() - start_time
                batch_times.append(batch_time)

            avg_batch_time = statistics.mean(batch_times)
            batch_qps = (
                (batch_size * 10) / sum(batch_times)
                if sum(batch_times) > 0
                else float("inf")
            )

            print(f"- 批量查询平均时间: {avg_batch_time:.6f}秒")
            print(f"- 批量查询QPS: {batch_qps:.0f} ops/s")

            batch_results[batch_size] = batch_qps

        return batch_results

    def test_concurrent_performance(self):
        """测试并发性能"""
        print("\n=== 并发性能测试 ===")

        def concurrent_worker(worker_id, operations):
            """并发工作线程"""
            results = []
            for i in range(operations):
                user_id = self.user_ids[
                    (worker_id * operations + i) % len(self.user_ids)
                ]
                start_time = time.time()
                permissions = self.optimized_query_single_user(user_id)
                query_time = time.time() - start_time
                results.append(query_time)
            return results

        # 测试不同并发级别
        concurrency_levels = [1, 5, 10, 20]
        concurrent_results = {}

        for concurrency in concurrency_levels:
            print(f"测试并发级别: {concurrency}")

            operations_per_worker = 100 // concurrency
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=concurrency
            ) as executor:
                futures = [
                    executor.submit(concurrent_worker, i, operations_per_worker)
                    for i in range(concurrency)
                ]
                all_results = [
                    future.result()
                    for future in concurrent.futures.as_completed(futures)
                ]

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

    def test_memory_efficiency(self):
        """测试内存效率"""
        print("\n=== 内存效率测试 ===")

        # 清空缓存
        _permission_cache.clear()

        # 测试缓存内存使用
        print("测试缓存内存使用...")

        # 缓存所有用户权限
        for user_id in self.user_ids:
            self.optimized_query_single_user(user_id)

        # 获取缓存统计
        cache_stats = _permission_cache.get_stats()

        print(f"- 缓存大小: {cache_stats['size']}")
        print(f"- 缓存命中率: {cache_stats['hit_rate']:.2%}")
        print(f"- 缓存命中次数: {cache_stats['hit_count']}")
        print(f"- 缓存未命中次数: {cache_stats['miss_count']}")

        return cache_stats

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
    print("权限查询叠加优化测试")
    print("=" * 50)

    # 创建超级优化系统
    super_system = SuperOptimizedPermissionSystem()

    try:
        # 1. 单用户查询性能测试
        single_qps = super_system.test_single_user_performance()

        # 2. 批量查询性能测试
        batch_results = super_system.test_batch_query_performance()

        # 3. 并发性能测试
        concurrent_results = super_system.test_concurrent_performance()

        # 4. 内存效率测试
        memory_stats = super_system.test_memory_efficiency()

        # 总结报告
        print("\n" + "=" * 50)
        print("叠加优化效果总结")
        print("=" * 50)

        print(f"\n1. 单用户查询性能:")
        print(f"   - 缓存命中QPS: {single_qps:.0f} ops/s")

        print(f"\n2. 批量查询性能:")
        for batch_size, qps in batch_results.items():
            print(f"   - 批量大小 {batch_size}: {qps:.0f} ops/s")

        print(f"\n3. 并发性能:")
        for concurrency, qps in concurrent_results.items():
            print(f"   - 并发级别 {concurrency}: {qps:.0f} ops/s")

        print(f"\n4. 内存效率:")
        print(f"   - 缓存大小: {memory_stats['size']}")
        print(f"   - 缓存命中率: {memory_stats['hit_rate']:.2%}")

        # 找出最佳性能
        best_single_qps = single_qps
        best_batch_qps = max(batch_results.values()) if batch_results else 0
        best_concurrent_qps = (
            max(concurrent_results.values()) if concurrent_results else 0
        )

        print(f"\n5. 最佳性能指标:")
        print(f"   - 单用户查询: {best_single_qps:.0f} ops/s")
        print(f"   - 批量查询: {best_batch_qps:.0f} ops/s")
        print(f"   - 并发查询: {best_concurrent_qps:.0f} ops/s")

        # 性能评估
        print(f"\n6. 性能评估:")
        if best_single_qps > 100000:
            print("   ✅ 单用户查询性能优秀 (>100k ops/s)")
        elif best_single_qps > 10000:
            print("   ⚠️  单用户查询性能良好 (10k-100k ops/s)")
        else:
            print("   ❌ 单用户查询性能需要优化 (<10k ops/s)")

        if best_concurrent_qps > 1000:
            print("   ✅ 并发查询性能优秀 (>1k ops/s)")
        elif best_concurrent_qps > 100:
            print("   ⚠️  并发查询性能良好 (100-1k ops/s)")
        else:
            print("   ❌ 并发查询性能需要优化 (<100 ops/s)")

        if memory_stats["hit_rate"] > 0.8:
            print("   ✅ 缓存命中率优秀 (>80%)")
        elif memory_stats["hit_rate"] > 0.6:
            print("   ⚠️  缓存命中率良好 (60-80%)")
        else:
            print("   ❌ 缓存命中率需要优化 (<60%)")

    finally:
        # 清理测试数据
        super_system.cleanup()


if __name__ == "__main__":
    main()
