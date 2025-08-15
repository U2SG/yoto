#!/usr/bin/env python3
"""
权限查询优化方案 - 提高QPS性能
"""
import time
import statistics
from sqlalchemy import text
from app import create_app
from app.core.extensions import db
from app.blueprints.auth.models import User
from app.blueprints.roles.models import Role, UserRole, RolePermission, Permission
from app.core.permissions import _permission_cache


def test_current_performance():
    """测试当前性能"""
    print("=== 当前权限查询性能测试 ===")

    app = create_app("mysql_testing")
    with app.app_context():
        try:
            # 准备测试数据
            db.create_all()

            # 创建测试数据（使用唯一标识符）
            import time

            unique_id = int(time.time() * 1000) % 100000

            user = User(
                username=f"test_user_opt_{unique_id}", password_hash="test_hash"
            )
            db.session.add(user)
            db.session.commit()

            role = Role(name=f"test_role_opt_{unique_id}", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建100个权限
            permissions = []
            for i in range(100):
                perm = Permission(
                    name=f"opt_perm_{unique_id}_{i}",
                    group="optimization",
                    description=f"Optimization test permission {i}",
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

            # 测试当前查询性能
            query_times = []
            for i in range(50):
                start_time = time.time()

                # 当前查询方式
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
                query_times.append(query_time)

            avg_time = statistics.mean(query_times)
            current_qps = 1 / avg_time if avg_time > 0 else float("inf")

            print(f"当前查询性能:")
            print(f"- 平均查询时间: {avg_time:.6f}秒")
            print(f"- 当前QPS: {current_qps:.0f} ops/s")

            # 清理（使用更安全的方式）
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

            return current_qps

        except Exception as e:
            print(f"测试失败: {e}")
            return 0


def test_optimized_performance():
    """测试优化后的性能"""
    print("\n=== 优化后权限查询性能测试 ===")

    app = create_app("mysql_testing")
    with app.app_context():
        try:
            # 准备测试数据
            db.create_all()

            # 创建测试数据（使用唯一标识符）
            import time

            unique_id = int(time.time() * 1000) % 100000 + 1  # 加1避免与第一个测试冲突

            user = User(
                username=f"test_user_opt2_{unique_id}", password_hash="test_hash"
            )
            db.session.add(user)
            db.session.commit()

            role = Role(name=f"test_role_opt2_{unique_id}", server_id=1)
            db.session.add(role)
            db.session.commit()

            # 创建100个权限
            permissions = []
            for i in range(100):
                perm = Permission(
                    name=f"opt_perm2_{unique_id}_{i}",
                    group="optimization",
                    description=f"Optimization test permission {i}",
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

            # 测试优化后的查询性能
            query_times = []
            for i in range(50):
                start_time = time.time()

                # 优化1: 使用JOIN查询，减少数据库往返
                query = (
                    db.session.query(Permission.name)
                    .join(RolePermission, Permission.id == RolePermission.permission_id)
                    .join(UserRole, RolePermission.role_id == UserRole.role_id)
                    .filter(UserRole.user_id == user.id)
                )

                user_permissions = {row[0] for row in query.all()}

                query_time = time.time() - start_time
                query_times.append(query_time)

            avg_time = statistics.mean(query_times)
            optimized_qps = 1 / avg_time if avg_time > 0 else float("inf")

            print(f"优化后查询性能:")
            print(f"- 平均查询时间: {avg_time:.6f}秒")
            print(f"- 优化后QPS: {optimized_qps:.0f} ops/s")

            # 清理（使用更安全的方式）
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

            return optimized_qps

        except Exception as e:
            print(f"测试失败: {e}")
            return 0


def propose_optimization_strategies():
    """提出优化策略"""
    print("\n=== 权限查询优化策略 ===")

    strategies = [
        {
            "name": "SQL查询优化",
            "description": "使用JOIN查询减少数据库往返次数",
            "improvement": "3-5倍性能提升",
            "implementation": "将多个查询合并为一个JOIN查询",
        },
        {
            "name": "缓存优化",
            "description": "将用户权限缓存到内存中",
            "improvement": "100-1000倍性能提升",
            "implementation": "使用LRU缓存存储用户权限",
        },
        {
            "name": "索引优化",
            "description": "为关键字段添加数据库索引",
            "improvement": "2-3倍性能提升",
            "implementation": "为user_id, role_id, permission_id添加索引",
        },
        {
            "name": "批量查询",
            "description": "批量获取多个用户的权限",
            "improvement": "5-10倍性能提升",
            "implementation": "使用IN查询批量获取权限",
        },
        {
            "name": "预加载",
            "description": "应用启动时预加载常用权限",
            "improvement": "2-3倍性能提升",
            "implementation": "在应用启动时预热缓存",
        },
    ]

    for i, strategy in enumerate(strategies, 1):
        print(f"\n{i}. {strategy['name']}")
        print(f"   描述: {strategy['description']}")
        print(f"   预期提升: {strategy['improvement']}")
        print(f"   实现方式: {strategy['implementation']}")


def main():
    """主函数"""
    print("权限查询性能优化分析")
    print("=" * 50)

    # 测试当前性能
    current_qps = test_current_performance()

    # 测试优化后性能
    optimized_qps = test_optimized_performance()

    # 性能对比
    print("\n" + "=" * 50)
    print("性能对比结果")
    print("=" * 50)

    print(f"当前查询QPS: {current_qps:.0f} ops/s")
    print(f"优化后QPS: {optimized_qps:.0f} ops/s")

    if optimized_qps > 0 and current_qps > 0:
        sql_improvement = optimized_qps / current_qps
        print(f"SQL优化提升: {sql_improvement:.1f}倍")

    # 提出优化策略
    propose_optimization_strategies()


if __name__ == "__main__":
    main()
