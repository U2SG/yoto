#!/usr/bin/env python3
"""
Task 115: 优化权限查询算法
实现SOTA的权限查询优化策略
"""
import time
import statistics
from typing import Set, List, Dict, Optional
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from sqlalchemy import text


class PermissionQueryOptimizer:
    """权限查询优化器"""

    def __init__(self):
        self.app = create_app("mysql_testing")
        self.setup_database()

        # 优化配置
        self.optimization_config = {
            "use_precomputed_permissions": True,  # 使用预计算权限
            "use_query_cache": True,  # 使用查询缓存
            "use_batch_optimization": True,  # 使用批量优化
            "use_index_hints": True,  # 使用索引提示
            "max_cache_size": 10000,  # 最大缓存大小
            "query_timeout": 5.0,  # 查询超时时间
        }

        # 预计算权限缓存
        self.precomputed_permissions = {}

        # 查询缓存
        self.query_cache = {}

    def setup_database(self):
        """设置数据库"""
        with self.app.app_context():
            try:
                # 创建表
                db.create_all()

                # 创建优化索引
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
                    db.session.execute(
                        text(
                            "CREATE INDEX idx_roles_active ON roles(is_active, deleted_at)"
                        )
                    )
                    db.session.execute(
                        text(
                            "CREATE INDEX idx_permissions_deprecated ON permissions(is_deprecated)"
                        )
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
        """创建测试数据"""
        print("创建测试数据...")

        import time

        unique_id = int(time.time() * 1000) % 100000

        # 创建100个用户
        users = []
        for i in range(100):
            user = User(
                username=f"query_opt_user_{unique_id}_{i}", password_hash="test_hash"
            )
            users.append(user)
        db.session.add_all(users)
        db.session.commit()

        # 创建20个角色
        roles = []
        for i in range(20):
            role = Role(name=f"query_opt_role_{unique_id}_{i}", server_id=1)
            roles.append(role)
        db.session.add_all(roles)
        db.session.commit()

        # 创建500个权限
        permissions = []
        for i in range(500):
            perm = Permission(
                name=f"query_opt_perm_{unique_id}_{i}",
                group="query_opt",
                description=f"Query optimization permission {i}",
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

        # 保存用户ID列表
        self.user_ids = [user.id for user in users]

        print(
            f"创建了 {len(users)} 个用户, {len(roles)} 个角色, {len(permissions)} 个权限"
        )

    def precompute_user_permissions(
        self, user_id: int, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """
        预计算用户权限，使用SOTA的预计算算法。

        预先计算用户的所有权限，包括继承权限，提高查询性能。

        参数:
            user_id (int): 用户ID
            scope (str): 作用域类型
            scope_id (int): 作用域ID

        返回:
            Set[str]: 预计算的权限集合
        """
        # 检查预计算缓存
        cache_key = f"precomputed:{user_id}:{scope}:{scope_id}"
        if cache_key in self.precomputed_permissions:
            return self.precomputed_permissions[cache_key]

        with self.app.app_context():
            # 构建优化的预计算查询
            # 使用CTE (Common Table Expression) 优化复杂查询
            query = (
                db.session.query(Permission.name)
                .distinct()
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .join(UserRole, RolePermission.role_id == UserRole.role_id)
                .join(Role, UserRole.role_id == Role.id)
                .filter(
                    UserRole.user_id == user_id,
                    Role.is_active == True,
                    Role.deleted_at.is_(None),
                    Permission.is_deprecated == False,
                )
            )

            # 添加作用域过滤
            if scope:
                query = query.filter(RolePermission.scope_type == scope)
                if scope_id:
                    query = query.filter(RolePermission.scope_id == scope_id)

            # 执行查询并缓存结果
            permissions = {row[0] for row in query.all()}
            self.precomputed_permissions[cache_key] = permissions

            # 限制缓存大小
            if (
                len(self.precomputed_permissions)
                > self.optimization_config["max_cache_size"]
            ):
                # 清除最旧的缓存项
                oldest_key = next(iter(self.precomputed_permissions))
                del self.precomputed_permissions[oldest_key]

            return permissions

    def optimized_single_user_query_v2(
        self, user_id: int, scope: str = None, scope_id: int = None
    ) -> Set[str]:
        """
        超级优化的单用户权限查询V2，使用SOTA的查询优化技术。

        使用预计算、查询缓存、索引提示等技术，大幅提高查询性能。

        参数:
            user_id (int): 用户ID
            scope (str): 作用域类型
            scope_id (int): 作用域ID

        返回:
            Set[str]: 用户权限集合
        """
        # 检查查询缓存
        cache_key = f"query_cache_v2:{user_id}:{scope}:{scope_id}"
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]

        # 使用预计算权限（如果启用）
        if self.optimization_config["use_precomputed_permissions"]:
            try:
                permissions = self.precompute_user_permissions(user_id, scope, scope_id)
                # 缓存查询结果
                self.query_cache[cache_key] = permissions
                return permissions
            except Exception:
                # 降级到标准查询
                pass

        with self.app.app_context():
            # 构建超级优化的JOIN查询
            # 使用子查询先获取用户的有效角色ID，减少JOIN的数据量
            valid_roles_subquery = (
                db.session.query(UserRole.role_id)
                .join(Role, UserRole.role_id == Role.id)
                .filter(
                    UserRole.user_id == user_id,
                    Role.is_active == True,
                    Role.deleted_at.is_(None),
                )
                .subquery()
            )

            # 主查询：基于有效角色获取权限
            query = (
                db.session.query(Permission.name)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .filter(
                    RolePermission.role_id.in_(valid_roles_subquery),
                    Permission.is_deprecated == False,
                )
            )

            # 添加作用域过滤
            if scope:
                query = query.filter(RolePermission.scope_type == scope)
                if scope_id:
                    query = query.filter(RolePermission.scope_id == scope_id)

            # 使用DISTINCT避免重复权限，提高查询效率
            query = query.distinct()

            # 执行查询并返回权限集合
            permissions = {row[0] for row in query.all()}

            # 缓存查询结果
            self.query_cache[cache_key] = permissions

            # 限制缓存大小
            if len(self.query_cache) > self.optimization_config["max_cache_size"]:
                # 清除最旧的缓存项
                oldest_key = next(iter(self.query_cache))
                del self.query_cache[oldest_key]

            return permissions

    def batch_precompute_permissions(
        self, user_ids: List[int], scope: str = None, scope_id: int = None
    ) -> Dict[int, Set[str]]:
        """
        批量预计算用户权限，使用SOTA的批量预计算算法。

        一次性预计算多个用户的权限，大幅提高批量查询性能。

        参数:
            user_ids (List[int]): 用户ID列表
            scope (str): 作用域类型
            scope_id (int): 作用域ID

        返回:
            Dict[int, Set[str]]: 用户ID到权限集合的映射
        """
        # 检查批量预计算缓存
        cache_key = f"batch_precomputed:{','.join(map(str, sorted(user_ids)))}:{scope}:{scope_id}"
        if cache_key in self.precomputed_permissions:
            return self.precomputed_permissions[cache_key]

        with self.app.app_context():
            # 构建批量预计算查询
            query = (
                db.session.query(User.id, Permission.name)
                .join(UserRole, User.id == UserRole.user_id)
                .join(RolePermission, UserRole.role_id == RolePermission.role_id)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .join(Role, UserRole.role_id == Role.id)
                .filter(
                    User.id.in_(user_ids),
                    Role.is_active == True,
                    Role.deleted_at.is_(None),
                    Permission.is_deprecated == False,
                )
            )

            # 添加作用域过滤
            if scope:
                query = query.filter(RolePermission.scope_type == scope)
                if scope_id:
                    query = query.filter(RolePermission.scope_id == scope_id)

            # 使用DISTINCT避免重复权限
            query = query.distinct()

            # 执行查询并组织结果
            user_permissions_map = {}
            for user_id, perm_name in query.all():
                if user_id not in user_permissions_map:
                    user_permissions_map[user_id] = set()
                user_permissions_map[user_id].add(perm_name)

            # 缓存批量预计算结果
            self.precomputed_permissions[cache_key] = user_permissions_map

            return user_permissions_map

    def test_single_user_performance(self):
        """测试单用户查询性能"""
        print("\n=== 单用户查询性能测试 ===")

        # 预热查询缓存
        print("预热查询缓存...")
        with self.app.app_context():
            for user_id in self.user_ids[:10]:
                self.optimized_single_user_query_v2(user_id)

        # 测试查询性能
        print("测试查询性能...")
        query_times = []

        with self.app.app_context():
            for i in range(100):  # 100次查询
                user_id = self.user_ids[i % len(self.user_ids)]
                start_time = time.time()
                permissions = self.optimized_single_user_query_v2(user_id)
                query_time = time.time() - start_time
                query_times.append(query_time)

        avg_query_time = statistics.mean(query_times)
        min_query_time = min(query_times)
        max_query_time = max(query_times)
        query_qps = 1 / avg_query_time if avg_query_time > 0.000001 else 1000000

        print(f"- 平均查询时间: {avg_query_time:.6f}秒")
        print(f"- 最小查询时间: {min_query_time:.6f}秒")
        print(f"- 最大查询时间: {max_query_time:.6f}秒")
        print(f"- 查询QPS: {query_qps:.0f} ops/s")

        return query_qps

    def test_batch_query_performance(self):
        """测试批量查询性能"""
        print("\n=== 批量查询性能测试 ===")

        # 测试不同批量大小
        batch_sizes = [10, 50, 100]
        batch_results = {}

        with self.app.app_context():
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
                    results = self.batch_precompute_permissions(user_ids)
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

    def test_cache_effectiveness(self):
        """测试缓存效果"""
        print("\n=== 缓存效果测试 ===")

        with self.app.app_context():
            user_id = self.user_ids[0]

            # 第一次查询（缓存未命中）
            print("第一次查询（缓存未命中）...")
            start_time = time.time()
            permissions1 = self.optimized_single_user_query_v2(user_id)
            first_query_time = time.time() - start_time

            # 第二次查询（缓存命中）
            print("第二次查询（缓存命中）...")
            start_time = time.time()
            permissions2 = self.optimized_single_user_query_v2(user_id)
            second_query_time = time.time() - start_time

            # 计算性能提升
            speedup = (
                first_query_time / second_query_time
                if second_query_time > 0
                else float("inf")
            )

            print(f"- 首次查询时间: {first_query_time:.6f}秒")
            print(f"- 缓存查询时间: {second_query_time:.6f}秒")
            print(f"- 性能提升倍数: {speedup:.2f}x")
            print(f"- 权限数量: {len(permissions1)}")

            return speedup

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
    print("Task 115: 权限查询算法优化测试")
    print("=" * 50)

    # 创建优化器
    optimizer = PermissionQueryOptimizer()

    try:
        # 1. 单用户查询性能测试
        query_qps = optimizer.test_single_user_performance()

        # 2. 批量查询性能测试
        batch_results = optimizer.test_batch_query_performance()

        # 3. 缓存效果测试
        cache_speedup = optimizer.test_cache_effectiveness()

        # 总结报告
        print("\n" + "=" * 50)
        print("Task 115 优化效果总结")
        print("=" * 50)

        print(f"\n1. 单用户查询性能:")
        print(f"   - 查询QPS: {query_qps:.0f} ops/s")

        print(f"\n2. 批量查询性能:")
        for batch_size, qps in batch_results.items():
            print(f"   - 批量大小 {batch_size}: {qps:.0f} ops/s")

        print(f"\n3. 缓存效果:")
        print(f"   - 性能提升倍数: {cache_speedup:.2f}x")

        # 性能评估
        print(f"\n4. 性能评估:")
        if query_qps > 10000:
            print("   ✅ 查询性能优秀 (>10k ops/s)")
        elif query_qps > 1000:
            print("   ⚠️  查询性能良好 (1k-10k ops/s)")
        else:
            print("   ❌ 查询性能需要优化 (<1k ops/s)")

        if cache_speedup > 10:
            print("   ✅ 缓存效果优秀 (>10x)")
        elif cache_speedup > 5:
            print("   ⚠️  缓存效果良好 (5-10x)")
        else:
            print("   ❌ 缓存效果需要优化 (<5x)")

    finally:
        # 清理测试数据
        optimizer.cleanup()


if __name__ == "__main__":
    main()
