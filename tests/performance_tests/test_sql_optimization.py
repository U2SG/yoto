#!/usr/bin/env python3
"""
SQL优化测试脚本
验证单用户查询性能提升效果
"""
import time
import statistics
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import _optimized_single_user_query
from sqlalchemy import text


class SQLOptimizationTester:
    """SQL优化测试器"""

    def __init__(self):
        self.app = create_app("mysql_testing")
        self.setup_database()

    def setup_database(self):
        """设置数据库"""
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
                username=f"sql_test_user_{unique_id}_{i}", password_hash="test_hash"
            )
            users.append(user)
        db.session.add_all(users)
        db.session.commit()

        # 创建20个角色
        roles = []
        for i in range(20):
            role = Role(name=f"sql_test_role_{unique_id}_{i}", server_id=1)
            roles.append(role)
        db.session.add_all(roles)
        db.session.commit()

        # 创建500个权限
        permissions = []
        for i in range(500):
            perm = Permission(
                name=f"sql_test_perm_{unique_id}_{i}",
                group="sql_test",
                description=f"SQL optimization permission {i}",
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

    def test_single_user_performance(self):
        """测试单用户查询性能"""
        print("\n=== 单用户查询性能测试 ===")

        # 预热查询缓存
        print("预热查询缓存...")
        with self.app.app_context():
            for user_id in self.user_ids[:5]:
                _optimized_single_user_query(user_id)

        # 测试查询性能
        print("测试查询性能...")
        query_times = []

        with self.app.app_context():
            for i in range(100):  # 100次查询
                user_id = self.user_ids[i % len(self.user_ids)]
                start_time = time.time()
                permissions = _optimized_single_user_query(user_id)
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

    def test_cache_effectiveness(self):
        """测试缓存效果"""
        print("\n=== 缓存效果测试 ===")

        with self.app.app_context():
            user_id = self.user_ids[0]

            # 第一次查询（缓存未命中）
            print("第一次查询（缓存未命中）...")
            start_time = time.time()
            permissions1 = _optimized_single_user_query(user_id)
            first_query_time = time.time() - start_time

            # 第二次查询（缓存命中）
            print("第二次查询（缓存命中）...")
            start_time = time.time()
            permissions2 = _optimized_single_user_query(user_id)
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

    def test_scope_performance(self):
        """测试作用域查询性能"""
        print("\n=== 作用域查询性能测试 ===")

        with self.app.app_context():
            user_id = self.user_ids[0]

            # 全局权限查询
            print("全局权限查询...")
            start_time = time.time()
            global_permissions = _optimized_single_user_query(user_id)
            global_time = time.time() - start_time

            # 服务器权限查询
            print("服务器权限查询...")
            start_time = time.time()
            server_permissions = _optimized_single_user_query(user_id, "server", 1)
            server_time = time.time() - start_time

            print(f"- 全局权限查询时间: {global_time:.6f}秒")
            print(f"- 服务器权限查询时间: {server_time:.6f}秒")
            print(f"- 全局权限数量: {len(global_permissions)}")
            print(f"- 服务器权限数量: {len(server_permissions)}")

            return global_time, server_time

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
    print("SQL优化测试")
    print("=" * 50)

    # 创建测试器
    tester = SQLOptimizationTester()

    try:
        # 1. 单用户查询性能测试
        query_qps = tester.test_single_user_performance()

        # 2. 缓存效果测试
        cache_speedup = tester.test_cache_effectiveness()

        # 3. 作用域查询性能测试
        global_time, server_time = tester.test_scope_performance()

        # 总结报告
        print("\n" + "=" * 50)
        print("SQL优化效果总结")
        print("=" * 50)

        print(f"\n1. 查询性能:")
        print(f"   - 查询QPS: {query_qps:.0f} ops/s")

        print(f"\n2. 缓存效果:")
        print(f"   - 性能提升倍数: {cache_speedup:.2f}x")

        print(f"\n3. 作用域查询:")
        print(f"   - 全局权限查询: {global_time:.6f}秒")
        print(f"   - 服务器权限查询: {server_time:.6f}秒")

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
        tester.cleanup()


if __name__ == "__main__":
    main()
