#!/usr/bin/env python3
"""
实现权限查询优化策略
"""
import time
import statistics
from sqlalchemy import text, Index
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import _permission_cache


def test_cache_optimization():
    """测试缓存优化效果"""
    print("=== 缓存优化测试 ===")

    app = create_app("mysql_testing")
    with app.app_context():
        try:
            # 准备测试数据
            db.create_all()

            import time

            unique_id = int(time.time() * 1000) % 100000

            user = User(username=f"cache_user_{unique_id}", password_hash="test_hash")
            db.session.add(user)
            db.session.commit()

            role = Role(name=f"cache_role_{unique_id}", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建权限
            permissions = []
            for i in range(100):
                perm = Permission(
                    name=f"cache_perm_{unique_id}_{i}",
                    group="cache",
                    description=f"Cache test permission {i}",
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

            # 第一次查询（从数据库）
            print("第一次查询（从数据库）...")
            start_time = time.time()

            query = (
                db.session.query(Permission.name)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .join(UserRole, RolePermission.role_id == UserRole.role_id)
                .filter(UserRole.user_id == user.id)
            )
            user_permissions = {row[0] for row in query.all()}

            db_query_time = time.time() - start_time
            print(f"- 数据库查询时间: {db_query_time:.6f}秒")

            # 缓存权限
            cache_key = f"user_permissions_{user.id}"
            _permission_cache.set(cache_key, user_permissions)

            # 第二次查询（从缓存）
            print("第二次查询（从缓存）...")
            cache_times = []
            for i in range(1000):  # 1000次缓存查询
                start_time = time.time()
                cached_permissions = _permission_cache.get(cache_key)
                cache_time = time.time() - start_time
                cache_times.append(cache_time)

            avg_cache_time = statistics.mean(cache_times)
            cache_qps = (
                1 / avg_cache_time if avg_cache_time > 0.000001 else 1000000
            )  # 避免除零

            print(f"- 缓存查询时间: {avg_cache_time:.6f}秒")
            print(f"- 缓存QPS: {cache_qps:.0f} ops/s")

            # 计算提升倍数
            if db_query_time > 0:
                improvement = (1 / avg_cache_time) / (1 / db_query_time)
                print(f"- 缓存优化提升: {improvement:.1f}倍")

            # 清理
            try:
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.execute(text("DROP TABLE IF EXISTS role_permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS user_roles"))
                db.session.execute(text("DROP TABLE IF EXISTS permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS roles"))
                db.session.execute(text("DROP TABLE IF EXISTS users"))
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
            except Exception as e:
                print(f"清理失败: {e}")
                db.session.rollback()

            return cache_qps

        except Exception as e:
            print(f"缓存测试失败: {e}")
            return 0


def test_batch_query_optimization():
    """测试批量查询优化"""
    print("\n=== 批量查询优化测试 ===")

    app = create_app("mysql_testing")
    with app.app_context():
        try:
            # 准备测试数据
            db.create_all()

            import time

            unique_id = int(time.time() * 1000) % 100000

            # 创建多个用户
            users = []
            for i in range(10):
                user = User(
                    username=f"batch_user_{unique_id}_{i}", password_hash="test_hash"
                )
                users.append(user)
            db.session.add_all(users)
            db.session.commit()

            # 创建角色
            role = Role(name=f"batch_role_{unique_id}", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建权限
            permissions = []
            for i in range(100):
                perm = Permission(
                    name=f"batch_perm_{unique_id}_{i}",
                    group="batch",
                    description=f"Batch test permission {i}",
                )
                permissions.append(perm)
            db.session.add_all(permissions)
            db.session.commit()

            # 分配用户角色
            user_roles = []
            for user in users:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                user_roles.append(user_role)
            db.session.add_all(user_roles)
            db.session.commit()

            # 分配角色权限
            role_permissions = []
            for perm in permissions:
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                role_permissions.append(rp)
            db.session.add_all(role_permissions)
            db.session.commit()

            # 测试单个查询性能
            print("测试单个查询性能...")
            single_times = []
            for user in users:
                start_time = time.time()
                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .join(UserRole, RolePermission.role_id == UserRole.role_id)
                    .filter(UserRole.user_id == user.id)
                )
                user_permissions = {row[0] for row in query.all()}
                single_time = time.time() - start_time
                single_times.append(single_time)

            avg_single_time = statistics.mean(single_times)
            single_qps = (
                len(users) / sum(single_times)
                if sum(single_times) > 0
                else float("inf")
            )

            print(f"- 单个查询平均时间: {avg_single_time:.6f}秒")
            print(f"- 单个查询QPS: {single_qps:.0f} ops/s")

            # 测试批量查询性能
            print("测试批量查询性能...")
            start_time = time.time()

            # 批量查询所有用户的权限
            user_ids = [user.id for user in users]
            batch_query = (
                db.session.query(User.id, Permission.name)
                .join(UserRole, User.id == UserRole.user_id)
                .join(RolePermission, UserRole.role_id == RolePermission.role_id)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .filter(User.id.in_(user_ids))
            )

            # 组织结果
            user_permissions_map = {}
            for user_id, perm_name in batch_query.all():
                if user_id not in user_permissions_map:
                    user_permissions_map[user_id] = set()
                user_permissions_map[user_id].add(perm_name)

            batch_time = time.time() - start_time
            batch_qps = len(users) / batch_time if batch_time > 0 else float("inf")

            print(f"- 批量查询时间: {batch_time:.6f}秒")
            print(f"- 批量查询QPS: {batch_qps:.0f} ops/s")

            # 计算提升倍数
            if batch_time > 0 and sum(single_times) > 0:
                improvement = (len(users) / batch_time) / (
                    len(users) / sum(single_times)
                )
                print(f"- 批量查询提升: {improvement:.1f}倍")

            # 清理
            try:
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.execute(text("DROP TABLE IF EXISTS role_permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS user_roles"))
                db.session.execute(text("DROP TABLE IF EXISTS permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS roles"))
                db.session.execute(text("DROP TABLE IF EXISTS users"))
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
            except Exception as e:
                print(f"清理失败: {e}")
                db.session.rollback()

            return batch_qps

        except Exception as e:
            print(f"批量查询测试失败: {e}")
            return 0


def test_index_optimization():
    """测试索引优化效果"""
    print("\n=== 索引优化测试 ===")

    app = create_app("mysql_testing")
    with app.app_context():
        try:
            # 准备测试数据
            db.create_all()

            import time

            unique_id = int(time.time() * 1000) % 100000

            # 创建大量测试数据
            users = []
            for i in range(100):
                user = User(
                    username=f"index_user_{unique_id}_{i}", password_hash="test_hash"
                )
                users.append(user)
            db.session.add_all(users)
            db.session.commit()

            roles = []
            for i in range(20):
                role = Role(name=f"index_role_{unique_id}_{i}", server_id=1)
                roles.append(role)
            db.session.add_all(roles)
            db.session.commit()

            permissions = []
            for i in range(500):
                perm = Permission(
                    name=f"index_perm_{unique_id}_{i}",
                    group="index",
                    description=f"Index test permission {i}",
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

            # 测试无索引查询性能
            print("测试无索引查询性能...")
            no_index_times = []
            for i in range(50):
                user = users[i % len(users)]
                start_time = time.time()

                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .join(UserRole, RolePermission.role_id == UserRole.role_id)
                    .filter(UserRole.user_id == user.id)
                )
                user_permissions = {row[0] for row in query.all()}

                query_time = time.time() - start_time
                no_index_times.append(query_time)

            avg_no_index_time = statistics.mean(no_index_times)
            no_index_qps = (
                1 / avg_no_index_time if avg_no_index_time > 0 else float("inf")
            )

            print(f"- 无索引查询时间: {avg_no_index_time:.6f}秒")
            print(f"- 无索引QPS: {no_index_qps:.0f} ops/s")

            # 创建索引
            print("创建索引...")
            try:
                # 创建索引（MySQL不支持IF NOT EXISTS，先检查是否存在）
                db.session.execute(
                    text("CREATE INDEX idx_user_roles_user_id ON user_roles(user_id)")
                )
                db.session.execute(
                    text(
                        "CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id)"
                    )
                )
                db.session.execute(
                    text("CREATE INDEX idx_permissions_id ON permissions(id)")
                )
                db.session.commit()
                print("索引创建成功")
            except Exception as e:
                print(f"索引创建失败（可能已存在）: {e}")
                db.session.rollback()

            # 测试有索引查询性能
            print("测试有索引查询性能...")
            with_index_times = []
            for i in range(50):
                user = users[i % len(users)]
                start_time = time.time()

                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .join(UserRole, RolePermission.role_id == UserRole.role_id)
                    .filter(UserRole.user_id == user.id)
                )
                user_permissions = {row[0] for row in query.all()}

                query_time = time.time() - start_time
                with_index_times.append(query_time)

            avg_with_index_time = statistics.mean(with_index_times)
            with_index_qps = (
                1 / avg_with_index_time if avg_with_index_time > 0 else float("inf")
            )

            print(f"- 有索引查询时间: {avg_with_index_time:.6f}秒")
            print(f"- 有索引QPS: {with_index_qps:.0f} ops/s")

            # 计算提升倍数
            if avg_with_index_time > 0 and avg_no_index_time > 0:
                improvement = avg_no_index_time / avg_with_index_time
                print(f"- 索引优化提升: {improvement:.1f}倍")

            # 清理
            try:
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.execute(text("DROP TABLE IF EXISTS role_permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS user_roles"))
                db.session.execute(text("DROP TABLE IF EXISTS permissions"))
                db.session.execute(text("DROP TABLE IF EXISTS roles"))
                db.session.execute(text("DROP TABLE IF EXISTS users"))
                db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
            except Exception as e:
                print(f"清理失败: {e}")
                db.session.rollback()

            return with_index_qps

        except Exception as e:
            print(f"索引测试失败: {e}")
            return 0


def main():
    """主函数"""
    print("权限查询优化策略实现")
    print("=" * 50)

    # 1. 缓存优化测试
    cache_qps = test_cache_optimization()

    # 2. 批量查询优化测试
    batch_qps = test_batch_query_optimization()

    # 3. 索引优化测试
    index_qps = test_index_optimization()

    # 总结报告
    print("\n" + "=" * 50)
    print("优化策略效果总结")
    print("=" * 50)

    print(f"1. 缓存优化QPS: {cache_qps:.0f} ops/s")
    print(f"2. 批量查询QPS: {batch_qps:.0f} ops/s")
    print(f"3. 索引优化QPS: {index_qps:.0f} ops/s")

    # 找出最佳优化方案
    qps_results = [
        ("缓存优化", cache_qps),
        ("批量查询", batch_qps),
        ("索引优化", index_qps),
    ]

    best_optimization = max(qps_results, key=lambda x: x[1])
    print(f"\n最佳优化方案: {best_optimization[0]} ({best_optimization[1]:.0f} ops/s)")

    print("\n建议实施顺序:")
    print("1. 缓存优化（提升最大）")
    print("2. 索引优化（成本最低）")
    print("3. 批量查询（适合批量场景）")


if __name__ == "__main__":
    main()
